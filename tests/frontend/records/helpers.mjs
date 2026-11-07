/**
 * 独立验证工具：编译真实 Vue 组件，仅在验证环境替换尚未交付的 7 号依赖。
 * 替换不会写入生产源码，后续正式项目仍直接导入公共客户端和格式化函数。
 */
import { readFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { compileScript, compileStyle, parse } from '@vue/compiler-sfc'

export const testDirectory = dirname(fileURLToPath(import.meta.url))
export const projectDirectory = resolve(testDirectory, '../../..')

export async function compileComponent(name, imports = {}) {
  const filename = resolve(projectDirectory, 'frontend/src/components/records', name + '.vue')
  const source = await readFile(filename, 'utf8')
  const { descriptor, errors } = parse(source, { filename })
  if (errors.length) throw errors[0]
  const id = 'records-' + name.toLowerCase()
  const compiled = compileScript(descriptor, {
    id,
    inlineTemplate: true,
    templateOptions: { compilerOptions: { scopeId: 'data-v-' + id } },
  })

  let code = compiled.content.replace('export default', 'const component =')
  for (const [from, to] of Object.entries(imports)) {
    code = code.replaceAll(JSON.stringify(from), JSON.stringify(to))
    code = code.replaceAll("'" + from + "'", JSON.stringify(to))
  }
  code += '\ncomponent.__scopeId = ' + JSON.stringify('data-v-' + id) + ';\nexport default component;\n'

  const css = descriptor.styles.map((style) => {
    const result = compileStyle({ source: style.content, filename, id: 'data-v-' + id, scoped: style.scoped })
    if (result.errors.length) throw result.errors[0]
    return result.code
  }).join('\n')

  return { code, css }
}

// 仅用于测试/预览的公共格式化替身；真实公共实现由 7 号负责。
export const formatFixture = 'export function formatMoney(cents) { return (cents / 100).toFixed(2) }'

export function makeRecord(overrides = {}) {
  return {
    id: '11111111-1111-4111-8111-111111111111',
    date: '2026-11-07',
    type: 'expense',
    amount_cents: 2000,
    category: '餐饮',
    note: '午餐',
    created_at: '2026-11-07T06:30:00.000+00:00',
    ...overrides,
  }
}
