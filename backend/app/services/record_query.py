"""查询与筛选业务（负责人：4 号 高一鹏）。

公开接口（README 8.5）：
    filter_records(records, filters) -> list[dict]        纯函数：过滤，不排序、不分页
    query_records(records, filters, *, limit, offset)     过滤 + 稳定排序 + 分页 + total

为什么统计模块也要调用 filter_records 而不是复用 HTTP 接口：
    列表和统计必须"看到同一批记录"。两边共用同一个过滤函数，才不会出现
    "列表筛出 3 条、统计算出 5 条"这种演示时最难解释的问题（README 14.5）。
    因此这里不读文件、不进 Flask 上下文，输入是调用方给的一份记录快照。

口径（README 6.4）：
    1. 六个条件之间是 AND；未填写的条件不参与筛选。
    2. 日期起止都包含，金额上下限都包含，且针对"单笔金额"而不是累计。
    3. 顺序固定为 date desc, created_at desc, id desc，第三个字段负责稳定排序。
    4. total 是分页前的匹配条数；offset 超出范围时 items 为空、total 仍是真实条数。
"""
from __future__ import annotations

from typing import Iterable, Sequence

from ..validators import RecordFilter


def filter_records(records: Sequence[dict], filters: RecordFilter) -> list[dict]:
    """按 AND 组合筛选记录，返回新的列表（不修改输入、不分页）。

    返回的是记录副本：调用方后续对结果做排序或改写字段时，
    不会影响存储层刚读出来的那份快照。
    """
    matched: list[dict] = []
    for record in records:
        if _matches(record, filters):
            matched.append(dict(record))
    return matched


def query_records(
    records: Sequence[dict],
    filters: RecordFilter,
    *,
    limit: int,
    offset: int,
) -> dict:
    """返回接口需要的 items / total / limit / offset。"""
    if limit < 1 or limit > 100:
        raise ValueError("limit 必须在 1~100 之间")
    if offset < 0:
        raise ValueError("offset 必须 >= 0")

    matched = filter_records(records, filters)
    ordered = _sort_records(matched)
    total = len(ordered)
    items = ordered[offset : offset + limit]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def _matches(record: dict, filters: RecordFilter) -> bool:
    """单条记录是否满足全部条件。

    业务日期在存储里已经是严格的 YYYY-MM-DD 字符串，字典序与时间顺序一致，
    因此直接用字符串比较，避免每次筛选都做一次日期解析。
    """
    record_date = record["date"]

    if filters.start_date is not None and record_date < filters.start_date.isoformat():
        return False
    if filters.end_date is not None and record_date > filters.end_date.isoformat():
        return False
    if filters.type is not None and record["type"] != filters.type:
        return False
    if filters.category is not None and record["category"] != filters.category:
        return False

    amount_cents = record["amount_cents"]
    if filters.min_amount_cents is not None and amount_cents < filters.min_amount_cents:
        return False
    if filters.max_amount_cents is not None and amount_cents > filters.max_amount_cents:
        return False

    return True


def _sort_key(record: dict) -> tuple[str, str, str]:
    return (record["date"], record["created_at"], record["id"])


def _sort_records(records: Iterable[dict]) -> list[dict]:
    """按 date、created_at、id 依次倒序。

    created_at 统一是 UTC 毫秒精度（README 6.1），字典序等于时间序；
    id 是 UUID 字符串，第三个键保证同一天同一毫秒的记录顺序稳定、可复现。
    """
    return sorted(records, key=_sort_key, reverse=True)
