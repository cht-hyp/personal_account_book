/**
 * 统一 API 客户端：7 号维护。页面与组件只通过这里访问后端，不各自写 fetch。
 *
 * 约定（README 9.4）：
 * - 统一 `/api` 前缀；开发期由 Vite 代理转发到 Flask，交付期由 Flask 同源提供。
 * - 成功时只返回响应体里的 `data`，调用方不再手动取第二层。
 * - 失败统一抛出 ApiError，携带 code、message、fields；网络不可达用 NETWORK_ERROR。
 * - 空查询项不发送；数值 0 必须原样发送（0 是合法边界，不能被当成“未填写”）。
 * - POST 不自动重试：网络状态不明时重试会造成重复记账。
 */

// 构建期可通过 VITE_API_BASE 指向其他前缀；默认 /api。
const rawBase = import.meta.env && import.meta.env.VITE_API_BASE
export const API_BASE = rawBase ? String(rawBase).replace(/\/+$/, '') : '/api'

/** 六个业务筛选参数，/api/records 与 /api/statistics 共用。 */
const FILTER_KEYS = ['start_date', 'end_date', 'type', 'category', 'min_amount', 'max_amount']

/** /api/records 额外接受分页参数。 */
const LIST_KEYS = [...FILTER_KEYS, 'limit', 'offset']

/** POST /api/records 允许提交的字段；id、amount_cents、created_at 一律由后端生成。 */
const CREATE_KEYS = ['date', 'type', 'amount', 'category', 'note']

export class ApiError extends Error {
  /**
   * @param {string} code 后端错误码或客户端兜底码
   * @param {string} message 面向用户的可读信息
   * @param {Record<string, string>} [fields] 字段级错误，键为字段名
   * @param {number} [status] HTTP 状态码，网络错误为 0
   */
  constructor(code, message, fields = {}, status = 0) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.fields = fields || {}
    this.status = status
  }
}

/** 判断是否为统一 API 错误，供组件区分“请求失败”与其他异常。 */
export function isApiError(error) {
  return error instanceof ApiError
}

/**
 * 按白名单把参数拼成查询字符串。
 * 规则：只取白名单内的键；undefined、null、空字符串视为未填写而跳过；
 * 数字 0 与字符串 "0" 都保留（金额下限可以是 0）。
 * @param {Record<string, unknown>} params
 * @param {string[]} allowedKeys
 * @returns {string}
 */
function buildQuery(params, allowedKeys) {
  const search = new URLSearchParams()
  for (const key of allowedKeys) {
    const value = params ? params[key] : undefined
    if (value === undefined || value === null) continue
    if (typeof value === 'string' && value.trim() === '') continue
    search.append(key, String(value))
  }
  return search.toString()
}

/**
 * 发一次请求并把响应解包成 data。
 * @param {string} path 以 / 开头的接口路径，不含 /api 前缀
 * @param {{ method?: string, query?: string, body?: unknown }} options
 * @returns {Promise<any>}
 */
async function request(path, { method = 'GET', query = '', body } = {}) {
  const url = `${API_BASE}${path}${query ? `?${query}` : ''}`
  const init = {
    method,
    headers: { Accept: 'application/json' }
  }
  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(body)
  }

  let response
  try {
    response = await fetch(url, init)
  } catch (cause) {
    // fetch 抛错只代表网络层失败（服务没启动、连接被拒），与业务错误分开报告
    throw new ApiError('NETWORK_ERROR', '无法连接本地服务，请确认后端已启动后重试', {}, 0)
  }

  let payload = null
  try {
    payload = await response.json()
  } catch (cause) {
    payload = null
  }

  if (!response.ok) {
    const errorBody = payload && payload.error ? payload.error : {}
    const code = errorBody.code || fallbackCode(response.status)
    const message = errorBody.message || fallbackMessage(response.status)
    throw new ApiError(code, message, errorBody.fields || {}, response.status)
  }

  if (!payload || !Object.prototype.hasOwnProperty.call(payload, 'data')) {
    // 成功状态码但响应结构不符合契约，同样不能当成有效数据
    throw new ApiError('INVALID_RESPONSE', '服务返回的数据格式不符合约定', {}, response.status)
  }
  return payload.data
}

function fallbackCode(status) {
  const map = {
    400: 'VALIDATION_ERROR',
    404: 'NOT_FOUND',
    405: 'METHOD_NOT_ALLOWED',
    415: 'UNSUPPORTED_MEDIA_TYPE',
    500: 'INTERNAL_ERROR'
  }
  return map[status] || 'INTERNAL_ERROR'
}

function fallbackMessage(status) {
  return status >= 500 ? '本地服务处理失败，请稍后重试' : '请求未被服务接受'
}

/** 获取收入与支出类别。形状：{ income: string[], expense: string[] }。 */
export function getCategories() {
  return request('/categories')
}

/**
 * 新增一条记录。只提交契约允许的字段；金额必须是字符串（"20"、"20.5"、"20.50"）。
 * 不重试、不兜底：失败直接抛 ApiError，由 RecordForm 保留输入并提示。
 * @param {{ date: string, type: 'income'|'expense', amount: string, category: string, note?: string }} payload
 * @returns {Promise<Record>}
 */
export function createRecord(payload) {
  if (!payload || typeof payload !== 'object') {
    throw new TypeError('createRecord 需要一个对象参数')
  }
  if (typeof payload.amount !== 'string') {
    // 挡住 parseFloat 后传数值的写法：金额字符串是契约，转换由后端 Decimal 完成
    throw new TypeError('amount 必须是字符串，例如 "20.50"')
  }
  const body = {}
  for (const key of CREATE_KEYS) {
    const value = payload[key]
    if (value === undefined || value === null) continue
    body[key] = value
  }
  return request('/records', { method: 'POST', body })
}

/**
 * 查询记录列表，支持六个筛选条件与 limit/offset。
 * @param {Record<string, unknown>} [params]
 * @returns {Promise<{ items: Record[], total: number, limit: number, offset: number }>}
 */
export function listRecords(params = {}) {
  return request('/records', { query: buildQuery(params, LIST_KEYS) })
}

/**
 * 查询统计。只接受六个业务筛选参数，不接受 limit/offset（统计针对全部匹配记录）。
 * @param {Record<string, unknown>} [filters]
 * @returns {Promise<{ income_cents: number, expense_cents: number, balance_cents: number, count: number, income_count: number, expense_count: number, expense_by_category: Array<{ category: string, amount_cents: number, count: number }> }>}
 */
export function getStatistics(filters = {}) {
  return request('/statistics', { query: buildQuery(filters, FILTER_KEYS) })
}
