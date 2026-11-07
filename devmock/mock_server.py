#!/usr/bin/env python3
"""开发期 Mock 后端（仅前端联调用，不是交付实现）。

用途：8/9/10/11 号在真实后端接好之前，可以让前端页面跑起来联调。
特点：只依赖 Python 标准库，不需要装 Flask，也不写入任何真实账本文件。

明确边界：
- 真实接口由 1/3/4/5/6 号在 backend/ 中实现；本文件不进入 Release 运行包。
- 数据只存在内存里，进程结束即丢失，不做持久化。
- 只实现第 7 节接口总表的五个接口和必要校验，便于发现前端参数错误。

用法（在 co-lab2 目录下）：
    python devmock/mock_server.py --web frontend/dist --port 5055
    python devmock/mock_server.py --web web --port 5055

调试开关（仅 Mock 有，用于验证前端错误态）：
    /__mock__/fail?target=categories   让 /api/categories 返回 500
    /__mock__/fail?target=off          恢复正常
"""

from __future__ import annotations

import argparse
import json
import re
import threading
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

INCOME_CATEGORIES = ["工资", "奖金", "兼职", "理财", "其他收入"]
EXPENSE_CATEGORIES = ["餐饮", "交通", "购物", "住房", "医疗", "娱乐", "学习", "其他支出"]

FILTER_KEYS = {"start_date", "end_date", "type", "category", "min_amount", "max_amount"}
LIST_KEYS = FILTER_KEYS | {"limit", "offset"}
CREATE_KEYS = {"date", "type", "amount", "category", "note"}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
AMOUNT_RE = re.compile(r"^\d+(\.\d{1,2})?$")
MAX_AMOUNT = Decimal("99999999.99")


class ApiError(Exception):
    def __init__(self, status, code, message, fields=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields or {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "+00:00")


def seed_records() -> list[dict]:
    today = date.today().isoformat()
    base = [
        ("income", 100000, "工资", "本月工资"),
        ("expense", 2000, "餐饮", "午餐"),
        ("expense", 500, "交通", "地铁"),
    ]
    records = []
    for index, (type_, cents, category, note) in enumerate(base):
        records.append(
            {
                "id": str(uuid.uuid4()),
                "date": today,
                "type": type_,
                "amount_cents": cents,
                "category": category,
                "note": note,
                "created_at": f"2026-11-07T0{6 + index}:30:00.000+00:00",
            }
        )
    return records


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.records = seed_records()
        self.failures: set[str] = set()


STORE = Store()


def parse_date(value: str, field: str) -> date:
    if not DATE_RE.match(value):
        raise ApiError(400, "VALIDATION_ERROR", "日期格式不合法", {field: "日期必须为 YYYY-MM-DD"})
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ApiError(400, "VALIDATION_ERROR", "日期格式不合法", {field: "日期不是真实存在的日期"})


def parse_amount(value: str, field: str, allow_zero: bool) -> Decimal:
    if not isinstance(value, str):
        raise ApiError(400, "VALIDATION_ERROR", "金额格式不合法", {field: "金额必须以字符串传入"})
    if not AMOUNT_RE.match(value):
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "金额格式不合法",
            {field: "金额最多两位小数，不能有货币符号、千分位或科学计数法"},
        )
    amount = Decimal(value)
    if amount <= 0 and not allow_zero:
        raise ApiError(400, "VALIDATION_ERROR", "金额格式不合法", {field: "金额必须大于 0"})
    if amount > MAX_AMOUNT:
        raise ApiError(400, "VALIDATION_ERROR", "金额超出范围", {field: "金额不能超过 99999999.99"})
    return amount


def cents_of(amount: Decimal) -> int:
    return int(amount * 100)


def validate_record_payload(payload) -> dict:
    if not isinstance(payload, dict):
        raise ApiError(400, "VALIDATION_ERROR", "请求体必须是 JSON 对象", {"body": "需要对象"})
    unknown = set(payload) - CREATE_KEYS
    if unknown:
        raise ApiError(400, "VALIDATION_ERROR", "存在未知字段", {key: "不允许提交该字段" for key in sorted(unknown)})

    fields = {}
    for key in ("date", "type", "amount", "category"):
        if key not in payload:
            fields[key] = "该字段必填"
    if fields:
        raise ApiError(400, "VALIDATION_ERROR", "输入参数不合法", fields)

    parsed_date = parse_date(payload["date"], "date")

    type_ = payload["type"]
    if type_ not in ("income", "expense"):
        raise ApiError(400, "VALIDATION_ERROR", "收支类型不合法", {"type": "只能是 income 或 expense"})

    amount_cents = cents_of(parse_amount(payload["amount"], "amount", allow_zero=False))

    category = payload["category"]
    allowed = INCOME_CATEGORIES if type_ == "income" else EXPENSE_CATEGORIES
    if category not in allowed:
        raise ApiError(400, "VALIDATION_ERROR", "类别不合法", {"category": "类别与收支类型不匹配"})

    note = payload.get("note", "")
    if note is None:
        note = ""
    if not isinstance(note, str):
        raise ApiError(400, "VALIDATION_ERROR", "备注不合法", {"note": "备注必须是文本"})
    note = note.strip()
    if len(note) > 200:
        raise ApiError(400, "VALIDATION_ERROR", "备注过长", {"note": "备注最多 200 个字符"})

    return {
        "date": parsed_date.isoformat(),
        "type": type_,
        "amount_cents": amount_cents,
        "category": category,
        "note": note,
    }


class Filter:
    def __init__(self, params: dict) -> None:
        self.start_date = None
        self.end_date = None
        self.type = None
        self.category = None
        self.min_amount_cents = None
        self.max_amount_cents = None
        self._parse(params)

    def _parse(self, params: dict) -> None:
        fields = {}
        if "start_date" in params:
            self.start_date = parse_date(params["start_date"], "start_date")
        if "end_date" in params:
            self.end_date = parse_date(params["end_date"], "end_date")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ApiError(400, "VALIDATION_ERROR", "日期范围不合法", {"start_date": "开始日期不能晚于结束日期"})
        if "type" in params:
            if params["type"] not in ("income", "expense"):
                raise ApiError(400, "VALIDATION_ERROR", "收支类型不合法", {"type": "只能是 income 或 expense"})
            self.type = params["type"]
        if "category" in params:
            category = params["category"]
            pool = INCOME_CATEGORIES + EXPENSE_CATEGORIES
            if category not in pool:
                raise ApiError(400, "VALIDATION_ERROR", "类别不合法", {"category": "未知类别"})
            if self.type:
                allowed = INCOME_CATEGORIES if self.type == "income" else EXPENSE_CATEGORIES
                if category not in allowed:
                    raise ApiError(400, "VALIDATION_ERROR", "类别与类型不匹配", {"category": "类别与收支类型不匹配"})
            self.category = category
        if "min_amount" in params:
            self.min_amount_cents = cents_of(parse_amount(params["min_amount"], "min_amount", allow_zero=True))
        if "max_amount" in params:
            self.max_amount_cents = cents_of(parse_amount(params["max_amount"], "max_amount", allow_zero=True))
        if (
            self.min_amount_cents is not None
            and self.max_amount_cents is not None
            and self.min_amount_cents > self.max_amount_cents
        ):
            raise ApiError(400, "VALIDATION_ERROR", "金额范围不合法", {"min_amount": "最低金额不能高于最高金额"})

    def match(self, record: dict) -> bool:
        record_date = date.fromisoformat(record["date"])
        if self.start_date and record_date < self.start_date:
            return False
        if self.end_date and record_date > self.end_date:
            return False
        if self.type and record["type"] != self.type:
            return False
        if self.category and record["category"] != self.category:
            return False
        if self.min_amount_cents is not None and record["amount_cents"] < self.min_amount_cents:
            return False
        if self.max_amount_cents is not None and record["amount_cents"] > self.max_amount_cents:
            return False
        return True


def collect_params(query: str, allowed: set[str]) -> dict:
    raw = parse_qs(query, keep_blank_values=True)
    params = {}
    unknown = set(raw) - allowed
    if unknown:
        raise ApiError(400, "VALIDATION_ERROR", "存在未知参数", {key: "不支持该参数" for key in sorted(unknown)})
    for key, values in raw.items():
        value = values[-1]
        if value == "":
            continue  # 空字符串视为未填写
        params[key] = value
    return params


def parse_pagination(params: dict) -> tuple[int, int]:
    limit = 20
    offset = 0
    fields = {}
    if "limit" in params:
        try:
            limit = int(params["limit"])
        except ValueError:
            raise ApiError(400, "VALIDATION_ERROR", "分页参数不合法", {"limit": "limit 必须是整数"})
        if not 1 <= limit <= 100:
            raise ApiError(400, "VALIDATION_ERROR", "分页参数不合法", {"limit": "limit 范围为 1—100"})
    if "offset" in params:
        try:
            offset = int(params["offset"])
        except ValueError:
            raise ApiError(400, "VALIDATION_ERROR", "分页参数不合法", {"offset": "offset 必须是整数"})
        if offset < 0:
            raise ApiError(400, "VALIDATION_ERROR", "分页参数不合法", {"offset": "offset 必须大于等于 0"})
    return limit, offset


def sort_key(record: dict):
    return (record["date"], record["created_at"], record["id"])


def sorted_records() -> list[dict]:
    with STORE.lock:
        snapshot = [dict(item) for item in STORE.records]
    return sorted(snapshot, key=sort_key, reverse=True)


def make_statistics(records: list[dict]) -> dict:
    income = sum(r["amount_cents"] for r in records if r["type"] == "income")
    expense = sum(r["amount_cents"] for r in records if r["type"] == "expense")
    by_category: dict[str, dict] = {}
    for record in records:
        if record["type"] != "expense":
            continue
        bucket = by_category.setdefault(record["category"], {"category": record["category"], "amount_cents": 0, "count": 0})
        bucket["amount_cents"] += record["amount_cents"]
        bucket["count"] += 1
    rows = sorted(by_category.values(), key=lambda item: (-item["amount_cents"], item["category"]))
    return {
        "income_cents": income,
        "expense_cents": expense,
        "balance_cents": income - expense,
        "count": len(records),
        "income_count": sum(1 for r in records if r["type"] == "income"),
        "expense_count": sum(1 for r in records if r["type"] == "expense"),
        "expense_by_category": rows,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "DevMock/1.0"
    web_dir: Path = Path("web")

    def log_message(self, fmt, *args):  # 安静一点，只打印必要信息
        return

    # ---- 响应工具 ----
    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, error: ApiError) -> None:
        self.send_json(
            error.status,
            {"error": {"code": error.code, "message": error.message, "fields": error.fields}},
        )

    def read_json_body(self):
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", "创建接口必须使用 application/json", {})
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "INVALID_JSON", "请求体不是合法的 JSON", {})

    # ---- 路由 ----
    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def do_DELETE(self):
        self.dispatch("DELETE")

    def dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/__mock__/"):
            self.handle_mock_control(path, parsed.query)
            return
        if path.startswith("/api/"):
            self.handle_api(method, path, parsed.query)
            return
        self.serve_static(path)

    def handle_mock_control(self, path: str, query: str) -> None:
        params = parse_qs(query)
        target = (params.get("target") or [""])[0]
        with STORE.lock:
            if target == "off":
                STORE.failures.clear()
            elif target in ("categories", "records", "statistics"):
                STORE.failures.add(target)
        self.send_json(200, {"data": {"failures": sorted(STORE.failures)}})

    def handle_api(self, method: str, path: str, query: str) -> None:
        routes = {
            "/api/health": {"GET"},
            "/api/categories": {"GET"},
            "/api/records": {"GET", "POST"},
            "/api/statistics": {"GET"},
        }
        allowed = routes.get(path)
        if allowed is None:
            self.send_error_json(ApiError(404, "NOT_FOUND", "接口不存在", {}))
            return
        if method not in allowed:
            self.send_error_json(ApiError(405, "METHOD_NOT_ALLOWED", "请求方法不支持", {}))
            return

        try:
            if path == "/api/health":
                self.send_json(200, {"data": {"status": "ok"}})
            elif path == "/api/categories":
                if "categories" in STORE.failures:
                    raise ApiError(500, "INTERNAL_ERROR", "Mock 故意注入的类别故障", {})
                self.send_json(200, {"data": {"income": INCOME_CATEGORIES, "expense": EXPENSE_CATEGORIES}})
            elif path == "/api/records" and method == "GET":
                if "records" in STORE.failures:
                    raise ApiError(500, "INTERNAL_ERROR", "Mock 故意注入的查询故障", {})
                self.handle_list(query)
            elif path == "/api/records" and method == "POST":
                self.handle_create()
            elif path == "/api/statistics":
                if "statistics" in STORE.failures:
                    raise ApiError(500, "INTERNAL_ERROR", "Mock 故意注入的统计故障", {})
                self.handle_statistics(query)
        except ApiError as error:
            self.send_error_json(error)

    def handle_list(self, query: str) -> None:
        params = collect_params(query, LIST_KEYS)
        filters = Filter(params)
        limit, offset = parse_pagination(params)
        matched = [record for record in sorted_records() if filters.match(record)]
        page = matched[offset : offset + limit]
        self.send_json(200, {"data": {"items": page, "total": len(matched), "limit": limit, "offset": offset}})

    def handle_create(self) -> None:
        payload = self.read_json_body()
        normalized = validate_record_payload(payload)
        record = {
            "id": str(uuid.uuid4()),
            **normalized,
            "created_at": now_iso(),
        }
        with STORE.lock:
            STORE.records.append(record)
        self.send_json(201, {"data": record})

    def handle_statistics(self, query: str) -> None:
        params = collect_params(query, FILTER_KEYS)
        filters = Filter(params)
        matched = [record for record in sorted_records() if filters.match(record)]
        self.send_json(200, {"data": make_statistics(matched)})

    def serve_static(self, path: str) -> None:
        relative = path.lstrip("/") or "index.html"
        candidate = (self.web_dir / relative).resolve()
        try:
            candidate.relative_to(self.web_dir.resolve())
        except ValueError:
            self.send_error(404)
            return
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.exists():
            body = (
                "前端构建产物不存在。先执行 cd frontend && npm run build，"
                "或把 --web 指向包含 index.html 的目录（例如 web/）。"
            ).encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        content_type = "application/octet-stream"
        if candidate.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif candidate.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        elif candidate.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif candidate.suffix in (".svg", ".png", ".jpg", ".ico"):
            content_type = f"image/{candidate.suffix.lstrip('.').replace('jpg', 'jpeg')}"
        data = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="轻账本开发期 Mock 后端（仅前端联调）")
    parser.add_argument("--web", default="frontend/dist", help="静态资源目录（构建产物）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5055)
    args = parser.parse_args()

    web_dir = Path(args.web).resolve()
    if not (web_dir / "index.html").exists():
        print(f"[提示] {web_dir} 下没有 index.html，页面会返回 404；先执行 npm run build。")

    Handler.web_dir = web_dir
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Mock 服务已启动：http://{args.host}:{args.port}  (静态目录 {web_dir})")
    print("接口：/api/health、/api/categories、/api/records、/api/statistics")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
