/**
 * 公共格式化自检：7 号维护。运行：npm run check
 * 只验证 utils/format.js 的纯函数，不依赖浏览器和后端。
 * 目的：证明“分 → 字符串”不经过浮点运算，0.10 与 0.20 的展示不会出现 0.30000000000000004。
 */
import { formatMoney, formatSignedMoney, todayLocalISO } from '../src/utils/format.js'

let checks = 0
const failures = []

function equal(label, actual, expected) {
  checks += 1
  if (actual === expected) {
    console.log(`PASS  ${label}`)
    return
  }
  failures.push(`${label}：期望 ${expected}，实际 ${actual}`)
  console.log(`FAIL  ${label}：期望 ${expected}，实际 ${actual}`)
}

function throws(label, fn) {
  checks += 1
  try {
    fn()
    failures.push(`${label}：应当抛出异常但返回了结果`)
    console.log(`FAIL  ${label}：应当抛出异常`)
  } catch {
    console.log(`PASS  ${label}`)
  }
}

console.log('1) formatMoney 整数分转两位小数')
equal('100000 → 1000.00', formatMoney(100000), '1000.00')
equal('2000 → 20.00', formatMoney(2000), '20.00')
equal('500 → 5.00', formatMoney(500), '5.00')
equal('10 → 0.10', formatMoney(10), '0.10')
equal('20 → 0.20', formatMoney(20), '0.20')
equal('30 → 0.30（0.10+0.20，无浮点尾差）', formatMoney(30), '0.30')
equal('97500 → 975.00', formatMoney(97500), '975.00')
equal('-2000 → -20.00（结余可为负）', formatMoney(-2000), '-20.00')
equal('5 → 0.05（补零）', formatMoney(5), '0.05')
equal('9999999999 → 99999999.99（上限）', formatMoney(9999999999), '99999999.99')
equal('0 → 0.00', formatMoney(0), '0.00')

console.log('2) 非整数分必须报错，避免悄悄四舍五入')
throws('1.5 分应抛 TypeError', () => formatMoney(1.5))
throws('字符串 "2000" 应抛 TypeError', () => formatMoney('2000'))
throws('undefined 应抛 TypeError', () => formatMoney(undefined))

console.log('3) formatSignedMoney 收支符号')
equal('收入 100000 → +1000.00', formatSignedMoney('income', 100000), '+1000.00')
equal('支出 2000 → -20.00', formatSignedMoney('expense', 2000), '-20.00')
throws('未知类型应抛 TypeError', () => formatSignedMoney('transfer', 100))

console.log('4) todayLocalISO 取本地日期，不做 UTC 截取')
equal('本地 2026-11-07 00:30 → 2026-11-07', todayLocalISO(new Date(2026, 10, 7, 0, 30)), '2026-11-07')
equal('本地 2026-11-07 23:59 → 2026-11-07', todayLocalISO(new Date(2026, 10, 7, 23, 59)), '2026-11-07')
equal('本地 2026-01-05 → 2026-01-05（补零）', todayLocalISO(new Date(2026, 0, 5, 12, 0)), '2026-01-05')

console.log('')
if (failures.length > 0) {
  console.log(`结果：${checks - failures.length}/${checks} 通过，${failures.length} 项失败`)
  for (const failure of failures) console.log(`  - ${failure}`)
  process.exit(1)
}
console.log(`结果：${checks}/${checks} 全部通过`)
