<script setup>
/**
 * 记录展示模块：只消费 records，不请求接口、不排序、不修改传入记录。
 * 金额由 7 号公共格式化函数处理，输入始终是后端返回的整数分。
 * actions 插槽预留行操作位置，后续编辑/删除由父页面处理。
 */
import { formatMoney } from '../../utils/format.js'

defineProps({
  records: { type: Array, default: () => [] },
  emptyText: { type: String, default: '暂无记账记录' },
})
</script>

<template>
  <div class="record-table-scroll" role="region" aria-label="收支记录表格" tabindex="0">
    <table class="record-table">
      <caption class="record-table-caption">收支记录明细，金额单位为人民币元</caption>
      <thead>
        <tr>
          <th scope="col">日期</th>
          <th scope="col">类型</th>
          <th scope="col">类别</th>
          <th scope="col" class="record-amount-heading">金额（元）</th>
          <th scope="col">备注</th>
          <th v-if="$slots.actions" scope="col">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="record in records" :key="record.id">
          <td class="record-date"><time :datetime="record.date">{{ record.date }}</time></td>
          <td>
            <span class="record-type" :class="'record-type--' + record.type">
              {{ record.type === 'income' ? '收入' : '支出' }}
            </span>
          </td>
          <td class="record-category">{{ record.category }}</td>
          <td class="record-amount" :class="'record-amount--' + record.type">
            <span>{{ record.type === 'income' ? '+' : '−' }}{{ formatMoney(record.amount_cents) }}</span>
          </td>
          <!-- 使用文本插值，备注中的 HTML 只按文字显示，不会执行。 -->
          <td class="record-note" :class="{ 'record-note--empty': !record.note }">
            {{ record.note || '—' }}
          </td>
          <td v-if="$slots.actions" class="record-actions">
            <slot name="actions" :record="record" />
          </td>
        </tr>
        <tr v-if="records.length === 0">
          <td class="record-table-empty" :colspan="$slots.actions ? 6 : 5">{{ emptyText }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.record-table-scroll {
  overflow-x: auto;
  border: 1px solid var(--border-color, #e3e8e7);
  border-radius: 12px;
}

.record-table-scroll:focus-visible {
  outline: 3px solid var(--focus-color, #88c5b4);
  outline-offset: 3px;
}

.record-table {
  width: 100%;
  min-width: 620px;
  border-collapse: collapse;
  color: var(--text-primary, #263c35);
  font-size: 14px;
  line-height: 1.6;
  text-align: left;
}

.record-table-caption {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

.record-table th,
.record-table td {
  padding: 15px 18px;
  vertical-align: top;
}

.record-table th {
  background: var(--surface-muted, #f4f7f6);
  color: var(--text-secondary, #667770);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.record-table tbody tr + tr {
  border-top: 1px solid var(--border-color, #e3e8e7);
}

.record-table tbody tr:hover {
  background: var(--surface-hover, #fafcfb);
}

.record-date,
.record-category {
  white-space: nowrap;
}

.record-type {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 6px;
  font-size: 12px;
  white-space: nowrap;
}

.record-type--income {
  background: #e8f4ed;
  color: #26734e;
}

.record-type--expense {
  background: #fff0e8;
  color: #a04726;
}

.record-amount-heading,
.record-amount {
  text-align: right;
  white-space: nowrap;
}

.record-amount {
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.record-amount--income { color: #26734e; }
.record-amount--expense { color: #a04726; }

.record-note {
  min-width: 120px;
  max-width: 340px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.record-note--empty { color: var(--text-secondary, #667770); }
.record-actions { white-space: nowrap; }

.record-table-empty {
  padding: 40px 18px;
  color: var(--text-secondary, #667770);
  text-align: center;
}

@media (max-width: 600px) {
  .record-table th,
  .record-table td { padding: 12px; }
}
</style>
