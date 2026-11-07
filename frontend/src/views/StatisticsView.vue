<script setup>
/**
 * 统计页：11 号负责。展示当前筛选范围内的收入、支出、结余、记录数与类别支出汇总。
 * 数据统一来自 /api/statistics（经 api/client.js），只消费后端汇总结果，
 * 不在本页重新实现业务统计。FilterPanel 契约：search(filters) / reset()。
 */
import { ref, watch } from 'vue'
import { getStatistics, isApiError } from '../api/client.js'
import { formatMoney } from '../utils/format.js'
import FilterPanel from '../components/filters/FilterPanel.vue'
import CategoryChart from '../components/statistics/CategoryChart.vue'

const props = defineProps({
  categories: { type: Object, default: null },
  refreshKey: { type: Number, default: 0 }
})

const stats = ref(null)
const loading = ref(false)
const errorMessage = ref('')
/** 当前生效的筛选条件，使用与 /api/statistics 相同的 HTTP 参数名。 */
const activeFilters = ref({})
let requestSeq = 0

async function load() {
  const seq = ++requestSeq
  loading.value = true
  errorMessage.value = ''
  try {
    // 统计接口只接受六个业务筛选参数；buildQuery 会按白名单丢弃其余键。
    const data = await getStatistics(activeFilters.value)
    if (seq !== requestSeq) return
    stats.value = data
  } catch (error) {
    // 请求失败必须保持错误态，不能伪装成“暂无数据”
    if (seq !== requestSeq) return
    stats.value = null
    errorMessage.value = isApiError(error) ? `${error.message}（${error.code}）` : '统计加载失败'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

function handleSearch(filters) {
  activeFilters.value = { ...(filters || {}) }
  load()
}

function handleReset() {
  activeFilters.value = {}
  load()
}

watch(() => props.refreshKey, load, { immediate: true })
</script>

<template>
  <div class="stats-view">
    <FilterPanel
      :categories="categories"
      :loading="loading"
      @search="handleSearch"
      @reset="handleReset"
    />

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

      <p v-if="stats.count === 0" class="hint stats-empty-note">
        当前筛选条件下没有匹配记录，上方数值均为零值。
      </p>
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

.stats-empty-note {
  margin: 0;
}
</style>
