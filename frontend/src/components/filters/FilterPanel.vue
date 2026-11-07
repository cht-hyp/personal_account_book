<template>
  <form class="filter-panel" :aria-busy="loading" @submit.prevent="handleSearch">
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
      <button class="primary-button" type="submit">
        {{ loading ? "查询中…" : "查询" }}
      </button>
      <button class="secondary-button" type="button" @click="handleReset">重置</button>
    </div>
  </form>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  categories: {
    type: Object,
    default: () => ({ income: [], expense: [] }),
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
  padding: 1.25rem;
  border: 1px solid var(--color-border, #d9e1ea);
  border-radius: var(--radius-lg, 16px);
  background: var(--color-surface, #ffffff);
  box-shadow: var(--shadow-sm, 0 8px 24px rgb(30 55 80 / 8%));
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.field {
  display: grid;
  gap: 0.4rem;
  color: var(--color-text, #203040);
  font-size: 0.9rem;
  font-weight: 600;
}

.field input,
.field select {
  width: 100%;
  min-height: 2.65rem;
  box-sizing: border-box;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--color-border, #cbd6e2);
  border-radius: var(--radius-sm, 8px);
  background: var(--color-input, #ffffff);
  color: inherit;
  font: inherit;
  font-weight: 400;
}

.field input:focus,
.field select:focus {
  border-color: var(--color-primary, #137c8b);
  outline: 3px solid var(--color-focus, rgb(19 124 139 / 18%));
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1.1rem;
}

.primary-button,
.secondary-button {
  min-width: 6rem;
  min-height: 2.65rem;
  padding: 0.5rem 1rem;
  border-radius: var(--radius-sm, 8px);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.primary-button {
  border: 1px solid var(--color-primary, #137c8b);
  background: var(--color-primary, #137c8b);
  color: #ffffff;
}

.secondary-button {
  border: 1px solid var(--color-border, #cbd6e2);
  background: var(--color-surface, #ffffff);
  color: var(--color-text, #203040);
}

.primary-button:hover,
.secondary-button:hover {
  filter: brightness(0.96);
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
    justify-content: stretch;
  }

  .primary-button,
  .secondary-button {
    flex: 1;
  }
}
</style>
