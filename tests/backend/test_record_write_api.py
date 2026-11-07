"""POST /api/records 接口层验证（3 号 周玘晖）。

这一层验证「参数进得去、错误出得来、落盘是真的」：
    - 201 且记录真的写进了 JSON 文件
    - 415 / 400 INVALID_JSON / 400 VALIDATION_ERROR 各自的触发条件与字段定位
    - 校验失败与存储失败都不写文件、不返回假成功

说明：统一错误响应与未知 /api 的 JSON 404 属于 1 号的应用工厂。这里按
4 号 test_query_api.py 的同样做法自建最小应用，只装配本模块需要的部分，
以便在 1 号 create_app 合并前也能独立验证；合并后用真实装配复跑。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from flask import Flask, jsonify

from backend.app.errors import ValidationError
from backend.app.routes.record_write import record_write_bp
from backend.app.storage import JsonRecordStore, StorageError

VALID_BODY = {
    "date": "2026-11-07",
    "type": "expense",
    "amount": "20.50",
    "category": "餐饮",
    "note": "午餐",
}


def build_app(data_file: Path) -> Flask:
    """只装配写入模块所需的部分：存储实例 + 写入 Blueprint + 错误处理。"""
    app = Flask(__name__)
    store = JsonRecordStore(data_file)
    store.initialize()
    app.extensions["record_store"] = store
    app.register_blueprint(record_write_bp)

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return (
            jsonify(
                {
                    "error": {
                        "code": error.code,
                        "message": error.message,
                        "fields": error.fields,
                    }
                }
            ),
            error.status_code,
        )

    @app.errorhandler(StorageError)
    def handle_storage_error(error):
        return (
            jsonify(
                {
                    "error": {
                        "code": "STORAGE_ERROR",
                        "message": "数据保存失败，请稍后重试",
                        "fields": {},
                    }
                }
            ),
            500,
        )

    return app


def read_file(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def data_file(tmp_path: Path) -> Path:
    return tmp_path / "records.json"


@pytest.fixture()
def app(data_file: Path) -> Flask:
    return build_app(data_file)


@pytest.fixture()
def client(app: Flask):
    return app.test_client()


class TestCreateSuccess:
    def test_returns_201_and_persists_record(self, client, data_file):
        response = client.post("/api/records", json=VALID_BODY)
        assert response.status_code == 201, response.get_data(as_text=True)

        record = response.get_json()["data"]
        assert record["date"] == "2026-11-07"
        assert record["type"] == "expense"
        assert record["amount_cents"] == 2050
        assert record["category"] == "餐饮"
        assert record["note"] == "午餐"
        assert record["id"] and record["created_at"]

        on_disk = read_file(data_file)
        assert len(on_disk) == 1, "201 之后记录必须已经落盘"
        assert on_disk[0]["id"] == record["id"]
        assert on_disk[0]["amount_cents"] == 2050

    def test_income_and_expense_both_saved(self, client, data_file):
        client.post("/api/records", json=VALID_BODY)
        client.post(
            "/api/records",
            json={"date": "2026-11-07", "type": "income", "amount": "1000",
                  "category": "工资"},
        )
        on_disk = read_file(data_file)
        assert len(on_disk) == 2
        assert {r["type"] for r in on_disk} == {"income", "expense"}
        assert [r["amount_cents"] for r in on_disk] == [2050, 100000]

    def test_amount_is_converted_without_float_error(self, client, data_file):
        """0.10 与 0.20 的经典浮点问题：落盘必须是 10 / 20 分。"""
        for amount in ("0.10", "0.20"):
            response = client.post("/api/records", json={**VALID_BODY, "amount": amount})
            assert response.status_code == 201
        cents = [r["amount_cents"] for r in read_file(data_file)]
        assert cents == [10, 20]
        assert sum(cents) == 30, "整数分求和不能出现 0.30000000000000004 类误差"

    def test_note_is_trimmed_and_optional(self, client, data_file):
        client.post("/api/records", json={**VALID_BODY, "note": "  午餐  "})
        client.post(
            "/api/records",
            json={k: v for k, v in VALID_BODY.items() if k != "note"},
        )
        on_disk = read_file(data_file)
        assert on_disk[0]["note"] == "午餐"
        assert on_disk[1]["note"] == "", "省略 note 时应存空字符串而不是 null"

    def test_chinese_is_returned_as_parsed_json_not_escaped(self, client):
        response = client.post("/api/records", json=VALID_BODY)
        assert response.get_json()["data"]["category"] == "餐饮"

    def test_boundary_amounts_are_accepted(self, client, data_file):
        client.post("/api/records", json={**VALID_BODY, "amount": "0.01"})
        client.post("/api/records", json={**VALID_BODY, "amount": "99999999.99"})
        cents = [r["amount_cents"] for r in read_file(data_file)]
        assert cents == [1, 9_999_999_999]


class TestCreateValidation:
    @pytest.mark.parametrize(
        ("patch", "bad_field"),
        [
            ({"amount": "20.005"}, "amount"),
            ({"amount": "0"}, "amount"),
            ({"amount": "-1"}, "amount"),
            ({"amount": "1e3"}, "amount"),
            ({"amount": 20}, "amount"),
            ({"date": "2026-02-30"}, "date"),
            ({"date": "2026/11/07"}, "date"),
            ({"type": "transfer"}, "type"),
            ({"category": "工资"}, "category"),  # 工资属收入，与 expense 不匹配
            ({"note": "备" * 201}, "note"),
        ],
    )
    def test_invalid_field_returns_400_with_field_errors(
        self, client, data_file, patch, bad_field
    ):
        response = client.post("/api/records", json={**VALID_BODY, **patch})
        assert response.status_code == 400, response.get_data(as_text=True)

        error = response.get_json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert bad_field in error["fields"], f"错误必须定位到字段 {bad_field}"
        assert read_file(data_file) == [], "校验失败不能写入文件"

    def test_missing_field_returns_400(self, client, data_file):
        body = {k: v for k, v in VALID_BODY.items() if k != "category"}
        response = client.post("/api/records", json=body)
        assert response.status_code == 400
        assert "category" in response.get_json()["error"]["fields"]
        assert read_file(data_file) == []

    def test_unknown_field_returns_400(self, client, data_file):
        response = client.post("/api/records", json={**VALID_BODY, "id": "forged"})
        assert response.status_code == 400
        assert "id" in response.get_json()["error"]["fields"], "前端不能提交 id"
        assert read_file(data_file) == []

    def test_amount_cents_cannot_be_supplied(self, client, data_file):
        response = client.post("/api/records", json={**VALID_BODY, "amount_cents": 2000})
        assert response.status_code == 400
        assert "amount_cents" in response.get_json()["error"]["fields"]
        assert read_file(data_file) == []


class TestCreateProtocol:
    def test_non_json_content_type_returns_415(self, client, data_file):
        response = client.post(
            "/api/records", data="date=2026-11-07", content_type="text/plain"
        )
        assert response.status_code == 415
        assert response.get_json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
        assert read_file(data_file) == []

    def test_missing_content_type_returns_415(self, client):
        response = client.post("/api/records", data="{}")
        assert response.status_code == 415

    def test_broken_json_returns_400_invalid_json(self, client, data_file):
        response = client.post(
            "/api/records", data='{"date":', content_type="application/json"
        )
        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "INVALID_JSON"
        assert read_file(data_file) == []

    def test_array_body_returns_400(self, client):
        response = client.post("/api/records", json=[VALID_BODY])
        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "INVALID_JSON"

    def test_empty_body_returns_400(self, client):
        response = client.post("/api/records", data="", content_type="application/json")
        assert response.status_code == 400


class TestStorageFailure:
    def test_storage_failure_returns_500_and_keeps_file_intact(
        self, app, client, data_file, monkeypatch
    ):
        """保存失败不会返回成功，也不能留下半条记录。"""
        store = app.extensions["record_store"]

        def boom(record):
            raise StorageError("数据保存失败，请稍后重试")

        monkeypatch.setattr(store, "append_record", boom)
        before = data_file.read_text(encoding="utf-8")

        response = client.post("/api/records", json=VALID_BODY)

        assert response.status_code == 500
        assert response.get_json()["error"]["code"] == "STORAGE_ERROR"
        assert data_file.read_text(encoding="utf-8") == before
