"""4 号（高一鹏）查询筛选业务层的验证。

对应 README 15.1 中 4 号的重点验证：
    日期和金额含边界、多条件组合、稳定排序、分页 total、超范围 offset。
"""
from __future__ import annotations

from datetime import date

import pytest

from backend.app.services.record_query import filter_records, query_records
from backend.app.validators import RecordFilter


def record(
    *,
    record_id: str,
    record_date: str,
    record_type: str,
    amount_cents: int,
    category: str,
    created_at: str,
    note: str = "",
) -> dict:
    return {
        "id": record_id,
        "date": record_date,
        "type": record_type,
        "amount_cents": amount_cents,
        "category": category,
        "note": note,
        "created_at": created_at,
    }


@pytest.fixture
def records() -> list[dict]:
    """固定样例：跨三天、两种类型、三个类别，含同一天同一毫秒的两条。"""
    return [
        record(
            record_id="00000000-0000-4000-8000-000000000001",
            record_date="2026-11-01",
            record_type="income",
            amount_cents=100000,
            category="工资",
            created_at="2026-11-01T01:00:00.000+00:00",
            note="10 月工资",
        ),
        record(
            record_id="00000000-0000-4000-8000-000000000002",
            record_date="2026-11-05",
            record_type="expense",
            amount_cents=2000,
            category="餐饮",
            created_at="2026-11-05T02:00:00.000+00:00",
            note="午餐",
        ),
        record(
            record_id="00000000-0000-4000-8000-000000000003",
            record_date="2026-11-05",
            record_type="expense",
            amount_cents=500,
            category="交通",
            created_at="2026-11-05T03:00:00.000+00:00",
            note="公交",
        ),
        record(
            record_id="00000000-0000-4000-8000-00000000000a",
            record_date="2026-11-07",
            record_type="expense",
            amount_cents=3500,
            category="餐饮",
            created_at="2026-11-07T04:00:00.000+00:00",
            note="晚餐",
        ),
        record(
            record_id="00000000-0000-4000-8000-00000000000b",
            record_date="2026-11-07",
            record_type="income",
            amount_cents=20000,
            category="兼职",
            created_at="2026-11-07T04:00:00.000+00:00",
            note="家教",
        ),
    ]


def test_no_filter_returns_everything(records):
    matched = filter_records(records, RecordFilter())
    assert len(matched) == len(records)


def test_date_range_is_inclusive_on_both_ends(records):
    matched = filter_records(
        records,
        RecordFilter(start_date=date(2026, 11, 5), end_date=date(2026, 11, 5)),
    )
    assert {item["category"] for item in matched} == {"餐饮", "交通"}


def test_only_start_date_or_only_end_date(records):
    only_start = filter_records(records, RecordFilter(start_date=date(2026, 11, 5)))
    assert {item["date"] for item in only_start} == {"2026-11-05", "2026-11-07"}

    only_end = filter_records(records, RecordFilter(end_date=date(2026, 11, 1)))
    assert [item["date"] for item in only_end] == ["2026-11-01"]


@pytest.mark.parametrize(
    ("min_cents", "max_cents", "expected"),
    [
        (2000, 3500, 2),  # 两端都包含，单笔金额而不是累计
        (3500, 3500, 1),
        (0, 500, 1),
        (3600, None, 2),   # 工资 1000.00 与兼职 200.00 都大于 36.00
        (None, 1999, 1),
        (9000, 10000, 0),
    ],
)
def test_amount_bounds_are_inclusive(records, min_cents, max_cents, expected):
    matched = filter_records(
        records,
        RecordFilter(min_amount_cents=min_cents, max_amount_cents=max_cents),
    )
    assert len(matched) == expected


def test_type_and_category_and_date_are_combined_with_and(records):
    matched = filter_records(
        records,
        RecordFilter(
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 7),
            type="expense",
            category="餐饮",
            min_amount_cents=3000,
        ),
    )
    assert len(matched) == 1
    assert matched[0]["category"] == "餐饮"
    assert matched[0]["amount_cents"] == 3500


def test_filter_does_not_mutate_input(records):
    snapshot = [dict(item) for item in records]
    matched = filter_records(records, RecordFilter(type="expense"))

    assert records == snapshot, "纯函数不能改动调用方传入的记录"
    matched[0]["note"] = "改结果"
    assert records == snapshot, "结果与输入必须解耦"


def test_sorting_is_date_then_created_at_desc(records):
    ordered = query_records(records, RecordFilter(), limit=20, offset=0)["items"]
    keys = [(item["date"], item["created_at"]) for item in ordered]
    assert keys == sorted(keys, reverse=True)


def test_same_date_and_created_at_falls_back_to_id_desc(records):
    ordered = query_records(records, RecordFilter(), limit=2, offset=0)["items"]
    # 11-07 的两条 created_at 完全相同，id 以 ...000b 结尾的更大，应排在前
    assert [item["id"] for item in ordered] == [
        "00000000-0000-4000-8000-00000000000b",
        "00000000-0000-4000-8000-00000000000a",
    ]


def test_recent_ten_uses_same_sorting(records):
    page = query_records(records, RecordFilter(), limit=10, offset=0)
    assert page["limit"] == 10
    assert page["total"] == 5
    assert len(page["items"]) == 5


@pytest.mark.parametrize(
    ("limit", "offset", "expected_items", "expected_total"),
    [
        (2, 0, 2, 5),
        (2, 2, 2, 5),
        (2, 4, 1, 5),
        (20, 5, 0, 5),   # offset 超出匹配范围
        (3, 10, 0, 5),
    ],
)
def test_pagination_reports_total_and_tolerates_out_of_range_offset(
    records, limit, offset, expected_items, expected_total
):
    page = query_records(records, RecordFilter(), limit=limit, offset=offset)
    assert len(page["items"]) == expected_items
    assert page["total"] == expected_total, "total 是分页前的匹配条数"


def test_pagination_keeps_filters_applied(records):
    page = query_records(
        records, RecordFilter(type="expense"), limit=1, offset=1
    )
    assert page["total"] == 3, "翻页不能丢掉筛选条件"
    assert page["items"][0]["type"] == "expense"


def test_empty_result_shape(records):
    page = query_records(
        records, RecordFilter(category="医疗"), limit=20, offset=0
    )
    assert page == {"items": [], "total": 0, "limit": 20, "offset": 0}


@pytest.mark.parametrize(("limit", "offset"), [(0, 0), (101, 0), (20, -1)])
def test_service_rejects_illegal_pagination(records, limit, offset):
    with pytest.raises(ValueError):
        query_records(records, RecordFilter(), limit=limit, offset=offset)
