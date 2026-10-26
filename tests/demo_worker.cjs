'use strict';
const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const site=path.resolve(process.argv[2]||path.join(__dirname,'../build/open-source-demo'));
let complete,id=0;
const sandbox={console,Map,Set,Promise,URLSearchParams,setTimeout,clearTimeout,
 fetch:async url=>({ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(site,url),'utf8'))}),
 postMessage:message=>complete(message)};
sandbox.self=sandbox;
const context=vm.createContext(sandbox);
sandbox.importScripts=(...names)=>names.forEach(name=>vm.runInContext(fs.readFileSync(path.join(site,name),'utf8'),context));
vm.runInContext(fs.readFileSync(path.join(site,'search-worker.js'),'utf8'),context);
function search(patch={}){
 const state={q:'',key:'',ch:0,lang:['en','ja','zh'],zh:'smart',mode:'plain',layout:'horizontal',page:1,...patch};
 return new Promise((resolve,reject)=>{
  const timeout=setTimeout(()=>reject(Error('worker timeout')),5000);
  complete=message=>{clearTimeout(timeout);message.type==='error'?reject(Error(message.message)):resolve(message);};
  sandbox.onmessage({data:{id:++id,state}});
 });
}
(async()=>{
 let r=await search();assert.equal(r.total,40);assert.equal(r.rows.length,30);assert.equal(r.pages,2);
 r=await search({page:2});assert.equal(r.rows.length,10);
 const fields={en:'lang_en.json',ja:'lang_ja.json',zh_default:'lang_zh.json',zh_names:'lang_zh_names.json',zh_recruitable:'lang_zh_recruitable.json'};
 for(let ch=1;ch<=5;ch++){
  r=await search({ch});assert.equal(r.total,8);
  const tables=Object.fromEntries(Object.entries(fields).map(([field,file])=>[field,JSON.parse(fs.readFileSync(path.join(__dirname,`../examples/input/ch${ch}`,file),'utf8'))]));
  for(const row of r.rows){
   assert.equal(row.chapter,ch);
   for(const field of Object.keys(fields))assert.equal(row[field],tables[field][row.key]??null);
  }
 }
 const key='obj_alphysalley_event_slash_Step_0_gml_25_0';
 r=await search({ch:[1,3]});assert.equal(r.total,16);assert(r.rows.every(row=>[1,3].includes(row.chapter)));
 const enOnly=await search({q:'克里斯',lang:['en'],zh:'default'});
 const zhOnly=await search({q:'克里斯',lang:['zh'],zh:'names'});
 assert(enOnly.total>0);assert.deepEqual(enOnly.rows,zhOnly.rows);assert.equal(enOnly.total,zhOnly.total);
 r=await search({key,ch:1});assert.equal(r.total,1);assert.notEqual(r.rows[0].zh_default,r.rows[0].zh_names);
 r=await search({q:'obj_treasure_room_slash_Other_10_gml_76_0'});assert.equal(r.total,4);
 await assert.rejects(search({q:'[',regex:true}),/正则表达式有误/);
 r=await search({key,ch:1});assert.equal(r.total,1);
 console.log('Real excerpt worker checks passed: paging, chapter/key, every original language value, variants, regex recovery.');
})().catch(e=>{console.error(e);process.exitCode=1;});
