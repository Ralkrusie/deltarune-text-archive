'use strict';
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const T=require('../../web/text.js'),A=require('../../web/actions.js');
const raw='* \\O0!/',words={'0':'Love'};
assert.equal(T.format(raw,3,words).plain,'* Love!');
assert.deepEqual(T.format(raw,3,words).artwordRanges,[[2,6]]);
assert.deepEqual(T.format('\\O0&x\\O1/',3,{'0':'甲\n乙','1':'丙'}).artwordRanges,[[0,3],[5,6]]);
assert.equal(T.format(raw,3,words).raw,raw);
assert.equal(T.format(raw,3).plain,'* 〔艺术字 0〕!');
assert.equal(T.format('`\\O0',3,words).plain,'\\O0');
assert.equal(T.format('\\I0',3,words).plain,'〔图标 0〕');
const data={chapter:3,languages:['en','ja','zh_default','zh_names','zh_recruitable'],strings:[raw],rows:[['one',0,0,0,0,0],['two',0,0,0,0,0]],artwords:{one:{en:words,ja:{'0':'大スキ♡'}},two:{en:{'0':'CHALLENGE'}}}};
const row=T.decodeRow(data,data.rows[0]);
assert(A.copyEntry(row,{lang:['en','ja'],mode:'plain'}).includes('JA: * 大スキ♡!'));
assert(A.copyEntry(row,{lang:['en'],mode:'source'}).includes(raw));
let done;
const sandbox={Map,Set,Promise,URLSearchParams,setTimeout,clearTimeout,console,
 fetch:async url=>({ok:true,json:async()=>url.endsWith('manifest.json')?{chapters:[{chapter:3}],total_rows:2}:data}),postMessage:m=>done(m)};
sandbox.self=sandbox;const context=vm.createContext(sandbox);
sandbox.importScripts=(...names)=>names.forEach(name=>vm.runInContext(fs.readFileSync('web/'+name,'utf8'),context));
vm.runInContext(fs.readFileSync('web/search-worker.js','utf8'),context);
async function search(q,id){return new Promise(resolve=>{done=resolve;sandbox.onmessage({data:{id,state:{q,ch:3,page:1}}});});}
(async()=>{
 let result=await search('Love',1);assert.equal(result.total,1);assert.equal(result.rows[0].key,'one');assert(result.rows[0].highlights.en.plain.length);
 result=await search('CHALLENGE',2);assert.equal(result.total,1);assert.equal(result.rows[0].key,'two');
 result=await search('大スキ',3);assert.equal(result.total,1);assert.equal(result.rows[0].key,'one');
 console.log('Artword checks passed: language, local slots, shared strings, copy, search, highlight, source.');
})().catch(e=>{console.error(e);process.exitCode=1;});
