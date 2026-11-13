import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {compile} from '@vue/compiler-dom';
const source=fs.readFileSync(new URL('./src.js',import.meta.url),'utf8');
function app(fetch){let state;vm.runInNewContext(source.replace(/^import .*;$/gm,''),{ref:value=>({value}),onMounted:()=>{},nextTick:async()=>{},createApp:options=>({mount:()=>{state=options.setup();}}),fetch,document:{querySelector:()=>({value:'csrf'})},URLSearchParams,Date,confirm:()=>true});return state;}
test('Vue template compiles',()=>{compile(source.match(/template:`([\s\S]*)`\}\)\.mount/)[1]);});
test('old rows clear during loading and new rows appear on completion',async()=>{let release;const gate=new Promise(resolve=>{release=resolve;});const state=app(async path=>{await gate;return {ok:true,status:200,json:async()=>path.includes('orders')?[{id:2}]:[]};});state.rows.value=[{id:1}];const pending=state.load();assert.equal(state.loading.value,true);assert.equal(state.rows.value.length,0);release();await pending;assert.equal(state.loading.value,false);assert.equal(state.rows.value[0].id,2);});
test('failure clears stale rows and exits loading state',async()=>{const state=app(async()=>{throw new Error('offline');});state.rows.value=[{id:1}];await state.load();assert.equal(state.rows.value.length,0);assert.equal(state.loading.value,false);assert.equal(state.error.value,'offline');});
test('availability tab does not retain order rows',async()=>{const state=app(async()=>({ok:true,status:200,json:async()=>[]}));state.rows.value=[{id:1}];state.tab.value='availability';await state.load();assert.equal(state.rows.value.length,0);assert.equal(state.searched.value,false);assert.equal(state.loading.value,false);});
