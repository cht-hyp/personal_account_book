<script setup>
/**
 * 最近记录模块：通过公共客户端获取最近十笔记录，再交给 RecordTable 展示。
 * 父页面只需在新增成功后修改 refreshKey；组件不操作账本或其他页面。
 */
import { onBeforeUnmount, ref, watch } from 'vue'
import { listRecords } from '../../api/client.js'
import RecordTable from './RecordTable.vue'

const props = defineProps({
  refreshKey: { type: [Number, String], default: 0 },
})

const records = ref([])
const total = ref(0)
const loading = ref(true)
const error = ref('')
let latestRequestId = 0

/**
 * 每次刷新领取新序号，只有最新请求能提交结果、错误和 loading 状态。
 * 场景：旧请求 A 较慢，新增后发起 B；即使 A 最后返回，也不能覆盖 B。
 * 请求失败时单独显示错误，而不是把失败伪装成“空账本”。
 */
async function loadRecords() {
  const requestId = ++latestRequestId
  loading.value = true
  error.value = ''

  try {
    // API 客户端已经解包 data；排序由查询模块负责，组件保留接口顺序。
    const page = await listRecords({ limit: 10, offset: 0 })
    if (requestId !== latestRequestId) return

    // 契约异常需要可见地失败，不能用 page.items || [] 隐藏联调问题。
    if (!Array.isArray(page?.items) || !Number.isInteger(page.total) || page.total < page.items.length) {
      throw new Error('记录数据格式不正确，请重试或联系维护者。')
    }

    records.value = page.items
    total.value = page.total
  } catch (cause) {
    if (requestId !== latestRequestId) return
    records.value = []
    total.value = 0
    error.value = cause?.message || '读取记录失败，请稍后重试。'
  } finally {
    // 旧请求结束不能提前解除新请求的加载状态。
    if (requestId === latestRequestId) loading.value = false
  }
}

// immediate 完成首次加载；后续仅在父组件的刷新标记变化时重新获取。
watch(() => props.refreshKey, loadRecords, { immediate: true })

// 页面离开后使尚未完成的请求失效，避免已卸载组件继续提交结果。
onBeforeUnmount(() => { latestRequestId += 1 })
</script>

<template>
  <section class="recent-records" aria-label="最近记账记录" :aria-busy="loading">
    <header class="recent-records-header">
      <div>
        <h2>最近记录</h2>
        <p>按记账日期倒序，显示最近 10 笔收支</p>
      </div>
      <button class="records-refresh" type="button" :disabled="loading" @click="loadRecords">
        {{ loading ? '加载中…' : '刷新记录' }}
      </button>
    </header>

    <div v-if="loading" class="records-state" role="status" aria-live="polite">
      <span class="records-loading-dot" aria-hidden="true" />
      <p>正在加载记录…</p>
    </div>
    <div v-else-if="error" class="records-state records-state--error" role="alert">
      <h3>记录加载失败</h3>
      <p>{{ error }}</p>
      <button class="records-refresh" type="button" @click="loadRecords">重试</button>
    </div>
    <div v-else-if="records.length === 0" class="records-state" role="status">
      <h3>还没有记账记录</h3>
      <p>保存第一笔收入或支出后，会在这里显示。</p>
    </div>
    <template v-else>
      <RecordTable :records="records" />
      <p class="recent-records-count" aria-live="polite">
        当前显示 {{ records.length }} 条，共 {{ total }} 条记录
      </p>
    </template>
  </section>
</template>

<style scoped>
.recent-records {
  padding: 24px;
  border: 1px solid var(--border-color, #e3e8e7);
  border-radius: 18px;
  background: var(--surface-color, #fff);
  color: var(--text-primary, #263c35);
}

.recent-records-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 22px;
}

.recent-records-header h2 {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 650;
}

.recent-records-header p,
.recent-records-count {
  margin: 0;
  color: var(--text-secondary, #667770);
  font-size: 13px;
  line-height: 1.6;
}

.records-refresh {
  flex-shrink: 0;
  padding: 9px 14px;
  border: 1px solid var(--border-color, #d5dfda);
  border-radius: 9px;
  background: var(--surface-color, #fff);
  color: var(--text-primary, #263c35);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.records-refresh:hover:not(:disabled) { background: #f0f7f3; }
.records-refresh:disabled { cursor: wait; opacity: 0.6; }
.records-refresh:focus-visible { outline: 3px solid #88c5b4; outline-offset: 2px; }

.records-state {
  display: flex;
  min-height: 220px;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 24px;
  border: 1px dashed var(--border-color, #d5dfda);
  border-radius: 12px;
  background: var(--surface-muted, #f8faf9);
  text-align: center;
}

.records-state h3 { margin: 0 0 10px; font-size: 16px; font-weight: 600; }
.records-state p { margin: 0; color: var(--text-secondary, #667770); font-size: 14px; line-height: 1.8; overflow-wrap: anywhere; }
.records-state--error { border-color: #e7cabb; background: #fffaf7; }
.records-state--error .records-refresh { margin-top: 18px; }
.records-loading-dot { width: 10px; height: 10px; margin-bottom: 14px; border-radius: 50%; background: #3a8b69; }
.recent-records-count { margin-top: 14px; text-align: right; }

@media (max-width: 600px) {
  .recent-records { padding: 16px; border-radius: 12px; }
  .recent-records-header { align-items: flex-start; }
  .recent-records-header h2 { font-size: 18px; }
  .recent-records-header p { max-width: 200px; }
}
</style>
