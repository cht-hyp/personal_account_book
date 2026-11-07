<script setup>
/**
 * 类别支出条形图：11 号负责。只消费后端 expense_by_category 汇总结果。
 * 展示规则（README 6.4）：按金额降序；没有支出时显示空态，不出现无效比例；
 * 金额为 0 的类别不占条形，避免无意义的 0% 行。
 */
import { computed } from 'vue'
import { formatMoney } from '../../utils/format.js'

const props = defineProps({
  items: { type: Array, default: () => [] },
  totalCents: { type: Number, default: 0 }
})

const rows = computed(() => {
  if (!props.totalCents) return []
  return props.items
    .filter((item) => item.amount_cents > 0)
    .map((item) => ({
      ...item,
      percent: Math.round((item.amount_cents / props.totalCents) * 100)
    }))
})
</script>

<template>
  <div class="card chart">
    <h2>类别支出</h2>

    <p v-if="totalCents === 0" class="state-block">当前条件下没有支出，暂无类别占比。</p>

    <ul v-else class="bars">
      <li v-for="row in rows" :key="row.category" class="bar-row">
        <span class="bar-label">{{ row.category }}</span>
        <span class="bar-track"><span class="bar-fill" :style="{ width: `${row.percent}%` }"></span></span>
        <span class="bar-value amount">{{ formatMoney(row.amount_cents) }}</span>
        <span class="bar-percent hint">{{ row.percent }}%</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.bars {
  margin-top: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.bar-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) 88px 40px;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--font-size-sm);
}

.bar-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bar-track {
  height: 10px;
  border-radius: 999px;
  background: var(--color-accent-soft);
  overflow: hidden;
}

.bar-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--color-accent);
}

.bar-value {
  text-align: right;
}

.bar-percent {
  text-align: right;
}
</style>
