"""本地 JSON 存储（负责人：2 号 林明亮）。

公开接口（README 8.2）：
    JsonRecordStore(file_path)
        initialize() -> None                     首次运行建目录 + 空数组；已有文件只校验不改写
        list_records() -> list[dict]              每次从磁盘重新读取，返回副本
        append_record(record: dict) -> dict       "读—追加—写回"整体加锁，写完才返回

四条必须守住的规则，也是本模块的验收点：
    1. 重启不丢数据：所有记录只经过本模块落盘，进程退出不需要额外 flush。
    2. 不覆盖坏文件：根节点不是数组、记录缺字段、id 重复、金额类型不对，
       一律抛 StorageError 并保留原文件字节不动，绝不"当成空账本"继续写。
    3. 写入要原子：先在同目录写临时文件，fsync 后 os.replace 覆盖正式文件，
       中途失败时正式文件仍是上一次的完整内容。
    4. 锁要覆盖整个"读—改—写"，不能只锁最后那次写入，否则两个并发 append
       会互相覆盖，丢其中一条。

存储层不处理 HTTP、不计算统计，也不提供"整体覆盖"的 save_all：
业务模块绕过追加约束就会写出 id 重复或金额非整数的记录（README 8.2）。
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

try:  # errors.py 由 1 号维护，正常路径下从这里取统一的异常类型
    from .errors import StorageError
except ImportError:  # 1 号尚未合并 StorageError 时，按 7.1 契约提供同名兜底实现
    class StorageError(RuntimeError):
        code = "STORAGE_ERROR"
        status_code = 500

        def __init__(self, message: str = "存储操作失败") -> None:
            super().__init__(message)
            self.message = message

REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "date",
    "type",
    "amount_cents",
    "category",
    "created_at",
)
VALID_TYPES: tuple[str, ...] = ("income", "expense")
MAX_AMOUNT_CENTS = 9_999_999_999


class JsonRecordStore:
    """单个 JSON 文件就是一个账本；一个应用只创建一个实例。"""

    def __init__(self, file_path: str | os.PathLike[str]) -> None:
        self._path = Path(file_path)
        self._lock = threading.RLock()

    @property
    def file_path(self) -> Path:
        return self._path

    # ------------------------------------------------------------------ 初始化

    def initialize(self) -> None:
        """文件不存在时创建空账本；已存在时只做结构校验。

        为什么已有文件也要校验：如果上次是被手工改坏的，启动时就应该报错，
        而不是让第一条新增把它覆盖成"只剩新记录"的账本。
        """
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if not self._path.exists():
                self._write_all([])
                return
            self._read_all()

    # ------------------------------------------------------------------ 读取

    def list_records(self) -> list[dict]:
        """返回账本全部记录。

        每次调用都重新读盘，不缓存：这样重启、外部编辑、另一个进程写入
        都能被读到；返回 dict 副本，调用方改返回值不会影响文件内容。
        """
        with self._lock:
            records = self._read_all()
            return [_normalize_note(dict(record)) for record in records]

    # ------------------------------------------------------------------ 追加

    def append_record(self, record: dict) -> dict:
        """追加一条已组装好的记录，落盘成功后才返回。

        锁的范围包括读取、校验、追加、写回全过程（README 8.2），
        临时文件写入失败时抛出 StorageError，正式文件保持原样。
        """
        if not isinstance(record, dict):
            raise StorageError("待保存的记录必须是对象")

        with self._lock:
            records = self._read_all()
            existing_ids = {item["id"] for item in records}
            self._check_record(record, existing_ids=existing_ids)
            new_record = _normalize_note(dict(record))
            records.append(new_record)
            self._write_all(records)
            return dict(new_record)

    # ------------------------------------------------------------------ 内部

    def _read_all(self) -> list[dict]:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise StorageError("数据文件不存在，请先完成初始化") from None
        except OSError as error:
            raise StorageError(f"数据文件读取失败：{error.strerror or error}") from error

        if not raw.strip():
            raise StorageError("数据文件为空，不是合法的记录数组")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as error:
            raise StorageError(
                f"数据文件不是合法 JSON（第 {error.lineno} 行第 {error.colno} 列），"
                "请检查或从备份恢复，程序不会覆盖该文件"
            ) from error

        if not isinstance(data, list):
            raise StorageError("数据文件根节点必须是数组")

        seen_ids: set[str] = set()
        for index, item in enumerate(data):
            self._check_record(item, index=index, existing_ids=seen_ids)
            seen_ids.add(item["id"])
        return data

    def _write_all(self, records: list[dict]) -> None:
        """原子写入：同目录临时文件 → fsync → os.replace。

        临时文件必须与目标同目录，跨盘 replace 不是原子操作；
        用 os.replace 而不是"先删后写"，避免中途失败留下半个文件。
        """
        payload = json.dumps(records, ensure_ascii=False, indent=2) + "\n"
        self._path.parent.mkdir(parents=True, exist_ok=True)

        temp_path: Path | None = None
        try:
            handle_fd, temp_name = tempfile.mkstemp(
                prefix=".records-", suffix=".tmp", dir=str(self._path.parent)
            )
            temp_path = Path(temp_name)
            with os.fdopen(handle_fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._path)
            temp_path = None
        except OSError as error:
            raise StorageError(f"数据文件写入失败，原文件未改动：{error}") from error
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except OSError:  # pragma: no cover - 清理失败不影响主流程
                    pass

    def _check_record(
        self,
        record: Any,
        *,
        index: int | None = None,
        existing_ids: set[str] | None = None,
    ) -> None:
        """校验一条记录的结构，不合法即判定文件损坏。

        index 为空表示这是即将追加的新记录，错误信息用"待保存的记录"措辞。
        """
        where = f"第 {index + 1} 条记录" if index is not None else "待保存的记录"

        if not isinstance(record, dict):
            raise StorageError(f"{where}必须是 JSON 对象")

        missing = [name for name in REQUIRED_FIELDS if name not in record]
        if missing:
            raise StorageError(f"{where}缺少必要字段：{', '.join(missing)}")

        record_id = record["id"]
        if not isinstance(record_id, str) or not record_id:
            raise StorageError(f"{where}的 id 必须是非空字符串")
        try:
            uuid.UUID(record_id)
        except (ValueError, AttributeError):
            raise StorageError(f"{where}的 id 不是合法的 UUID：{record_id}") from None
        if existing_ids is not None and record_id in existing_ids:
            raise StorageError(f"{where}的 id 与已有记录重复：{record_id}")

        record_date = record["date"]
        if not isinstance(record_date, str):
            raise StorageError(f"{where}的 date 必须是字符串")
        try:
            datetime.strptime(record_date, "%Y-%m-%d")
        except ValueError:
            raise StorageError(f"{where}的 date 不是合法日期：{record_date}") from None

        record_type = record["type"]
        if record_type not in VALID_TYPES:
            raise StorageError(f"{where}的 type 只能是 income 或 expense")

        amount_cents = record["amount_cents"]
        # bool 是 int 的子类，True 会被当成 1 分，必须单独排除
        if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
            raise StorageError(
                f"{where}的 amount_cents 必须是整数分（不是浮点、字符串或布尔值）"
            )
        if not 0 < amount_cents <= MAX_AMOUNT_CENTS:
            raise StorageError(f"{where}的 amount_cents 超出允许范围")

        category = record["category"]
        if not isinstance(category, str) or not category.strip():
            raise StorageError(f"{where}的 category 必须是非空字符串")

        note = record.get("note", "")
        if note is not None and not isinstance(note, str):
            raise StorageError(f"{where}的 note 必须是字符串")

        created_at = record["created_at"]
        if not isinstance(created_at, str):
            raise StorageError(f"{where}的 created_at 必须是字符串")
        try:
            parsed = datetime.fromisoformat(created_at)
        except ValueError:
            raise StorageError(
                f"{where}的 created_at 不是 ISO 8601 时间：{created_at}"
            ) from None
        if parsed.tzinfo is None:
            raise StorageError(f"{where}的 created_at 必须带时区（统一存 UTC）")


def _normalize_note(record: dict) -> dict:
    """note 缺失或为 null 时统一补成空字符串。

    契约写的是"note 可空"，前端直接插值展示；如果存成 null，界面会显示成
    "null"。在存储边界补齐默认值，比让每个消费者各自兜底可靠（README 14.4）。
    """
    if record.get("note") is None:
        record["note"] = ""
    return record
