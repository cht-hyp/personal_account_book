<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { createRecord } from '../../api/client.js'
import { formatMoney, todayLocalISO } from '../../utils/format.js'

// README 9.2：类别由 App 通过 props 注入，表单不自行请求，也不内置备用类别。
const props = defineProps({
  categories: { type: Object, default: null }
})

// README 9.3：仅持久化成功后发出 saved(record)，由 EntryView 转发给 App 增加 refreshKey。
const emit = defineEmits(['saved', 'saving'])

const MAX_NOTE_LENGTH = 200
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/
// 只做提交前的结构预检；范围、类别合法性等权威规则由后端 validate_record_payload 负责。
const AMOUNT_PATTERN = /^\d+(?:\.\d{1,2})?$/

// 默认日期复用 7 号的公共函数（浏览器本地年月日），不重复实现业务日期规则。
const form = reactive({
  date: todayLocalISO(),
  type: 'expense',
  amount: '',
  category: '',
  note: ''
})

const submitting = ref(false)
const fieldErrors = ref({})
const errorMessage = ref('')
const successMessage = ref('')

const categoryOptions = computed(() => {
  const list = props.categories?.[form.type]
  return Array.isArray(list) ? list : []
})
const categoriesReady = computed(() => categoryOptions.value.length > 0)
const canSubmit = computed(() => !submitting.value && categoriesReady.value)

function clearFieldError(field) {
  if (!fieldErrors.value[field]) return
  const next = { ...fieldErrors.value }
  delete next[field]
  fieldErrors.value = next
}

// 切换收支类型后，原类别不属于新类型时清空；不修改 props 本身。
watch(
  () => form.type,
  () => {
    if (form.category && !categoryOptions.value.includes(form.category)) {
      form.category = ''
    }
    clearFieldError('category')
  }
)

function validate() {
  const errors = {}
  const amount = form.amount.trim()

  if (!DATE_PATTERN.test(form.date)) errors.date = '请选择有效日期'
  if (form.type !== 'income' && form.type !== 'expense') errors.type = '请选择收入或支出'
  if (!amount) {
    errors.amount = '请输入金额'
  } else if (!AMOUNT_PATTERN.test(amount)) {
    errors.amount = '金额需为普通十进制，最多两位小数，不含符号与千分位'
  } else if (Number(amount) <= 0) {
    // Number 只用于预检零值，不作为业务金额；整数分一律由后端 Decimal 转换。
    errors.amount = '金额必须大于 0'
  }
  if (!form.category) {
    errors.category = '请选择类别'
  } else if (!categoryOptions.value.includes(form.category)) {
    errors.category = '类别与当前收支类型不匹配'
  }
  if (form.note.length > MAX_NOTE_LENGTH) {
    errors.note = `备注最多 ${MAX_NOTE_LENGTH} 个字符`
  }
  return errors
}

async function handleSubmit() {
  // 状态锁：保存期间的连点不会发出第二次 POST；client.js 也不会自动重试。
  if (submitting.value) return
  successMessage.value = ''
  errorMessage.value = ''

  const errors = validate()
  fieldErrors.value = errors
  if (Object.keys(errors).length > 0) return

  if (!categoriesReady.value) {
    errorMessage.value = '类别尚未加载成功，请通过页面的类别重试入口恢复后再录入'
    return
  }

  // 金额保持原始字符串提交，不 parseFloat、不乘 100（README 6.2 / 10.3）。
  // 未知字段一律不发送，尤其不发送 id、amount_cents、created_at。
  const payload = {
    date: form.date,
    type: form.type,
    amount: form.amount.trim(),
    category: form.category,
    note: form.note.trim()
  }

  submitting.value = true
  emit('saving', true)
  try {
    const record = await createRecord(payload)
    const cents = record?.amount_cents
    const formatted = typeof cents === 'number' ? formatMoney(cents) : ''
    successMessage.value = formatted
      ? `已保存：${payload.type === 'income' ? '收入' : '支出'} · ${payload.category} ${formatted} 元`
      : `已保存：${payload.type === 'income' ? '收入' : '支出'} · ${payload.category}`

    // 仅清空金额与备注，保留日期、类型和类别便于连续录入；失败时保留全部输入。
    form.amount = ''
    form.note = ''
    fieldErrors.value = {}
    emit('saved', record)
  } catch (err) {
    // ApiError 携带 code / message / fields；网络故障使用 NETWORK_ERROR。
    const fields = err?.fields && typeof err.fields === 'object' ? err.fields : {}
    fieldErrors.value = { ...fields }
    errorMessage.value = err?.code === 'NETWORK_ERROR'
      ? '无法连接服务，请确认后端已启动后重试'
      : (err?.message || '保存失败，请稍后重试')
    // 失败不 emit saved，不增加刷新标记，不清空表单。
  } finally {
    submitting.value = false
    emit('saving', false)
  }
}
</script>

<template>
  <form class="record-form" novalidate @submit.prevent="handleSubmit">
    <h2 class="record-form__title">记一笔</h2>

    <fieldset class="record-form__group">
      <legend>收支类型 <span class="record-form__required" aria-hidden="true">*</span></legend>
      <div class="record-form__types">
        <label class="record-form__type">
          <input v-model="form.type" type="radio" name="record-type" value="expense" :disabled="submitting" />
          <span>支出</span>
        </label>
        <label class="record-form__type">
          <input v-model="form.type" type="radio" name="record-type" value="income" :disabled="submitting" />
          <span>收入</span>
        </label>
      </div>
      <p v-if="fieldErrors.type" class="record-form__field-error">{{ fieldErrors.type }}</p>
    </fieldset>

    <div class="record-form__field">
      <label for="entry-date">日期 <span class="record-form__required" aria-hidden="true">*</span></label>
      <input
        id="entry-date"
        v-model="form.date"
        type="date"
        required
        :disabled="submitting"
        :aria-invalid="Boolean(fieldErrors.date)"
        @input="clearFieldError('date')"
      />
      <p v-if="fieldErrors.date" class="record-form__field-error">{{ fieldErrors.date }}</p>
    </div>

    <div class="record-form__field">
      <label for="entry-category">类别 <span class="record-form__required" aria-hidden="true">*</span></label>
      <select
        id="entry-category"
        v-model="form.category"
        required
        :disabled="submitting || !categoriesReady"
        :aria-invalid="Boolean(fieldErrors.category)"
        @change="clearFieldError('category')"
      >
        <option value="" disabled>请选择类别</option>
        <option v-for="name in categoryOptions" :key="name" :value="name">{{ name }}</option>
      </select>
      <p v-if="!categoriesReady" class="record-form__hint record-form__hint--warn">
        类别未加载成功，请使用页面提供的重试入口恢复，表单不会使用内置类别提交。
      </p>
      <p v-if="fieldErrors.category" class="record-form__field-error">{{ fieldErrors.category }}</p>
    </div>

    <div class="record-form__field">
      <label for="entry-amount">金额（元） <span class="record-form__required" aria-hidden="true">*</span></label>
      <input
        id="entry-amount"
        v-model="form.amount"
        type="text"
        inputmode="decimal"
        autocomplete="off"
        placeholder="例如 20.50"
        required
        :disabled="submitting"
        :aria-invalid="Boolean(fieldErrors.amount)"
        @input="clearFieldError('amount')"
      />
      <p class="record-form__hint">可填 20、20.5、20.50；不要输入货币符号、千分位或三位以上小数。</p>
      <p v-if="fieldErrors.amount" class="record-form__field-error">{{ fieldErrors.amount }}</p>
    </div>

    <div class="record-form__field">
      <label for="entry-note">备注（可选）</label>
      <input
        id="entry-note"
        v-model="form.note"
        type="text"
        autocomplete="off"
        placeholder="补充说明"
        :maxlength="MAX_NOTE_LENGTH"
        :disabled="submitting"
        :aria-invalid="Boolean(fieldErrors.note)"
        @input="clearFieldError('note')"
      />
      <p class="record-form__hint">{{ form.note.length }} / {{ MAX_NOTE_LENGTH }}</p>
      <p v-if="fieldErrors.note" class="record-form__field-error">{{ fieldErrors.note }}</p>
    </div>

    <div class="record-form__actions">
      <button class="record-form__submit" type="submit" :disabled="!canSubmit">
        {{ submitting ? '保存中…' : '保存记录' }}
      </button>
      <span v-if="submitting" class="record-form__hint">正在写入，请勿重复提交</span>
    </div>

    <p v-if="errorMessage" class="record-form__message record-form__message--error" role="alert">
      {{ errorMessage }}
    </p>
    <p v-if="successMessage" class="record-form__message record-form__message--success" role="status" aria-live="polite">
      {{ successMessage }}
    </p>
  </form>
</template>

<style scoped>
/* 公共变量由 7 号 base.css 维护；组件只补充自身布局细节。 */
.record-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-text);
  box-shadow: var(--shadow-card);
  font: inherit;
}

.record-form__title {
  margin: 0;
  font-size: var(--font-size-lg);
}

.record-form__group {
  margin: 0;
  padding: 0;
  border: 0;
}

.record-form__group legend,
.record-form__field label {
  display: block;
  margin-bottom: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.record-form__required {
  color: var(--color-danger);
}

.record-form__types {
  display: flex;
  gap: var(--space-3);
}

.record-form__type {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.record-form__field input,
.record-form__field select {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: inherit;
  font: inherit;
}

.record-form__field input:focus-visible,
.record-form__field select:focus-visible,
.record-form__submit:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 1px;
}

.record-form__field input[aria-invalid='true'],
.record-form__field select[aria-invalid='true'] {
  border-color: var(--color-danger);
}

.record-form__hint,
.record-form__field-error {
  margin: 5px 0 0;
  font-size: var(--font-size-sm);
}

.record-form__hint {
  color: var(--color-muted);
}

.record-form__hint--warn,
.record-form__field-error {
  color: var(--color-danger);
}

.record-form__actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.record-form__submit {
  padding: 9px 20px;
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  color: #ffffff;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.record-form__submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.record-form__message {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
}

.record-form__message--error {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

.record-form__message--success {
  background: var(--color-accent-soft);
  color: var(--color-accent-strong);
}
</style>
