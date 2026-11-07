"""GET /api/records 接口层验证（4 号 高一鹏）。

这一层验证的是"参数进得去、错误出得来、结果结构对"：
    - 默认 limit=20，最近记录传 limit=10
    - 组合筛选（中文类别要能被 URL 编码正确解码）
    - 非法值、倒置边界、未知参数返回 400 并定位字段
    - 空账本返回空列表而不是报错

说明：统一错误响应与未知 /api 的 JSON 404 属于 1 号的应用工厂，
这里自建最小应用并复刻 7.1 的错误结构，只为了让本模块能独立验证；
1 号合并 create_app 后，用真实装配复跑这些用例。
"""
from __future__ import annotations

import uuid

import pytest
from flask import Flask, jsonify

from backend.app.errors import ValidationError
from backend.app.routes.record_query import record_query_bp
from backend.app.storage import JsonRecordStore


def make_record(*, record_date="2026-11-07", record_type="expense", amount_cents=2000,
                category="餐饮", note="午餐", created_at="2026-11-07T06:30:00.000+00:00"):
    return {
        "id": str(uuid.uuid4()),
        "date": record_date,
        "type": record_type,
        "amount_cents": amount_cents,
        "category": category,
        "note": note,
        "created_at": created_at,
    }


def build_app(data_file):
    """只装配查询模块所需的部分：存储实例 + 查询 Blueprint + 校验错误处理。"""
    app = Flask(__name__)
    store = JsonRecordStore(data_file)
    store.initialize()
    app.extensions["record_store"] = store
    app.register_blueprint(record_query_bp)

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        body = {
            "error": {
                "code": error.code,
                "message": error.message,
                "fields": error.fields,
            }
        }
        return jsonify(body), error.status_code

    return app


@pytest.fixture
def ledger(tmp_path):
    """每个用例一个隔离账本，绝不碰 data/records.json。"""
    return build_app(tmp_path / "records.json")


@pytest.fixture
def client(ledger):
    return ledger.test_client()


@pytest.fixture
def seeded(ledger):
    store = ledger.extensions["record_store"]
    store.append_record(make_record(record_date="2026-11-07", record_type="income",
                                    amount_cents=100000, category="工资", note="工资"))
    store.append_record(make_record(record_date="2026-11-07", record_type="expense",
                                    amount_cents=2000, category="餐饮", note="午餐"))
    store.append_record(make_record(record_date="2026-11-06", record_type="expense",
                                    amount_cents=500, category="交通", note="公交",
                                    created_at="2026-11-06T09:00:00.000+00:00"))
    return ledger


def test_returns_wrapped_data_with_default_pagination(seeded):
    client = seeded.test_client()
    response = client.get("/api/records")

    assert response.status_code == 200
    body = response.get_json()
    assert set(body) == {"data"}
    data = body["data"]
    assert set(data) == {"items", "total", "limit", "offset"}
    assert data["total"] == 3
    assert data["limit"] == 20
    assert data["offset"] == 0
    assert data["items"][0]["date"] >= data["items"][-1]["date"]


def test_recent_records_limit_ten(seeded):
    client = seeded.test_client()
    response = client.get("/api/records", query_string={"limit": "10"})

    assert response.status_code == 200
    assert response.get_json()["data"]["limit"] == 10


def test_filter_by_chinese_category(seeded):
    client = seeded.test_client()
    response = client.get("/api/records", query_string={"category": "餐饮"})

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["category"] == "餐饮"
    assert data["items"][0]["amount_cents"] == 2000


def test_combined_filters_and_total_ignores_limit(seeded):
    client = seeded.test_client()
    response = client.get(
        "/api/records",
        query_string={
            "type": "expense",
            "start_date": "2026-11-06",
            "end_date": "2026-11-07",
            "limit": "1",
            "offset": "0",
        },
    )
    data = response.get_json()["data"]
    assert data["total"] == 2, "total 是分页前的匹配条数"
    assert len(data["items"]) == 1
    assert data["items"][0]["type"] == "expense"


def test_empty_string_params_are_ignored(seeded):
    client = seeded.test_client()
    response = client.get("/api/records", query_string={"type": "", "category": ""})
    assert response.status_code == 200
    assert response.get_json()["data"]["total"] == 3


def test_empty_ledger_returns_zero_totals(ledger):
    client = ledger.test_client()
    response = client.get("/api/records")
    assert response.status_code == 200
    assert response.get_json()["data"]["items"] == []
    assert response.get_json()["data"]["total"] == 0


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"start_date": "2026/11/07"}, "start_date"),
        ({"end_date": "2026-02-30"}, "end_date"),
        ({"start_date": "2026-11-08", "end_date": "2026-11-01"}, "end_date"),
        ({"type": "all"}, "type"),
        ({"category": "不存在的类别"}, "category"),
        ({"type": "income", "category": "餐饮"}, "category"),
        ({"min_amount": "-1"}, "min_amount"),
        ({"max_amount": "1e3"}, "max_amount"),
        ({"min_amount": "10.00", "max_amount": "5.00"}, "max_amount"),
        ({"limit": "0"}, "limit"),
        ({"limit": "101"}, "limit"),
        ({"limit": "abc"}, "limit"),
        ({"limit": "²"}, "limit"),   # Unicode 数字：不能变成 500
        ({"offset": "１"}, "offset"),
        ({"offset": "-1"}, "offset"),
    ],
)
def test_illegal_params_return_400_with_field_errors(seeded, params, field):
    client = seeded.test_client()
    response = client.get("/api/records", query_string=params)

    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert field in error["fields"], "错误必须定位到具体字段"


def test_unknown_query_param_is_rejected(seeded):
    client = seeded.test_client()
    response = client.get("/api/records", query_string={"startDate": "2026-11-07"})

    assert response.status_code == 400
    fields = response.get_json()["error"]["fields"]
    assert fields == {"startDate": "未知查询参数"}, "参数大小写写错也必须报出来"
