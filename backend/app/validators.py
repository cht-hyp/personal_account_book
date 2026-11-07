"""Member 6: normalize API input without Flask or filesystem dependencies."""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .categories import get_categories
from .errors import ValidationError

MAX_AMOUNT = Decimal('99999999.99')
FILTER_FIELDS = frozenset({'start_date', 'end_date', 'type', 'category', 'min_amount', 'max_amount'})
RECORD_FIELDS = frozenset({'date', 'type', 'amount', 'category', 'note'})


def _fail(field, message):
    raise ValidationError(message, {field: message})


def _text(value, field):
    if not isinstance(value, str):
        _fail(field, '必须为字符串')
    return value.strip()


def _date(value, field):
    value = _text(value, field)
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        _fail(field, '日期格式必须为 YYYY-MM-DD')
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail(field, '日期不存在')


def _cents(value, field, allow_zero=False):
    value = _text(value, field)
    if len(value) > 32 or not re.fullmatch(r'[0-9]+(?:\.[0-9]{1,2})?', value):
        _fail(field, '金额必须为普通十进制字符串，最多两位小数')
    amount = Decimal(value)
    if amount > MAX_AMOUNT or amount < 0 or (amount == 0 and not allow_zero):
        _fail(field, '金额超出允许范围')
    return int(amount * 100)


def _category(value, kind):
    value = _text(value, 'category')
    categories = get_categories()
    allowed = categories[kind] if kind else categories['income'] + categories['expense']
    if value not in allowed:
        _fail('category', '类别不存在或与收支类型不匹配')
    return value


def _type(value):
    value = _text(value, 'type')
    if value not in ('income', 'expense'):
        _fail('type', '类型必须为 income 或 expense')
    return value


def validate_record_payload(payload: dict) -> dict:
    """Validate creation fields; the write service adds id and created_at."""
    if not isinstance(payload, dict):
        _fail('body', '请求体必须为 JSON 对象')
    unknown = set(payload) - RECORD_FIELDS
    if unknown:
        _fail(sorted(unknown)[0], '不支持的字段')
    for field in ('date', 'type', 'amount', 'category'):
        if field not in payload:
            _fail(field, '必填字段')
    kind = _type(payload['type'])
    note = _text(payload.get('note', ''), 'note')
    if len(note) > 200:
        _fail('note', '备注最多 200 个字符')
    return {
        'date': _date(payload['date'], 'date').isoformat(),
        'type': kind,
        'amount_cents': _cents(payload['amount'], 'amount'),
        'category': _category(payload['category'], kind),
        'note': note,
    }


@dataclass(frozen=True)
class RecordFilter:
    start_date: date | None = None
    end_date: date | None = None
    type: str | None = None
    category: str | None = None
    min_amount_cents: int | None = None
    max_amount_cents: int | None = None


def _optional(params, field):
    value = params.get(field)
    if value is None:
        return None
    return _text(value, field) or None


def parse_filters(params) -> RecordFilter:
    """Parse only business filters; each route rejects unknown query keys."""
    values = {field: _optional(params, field) for field in FILTER_FIELDS}
    start = _date(values['start_date'], 'start_date') if values['start_date'] else None
    end = _date(values['end_date'], 'end_date') if values['end_date'] else None
    kind = _type(values['type']) if values['type'] else None
    category = _category(values['category'], kind) if values['category'] else None
    minimum = _cents(values['min_amount'], 'min_amount', True) if values['min_amount'] else None
    maximum = _cents(values['max_amount'], 'max_amount', True) if values['max_amount'] else None
    if start and end and start > end:
        _fail('end_date', '结束日期不得早于开始日期')
    if minimum is not None and maximum is not None and minimum > maximum:
        _fail('max_amount', '最高金额不得低于最低金额')
    return RecordFilter(start, end, kind, category, minimum, maximum)


def parse_pagination(params) -> tuple[int, int]:
    """Return (limit, offset), preserving explicit invalid input as errors."""
    result = []
    for field, default in [('limit', 20), ('offset', 0)]:
        value = _optional(params, field)
        if value is None:
            result.append(default)
            continue
        if len(value) > 18 or not re.fullmatch(r'[0-9]+', value):
            _fail(field, '分页参数必须为非负整数字符串')
        number = int(value)
        if field == 'limit' and not 1 <= number <= 100:
            _fail(field, 'limit 必须介于 1 和 100')
        result.append(number)
    return tuple(result)
