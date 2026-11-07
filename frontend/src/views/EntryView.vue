<script setup>
/**
 * 记账页：7 号维护，只负责组合本页组件。
 * RecordForm（8 号）负责录入与提交，RecentRecords（9 号）负责最近 10 条。
 * 这里不写表单字段、不发请求，只把 saved 事件原样转发给 App。
 */
import RecordForm from '../components/entry/RecordForm.vue'
import RecentRecords from '../components/records/RecentRecords.vue'

defineProps({
  categories: { type: Object, default: null },
  refreshKey: { type: Number, default: 0 }
})

const emit = defineEmits(['saved'])
</script>

<template>
  <div class="entry-view">
    <section class="panel panel-form">
      <RecordForm :categories="categories" @saved="emit('saved', $event)" />
    </section>

    <section class="panel panel-recent">
      <RecentRecords :refresh-key="refreshKey" />
    </section>
  </div>
</template>

<style scoped>
.entry-view {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: var(--space-5);
  align-items: start;
}

.panel {
  min-width: 0;
}

@media (max-width: 860px) {
  .entry-view {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
