"""POST /api/records 路由（负责人：3 号 周玘晖）。

职责边界（README 3、7.5、8.3）：
    路由只做「接口层判断 → 调业务 → 包 data 并给出状态码」，
    不重复实现金额、日期、类别规则（全部在 validators），也不打开数据文件。

失败状态码（README 7.1）：
    415  未使用 application/json
    400  请求体不是合法 JSON 对象、字段不合法、含未知字段
    500  存储故障（由统一错误处理把 StorageError 转成 500）
"""
from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify, request

from ..services.record_write import create_record

record_write_bp = Blueprint("record_write_bp", __name__)


@record_write_bp.post("/api/records")
def post_record() -> Any:
    """新增一条收入或支出记录；持久化成功后返回 201。"""
    # 1. 媒体类型必须是 JSON。不交给 request.get_json() 抛默认 415：
    #    那样响应会是 Flask 的 HTML 错误页，违反「错误响应一律 JSON」的约定。
    if not request.is_json:
        return _error_response(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "请求头需要包含 Content-Type: application/json",
        )

    # 2. 请求体必须能解析成 JSON 对象（数组、空体、坏 JSON 都在这里被挡下）
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error_response(400, "INVALID_JSON", "请求体必须是合法的 JSON 对象")

    # 3. 未知字段（例如前端误传 id / amount_cents / created_at）由 6 号
    #    validate_record_payload 统一拒绝，这里不再写第二份白名单：
    #    同一业务规则只保留一个来源（README 10.1 第 2 条）。
    store = current_app.extensions.get("record_store")
    if store is None:
        # 存储实例由 1 号的应用工厂挂在 app.extensions["record_store"]；
        # 缺失属于装配错误而不是用户输入错误，交给统一错误处理转成 500。
        raise RuntimeError("存储实例未初始化，请检查应用装配")

    # 4. 业务层：校验 → 生成 id/created_at → 组装 → 持久化 → 返回记录
    record = create_record(payload, store)

    # 201 表示「新增成功且已经持久化」
    return jsonify({"data": record}), 201


def _error_response(
    status: int,
    code: str,
    message: str,
    fields: dict[str, str] | None = None,
) -> tuple[Any, int]:
    """构造 README 7.1 约定的错误响应体。

    只有 415 与 INVALID_JSON 这两种「接口协议判断」在这里直接成形；
    字段级错误仍然抛出 ValidationError，交给 errors.py 的公共处理器，
    保证字段错误的成形方式只有一个。

    如果 1 号在 errors.py 里提供了统一的错误响应构造函数，
    把这里改成调用它即可，改动范围仅此一个函数。
    """
    return (
        jsonify(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "fields": fields or {},
                }
            }
        ),
        status,
    )
