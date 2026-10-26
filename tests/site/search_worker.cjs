'use strict';
const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),web=path.join(root,'web');
let complete;
const sandbox={console,Map,Set,Promise,URLSearchParams,setTimeout,clearTimeout,
 fetch:async url=>({ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,'dist',url),'utf8'))}),
 postMessage:message=>{if(complete)complete(message);}};
sandbox.self=sandbox;
const context=vm.createContext(sandbox);
sandbox.importScripts=(...names)=>names.forEach(name=>vm.runInContext(fs.readFileSync(path.join(web,name),'utf8'),context));
vm.runInContext(fs.readFileSync(path.join(web,'search-worker.js'),'utf8'),context);
let id=0;
async function search(patch){
 const state={q:'',key:'',ch:0,lang:['en','ja','zh'],zh:'smart',mode:'plain',layout:'horizontal',page:1,...patch};
 return new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(Error('worker timeout')),15000);complete=message=>{clearTimeout(timeout);if(message.type==='error')reject(Error(message.message));else resolve(message);};sandbox.onmessage({data:{id:++id,state}});});
}
(async()=>{
 let r=await search({});assert.equal(r.total,66144);assert.equal(r.rows.length,30);
 r=await search({q:'obj_dummyenemy_slash_Step_0_gml_558_0'});assert.equal(r.total,5);
 r=await search({ch:4,key:'obj_dummyenemy_slash_Step_0_gml_558_0'});assert.equal(r.total,1);assert.equal(r.rows[0].chapter,4);
 r=await search({ch:[1,3],key:'obj_dummyenemy_slash_Step_0_gml_558_0'});
 assert.deepEqual(Array.from(r.rows,row=>row.chapter),[1,3]);
 const hidden=await search({ch:[1],q:'克里斯',lang:['en'],zh:'default'});
 const shown=await search({ch:[1],q:'克里斯',lang:['zh'],zh:'names'});
 assert(hidden.total>0);assert.equal(hidden.total,shown.total);assert.deepEqual(hidden.rows,shown.rows);
 r=await search({ch:1,q:'克里斯',lang:['zh'],zh:'names'});assert(r.total>0);assert(r.rows.every(row=>row.zh_names.includes('克里斯')));
 r=await search({ch:1,q:'\\E3',lang:['en']});assert(r.total>0);assert(r.rows.every(row=>sandbox.DialogueModel.SEARCH_FIELDS.some(field=>row[field]?.includes('\\E3'))));
 const plain=await search({ch:1,q:'yes',lang:['en']});
 const sensitive=await search({ch:1,q:'yes',lang:['en'],caseSensitive:true});
 const whole=await search({ch:1,q:'yes',lang:['en'],wholeWord:true});
 assert(plain.total>sensitive.total);assert(plain.total>whole.total);
 r=await search({ch:1,q:'^(YES|NO)$',lang:['en'],caseSensitive:true,regex:true});
 assert(r.total>0);assert(r.rows.every(row=>['YES','NO'].includes(row.en)));assert(r.rows.every(row=>row.highlights.en.source.length));
 console.log(JSON.stringify({yes:plain.total,caseSensitive:sensitive.total,wholeWord:whole.total,regexYesNo:r.total}));
 await assert.rejects(search({q:'[',regex:true}),/正则表达式有误/);
 r=await search({ch:1,q:'YES',lang:['en'],wholeWord:true});assert(r.total>0);
 r=await search({q:'UNMATCHED_TEST_627492'});assert.equal(r.total,0);assert.equal(r.page,1);
 r=await search({ch:1,page:9999});assert.equal(r.page,r.pages);assert(r.rows.length>0);
 console.log('Real worker checks passed: all rows, key, chapter, Chinese variant, raw controls, empty result and page clamp.');
})().catch(e=>{console.error(e);process.exitCode=1;});
