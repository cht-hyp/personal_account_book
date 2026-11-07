<script setup>
/**
 * 【占位骨架】本文件属于 10 号（筛选与明细），由 7 号在骨架期提供最小可运行外壳。
 * 交付前必须由 10 号替换：六个筛选条件、内部草稿、type 与 category 联动清空、
 * 查询/重置按钮、loading 禁用。
 * 契约要求保持不变：props 只有 categories、loading；发出 search(filters)、reset()；
 * filters 使用 HTTP 参数名，金额保持字符串，空项省略。
 */
defineProps({
  categories: { type: Object, default: null },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['search', 'reset'])
</script>

<template>
  <div class="card filter-panel">
    <div>
      <h2>筛选条件</h2>
      <p class="hint">10 号实现中：日期范围、收支类型、类别、金额范围组合筛选。</p>
    </div>
    <div class="actions">
      <button type="button" class="btn btn-primary" :disabled="loading" @click="emit('search', {})">查询</button>
      <button type="button" class="btn" :disabled="loading" @click="emit('reset')">重置</button>
    </div>
  </div>
</template>

<style scoped>
.filter-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.actions {
  display: flex;
  gap: var(--space-2);
}
</style>
