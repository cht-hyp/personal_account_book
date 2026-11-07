/** Local-only review probe. Compiles real Vue source; external API responses are controlled. */
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, join, relative, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const root=resolve(process.cwd(), '../../..')
const require=createRequire(join(root,'tests/frontend/records/package.json'))
const { JSDOM }=require('jsdom')
const { parse,compileScript }=require('@vue/compiler-sfc')
const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'http://localhost/'})
for(const key of ['window','document','Document','ShadowRoot','Node','Element','HTMLElement','SVGElement','Event','MouseEvent']) globalThis[key]=dom.window[key]
const {createApp,nextTick}=require('vue')
const cache=join(root,'tests/frontend/records/node_modules/.cache/review-671bb46')
await mkdir(cache,{recursive:true})
const client=join(cache,'client.mjs')
await writeFile(client,[
 'export class ApiError extends Error {}',
 'export const isApiError = e => e instanceof ApiError;',
 'export const getCategories = () => globalThis.__reviewApi.getCategories();',
 'export const createRecord = p => globalThis.__reviewApi.createRecord(p);',
 'export const listRecords = p => globalThis.__reviewApi.listRecords(p);',
 'export const getStatistics = p => globalThis.__reviewApi.getStatistics(p);',
].join('\n'))
const compiled=new Map()
async function compileVue(filename){
 filename=resolve(filename)
 if(compiled.has(filename)) return compiled.get(filename)
 const target=join(cache,relative(root,filename).replace(/[\\/]/g,'_')+'.mjs')
 compiled.set(filename,target)
 const {descriptor,errors}=parse(await readFile(filename,'utf8'),{filename})
 if(errors.length) throw errors[0]
 let code=compileScript(descriptor,{id:'review-'+compiled.size,inlineTemplate:true}).content
 const imports=[...code.matchAll(/\bfrom\s+(['"])([^'"]+)\1/g)]
 for(const match of imports){
   const specifier=match[2]
   if(!specifier.startsWith('.')) continue
   const source=resolve(dirname(filename),specifier)
   const destination=source===resolve(root,'frontend/src/api/client.js')?client:(source.endsWith('.vue')?await compileVue(source):source)
   code=code.replace(match[0],'from '+JSON.stringify(pathToFileURL(destination).href))
 }
 await writeFile(target,code)
 return target
}
const App=(await import(pathToFileURL(await compileVue(join(root,'frontend/src/App.vue'))).href)).default
const RecordsView=(await import(pathToFileURL(await compileVue(join(root,'frontend/src/views/RecordsView.vue'))).href)).default
async function settle(){await new Promise(resolve=>setImmediate(resolve));await nextTick()}
let finishSave
const pending=new Promise(resolve=>{finishSave=resolve})
const records=[]
let statisticsCalls=0
let createCalls=0
const categories={income:['工资'],expense:['餐饮','交通']}
globalThis.__reviewApi={
 getCategories:async()=>categories,
 listRecords:async()=>({items:[...records],total:records.length,limit:10,offset:0}),
 createRecord:()=>{createCalls+=1;return pending},
 getStatistics:async()=>{statisticsCalls+=1;return {income_cents:0,expense_cents:records.length*2000,balance_cents:-records.length*2000,count:records.length,income_count:0,expense_count:records.length,expense_by_category:records.length?[{category:'餐饮',amount_cents:records.length*2000,count:records.length}]:[]}},
}
const host=document.createElement('div');document.body.append(host)
const app=createApp(App);const warnings=[];app.config.warnHandler=message=>warnings.push(message)
app.mount(host);await settle()
const category=host.querySelector('#entry-category');assert.ok(category)
category.value='餐饮';category.dispatchEvent(new dom.window.Event('change',{bubbles:true}))
const amount=host.querySelector('#entry-amount');amount.value='20.00';amount.dispatchEvent(new dom.window.Event('input',{bubbles:true}))
host.querySelector('form').dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}));await settle()
assert.equal(createCalls,1)
const nav=[...host.querySelectorAll('nav button')].find(button=>button.textContent.trim()==='统计');assert.ok(nav)
assert.equal(nav.disabled,true, '保存期间应禁止切页')
nav.click();await settle()
assert.ok(host.querySelector('#entry-amount'), '保存期间表单必须保持挂载')
const record={id:'11111111-1111-4111-8111-111111111111',date:'2026-11-07',type:'expense',amount_cents:2000,category:'餐饮',note:'review',created_at:'2026-11-07T06:30:00.000+00:00'}
records.push(record);finishSave(record);await settle()
assert.equal(nav.disabled,false, '保存完成后恢复导航')
assert.ok(host.textContent.includes('已保存'), '保存成功通知应到达 App')
nav.click();await settle()
const count=[...host.querySelectorAll('.stat')].find(node=>node.querySelector('dt')?.textContent.trim()==='记录数')
assert.equal(count?.querySelector('dd')?.textContent.trim(),'1')
app.unmount();host.remove()

globalThis.__reviewApi.listRecords=async()=>({})
const secondHost=document.createElement('div');document.body.append(secondHost)
const second=createApp(RecordsView,{categories});second.mount(secondHost);await settle()
const malformedResponse={emptyLedgerShown:secondHost.textContent.includes('账本还是空的'),errorShown:secondHost.textContent.includes('记录加载失败')}
assert.equal(malformedResponse.emptyLedgerShown,false);assert.equal(malformedResponse.errorShown,true)
second.unmount();secondHost.remove()
console.log('PASS 保存期间阻止切页；保存后刷新；异常响应显示错误')
dom.window.close()
