"""Member 5: HTTP endpoint for filtered income and expense statistics."""

from flask import Blueprint, current_app, jsonify, request

from ..errors import ValidationError
from ..services.statistics import summarize_records
from ..validators import FILTER_FIELDS, parse_filters


statistics_bp = Blueprint('statistics', __name__)


@statistics_bp.get('/api/statistics')
def statistics():
    """Summarize all records matching the six shared business filters."""
    unknown_fields = sorted(set(request.args) - FILTER_FIELDS)
    if unknown_fields:
        fields = {
            field: (
                '统计接口不接受分页参数'
                if field in ('limit', 'offset')
                else '统计接口不接受该参数'
            )
            for field in unknown_fields
        }
        raise ValidationError('输入参数不合法', fields)

    filters = parse_filters(request.args)
    store = current_app.extensions['record_store']
    records = store.list_records()
    return jsonify(data=summarize_records(records, filters))
