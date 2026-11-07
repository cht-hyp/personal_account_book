/**
 * 公共格式化工具：7 号维护。
 *
 * 金额的唯一来源是后端返回的整数分（*_cents）。前端只做“分 → 两位小数字符串”的显示，
 * 不用浮点数参与任何运算：0.1 + 0.2 的经典误差会让展示金额和统计结果对不上。
 * 界面需要正负号或颜色时，再在上层根据 type 决定，格式化函数本身不带符号。
 */

const pad2 = (value) => String(value).padStart(2, '0')

/**
 * 把整数分格式化为两位小数的金额字符串，例如 100000 → "1000.00"、-2000 → "-20.00"。
 * 直接按整数拆分元/角/分，不经过 Number 浮点运算。
 * @param {number} cents 整数分，允许负数（结余可以为负）
 * @returns {string}
 */
export function formatMoney(cents) {
  if (!Number.isInteger(cents)) {
    throw new TypeError(`formatMoney 只接受整数分，收到：${String(cents)}`)
  }
  const sign = cents < 0 ? '-' : ''
  const abs = Math.abs(cents)
  const yuan = Math.floor(abs / 100)
  const fen = abs % 100
  return `${sign}${yuan}.${pad2(fen)}`
}

/**
 * 按收支类型给出带符号的金额字符串，供列表和统计卡片显示：
 * 收入 "+1000.00"，支出 "-20.00"。颜色由使用它的组件决定。
 * @param {'income'|'expense'} type
 * @param {number} cents 正整数分
 * @returns {string}
 */
export function formatSignedMoney(type, cents) {
  if (type === 'income') return `+${formatMoney(cents)}`
  if (type === 'expense') return `-${formatMoney(cents)}`
  throw new TypeError(`未知收支类型：${String(type)}`)
}

/**
 * 浏览器本地“今天”的 YYYY-MM-DD，作为表单默认日期。
 * 不能用 toISOString().slice(0, 10)：那是 UTC 日期，东八区 00:00—08:00 会显示成前一天。
 * @param {Date} [now]
 * @returns {string}
 */
export function todayLocalISO(now = new Date()) {
  return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`
}

/**
 * 页面上统一的中文日期显示，YYYY-MM-DD → 2026-11-07 原样返回。
 * 保留独立函数是为了以后调整显示格式时只改一处。
 * @param {string} isoDate
 * @returns {string}
 */
export function formatDate(isoDate) {
  return typeof isoDate === 'string' ? isoDate : ''
}
