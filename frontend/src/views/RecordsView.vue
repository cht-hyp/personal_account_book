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

    <div class="card records-results">
      <div class="results-heading">
        <h2>记录列表</h2>
        <span v-if="!loading && !error" class="hint">
          共 {{ total }} 条记录，第 {{ pageNumber }} / {{ totalPages }} 页
        </span>
      </div>

      <p v-if="loading" class="state-block state-loading" role="status" aria-live="polite">
        正在查询记录，请稍候…
      </p>

      <div v-else-if="error" class="state-block state-error" role="alert">
        <p><strong>记录加载失败：</strong>{{ error }}</p>
        <ul v-if="fieldErrors.length" class="field-errors">
          <li v-for="fieldError in fieldErrors" :key="fieldError.field">
            {{ fieldError.label }}：{{ fieldError.message }}
          </li>
        </ul>
        <button class="btn" type="button" @click="loadPage(retryOffset)">重新加载</button>
      </div>

      <p v-else-if="items.length === 0" class="state-block">
        {{ hasActiveFilters ? '没有符合当前筛选条件的记录。' : '账本还是空的，请先新增一笔收入或支出。' }}
      </p>

      <template v-else>
        <RecordTable :records="items" empty-text="没有符合当前筛选条件的记录" />

        <nav class="pagination" aria-label="记录分页">
          <button
            class="btn"
            type="button"
            :disabled="offset <= 0"
            @click="loadPage(offset - pageLimit)"
          >
            上一页
          </button>
          <span class="hint">第 {{ pageNumber }} 页，共 {{ totalPages }} 页</span>
          <button
            class="btn"
            type="button"
            :disabled="offset + pageLimit >= total"
            @click="loadPage(offset + pageLimit)"
          >
            下一页
          </button>
        </nav>
      </template>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import FilterPanel from '../components/filters/FilterPanel.vue'
import RecordTable from '../components/records/RecordTable.vue'
import { isApiError, listRecords } from '../api/client.js'

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
const retryOffset = ref(0)

let requestSequence = 0

const FIELD_LABELS = {
  start_date: '开始日期',
  end_date: '结束日期',
  type: '收支类型',
  category: '类别',
  min_amount: '最低金额',
  max_amount: '最高金额',
  limit: '每页条数',
  offset: '分页位置',
}

const pageNumber = computed(() => Math.floor(offset.value / pageLimit.value) + 1)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageLimit.value)))
const hasActiveFilters = computed(() => Object.keys(appliedFilters.value).length > 0)
const fieldErrors = computed(() =>
  Object.entries(errorDetails.value ?? {}).map(([field, message]) => ({
    field,
    label: FIELD_LABELS[field] || field,
    message,
  })),
)

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
  retryOffset.value = requestedOffset

  try {
    const page = await listRecords({
      ...appliedFilters.value,
      limit: PAGE_SIZE,
      offset: requestedOffset,
    })

    if (requestId !== requestSequence) {
      return
    }

    if (!Array.isArray(page?.items) || !Number.isInteger(page.total) || page.total < page.items.length ||
        !Number.isInteger(page.offset) || page.offset < 0 || !Number.isInteger(page.limit) || page.limit < 1) {
      throw new Error('记录数据格式不正确，请重试。')
    }
    items.value = page.items
    total.value = page.total
    offset.value = page.offset
    pageLimit.value = page.limit
  } catch (requestError) {
    if (requestId !== requestSequence) {
      return
    }

    error.value = isApiError(requestError)
      ? `${requestError.message}（${requestError.code}）`
      : (requestError?.message || '请求失败，请稍后重试。')
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
  { immediate: true },
)

onBeforeUnmount(() => {
  // 页面卸载后丢弃尚未完成的响应，避免旧请求回写已销毁组件。
  requestSequence += 1
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
  gap: var(--space-4);
}

.view-header h2 {
  margin: 0 0 var(--space-1);
  color: var(--color-text, #1f2933);
  font-size: clamp(1.45rem, 3vw, 2rem);
}

.view-header p {
  color: var(--color-muted, #5f6b73);
}

.eyebrow {
  color: var(--color-accent, #0f766e) !important;
  font-size: 0.8rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.records-results {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.results-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
}

.field-errors {
  margin: var(--space-2) 0;
  padding-left: 1.25rem;
  color: var(--color-danger, #b42318);
  font-size: var(--font-size-sm);
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

@media (max-width: 560px) {
  .pagination {
    flex-wrap: wrap;
    justify-content: center;
  }

  .results-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
