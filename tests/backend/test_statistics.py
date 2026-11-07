import sys
import types

import pytest
from flask import Flask

from backend.app.errors import ValidationError
from backend.app.routes.statistics import statistics_bp
from backend.app.services.statistics import summarize_records
from backend.app.validators import RecordFilter


def record(kind, amount_cents, category, record_id):
    return {
        'id': record_id,
        'date': '2026-11-07',
        'type': kind,
        'amount_cents': amount_cents,
        'category': category,
        'note': '',
        'created_at': '2026-11-07T06:30:00.000+00:00',
    }


def install_filter(monkeypatch, result):
    calls = []
    module = types.ModuleType('backend.app.services.record_query')

    def filter_records(records, filters):
        calls.append((records, filters))
        return result

    module.filter_records = filter_records
    monkeypatch.setitem(sys.modules, 'backend.app.services.record_query', module)
    return calls


def test_summarizes_reference_data_and_expense_categories(monkeypatch):
    records = [
        record('income', 100000, '工资', 'income-1'),
        record('expense', 2000, '餐饮', 'expense-1'),
        record('expense', 500, '交通', 'expense-2'),
    ]
    calls = install_filter(monkeypatch, records)

    result = summarize_records(records, RecordFilter())

    assert calls == [(records, RecordFilter())]
    assert result == {
        'income_cents': 100000,
        'expense_cents': 2500,
        'balance_cents': 97500,
        'count': 3,
        'income_count': 1,
        'expense_count': 2,
        'expense_by_category': [
            {'category': '餐饮', 'amount_cents': 2000, 'count': 1},
            {'category': '交通', 'amount_cents': 500, 'count': 1},
        ],
    }


def test_negative_balance_for_expense_only_result(monkeypatch):
    records = [record('expense', 2050, '餐饮', 'expense-1')]
    install_filter(monkeypatch, records)

    result = summarize_records(records, RecordFilter(type='expense'))

    assert result['income_cents'] == 0
    assert result['expense_cents'] == 2050
    assert result['balance_cents'] == -2050
    assert result['income_count'] == 0
    assert result['expense_count'] == 1


def test_integer_cents_avoid_float_rounding(monkeypatch):
    records = [
        record('expense', 10, '餐饮', 'expense-1'),
        record('expense', 20, '餐饮', 'expense-2'),
    ]
    install_filter(monkeypatch, records)

    result = summarize_records(records, RecordFilter())

    assert result['expense_cents'] == 30
    assert result['expense_by_category'] == [
        {'category': '餐饮', 'amount_cents': 30, 'count': 2}
    ]


def test_expense_categories_sort_by_amount_then_name(monkeypatch):
    records = [
        record('expense', 300, '交通', 'expense-1'),
        record('expense', 600, '餐饮', 'expense-2'),
        record('expense', 100, '购物', 'expense-3'),
        record('expense', 300, '交通', 'expense-4'),
    ]
    install_filter(monkeypatch, records)

    result = summarize_records(records, RecordFilter())

    assert result['expense_by_category'] == [
        {'category': '交通', 'amount_cents': 600, 'count': 2},
        {'category': '餐饮', 'amount_cents': 600, 'count': 1},
        {'category': '购物', 'amount_cents': 100, 'count': 1},
    ]


def test_no_matches_include_all_zero_fields(monkeypatch):
    install_filter(monkeypatch, [])

    result = summarize_records([], RecordFilter())

    assert result == {
        'income_cents': 0,
        'expense_cents': 0,
        'balance_cents': 0,
        'count': 0,
        'income_count': 0,
        'expense_count': 0,
        'expense_by_category': [],
    }


class FakeStore:
    def __init__(self, records):
        self.records = records
        self.calls = 0

    def list_records(self):
        self.calls += 1
        return self.records


def make_app(store):
    app = Flask(__name__)
    app.extensions['record_store'] = store
    app.register_blueprint(statistics_bp)

    @app.errorhandler(ValidationError)
    def handle_validation(error):
        return {
            'error': {
                'code': error.code,
                'message': error.message,
                'fields': error.fields,
            }
        }, error.status_code

    return app


def test_statistics_http_uses_one_store_snapshot_and_shared_filters(monkeypatch):
    records = [
        record('income', 100000, '工资', 'income-1'),
        record('expense', 2000, '餐饮', 'expense-1'),
        record('expense', 500, '交通', 'expense-2'),
    ]
    store = FakeStore(records)
    calls = install_filter(monkeypatch, records)
    app = make_app(store)

    response = app.test_client().get(
        '/api/statistics?start_date=2026-11-07&type=expense'
    )

    assert response.status_code == 200
    assert response.json['data']['expense_cents'] == 2500
    assert store.calls == 1
    assert len(calls) == 1
    assert calls[0][0] is records
    assert calls[0][1].start_date.isoformat() == '2026-11-07'
    assert calls[0][1].type == 'expense'


@pytest.mark.parametrize(
    ('query', 'field'),
    [('limit=1', 'limit'), ('offset=20', 'offset'), ('unknown=value', 'unknown')],
)
def test_statistics_http_rejects_pagination_and_unknown_parameters(
    monkeypatch, query, field
):
    store = FakeStore([])
    install_filter(monkeypatch, [])
    app = make_app(store)

    response = app.test_client().get(f'/api/statistics?{query}')

    assert response.status_code == 400
    assert response.json['error']['code'] == 'VALIDATION_ERROR'
    assert field in response.json['error']['fields']
    assert store.calls == 0
