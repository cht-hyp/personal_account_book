#!/usr/bin/env python3
"""Mock 契约检查：只用标准库，针对 devmock/mock_server.py 验证第 7 节接口契约。

这是开发期自检工具，不是 pytest 测试，也不替代后端负责人的 tests/backend。
用法（先启动 mock_server.py，再另开一个终端）：
    python devmock/check_contract.py --base http://127.0.0.1:5055

检查项覆盖：健康、类别、列表排序与分页、统计口径、金额字符串校验、未知字段、
错误状态码、筛选组合、统计不接受分页参数。任何一项不符即退出码 1。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

FAILURES: list[str] = []
CHECKS = 0


def call(method: str, base: str, path: str, payload=None, query=None, content_type="application/json"):
    url = base + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        try:
            return error.code, json.loads(body) if body else None
        except json.JSONDecodeError:
            return error.code, None


def check(name: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  PASS  {name}")
        return
    FAILURES.append(f"{name} {detail}".strip())
    print(f"  FAIL  {name} {detail}".strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:5055")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    print("1) 健康与类别")
    status, body = call("GET", base, "/api/health")
    check("health 返回 200", status == 200, f"实际 {status}")
    check("health data.status=ok", bool(body) and body["data"]["status"] == "ok")

    status, body = call("GET", base, "/api/categories")
    check("categories 返回 200", status == 200, f"实际 {status}")
    data = body["data"] if body else {}
    check("收入类别 5 个", len(data.get("income", [])) == 5, str(data.get("income")))
    check("支出类别 8 个", len(data.get("expense", [])) == 8, str(data.get("expense")))
    check("类别名称一致", data.get("expense", [])[:2] == ["餐饮", "交通"])

    print("2) 三条基准数据与统计")
    status, body = call("GET", base, "/api/records", query={"limit": 10})
    check("records 返回 200", status == 200, f"实际 {status}")
    page = body["data"] if body else {}
    check("total=3", page.get("total") == 3, str(page.get("total")))
    check("items 长度 3", len(page.get("items", [])) == 3)
    items = page.get("items", [])
    check(
        "排序 date desc",
        [i["date"] for i in items] == sorted([i["date"] for i in items], reverse=True),
    )
    check("金额为整数分", all(isinstance(i["amount_cents"], int) for i in items))

    status, body = call("GET", base, "/api/statistics")
    stats = body["data"] if body else {}
    check("收入 100000 分", stats.get("income_cents") == 100000, str(stats.get("income_cents")))
    check("支出 2500 分", stats.get("expense_cents") == 2500, str(stats.get("expense_cents")))
    check("结余 97500 分", stats.get("balance_cents") == 97500, str(stats.get("balance_cents")))
    check("count=3", stats.get("count") == 3, str(stats.get("count")))
    rows = stats.get("expense_by_category", [])
    check("类别汇总 2 行", len(rows) == 2, str(rows))
    check("汇总金额和等于总支出", sum(r["amount_cents"] for r in rows) == stats.get("expense_cents"))
    check("类别按金额降序", [r["amount_cents"] for r in rows] == sorted([r["amount_cents"] for r in rows], reverse=True))

    print("3) 筛选：餐饮")
    status, body = call("GET", base, "/api/statistics", query={"type": "expense", "category": "餐饮"})
    check("筛选返回 200", status == 200, f"实际 {status} {body}")
    if body:
        s = body["data"]
        check("筛选收入 0", s["income_cents"] == 0, str(s["income_cents"]))
        check("筛选支出 2000 分", s["expense_cents"] == 2000, str(s["expense_cents"]))
        check("筛选结余 -2000 分", s["balance_cents"] == -2000, str(s["balance_cents"]))
        check("筛选 count=1", s["count"] == 1, str(s["count"]))

    status, body = call("GET", base, "/api/records", query={"type": "expense", "category": "餐饮"})
    check("列表与统计同条件一致", body and body["data"]["total"] == 1, str(body))

    print("4) 新增与金额字符串校验")
    payload = {"date": "2026-11-07", "type": "expense", "amount": "20.50", "category": "餐饮", "note": "契约检查"}
    status, body = call("POST", base, "/api/records", payload=payload)
    check("新增返回 201", status == 201, f"实际 {status}")
    record = body["data"] if body else {}
    check("amount_cents=2050", record.get("amount_cents") == 2050, str(record.get("amount_cents")))
    check("返回 id", bool(record.get("id")))
    check("created_at 带时区", "+00:00" in str(record.get("created_at")), str(record.get("created_at")))

    cases = [
        ("三位小数", {"amount": "20.123"}, "amount"),
        ("金额传数值", {"amount": 20}, "amount"),
        ("零金额", {"amount": "0"}, "amount"),
        ("负数", {"amount": "-5"}, "amount"),
        ("科学计数法", {"amount": "2e3"}, "amount"),
        ("千分位", {"amount": "1,000"}, "amount"),
        ("类别与类型不匹配", {"type": "income", "category": "餐饮"}, "category"),
        ("未知字段", {"id": "x"}, "id"),
    ]
    for label, patch, field in cases:
        body_in = {**payload, **patch}
        status, body = call("POST", base, "/api/records", payload=body_in)
        fields = (body or {}).get("error", {}).get("fields", {})
        check(f"{label} 返回 400", status == 400, f"实际 {status}")
        check(f"{label} 定位到 {field}", field in fields, str(fields))

    missing = {"date": "2026-11-07", "type": "expense", "amount": "20.50"}
    status, body = call("POST", base, "/api/records", payload=missing)
    check("缺 category 返回 400", status == 400, f"实际 {status}")

    status, body = call(
        "POST", base, "/api/records", payload=payload, content_type="text/plain; charset=utf-8"
    )
    check("非 JSON Content-Type 返回 415", status == 415, f"实际 {status}")

    print("5) 列表分页与边界")
    status, body = call("GET", base, "/api/records", query={"limit": 2, "offset": 0})
    check("limit=2 生效", len(body["data"]["items"]) == 2 and body["data"]["limit"] == 2)
    status, body = call("GET", base, "/api/records", query={"limit": 2, "offset": 2})
    check("第二页 total 不变", body["data"]["total"] == 4, str(body["data"]["total"]))
    status, body = call("GET", base, "/api/records", query={"limit": 10, "offset": 99})
    check("超范围 offset 返回空 items", body["data"]["items"] == [])
    check("超范围 offset total 仍真实", body["data"]["total"] == 4, str(body["data"]["total"]))

    status, body = call("GET", base, "/api/records", query={"min_amount": "0", "max_amount": "0"})
    check("金额边界 0 被保留而非忽略", body["data"]["total"] == 0, str(body["data"]["total"]))

    status, body = call("GET", base, "/api/records", query={"limit": "0"})
    check("limit=0 返回 400", status == 400, f"实际 {status}")
    status, body = call("GET", base, "/api/records", query={"start_date": "2026-11-09", "end_date": "2026-11-01"})
    check("反向日期返回 400", status == 400, f"实际 {status}")

    print("6) 状态码与未知接口")
    status, body = call("GET", base, "/api/does-not-exist")
    check("未知 API 返回 404", status == 404, f"实际 {status}")
    check("404 是 JSON 错误体", bool(body) and body.get("error", {}).get("code") == "NOT_FOUND")
    status, body = call("POST", base, "/api/categories")
    check("方法不支持返回 405", status == 405, f"实际 {status}")
    status, body = call("GET", base, "/api/statistics", query={"limit": "10"})
    check("统计拒绝 limit 参数", status == 400, f"实际 {status}")

    print()
    if FAILURES:
        print(f"结果：{CHECKS - len(FAILURES)}/{CHECKS} 通过，{len(FAILURES)} 项失败")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1
    print(f"结果：{CHECKS}/{CHECKS} 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
