/**
 * 记录展示验收：挂载真实 Vue 组件，验证 DOM、接口契约和异步竞态。
 * 使用 Node 内置测试器，无需改动 7 号 package.json 或引入完整 E2E 框架。
 */
import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { compileComponent, formatFixture, makeRecord, testDirectory } from './helpers.mjs'

// Vue runtime-dom 在导入时读取 document，因此先建立 DOM，再动态导入 Vue。
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const key of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'SVGElement', 'Event', 'MouseEvent']) {
  globalThis[key] = dom.window[key]
}
const { createApp, h, reactive, nextTick } = await import('vue')
const generated = join(testDirectory, 'node_modules/.cache/record-components')
await mkdir(generated, { recursive: true })
await writeFile(join(generated, 'format.mjs'), formatFixture)
await writeFile(join(generated, 'client.mjs'), 'export const listRecords = (params) => globalThis.__recordsApiMock(params)')
const table = await compileComponent('RecordTable', { '../../utils/format.js': './format.mjs' })
const recent = await compileComponent('RecentRecords', {
  '../../api/client.js': './client.mjs',
  './RecordTable.vue': './RecordTable.mjs',
})
await writeFile(join(generated, 'RecordTable.mjs'), table.code)
await writeFile(join(generated, 'RecentRecords.mjs'), recent.code)
const { default: RecordTable } = await import(pathToFileURL(join(generated, 'RecordTable.mjs')).href)
const { default: RecentRecords } = await import(pathToFileURL(join(generated, 'RecentRecords.mjs')).href)

const mounted = new Set()
function mount(component, initialProps = {}, slots) {
  const props = reactive({ ...initialProps })
  const root = document.createElement('div')
  document.body.append(root)
  const app = createApp({ render: () => h(component, props, slots) })
  app.mount(root)
  let disposed = false
  const wrapper = {
    root,
    async setProps(values) { Object.assign(props, values); await nextTick() },
    unmount() {
      if (disposed) return
      disposed = true
      app.unmount()
      root.remove()
      mounted.delete(wrapper)
    },
  }
  mounted.add(wrapper)
  return wrapper
}

async function settle() {
  await new Promise((resolve) => setImmediate(resolve))
  await nextTick()
}

function deferred() {
  let resolve, reject
  const promise = new Promise((accept, fail) => { resolve = accept; reject = fail })
  return { promise, resolve, reject }
}

function page(items) { return { items, total: items.length, limit: 10, offset: 0 } }
function click(element) { element.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) }

afterEach(() => {
  for (const wrapper of [...mounted]) wrapper.unmount()
  delete globalThis.__recordsApiMock
})

test('表格展示日期、收支文字、正负金额和空备注，保留服务端顺序', () => {
  const records = [
    makeRecord({ id: 'salary', type: 'income', category: '工资', amount_cents: 100000, note: '' }),
    makeRecord({ id: 'lunch' }),
  ]
  const { root } = mount(RecordTable, { records })
  const rows = root.querySelectorAll('tbody tr')
  assert.equal(rows.length, 2)
  assert.match(rows[0].textContent, /收入/)
  assert.match(rows[0].textContent, /\+1000\.00/)
  assert.match(rows[0].textContent, /—/)
  assert.match(rows[1].textContent, /支出/)
  assert.match(rows[1].textContent, /−20\.00/)
  assert.equal(root.querySelector('time').getAttribute('datetime'), '2026-11-07')
  assert.ok(table.css.includes('[data-v-records-recordtable]'))
})

test('表格不修改冻结的输入，备注 HTML 只能作为文字显示', () => {
  const note = '<img data-injected src=x onerror="alert(1)">'
  const record = Object.freeze(makeRecord({ note }))
  const records = Object.freeze([record])
  const { root } = mount(RecordTable, { records })
  assert.ok(root.textContent.includes(note))
  assert.equal(root.querySelector('[data-injected]'), null)
  assert.equal(record.note, note)
  assert.equal(records[0], record)
})

test('表格支持自定义空态和可选操作插槽，不增加内置业务副作用', () => {
  const empty = mount(RecordTable, { emptyText: '没有匹配的记录' })
  assert.match(empty.root.textContent, /没有匹配的记录/)
  assert.equal(empty.root.querySelector('tbody td').colSpan, 5)
  const { root } = mount(RecordTable, { records: [makeRecord()] }, {
    actions: ({ record }) => h('button', { type: 'button' }, '编辑' + record.category),
  })
  assert.equal(root.querySelectorAll('thead th').length, 6)
  assert.equal(root.querySelector('button').textContent, '编辑餐饮')
})

test('父页面更换 records 后表格更新，不保留内部副本', async () => {
  const wrapper = mount(RecordTable, { records: [makeRecord({ note: '旧备注' })] })
  await wrapper.setProps({ records: [makeRecord({ note: '新备注' })] })
  assert.match(wrapper.root.textContent, /新备注/)
  assert.doesNotMatch(wrapper.root.textContent, /旧备注/)
})

test('首次加载只请求 limit=10/offset=0，加载时不显示空账本', async () => {
  const request = deferred()
  const calls = []
  globalThis.__recordsApiMock = (params) => { calls.push(params); return request.promise }
  const { root } = mount(RecentRecords)
  assert.deepEqual(calls, [{ limit: 10, offset: 0 }])
  assert.match(root.querySelector('[role="status"]').textContent, /正在加载/)
  assert.doesNotMatch(root.textContent, /还没有记账记录/)
  assert.equal(root.querySelector('button').disabled, true)
  request.resolve({ ...page([makeRecord()]), total: 23 })
  await settle()
  assert.equal(root.querySelectorAll('tbody tr').length, 1)
  assert.match(root.textContent.replace(/\s+/g, ' '), /当前显示 1 条，共 23 条记录/)
})

test('合法空列表显示空账本，区别于加载和失败', async () => {
  globalThis.__recordsApiMock = async () => page([])
  const { root } = mount(RecentRecords)
  await settle()
  assert.match(root.textContent, /还没有记账记录/)
  assert.equal(root.querySelector('[role="alert"]'), null)
  assert.equal(root.querySelector('table'), null)
})

test('请求失败显示服务端错误，点击重试能够恢复', async () => {
  let calls = 0
  globalThis.__recordsApiMock = async () => {
    if (++calls === 1) throw new Error('账本暂时无法读取')
    return page([makeRecord()])
  }
  const { root } = mount(RecentRecords)
  await settle()
  assert.match(root.querySelector('[role="alert"]').textContent, /账本暂时无法读取/)
  assert.doesNotMatch(root.textContent, /还没有记账记录/)
  click(root.querySelector('[role="alert"] button'))
  await settle()
  assert.equal(calls, 2)
  assert.equal(root.querySelector('[role="alert"]'), null)
  assert.ok(root.querySelector('table'))
})

test('刷新标记触发重读，晚到的旧响应不能覆盖最新记录', async () => {
  const old = deferred(), latest = deferred()
  let calls = 0
  globalThis.__recordsApiMock = () => (++calls === 1 ? old.promise : latest.promise)
  const wrapper = mount(RecentRecords, { refreshKey: 0 })
  await wrapper.setProps({ refreshKey: 1 })
  latest.resolve(page([makeRecord({ note: '最新记录' })]))
  await settle()
  old.resolve(page([makeRecord({ note: '过时记录' })]))
  await settle()
  assert.equal(calls, 2)
  assert.match(wrapper.root.textContent, /最新记录/)
  assert.doesNotMatch(wrapper.root.textContent, /过时记录/)
})

test('旧请求完成不会提前解除新请求的 loading', async () => {
  const old = deferred(), latest = deferred()
  let calls = 0
  globalThis.__recordsApiMock = () => (++calls === 1 ? old.promise : latest.promise)
  const wrapper = mount(RecentRecords)
  await wrapper.setProps({ refreshKey: 1 })
  old.resolve(page([makeRecord()]))
  await settle()
  assert.equal(wrapper.root.querySelector('section').getAttribute('aria-busy'), 'true')
  assert.match(wrapper.root.textContent, /正在加载/)
  latest.resolve(page([]))
  await settle()
  assert.equal(wrapper.root.querySelector('section').getAttribute('aria-busy'), 'false')
})

test('旧请求失败不会覆盖已经成功的新请求', async () => {
  const old = deferred(), latest = deferred()
  let calls = 0
  globalThis.__recordsApiMock = () => (++calls === 1 ? old.promise : latest.promise)
  const wrapper = mount(RecentRecords)
  await wrapper.setProps({ refreshKey: 1 })
  latest.resolve(page([makeRecord()]))
  await settle()
  old.reject(new Error('过时错误'))
  await settle()
  assert.equal(wrapper.root.querySelector('[role="alert"]'), null)
  assert.ok(wrapper.root.querySelector('table'))
})

test('刷新失败不会把旧表格继续显示为最新结果', async () => {
  let calls = 0
  globalThis.__recordsApiMock = async () => {
    if (++calls === 2) throw new Error('刷新失败')
    return page([makeRecord()])
  }
  const wrapper = mount(RecentRecords)
  await settle()
  await wrapper.setProps({ refreshKey: 1 })
  await settle()
  assert.match(wrapper.root.textContent, /刷新失败/)
  assert.equal(wrapper.root.querySelector('table'), null)
})

test('响应违反契约时显示错误，不能悄悄当成空账本', async () => {
  globalThis.__recordsApiMock = async () => ({ data: page([]) })
  const { root } = mount(RecentRecords)
  await settle()
  assert.match(root.querySelector('[role="alert"]').textContent, /数据格式不正确/)
  assert.doesNotMatch(root.textContent, /还没有记账记录/)
})

test('卸载后完成的请求不会恢复已经移除的界面', async () => {
  const request = deferred()
  globalThis.__recordsApiMock = () => request.promise
  const wrapper = mount(RecentRecords)
  wrapper.unmount()
  request.resolve(page([makeRecord()]))
  await settle()
  assert.equal(document.body.children.length, 0)
})

test('独立预览的浏览器 DOM 模板能够实际挂载最近记录组件', async () => {
  // HTML 解析会小写化标签；验证真实 DOM 模板，避免自闭合/PascalCase 导致静默空白。
  const html = await readFile(join(testDirectory, 'preview.html'), 'utf8')
  const parsed = new JSDOM(html)
  const template = parsed.window.document.querySelector('#preview-template').innerHTML
  globalThis.__recordsApiMock = async () => page([makeRecord()])
  const Preview = {
    components: { RecentRecords },
    template,
    setup: () => ({ modes: [], mode: 'normal', refreshKey: 0, compact: false, changing: false, controlError: '' }),
  }
  const { root } = mount(Preview)
  await settle()
  assert.ok(root.querySelector('.recent-records'))
  assert.equal(root.querySelectorAll('tbody tr').length, 1)
  parsed.window.close()
})
