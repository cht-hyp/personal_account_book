import pytest

from backend.app.categories import get_categories
from backend.app.errors import ValidationError
from backend.app.validators import parse_filters, parse_pagination, validate_record_payload


def payload(**changes):
    return dict(date='2026-11-07', type='expense', amount='20.50', category='餐饮', **changes)


def test_normalization():
    result = validate_record_payload(payload(note=' 午餐 '))
    assert result == dict(date='2026-11-07', type='expense', amount_cents=2050, category='餐饮', note='午餐')
    assert validate_record_payload(payload())['note'] == ''


@pytest.mark.parametrize('amount', [0, 20, True, None, '', '0', '-1', '1e2', '1.234', 'NaN', '100,000', '100000000.00'])
def test_invalid_amount(amount):
    body = payload()
    body['amount'] = amount
    with pytest.raises(ValidationError) as error:
        validate_record_payload(body)
    assert 'amount' in error.value.fields


@pytest.mark.parametrize('field,value', [('date','2026-02-30'), ('date','2026-1-01'), ('category','工资'), ('type','other'), ('note',None), ('note','a'*201), ('id','client-id')])
def test_invalid_fields(field, value):
    body = payload()
    body[field] = value
    with pytest.raises(ValidationError):
        validate_record_payload(body)


def test_invalid_body_and_missing():
    for body in [None, [], {}, 'text']:
        with pytest.raises(ValidationError):
            validate_record_payload(body)


def test_filters():
    filters = parse_filters({'start_date':'2026-11-07', 'category':'工资', 'min_amount':'0', 'max_amount':'20.50'})
    assert filters.start_date.isoformat() == '2026-11-07'
    assert filters.min_amount_cents == 0
    assert filters.max_amount_cents == 2050
    assert filters.type is None
    assert parse_filters({'type':''}).type is None


@pytest.mark.parametrize('query', [
    {'start_date':'2026-11-08','end_date':'2026-11-07'},
    {'min_amount':'2','max_amount':'1'},
    {'type':'income','category':'餐饮'}, {'category':'不存在'}, {'min_amount':'-1'}
])
def test_invalid_filters(query):
    with pytest.raises(ValidationError):
        parse_filters(query)


def test_pagination():
    assert parse_pagination({}) == (20, 0)
    assert parse_pagination({'limit':'10', 'offset':'20'}) == (10, 20)
    assert parse_pagination({'limit':'', 'offset':''}) == (20, 0)
    for query in [{'limit':'0'}, {'limit':'101'}, {'offset':'-1'}, {'limit':'1.5'}]:
        with pytest.raises(ValidationError):
            parse_pagination(query)


def test_categories_are_independent():
    first = get_categories()
    first['income'].clear()
    assert '工资' in get_categories()['income']


def test_categories_http():
    from flask import Flask
    from backend.app.routes.categories import categories_bp
    app = Flask(__name__)
    app.register_blueprint(categories_bp)
    response = app.test_client().get('/api/categories')
    assert response.status_code == 200
    assert response.json == {'data': get_categories()}
