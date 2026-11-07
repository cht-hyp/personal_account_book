/**
 * 9 号模块独立预览服务器：编译真实组件，提供显式标记的内存样例接口。
 * 不读取或写入 data/，不创建生产 api/client.js，不替代 4/7 号实现。
 */
import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { compileComponent, formatFixture, makeRecord, testDirectory } from './helpers.mjs'

const table = await compileComponent('RecordTable', {
  vue: '/vendor/vue.js', '../../utils/format.js': '/fixtures/format.js',
})
const recent = await compileComponent('RecentRecords', {
  vue: '/vendor/vue.js',
  '../../api/client.js': '/fixtures/client.js',
  './RecordTable.vue': '/components/RecordTable.js',
})
const html = await readFile(resolve(testDirectory, 'preview.html'), 'utf8')
const vue = await readFile(resolve(testDirectory, 'node_modules/vue/dist/vue.esm-browser.prod.js'), 'utf8')
const samples = Array.from({ length: 12 }, (_, index) => makeRecord({
  id: 'sample-' + index,
  date: new Date(Date.UTC(2026, 10, 7 - index)).toISOString().slice(0, 10),
  type: index === 1 ? 'income' : 'expense',
  category: index === 1 ? '工资' : ['餐饮', '交通', '学习'][index % 3],
  amount_cents: index === 1 ? 100000 : 2000 + index * 150,
  note: index === 0 ? '午餐 · 日常生活' : (index === 2 ? '' : '样例记录 ' + (index + 1)),
}))
let mode = 'normal'

function send(response, status, body, type = 'application/json') {
  response.writeHead(status, { 'Content-Type': type + '; charset=utf-8', 'Cache-Control': 'no-store' })
  response.end(type === 'application/json' ? JSON.stringify(body) : body)
}

const client = [
  'export async function listRecords(params) {',
  '  const response = await fetch("/api/records?" + new URLSearchParams(params));',
  '  const body = await response.json();',
  '  if (!response.ok) throw new Error(body.error.message);',
  '  return body.data;',
  '}',
].join('\n')

const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, 'http://127.0.0.1:5179')
    if (request.method === 'POST' && url.pathname === '/__preview/mode') {
      const next = url.searchParams.get('mode')
      if (!['normal', 'empty', 'error', 'added'].includes(next)) {
        return send(response, 400, { error: { message: '未知预览状态' } })
      }
      mode = next
      return send(response, 200, { data: { mode } })
    }
    if (request.method !== 'GET') return send(response, 405, { error: { message: '不支持该方法' } })
    if (url.pathname === '/') return send(response, 200, html, 'text/html')
    if (url.pathname === '/vendor/vue.js') return send(response, 200, vue, 'text/javascript')
    if (url.pathname === '/components/RecordTable.js') return send(response, 200, table.code, 'text/javascript')
    if (url.pathname === '/components/RecentRecords.js') return send(response, 200, recent.code, 'text/javascript')
    if (url.pathname === '/fixtures/format.js') return send(response, 200, formatFixture, 'text/javascript')
    if (url.pathname === '/fixtures/client.js') return send(response, 200, client, 'text/javascript')
    if (url.pathname === '/components.css') return send(response, 200, table.css + '\n' + recent.css, 'text/css')
    if (url.pathname === '/favicon.ico') { response.writeHead(204); return response.end() }
    if (url.pathname === '/api/records') {
      if (mode === 'error') return send(response, 500, { error: { code: 'STORAGE_ERROR', message: '样例：账本暂时无法读取，请点击重试或切换正常数据。', fields: {} } })
      let items = mode === 'empty' ? [] : samples
      if (mode === 'added') items = [makeRecord({ id: 'new-sample', amount_cents: 1250, note: '新增记录：保存后刷新' }), ...samples]
      const limit = Number(url.searchParams.get('limit') || 20)
      const offset = Number(url.searchParams.get('offset') || 0)
      if (!Number.isInteger(limit) || limit < 1 || limit > 100 || !Number.isInteger(offset) || offset < 0) {
        return send(response, 400, { error: { message: '分页参数不合法' } })
      }
      return send(response, 200, { data: { items: items.slice(offset, offset + limit), total: items.length, limit, offset } })
    }
    return send(response, 404, { error: { message: '预览资源不存在' } })
  } catch (error) {
    console.error(error)
    send(response, 500, { error: { message: '预览服务器错误' } })
  }
})

server.on('error', (error) => {
  console.error(error.code === 'EADDRINUSE' ? '5179 端口已占用，请关闭已有预览后重试。' : error)
  process.exitCode = 1
})
server.listen(5179, '127.0.0.1', () => console.log('记录展示模块预览：http://127.0.0.1:5179（内存样例，不保存账本；Ctrl+C 停止）'))
