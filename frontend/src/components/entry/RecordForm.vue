<script setup>
/**
 * 【占位骨架】本文件属于 8 号（记账表单），由 7 号在骨架期提供最小可运行外壳。
 * 交付前必须由 8 号替换为真实实现：日期、收支类型、金额字符串、动态类别、备注、
 * 保存中/失败状态、防重复提交、保存成功发出 saved(record)。
 * 当前外壳只提供“发出 saved”的联调按钮，不代表表单已完成，也不做任何真实提交。
 */
import { formatMoney, todayLocalISO } from '../../utils/format.js'

const props = defineProps({
  categories: { type: Object, default: null }
})
const emit = defineEmits(['saved'])

const canEmit = () => Boolean(props.categories && props.categories.expense)

function emitMockSaved() {
  // 仅用于验证 7 号的刷新链路：saved → refreshKey → 最近记录重新请求
  emit('saved', {
    id: 'placeholder-mock',
    date: todayLocalISO(),
    type: 'expense',
    amount_cents: 100,
    category: props.categories.expense[0],
    note: '骨架占位数据，非真实保存'
  })
}
</script>

<template>
  <div class="card">
    <h2>记一笔</h2>
    <p class="hint">8 号实现中：录入表单、字段校验提示、保存中与失败状态。</p>

    <div class="placeholder">
      <p>骨架期不提供真实录入。类别可用后，可用下面的按钮验证“保存成功后相关页面刷新”。</p>
      <p v-if="categories" class="hint">
        已从后端取得类别：收入 {{ categories.income.length }} 类、支出 {{ categories.expense.length }} 类；
        金额示例格式 {{ formatMoney(2000) }} 元。
      </p>
      <p v-else class="field-error">类别尚未可用，骨架按钮已禁用。</p>
      <button type="button" class="btn btn-primary" :disabled="!canEmit()" @click="emitMockSaved">
        模拟保存成功（仅骨架联调）
      </button>
    </div>
  </div>
</template>

<style scoped>
.placeholder {
  margin-top: var(--space-4);
  padding: var(--space-4);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-sm);
  background: #fbfcfd;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  align-items: flex-start;
}
</style>
