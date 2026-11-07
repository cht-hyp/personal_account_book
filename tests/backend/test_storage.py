"""2 号（林明亮）本地存储模块的验证。

对应 README 15.1 中 2 号的重点验证：
    空文件初始化、追加与重读、损坏文件保留、写入失败后原数据仍可读、
    同进程并发追加。
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

import pytest

from backend.app.storage import JsonRecordStore, StorageError


def make_record(**overrides) -> dict:
    base = {
        "id": str(uuid.uuid4()),
        "date": "2026-11-07",
        "type": "expense",
        "amount_cents": 2000,
        "category": "餐饮",
        "note": "午餐",
        "created_at": "2026-11-07T06:30:00.000+00:00",
    }
    base.update(overrides)
    return base


@pytest.fixture
def store(tmp_path: Path) -> JsonRecordStore:
    instance = JsonRecordStore(tmp_path / "data" / "records.json")
    instance.initialize()
    return instance


def test_initialize_creates_directory_and_empty_array(store: JsonRecordStore):
    assert store.file_path.exists()
    assert store.file_path.read_text(encoding="utf-8") == "[]\n"
    assert store.list_records() == []


def test_initialize_is_idempotent_and_keeps_existing_records(store: JsonRecordStore):
    record = make_record()
    store.append_record(record)

    before = store.file_path.read_bytes()
    JsonRecordStore(store.file_path).initialize()
    assert store.file_path.read_bytes() == before
    assert store.list_records() == [record]


def test_initialize_does_not_overwrite_corrupt_file(tmp_path: Path):
    path = tmp_path / "records.json"
    path.write_text('{"records": []}', encoding="utf-8")  # 根节点是对象，不是数组
    before = path.read_bytes()

    with pytest.raises(StorageError, match="根节点"):
        JsonRecordStore(path).initialize()

    assert path.read_bytes() == before, "损坏文件必须保留原样，不能被空账本覆盖"


def test_list_records_returns_copy_not_shared_cache(store: JsonRecordStore):
    record = make_record()
    store.append_record(record)

    first = store.list_records()
    first[0]["note"] = "被调用方改坏了"
    first.append(make_record())

    second = store.list_records()
    assert len(second) == 1, "返回值必须是副本，改它不能影响文件内容"
    assert second[0]["note"] == "午餐"


def test_append_then_read_back(store: JsonRecordStore):
    record = make_record()
    returned = store.append_record(record)

    assert returned == record
    data = json.loads(store.file_path.read_text(encoding="utf-8"))
    assert data == [record]


def test_chinese_note_is_stored_as_utf8_not_escaped(store: JsonRecordStore):
    store.append_record(make_record(note="食堂二楼的麻辣香锅"))

    raw = store.file_path.read_text(encoding="utf-8")
    assert "食堂二楼的麻辣香锅" in raw
    assert "\\u" not in raw, "中文必须按 UTF-8 明文落盘，方便人工检查样例文件"


def test_missing_note_defaults_to_empty_string(store: JsonRecordStore):
    record = make_record()
    record.pop("note")

    saved = store.append_record(record)
    assert saved["note"] == ""
    assert store.list_records()[0]["note"] == ""


def test_none_note_is_normalized_not_stored_as_null(store: JsonRecordStore):
    saved = store.append_record(make_record(note=None))

    assert saved["note"] == ""
    assert store.list_records()[0]["note"] == "", "前端直接插值展示，null 会显示成 null"


def test_append_rejects_duplicate_id(store: JsonRecordStore):
    record = make_record()
    store.append_record(record)

    with pytest.raises(StorageError, match="重复"):
        store.append_record(dict(record))
    assert len(store.list_records()) == 1


@pytest.mark.parametrize(
    "bad_amount",
    [20.0, "2000", True, 0, -1, 10_000_000_000],
    ids=["float", "string", "bool", "zero", "negative", "over_limit"],
)
def test_append_rejects_bad_amount_cents(store: JsonRecordStore, bad_amount):
    with pytest.raises(StorageError, match="amount_cents"):
        store.append_record(make_record(amount_cents=bad_amount))
    assert store.list_records() == []


def test_missing_field_is_corruption(tmp_path: Path):
    path = tmp_path / "records.json"
    path.write_text(
        json.dumps([{"id": "not-a-uuid", "date": "2026-11-07"}], ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(StorageError, match="缺少必要字段"):
        JsonRecordStore(path).list_records()


def test_duplicate_id_inside_file_is_corruption(tmp_path: Path):
    path = tmp_path / "records.json"
    record = make_record()
    path.write_text(json.dumps([record, record], ensure_ascii=False), encoding="utf-8")

    with pytest.raises(StorageError, match="重复"):
        JsonRecordStore(path).list_records()


def test_invalid_json_is_reported_with_location(tmp_path: Path):
    path = tmp_path / "records.json"
    path.write_text('[\n  {"id": "x"}\n', encoding="utf-8")

    with pytest.raises(StorageError, match="不是合法 JSON"):
        JsonRecordStore(path).list_records()


def test_write_failure_keeps_original_file_readable(store: JsonRecordStore, monkeypatch):
    store.append_record(make_record(note="写入失败前的数据"))
    before = store.file_path.read_bytes()

    def broken_replace(*args, **kwargs):
        raise OSError("模拟磁盘写入失败")

    monkeypatch.setattr("backend.app.storage.os.replace", broken_replace)

    with pytest.raises(StorageError, match="原文件未改动"):
        store.append_record(make_record(note="这条不应该出现"))

    monkeypatch.undo()
    assert store.file_path.read_bytes() == before, "写入失败不能改动正式文件"
    assert store.list_records()[0]["note"] == "写入失败前的数据"
    assert not list(store.file_path.parent.glob(".records-*.tmp")), "临时文件必须清理"


def test_no_temp_file_left_after_success(store: JsonRecordStore):
    store.append_record(make_record())
    assert not list(store.file_path.parent.glob(".records-*.tmp"))


def test_new_instance_sees_data_after_restart(tmp_path: Path):
    path = tmp_path / "records.json"
    first = JsonRecordStore(path)
    first.initialize()
    first.append_record(make_record(note="重启前的记录"))

    second = JsonRecordStore(path)
    second.initialize()
    assert [item["note"] for item in second.list_records()] == ["重启前的记录"]


def test_concurrent_append_writes_every_record(store: JsonRecordStore):
    total_threads, per_thread = 8, 10
    errors: list[Exception] = []

    def worker(tag: int) -> None:
        try:
            for index in range(per_thread):
                store.append_record(make_record(note=f"{tag}-{index}"))
        except Exception as error:  # noqa: BLE001 - 线程内错误统一收集后断言
            errors.append(error)

    threads = [threading.Thread(target=worker, args=(tag,)) for tag in range(total_threads)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, f"并发追加出现异常：{errors}"
    records = store.list_records()
    assert len(records) == total_threads * per_thread, "锁必须覆盖读—改—写全过程，不能丢记录"
    assert len({item["id"] for item in records}) == total_threads * per_thread
