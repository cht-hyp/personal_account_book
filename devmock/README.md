# 开发期 Mock 后端（仅前端联调）

前端 8/9/10/11 号在真实 Flask 接口就绪前，用它把页面跑起来联调；也可以用来快速判断问题出在前端还是后端。

## 边界（重要）

- 只用 Python 标准库，**不需要安装 Flask**，不改任何真实账本文件。
- 数据只在内存里，进程结束即丢失，不做持久化、不做并发存储验证。
- 真实接口由 1/3/4/5/6 号在 `backend/` 实现。本目录内容**不进入 Release 运行包**，也不能留在发布版里假装后端。
- 校验只为联调服务，不是 6 号 `validators.py` 的替代品；字段错误格式与 README 第 7 节保持一致。

## 启动

在 `co-lab2/` 目录下：

```powershell
# 用构建产物（先 cd frontend; npm run build）
python devmock/mock_server.py --web frontend/dist --port 5055
# 或用 1 号复制出来的 web/
python devmock/mock_server.py --web web --port 5055
```

访问 `http://127.0.0.1:5055`。开发模式请另开终端跑 `npm run dev`，并用
`$env:VITE_API_PROXY_TARGET = "http://127.0.0.1:5055"` 让 Vite 代理到 Mock。

首次启动会预置 README 15.2 的三条基准数据：工资收入 1000.00、餐饮支出 20.00、交通支出 5.00。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 返回 `{"data":{"status":"ok"}}` |
| GET | `/api/categories` | 收入 5 类、支出 8 类 |
| POST | `/api/records` | 只收金额字符串；未知字段、数值金额、三位小数、零/负数、非 JSON Content-Type 均按第 7 节返回错误码 |
| GET | `/api/records` | 组合筛选、`date desc, created_at desc, id desc` 排序、`limit/offset`、`total` |
| GET | `/api/statistics` | 六个业务条件，返回收入/支出/结余/条数/类别汇总；拒绝 `limit/offset` |

## 调试开关（仅 Mock 有）

用于验证前端的错误态与重试：

```powershell
# 让 /api/categories 返回 500，刷新页面即可看到类别失败提示与重试按钮
curl.exe "http://127.0.0.1:5055/__mock__/fail?target=categories"
# 统计或列表故障
curl.exe "http://127.0.0.1:5055/__mock__/fail?target=statistics"
# 恢复
curl.exe "http://127.0.0.1:5055/__mock__/fail?target=off"
```

## 契约检查

```powershell
python devmock/check_contract.py --base http://127.0.0.1:5055
```

覆盖：健康与类别、三条基准数据、餐饮筛选、金额字符串校验（三位小数/数值/零/负数/科学计数法/千分位）、类别与类型不匹配、未知字段、415、分页与超范围 offset、金额边界 0、反向日期、未知 API 404、方法不支持 405、统计拒绝分页参数。全部通过时返回码 0，否则列出失败项并返回 1。

注意：本脚本会写入新记录，跑完后 `total` 不再是 3。需要干净基准数据时重启 Mock 进程。
