# 9 号：记录展示

负责人：龚巍斌。本地开发分支：`feat/09-record-table`。

- `RecordTable.vue`：接收 records，展示日期、类型、类别、金额与备注；可选 emptyText 和 actions 插槽。
- `RecentRecords.vue`：首次及 refreshKey 变化时调用 listRecords({ limit: 10, offset: 0 })，处理加载、空态、失败与竞态。

公共客户端 api/client.js、公共格式化 utils/format.js 由 7 号提供，组件不创建替代的生产实现。

详见 [模块接入与验证说明](../../../../docs/9号记录展示模块说明.md)。
