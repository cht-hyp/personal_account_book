<template>
  <form class="card filter-panel" :aria-busy="loading" @submit.prevent="handleSearch">
    <div class="filter-heading">
      <h2>筛选条件</h2>
      <p class="hint">组合日期、收支类型、类别和金额范围查询明细。</p>
    </div>

    <div class="filter-grid">
      <label class="field">
        <span>开始日期</span>
        <input v-model="draft.start_date" type="date" autocomplete="off">
      </label>

      <label class="field">
        <span>结束日期</span>
        <input v-model="draft.end_date" type="date" autocomplete="off">
      </label>

      <label class="field">
        <span>收支类型</span>
        <select v-model="draft.type">
          <option value="">全部类型</option>
          <option value="income">收入</option>
          <option value="expense">支出</option>
        </select>
      </label>

      <label class="field">
        <span>类别</span>
        <select v-model="draft.category" :disabled="categoryOptions.length === 0">
          <option value="">全部类别</option>
          <option v-for="category in categoryOptions" :key="category" :value="category">
            {{ category }}
          </option>
        </select>
      </label>

      <label class="field">
        <span>最低金额（元）</span>
        <input
          v-model="draft.min_amount"
          type="text"
          inputmode="decimal"
          autocomplete="off"
          placeholder="例如 10.00"
        >
      </label>

      <label class="field">
        <span>最高金额（元）</span>
        <input
          v-model="draft.max_amount"
          type="text"
          inputmode="decimal"
          autocomplete="off"
          placeholder="例如 100.00"
        >
      </label>
    </div>

    <div class="filter-actions">
      <button class="btn btn-primary" type="submit" :disabled="loading">
        {{ loading ? "查询中…" : "查询" }}
      </button>
      <button class="btn" type="button" :disabled="loading" @click="handleReset">重置</button>
    </div>
  </form>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  categories: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['search', 'reset'])

function createEmptyDraft() {
  return {
    start_date: '',
    end_date: '',
    type: '',
    category: '',
    min_amount: '',
    max_amount: '',
  }
}

const draft = reactive(createEmptyDraft())

const categoryOptions = computed(() => {
  const income = Array.isArray(props.categories?.income) ? props.categories.income : []
  const expense = Array.isArray(props.categories?.expense) ? props.categories.expense : []

  if (draft.type === 'income') {
    return income
  }
  if (draft.type === 'expense') {
    return expense
  }
  return [...income, ...expense]
})

function clearInvalidCategory() {
  if (draft.category && !categoryOptions.value.includes(draft.category)) {
    draft.category = ''
  }
}

watch(() => draft.type, clearInvalidCategory)
watch(() => props.categories, clearInvalidCategory, { deep: true })

function buildFilters() {
  return Object.entries(draft).reduce((filters, [key, value]) => {
    const normalized = typeof value === 'string' ? value.trim() : value
    if (normalized !== '') {
      filters[key] = normalized
    }
    return filters
  }, {})
}

function handleSearch() {
  emit('search', buildFilters())
}

function handleReset() {
  Object.assign(draft, createEmptyDraft())
  emit('reset')
}
</script>

<style scoped>
.filter-panel {
  display: grid;
  gap: var(--space-4);
}

.filter-heading h2 {
  margin-bottom: var(--space-1);
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.field {
  display: grid;
  gap: var(--space-2);
  color: var(--color-text, #1f2933);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.field input,
.field select {
  width: 100%;
  min-height: 38px;
  box-sizing: border-box;
  padding: var(--space-2) 10px;
  border: 1px solid var(--color-border, #e2e6ea);
  border-radius: var(--radius-sm, 6px);
  background: var(--color-surface, #ffffff);
  color: inherit;
  font: inherit;
  font-weight: 400;
}

.field input:focus,
.field select:focus {
  border-color: var(--color-accent, #0f766e);
  outline: 2px solid var(--color-accent, #0f766e);
  outline-offset: 1px;
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}

@media (max-width: 760px) {
  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 480px) {
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .filter-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
}
</style>
