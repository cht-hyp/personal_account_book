<script setup>
/**
 * 【占位骨架】本文件属于 11 号（统计展示 / DevOps），由 7 号在骨架期提供最小可运行外壳。
 * 交付前必须由 11 号替换：正式统计卡片、FilterPanel 集成、空态与刷新。
 * 契约要求保持不变：props 只有 categories、refreshKey；数据来自 /api/statistics。
 */
import { ref, watch } from 'vue'
import { getStatistics, isApiError } from '../api/client.js'
import { formatMoney } from '../utils/format.js'
import CategoryChart from '../components/statistics/CategoryChart.vue'

const props = defineProps({
  categories: { type: Object, default: null },
  refreshKey: { type: Number, default: 0 }
})

const stats = ref(null)
const loading = ref(false)
const errorMessage = ref('')
let requestSeq = 0

async function load() {
  const seq = ++requestSeq
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await getStatistics({})
    if (seq !== requestSeq) return
    stats.value = data
  } catch (error) {
    if (seq !== requestSeq) return
    stats.value = null
    errorMessage.value = isApiError(error) ? `${error.message}（${error.code}）` : '统计加载失败'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

watch(() => props.refreshKey, load, { immediate: true })
</script>

<template>
  <div class="stats-view">
    <div class="card">
      <h2>收支统计</h2>
      <p class="hint">11 号实现中：筛选集成与统计卡片。当前骨架展示全部记录汇总。</p>
    </div>

    <p v-if="loading" class="state-block state-loading">正在加载统计…</p>
    <div v-else-if="errorMessage" class="state-block state-error" role="alert">
      <p>{{ errorMessage }}</p>
      <button type="button" class="btn" @click="load">重新加载</button>
    </div>

    <template v-else-if="stats">
      <dl class="cards">
        <div class="card stat">
          <dt>收入</dt>
          <dd class="amount amount-income">{{ formatMoney(stats.income_cents) }}</dd>
        </div>
        <div class="card stat">
          <dt>支出</dt>
          <dd class="amount amount-expense">{{ formatMoney(stats.expense_cents) }}</dd>
        </div>
        <div class="card stat">
          <dt>结余</dt>
          <dd class="amount" :class="stats.balance_cents < 0 ? 'amount-expense' : 'amount-income'">
            {{ formatMoney(stats.balance_cents) }}
          </dd>
        </div>
        <div class="card stat">
          <dt>记录数</dt>
          <dd class="amount">{{ stats.count }}</dd>
        </div>
      </dl>

      <CategoryChart :items="stats.expense_by_category" :total-cents="stats.expense_cents" />
    </template>
  </div>
</template>

<style scoped>
.stats-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--space-4);
  margin: 0;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-4) var(--space-5);
}

.stat dt {
  color: var(--color-muted);
  font-size: var(--font-size-sm);
}

.stat dd {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
}
</style>
