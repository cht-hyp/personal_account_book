"""记账写入业务（负责人：3 号 周玘晖）。

职责边界（README 3、8.4）：
    只负责「校验之后的记账处理」——校验 → 生成 id 与创建时间 → 组装记录
    → 持久化 → 返回记录。不导入 Flask、不打开数据文件、不做状态码判断。

公开接口（README 8.4）：
    create_record(payload: dict, store: JsonRecordStore) -> dict

依赖：
    ..validators.validate_record_payload（6 号）：负责日期、金额字符串、类别与
    未知字段的全部规则，本模块不重复实现任何一条。
    store.append_record（2 号）：负责加锁与原子落盘，本模块只调用。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..validators import validate_record_payload


def create_record(payload: dict[str, Any], store: Any) -> dict[str, Any]:
    """校验并持久化一条记账记录，返回已经落盘的那条记录。

    参数:
        payload: 创建接口收到的请求体。本函数不会就地修改它。
        store: 具有 ``append_record(record) -> dict`` 的存储实例。

    返回:
        含 id / date / type / amount_cents / category / note / created_at 的字典。
        返回值取自存储层的返回结果，保证与文件中真正写入的内容一致。

    异常:
        ValidationError（6 号校验抛出）: 此时尚未触碰存储，文件不会被写入。
        存储异常（StorageError 等）: 原样向上抛出，由统一错误处理转成 5xx。
            这里绝不吞掉异常后返回「成功」，否则就是假成功。

    实现顺序严格按 README 8.4：校验 → 生成 UUID 与 UTC 时间 → 组装 → 持久化 → 返回。
    id 与 created_at 只能由后端生成（README 6.1），因此这里重新装配字典而不沿用
    payload；即使前端伪造了 id、amount_cents 或 created_at，也不会生效。
    """
    normalized = validate_record_payload(payload)

    record: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "date": normalized["date"],  # 校验层已收敛为 YYYY-MM-DD 字符串
        "type": normalized["type"],
        "amount_cents": normalized["amount_cents"],  # 整数分，不是 "20.00"
        "category": normalized["category"],
        "note": normalized.get("note", ""),
        "created_at": _utc_now_iso_millis(),
    }

    # 只有 append_record 成功返回后，才把结果交出去；失败时调用方拿不到记录
    return store.append_record(record)


def _utc_now_iso_millis() -> str:
    """生成带时区的 UTC 创建时间，统一毫秒精度（README 6.1）。

    结果形如 2026-11-07T06:30:00.000+00:00，可用 datetime.fromisoformat 解析。
    timespec="milliseconds" 是截断而非四舍五入，所以写入时间可能比调用时刻
    早不足 1ms；时间只用于排序与展示，不需要更高精度。
    """
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
