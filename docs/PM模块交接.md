# 6 号黄俊凡：类别与校验 / PM 模块交接

交接技术依据为 [项目设计与协作规范](项目设计与协作规范.md)（原 README），实名对应现场总览既有名单。现场总览不替代接口契约。

## 已实现

- `backend/app/categories.py`：唯一类别来源，返回独立列表。
- `backend/app/validators.py`：录入参数校验、金额精确转分、日期和类别校验、RecordFilter、筛选解析、分页解析。
- `backend/app/routes/categories.py`：GET /api/categories，返回 [项目设计与协作规范](项目设计与协作规范.md)约定的 data 对象。
- `backend/app/errors.py`：最小共享 ValidationError 契约，供 1 号叶凯乐接入统一错误处理。
- `tests/backend/test_validators.py`：业务校验及类别 HTTP 接口验证。

代码按用户授权通过 Codex 辅助实现；Git 提交使用本机已有身份，不代其他成员提交。

## 其他成员如何接入

1 号叶凯乐在 create_app 中注册 `categories_bp`，此 Blueprint 已含完整 `/api/categories` 路径，注册时不要再次添加 `/api` 前缀。

```python
from .routes.categories import categories_bp
from .errors import ValidationError

app.register_blueprint(categories_bp)

@app.errorhandler(ValidationError)
def handle_validation(error):
    return {"error": {"code": error.code, "message": error.message,
                      "fields": error.fields}}, error.status_code
```

3 号周玘晖调用 `validate_record_payload(payload)`，取得 date/type/amount_cents/category/note，再生成 UUID 和 created_at、保存文件。输入 amount 为元字符串，输出 amount_cents 为整数分。

4 号高一鹏调用 `parse_filters(request.args)` 和 `parse_pagination(request.args)`；后者返回 `(limit, offset)`。5 号王圣杰只调用 parse_filters；金额筛选允许零。RecordFilter 日期为 Python date，比较时将记录 date 字符串转为 date，或使用过滤日期的 isoformat()。

路由按自己的白名单拒绝未知查询参数：记录接口允许 FILTER_FIELDS 加 limit/offset；统计接口仅允许 FILTER_FIELDS。parse_filters 有意不拒绝分页参数，以便查询接口共用。未知录入字段由 validate_record_payload 直接拒绝。

7 号郑志銮 / 8 号王翔鹏从类别接口加载合法类别；校验失败的字段信息位于 error.fields。

## PM 协调与验收交接

| 对接人 | 待确认/交付事项 |
| --- | --- |
| 1 号叶凯乐 | 应用工厂注册类别 Blueprint、接入统一异常处理；负责后端整合与发布 |
| 2 号林明亮 | 存储接收规范化的 amount_cents 等字段；文件校验与保护仍由存储模块负责 |
| 3 号周玘晖 | 新增接口调用录入校验；确认失败不落盘、成功后才返回 201 |
| 4 号高一鹏 / 5 号王圣杰 | 使用相同 RecordFilter；路由拒绝未知参数；统计不接受分页参数 |
| 7 号郑志銮 / 8 号王翔鹏 | 类别加载、金额字符串提交及 error.fields 展示 |
| 9 号龚巍斌 / 10 号沈雷 | 列表字段与筛选参数对齐；沈雷汇总测试清单与缺陷，PM 跟进闭环 |
| 11 号林子涵 | 统计展示与演示串联；配合 1 号检查启动与 Release |

黄俊凡作为 PM 负责口径协调、进度跟进、博客统稿及贡献评分材料汇总；其他成员的代码实现与验证由对应负责人交付。技术审核负责人（TL）在总览中未明确实名，需团队指定，不自动认定某位成员担任。

审查时统一以下口径：

- 新增金额必须大于零，筛选金额上下限允许零。
- 分页和类别汇总仍按原 README 列为首版要求；现场应急降级不等于完整首版验收通过，也不改变约定的接口字段。
- 工资 1000、餐饮 20、交通 5 的全量统计为 1000/25/975；筛选餐饮后为 0/20/-20，重置后才恢复全量结果。
- 30 项模块测试通过是此前模块提交的验证记录；完整应用接通、全流程验收和发布需在整合后另行记录，不能据此标记已经完成。

## 验证方式与范围

已在 Python 3.11.9、Flask 3.1.2、pytest 9.1.0 环境验证。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

当前为目录骨架和 PM 模块，应用工厂、其他业务路由、前端和发布脚本仍待各负责人实现。类别接口已通过独立 Flask 测试应用验证；完整应用联调待 1 号叶凯乐装配后执行。

## 目录约定

根目录即项目根目录，不再套 co-lab2。目录 README 标注负责人，避免空目录无法被 Git 跟踪；不创建假业务实现。data/、web/ 为本地运行/构建目录，按规范忽略 Git，其他机器运行或构建时创建。
