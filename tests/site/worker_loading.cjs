'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const state={q:'',key:'',ch:[1,2],lang:['en'],zh:'smart',mode:'plain',layout:'horizontal',page:1};
const messages=[],pending=new Map(),requests=[];
const sandbox={Map,Set,Promise,URLSearchParams,setTimeout,clearTimeout,
 fetch:async url=>{requests.push(url);return {ok:true,json:()=>new Promise((resolve,reject)=>pending.set(url,{resolve,reject}))}},
 postMessage:message=>messages.push(message)};
sandbox.self=sandbox;const context=vm.createContext(sandbox);
sandbox.importScripts=(...names)=>names.forEach(name=>vm.runInContext(fs.readFileSync('web/'+name,'utf8'),context));
vm.runInContext(fs.readFileSync('web/search-worker.js','utf8'),context);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const data=chapter=>({chapter,languages:['en','ja','zh_default','zh_recruitable','zh_names'],strings:[],rows:[]});
(async()=>{
 const first=sandbox.onmessage({data:{id:1,state,progress:true}});await flush();
 assert.equal(messages.length,0,'HTTP success headers alone do not mean the body is ready');
 pending.get('data/manifest.json').resolve({chapters:[1,2,3,4].map(chapter=>({chapter})),total_rows:0});await flush();
 assert.deepEqual(messages.map(m=>[m.phase,m.completed,m.total]),[['loading',0,2]]);
 pending.get('data/ch2.json').resolve(data(2));await flush();
 assert.equal(messages.at(-1).completed,1);assert(!messages.some(m=>m.phase==='searching'));
 // A new query reuses in-flight downloads. Old completions cannot report stale progress/results.
 const second=sandbox.onmessage({data:{id:2,state,progress:true}});await flush();
 pending.get('data/ch1.json').resolve(data(1));await Promise.all([first,second]);
 assert.equal(requests.filter(url=>url==='data/ch1.json').length,1);
 assert.equal(messages.filter(m=>m.type==='result').length,1);
 assert.equal(messages.at(-1).id,2);
 const current=messages.filter(m=>m.id===2);
 assert.deepEqual(current.map(m=>m.type==='phase'?m.phase+':'+(m.completed??''):m.type),['loading:0','loading:1','loading:2','searching:','result']);
 messages.length=0;
 await sandbox.onmessage({data:{id:3,state}});
 assert.deepEqual(messages.map(m=>m.type),['result'],'Old cached clients get no unexpected phase messages');
 assert.equal(requests.length,3,'Loaded chapters are reused');
 // One failed file reports a load error; later successful files cannot overwrite it.
 const failed=sandbox.onmessage({data:{id:4,state:{...state,ch:[3,4]},progress:true}});
 await flush();pending.get('data/ch3.json').reject(Error('network failure'));await failed;
 assert.equal(messages.at(-1).type,'error');assert.equal(messages.at(-1).phase,'loading');
 const count=messages.length;
 pending.get('data/ch4.json').resolve(data(4));await flush();
 assert.equal(messages.length,count,'No loading progress may arrive after a terminal error');
 const retry=sandbox.onmessage({data:{id:5,state:{...state,ch:[3,4]},progress:true}});await flush();
 pending.get('data/ch3.json').resolve(data(3));await retry;
 assert.equal(messages.at(-1).type,'result');
 assert.equal(requests.filter(url=>url==='data/ch3.json').length,2);
 assert.equal(requests.filter(url=>url==='data/ch4.json').length,1,'Successful files survive retry');
 console.log('Worker phase ordering, complete bodies, stale requests, shared downloads, legacy clients and partial-load retry passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
