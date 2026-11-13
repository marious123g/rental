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

test('order asset search matches name model and code and excludes inactive stock',()=>{
 const state=app(async()=>({ok:true,status:200,json:async()=>[]}));
 state.products.value=[{id:1,name:'魔法少女',model:'粉色'},{id:2,name:'女仆',model:'Blue'}];
 state.assets.value=[{id:1,product:1,code:'AUTO-001',state:'active'},{id:2,product:2,code:'CAM-002',state:'active'},{id:3,product:1,code:'OFF-003',state:'inactive'}];
 state.editing.value={};
 for(const [keyword,id] of [['魔法',1],['粉色',1],['auto-001',1],['blue',2],['女仆 BLUE',2]]){state.assetSearch.value=keyword;assert.equal(state.matchingAssets().length,1);assert.equal(state.matchingAssets()[0].id,id);}
 state.assetSearch.value='不存在';assert.equal(state.matchingAssets().length,0);
 state.editing.value.asset=1;assert.equal(state.selectedAsset().id,1);assert.equal(state.editing.value.asset,1);
 state.assetSearch.value='';assert.equal(state.matchingAssets().length,2);
});
