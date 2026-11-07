<script setup>
/**
 * 【占位骨架】本文件属于 10 号（筛选与明细），由 7 号在骨架期提供最小可运行外壳。
 * 交付前必须由 10 号替换：appliedFilters、分页、total、快速查询只取最后一次响应、
 * 失败与空态区分。当前外壳只拉取第一页，用于验证页面可访问与刷新链路。
 * 契约要求保持不变：props 只有 categories、refreshKey；复用 9 号 RecordTable。
 */
import { ref, watch } from 'vue'
import { listRecords, isApiError } from '../api/client.js'
import FilterPanel from '../components/filters/FilterPanel.vue'
import RecordTable from '../components/records/RecordTable.vue'

const props = defineProps({
  categories: { type: Object, default: null },
  refreshKey: { type: Number, default: 0 }
})

const items = ref([])
const total = ref(0)
const loading = ref(false)
const errorMessage = ref('')
let requestSeq = 0

async function load() {
  const seq = ++requestSeq
  loading.value = true
  errorMessage.value = ''
  try {
    const page = await listRecords({ limit: 20, offset: 0 })
    if (seq !== requestSeq) return
    items.value = page.items
    total.value = page.total
  } catch (error) {
    if (seq !== requestSeq) return
    items.value = []
    total.value = 0
    errorMessage.value = isApiError(error) ? `${error.message}（${error.code}）` : '明细加载失败'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

watch(() => props.refreshKey, load, { immediate: true })
</script>

<template>
  <div class="records-view">
    <div class="card">
      <h2>明细</h2>
      <p class="hint">10 号实现中：筛选、分页与总条数。当前骨架固定显示第一页 20 条。</p>
    </div>

    <FilterPanel :categories="categories" :loading="loading" @search="load" @reset="load" />

    <div class="card">
      <div class="head">
        <h2>记录列表</h2>
        <span v-if="!loading && !errorMessage" class="hint">共 {{ total }} 条</span>
      </div>

      <p v-if="loading" class="state-block state-loading">正在加载明细…</p>
      <div v-else-if="errorMessage" class="state-block state-error" role="alert">
        <p>{{ errorMessage }}</p>
        <button type="button" class="btn" @click="load">重新加载</button>
      </div>
      <p v-else-if="items.length === 0" class="state-block">没有符合条件的记录。</p>
      <RecordTable v-else :records="items" />
    </div>
  </div>
</template>

<style scoped>
.records-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
</style>
