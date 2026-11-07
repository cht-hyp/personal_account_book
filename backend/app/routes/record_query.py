"""GET /api/records 路由（负责人：4 号 高一鹏）。

职责边界（README 3、8.5）：
    路由只做"取参数白名单 → 调校验 → 读一次存储 → 调业务 → 包 data"，
    不自己实现筛选、不直接打开 JSON 文件、不重复计算 total。
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..errors import ValidationError
from ..services.record_query import query_records
from ..validators import parse_filters, parse_pagination

record_query_bp = Blueprint("record_query_bp", __name__)

# 白名单而不是黑名单：拼错参数名（例如 startDate、category_id）必须报 400，
# 否则用户以为筛选生效了，实际拿到的是全量数据（README 7.6）。
ALLOWED_PARAMS = frozenset(
    {
        "start_date",
        "end_date",
        "type",
        "category",
        "min_amount",
        "max_amount",
        "limit",
        "offset",
    }
)


@record_query_bp.get("/api/records")
def get_records():
    unknown = sorted(set(request.args.keys()) - ALLOWED_PARAMS)
    if unknown:
        raise ValidationError(
            "查询参数中包含不支持的字段",
            fields={name: "未知查询参数" for name in unknown},
        )

    filters = parse_filters(request.args)
    limit, offset = parse_pagination(request.args)

    store = current_app.extensions.get("record_store")
    if store is None:
        # 存储实例由 1 号的应用工厂挂在 app.extensions["record_store"]；
        # 缺失属于装配错误而不是用户输入错误，交给统一错误处理转成 500。
        raise RuntimeError("存储实例未初始化，请检查应用装配")

    # 只读一次：统计与分页都基于同一份快照，避免两次读盘之间数据变化
    records = store.list_records()

    result = query_records(records, filters, limit=limit, offset=offset)
    return jsonify({"data": result}), 200
