"""记账写入业务的单元测试（3 号 周玘晖）。

这一层只验证「写入业务自己的控制流」：用 FakeStore 和打桩的校验函数，
不依赖 2 号存储与 6 号校验的实现细节，因此依赖未合并时也能独立运行。
接口层的 201/400/415/500 见 tests/backend/test_record_write_api.py。
"""
from __future__ import annotations

import copy
import re
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.errors import ValidationError
from backend.app.services import record_write as rw
from backend.app.storage import StorageError

# 2026-11-07T06:30:00.000+00:00 这种形状：毫秒精度 + 显式 UTC 偏移
ISO_MILLIS_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00$")
UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

RAW_PAYLOAD = {
    "date": "2026-11-07",
    "type": "expense",
    "amount": "20.00",
    "category": "餐饮",
    "note": "午餐",
}

NORMALIZED = {
    "date": "2026-11-07",
    "type": "expense",
    "amount_cents": 2000,
    "category": "餐饮",
    "note": "午餐",
}


class FakeStore:
    """满足 append_record 契约的假存储，用来观察调用次数并制造失败。"""

    def __init__(self, fail_with: Exception | None = None) -> None:
        self.fail_with = fail_with
        self.calls: list[dict] = []
        self.records: list[dict] = []

    def append_record(self, record: dict) -> dict:
        self.calls.append(copy.deepcopy(record))
        if self.fail_with is not None:
            raise self.fail_with
        self.records.append(copy.deepcopy(record))
        return copy.deepcopy(record)


@pytest.fixture()
def store() -> FakeStore:
    return FakeStore()


def _stub_validate(monkeypatch: pytest.MonkeyPatch, result: dict) -> None:
    """把校验打桩，让本文件只验证写入业务自身的逻辑。"""

    def fake_validate(payload: dict) -> dict:
        return copy.deepcopy(result)

    monkeypatch.setattr(rw, "validate_record_payload", fake_validate)


class TestCreateRecordHappyPath:
    def test_persists_exactly_one_record_with_contract_fields(self, monkeypatch, store):
        _stub_validate(monkeypatch, NORMALIZED)
        rw.create_record(RAW_PAYLOAD, store)

        assert len(store.calls) == 1, "一次新增只能调用一次存储写入"
        written = store.calls[0]
        assert set(written) == {
            "id",
            "date",
            "type",
            "amount_cents",
            "category",
            "note",
            "created_at",
        }, "落盘记录字段必须与 README 6.1 完全一致"
        assert written["amount_cents"] == 2000, "金额必须以整数分落盘"
        assert "amount" not in written, "字符串金额不能进入持久化格式"

    def test_returns_the_record_returned_by_storage(self, monkeypatch):
        """返回值取自存储层，保证接口返回的就是真正写入的那条。"""

        class EchoStore:
            def __init__(self) -> None:
                self.received: dict | None = None

            def append_record(self, record: dict) -> dict:
                self.received = copy.deepcopy(record)
                return {**record, "source": "storage"}

        _stub_validate(monkeypatch, NORMALIZED)
        echo = EchoStore()
        result = rw.create_record(RAW_PAYLOAD, echo)

        assert result["source"] == "storage"
        assert result["id"] == echo.received["id"]

    def test_ids_are_unique_uuid4(self, monkeypatch, store):
        _stub_validate(monkeypatch, NORMALIZED)
        ids = [rw.create_record(RAW_PAYLOAD, store)["id"] for _ in range(50)]
        assert len(ids) == len(set(ids)), "id 必须唯一"
        assert all(UUID4_PATTERN.match(i) for i in ids), "id 必须是 UUID v4 字符串"

    def test_frontend_supplied_id_is_not_used(self, monkeypatch, store):
        """前端伪造 id 不生效：id 只能由后端生成（README 6.1）。"""
        _stub_validate(monkeypatch, NORMALIZED)
        forged = "00000000-0000-4000-8000-000000000000"
        record = rw.create_record({**RAW_PAYLOAD, "id": forged}, store)

        assert record["id"] != forged
        assert UUID4_PATTERN.match(record["id"])

    def test_created_at_is_utc_with_millisecond_precision(self, monkeypatch, store):
        _stub_validate(monkeypatch, NORMALIZED)
        before = datetime.now(timezone.utc)
        record = rw.create_record(RAW_PAYLOAD, store)
        after = datetime.now(timezone.utc)

        assert ISO_MILLIS_UTC.match(record["created_at"]), (
            "created_at 必须是 UTC、带偏移、毫秒精度"
        )
        parsed = datetime.fromisoformat(record["created_at"])
        assert parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0
        # 毫秒截断只丢不足 1ms 的精度，因此允许 before 与 parsed 相差不到 1ms
        assert abs(before - parsed) < timedelta(milliseconds=1), "创建时间应与调用时刻同期"
        assert parsed <= after, "创建时间不应晚于调用结束时刻"

    def test_optional_note_defaults_to_empty_string(self, monkeypatch, store):
        normalized = {key: value for key, value in NORMALIZED.items() if key != "note"}
        _stub_validate(monkeypatch, normalized)
        record = rw.create_record(
            {"date": "2026-11-07", "type": "expense", "amount": "20.00", "category": "餐饮"},
            store,
        )
        assert record["note"] == ""


class TestCreateRecordFailure:
    def test_invalid_payload_never_touches_storage(self, monkeypatch, store):
        """无效输入不会写入文件：校验抛错时存储必须零调用。"""

        def raising_validate(payload: dict) -> dict:
            raise ValidationError("输入参数不合法", {"amount": "金额最多保留两位小数"})

        monkeypatch.setattr(rw, "validate_record_payload", raising_validate)

        with pytest.raises(ValidationError) as exc_info:
            rw.create_record({**RAW_PAYLOAD, "amount": "20.005"}, store)

        assert store.calls == [], "校验失败时不能调用 append_record"
        assert store.records == [], "校验失败时不能产生任何写入"
        assert exc_info.value.fields == {"amount": "金额最多保留两位小数"}

    def test_storage_failure_is_raised_not_swallowed(self, monkeypatch, store):
        """保存失败不会返回成功：异常必须原样抛给上层，由错误处理转 5xx。"""
        _stub_validate(monkeypatch, NORMALIZED)
        store.fail_with = StorageError("数据保存失败，请稍后重试")

        with pytest.raises(StorageError):
            rw.create_record(RAW_PAYLOAD, store)

        assert store.records == [], "写入失败时不应留下半条记录"

    def test_payload_is_not_mutated(self, monkeypatch, store):
        _stub_validate(monkeypatch, NORMALIZED)
        payload = copy.deepcopy(RAW_PAYLOAD)
        rw.create_record(payload, store)
        assert payload == RAW_PAYLOAD, "业务函数不应就地修改调用方传入的请求体"
