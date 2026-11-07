<template>
  <section class="records-view" aria-labelledby="records-title">
    <header class="view-header">
      <div>
        <p class="eyebrow">明细</p>
        <h2 id="records-title">查看收支记录</h2>
        <p>组合日期、类型、类别和金额条件，查找需要核对的每一笔记录。</p>
      </div>
    </header>

    <FilterPanel
      :categories="categories"
      :loading="loading"
      @search="handleSearch"
      @reset="handleReset"
    />

    <div v-if="loading" class="state-card" role="status" aria-live="polite">
      <span class="state-mark" aria-hidden="true"></span>
      <div>
        <strong>正在查询记录</strong>
        <p>请稍候，结果即将显示。</p>
      </div>
    </div>

    <div v-else-if="error" class="state-card state-card--error" role="alert">
      <div>
        <strong>记录加载失败</strong>
        <p>{{ error }}</p>
        <ul v-if="fieldErrors.length" class="field-errors">
          <li v-for="[field, message] in fieldErrors" :key="field">
            {{ field }}：{{ message }}
          </li>
        </ul>
      </div>
      <button class="retry-button" type="button" @click="loadPage(offset)">重新加载</button>
    </div>

    <div v-else-if="items.length === 0" class="state-card state-card--empty">
      <div>
        <strong>{{ hasActiveFilters ? '没有符合条件的记录' : '账本还是空的' }}</strong>
        <p>
          {{ hasActiveFilters ? '可以调整筛选条件后再次查询。' : '新增一笔收入或支出后，记录会显示在这里。' }}
        </p>
      </div>
    </div>

    <template v-else>
      <div class="result-summary" aria-live="polite">
        <span>共 <strong>{{ total }}</strong> 条记录</span>
        <span>第 {{ pageNumber }} / {{ totalPages }} 页</span>
      </div>

      <RecordTable :records="items" />

      <nav class="pagination" aria-label="记录分页">
        <button
          type="button"
          :disabled="offset <= 0"
          @click="loadPage(offset - PAGE_SIZE)"
        >
          上一页
        </button>
        <span>第 {{ pageNumber }} 页，共 {{ totalPages }} 页</span>
        <button
          type="button"
          :disabled="offset + pageLimit >= total"
          @click="loadPage(offset + PAGE_SIZE)"
        >
          下一页
        </button>
      </nav>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import FilterPanel from '../components/filters/FilterPanel.vue'
import RecordTable from '../components/records/RecordTable.vue'
import { listRecords } from '../api/client'

const props = defineProps({
  categories: {
    type: Object,
    default: () => ({ income: [], expense: [] }),
  },
  refreshKey: {
    type: Number,
    default: 0,
  },
})

const PAGE_SIZE = 20

const appliedFilters = ref({})
const items = ref([])
const total = ref(0)
const offset = ref(0)
const pageLimit = ref(PAGE_SIZE)
const loading = ref(false)
const error = ref('')
const errorDetails = ref({})

let requestSequence = 0

const pageNumber = computed(() => Math.floor(offset.value / PAGE_SIZE) + 1)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const hasActiveFilters = computed(() => Object.keys(appliedFilters.value).length > 0)
const fieldErrors = computed(() => Object.entries(errorDetails.value ?? {}))

function normalizeOffset(value) {
  const number = Number(value)
  return Number.isInteger(number) && number >= 0 ? number : 0
}

async function loadPage(nextOffset) {
  const requestedOffset = normalizeOffset(nextOffset)
  const requestId = ++requestSequence

  loading.value = true
  error.value = ''
  errorDetails.value = {}

  try {
    const page = await listRecords({
      ...appliedFilters.value,
      limit: PAGE_SIZE,
      offset: requestedOffset,
    })

    if (requestId !== requestSequence) {
      return
    }

    items.value = Array.isArray(page?.items) ? page.items : []
    total.value = Number.isInteger(page?.total) ? page.total : 0
    offset.value = Number.isInteger(page?.offset) ? page.offset : requestedOffset
    pageLimit.value = Number.isInteger(page?.limit) && page.limit > 0
      ? page.limit
      : PAGE_SIZE
  } catch (requestError) {
    if (requestId !== requestSequence) {
      return
    }

    error.value = requestError?.message || '请求失败，请稍后重试。'
    errorDetails.value = requestError?.fields ?? {}
  } finally {
    if (requestId === requestSequence) {
      loading.value = false
    }
  }
}

function handleSearch(filters) {
  appliedFilters.value = { ...filters }
  void loadPage(0)
}

function handleReset() {
  appliedFilters.value = {}
  void loadPage(0)
}

watch(
  () => props.refreshKey,
  () => {
    void loadPage(offset.value)
  },
)

onMounted(() => {
  void loadPage(0)
})
</script>

<style scoped>
.records-view {
  display: grid;
  gap: 1rem;
}

.view-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
}

.view-header h2 {
  margin: 0.15rem 0 0.4rem;
  color: var(--color-heading, #163246);
  font-size: clamp(1.45rem, 3vw, 2rem);
}

.view-header p {
  margin: 0;
  color: var(--color-muted, #5e6d7b);
}

.eyebrow {
  color: var(--color-primary, #137c8b) !important;
  font-size: 0.8rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.state-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  min-height: 7rem;
  padding: 1.25rem;
  border: 1px dashed var(--color-border, #cbd6e2);
  border-radius: var(--radius-lg, 16px);
  background: var(--color-surface, #ffffff);
}

.state-card strong {
  color: var(--color-heading, #163246);
}

.state-card p {
  margin: 0.35rem 0 0;
  color: var(--color-muted, #5e6d7b);
}

.state-card--error {
  border-color: var(--color-danger-border, #e3a7a7);
  background: var(--color-danger-bg, #fff7f7);
}

.state-card--empty {
  justify-content: center;
  text-align: center;
}

.state-mark {
  width: 1.2rem;
  height: 1.2rem;
  flex: 0 0 auto;
  border: 3px solid var(--color-border, #cbd6e2);
  border-top-color: var(--color-primary, #137c8b);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.field-errors {
  margin: 0.6rem 0 0;
  padding-left: 1.25rem;
  color: var(--color-danger, #9b2525);
  font-size: 0.9rem;
}

.retry-button,
.pagination button {
  min-height: 2.4rem;
  padding: 0.45rem 0.85rem;
  border: 1px solid var(--color-border, #cbd6e2);
  border-radius: var(--radius-sm, 8px);
  background: var(--color-surface, #ffffff);
  color: var(--color-text, #203040);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.retry-button:hover,
.pagination button:hover:not(:disabled) {
  border-color: var(--color-primary, #137c8b);
  color: var(--color-primary, #137c8b);
}

.pagination button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.result-summary,
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  color: var(--color-muted, #5e6d7b);
  font-size: 0.92rem;
}

.result-summary strong {
  color: var(--color-heading, #163246);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 560px) {
  .pagination {
    flex-wrap: wrap;
    justify-content: center;
  }

  .state-card {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (prefers-reduced-motion: reduce) {
  .state-mark {
    animation: none;
  }
}
</style>
