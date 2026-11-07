<script setup>
/**
 * 根组件：7 号维护。
 * 职责（README 9.1 / 9.3）：三页导航、类别加载、刷新协调。页面内容由各页面组件负责，
 * App 不代写子组件，也不直接拼业务数据。
 *
 * 刷新链路：RecordForm 保存成功发出 saved → EntryView 转发 → 这里 refreshKey + 1
 * → 已挂载的 RecentRecords 监听 refreshKey 重新请求。失败不递增，避免“没保存却刷新”。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getCategories, isApiError } from './api/client.js'
import EntryView from './views/EntryView.vue'
import RecordsView from './views/RecordsView.vue'
import StatisticsView from './views/StatisticsView.vue'

const PAGES = [
  { key: 'entry', label: '记一笔' },
  { key: 'records', label: '明细' },
  { key: 'statistics', label: '统计' }
]

const activePage = ref('entry')

/** 成功后递增，作为“数据已变化”的信号发给页面组件。 */
const refreshKey = ref(0)

const categories = ref(null)
const categoriesLoading = ref(false)
const categoriesError = ref('')
const categoriesErrorCode = ref('')

let toastTimer = null
const toast = ref('')

async function loadCategories() {
  categoriesLoading.value = true
  categoriesError.value = ''
  categoriesErrorCode.value = ''
  try {
    categories.value = await getCategories()
  } catch (error) {
    // 类别失败时不使用前端写死的备用类别，录入表单继续等待重试
    categories.value = null
    categoriesError.value = isApiError(error) ? error.message : '类别加载失败，请重试'
    categoriesErrorCode.value = isApiError(error) ? error.code : 'UNKNOWN'
  } finally {
    categoriesLoading.value = false
  }
}

/** 8 号 RecordForm 保存成功 → 递增刷新标记并给出全局反馈。 */
function handleSaved(record) {
  refreshKey.value += 1
  const summary = record && record.category ? `已保存：${record.category}` : '已保存'
  toast.value = summary
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.value = ''
  }, 2500)
}

function selectPage(key) {
  activePage.value = key
}

onMounted(loadCategories)

onBeforeUnmount(() => {
  if (toastTimer) clearTimeout(toastTimer)
})
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="header-inner">
        <div class="brand">
          <h1>轻账本</h1>
          <p class="hint">本地记账 · 数据保存在本机 JSON 文件</p>
        </div>

        <nav class="nav" aria-label="页面导航">
          <button
            v-for="page in PAGES"
            :key="page.key"
            type="button"
            class="nav-item"
            :class="{ 'nav-item-active': activePage === page.key }"
            :aria-current="activePage === page.key ? 'page' : undefined"
            @click="selectPage(page.key)"
          >
            {{ page.label }}
          </button>
        </nav>
      </div>
    </header>

    <div v-if="categoriesError" class="container">
      <div class="state-block state-error banner" role="alert">
        <p><strong>类别加载失败：</strong>{{ categoriesError }}</p>
        <p class="hint">错误码 {{ categoriesErrorCode }}。录入表单在类别可用前不会提交。</p>
        <button type="button" class="btn banner-retry" :disabled="categoriesLoading" @click="loadCategories">
          {{ categoriesLoading ? '正在重试…' : '重试加载类别' }}
        </button>
      </div>
    </div>

    <main class="container app-main">
      <div v-if="categoriesLoading && !categories" class="state-block state-loading">正在加载类别…</div>

      <template v-else-if="activePage === 'entry'">
        <EntryView
          :categories="categories"
          :refresh-key="refreshKey"
          @saved="handleSaved"
        />
      </template>

      <template v-else-if="activePage === 'records'">
        <RecordsView :categories="categories" :refresh-key="refreshKey" />
      </template>

      <template v-else>
        <StatisticsView :categories="categories" :refresh-key="refreshKey" />
      </template>
    </main>

    <p v-if="toast" class="toast" role="status">{{ toast }}</p>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 10;
  border-bottom: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(6px);
}

.header-inner {
  max-width: var(--content-width);
  margin: 0 auto;
  padding: var(--space-4) var(--space-5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.brand h1 {
  letter-spacing: 0.5px;
}

.nav {
  display: inline-flex;
  gap: var(--space-1);
  padding: var(--space-1);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
}

.nav-item {
  min-width: 84px;
  min-height: 36px;
  padding: 0 var(--space-4);
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-muted);
  transition: background-color 0.15s ease, color 0.15s ease;
}

.nav-item:hover {
  color: var(--color-text);
}

.nav-item:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 1px;
}

.nav-item-active {
  background: var(--color-surface);
  color: var(--color-accent-strong);
  box-shadow: var(--shadow-card);
  font-weight: 600;
}

.container {
  width: 100%;
  max-width: var(--content-width);
  margin: 0 auto;
  padding: 0 var(--space-5);
}

.app-main {
  flex: 1;
  padding-top: var(--space-5);
  padding-bottom: var(--space-6);
}

.banner {
  margin-top: var(--space-4);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.banner > p {
  flex-basis: 100%;
}

.banner-retry {
  margin-top: var(--space-1);
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 28px;
  transform: translateX(-50%);
  padding: var(--space-2) var(--space-5);
  border-radius: 999px;
  background: var(--color-text);
  color: #ffffff;
  font-size: var(--font-size-sm);
  box-shadow: var(--shadow-card);
}
</style>
