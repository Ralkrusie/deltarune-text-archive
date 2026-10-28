'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const M=require('../../web/model.js');
function boot(regex=false){
 const nodes=new Map(),workers=[],timers=new Map();let now=0,next=0;
 function node(){return {value:'',hidden:true,textContent:'',children:[],attrs:{},style:{setProperty(){}},
  append(...items){this.children.push(...items)},replaceChildren(...items){this.children=items},
  setAttribute(k,v){this.attrs[k]=v},querySelector(){return this.p??=node()},
  addEventListener(type,fn){this[type]=fn},getBoundingClientRect(){return {top:400,height:120}},scrollIntoView(){},dataset:{}};}
 const document={getElementById(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id)},createElement:node,createTextNode:text=>({textContent:text}),documentElement:node()};
 class Worker {constructor(url){this.url=url;this.sent=[];this.terminated=false;workers.push(this)}terminate(){this.terminated=true}postMessage(message){this.sent.push(message)}}
 const search=regex?'?regex=1':'';
 const context={window:{DialogueModel:M,DialogueContext:{mount(){return {show(){}}}}},document,location:{protocol:'http:',href:'http://localhost/'+search,search},Worker,
  URL,URLSearchParams,localStorage:{getItem(){return null},setItem(){}},history:{pushState(){},replaceState(){}},
  matchMedia(){return {matches:false,addEventListener(){}}},addEventListener(){},ResizeObserver:class{observe(){}},
  setTimeout(fn,ms){timers.set(++next,{fn,at:now+ms});return next},clearTimeout(id){timers.delete(id)}};
 vm.runInNewContext(fs.readFileSync('web/app.js','utf8'),context);
 function advance(ms){const target=now+ms;for(;;){const entry=[...timers].sort((a,b)=>a[1].at-b[1].at)[0];if(!entry||entry[1].at>target)break;now=entry[1].at;timers.delete(entry[0]);entry[1].fn()}now=target}
 function send(data,worker=workers.at(-1)){worker.onmessage({data:{id:worker.sent.at(-1).id,...data}})}
 return {nodes,workers,advance,send};
}
for(const regex of [false,true]){
 const h=boot(regex),worker=h.workers[0];
 assert.match(worker.url,/protocol=4/);
 assert.equal(worker.sent[0].progress,true);
 h.advance(25000);assert.equal(worker.terminated,false,'Slow downloads must survive the former 20s limit');
 h.send({type:'phase',phase:'loading',completed:2,total:5});
 assert.match(h.nodes.get('status').textContent,/2\/5/);
 assert.equal(h.nodes.get('cancel-search').hidden,false);
 h.advance(65000);assert.equal(worker.terminated,false);
 h.send({type:'phase',phase:'searching'});
 const limit=regex?8000:30000;
 h.advance(limit-1);assert.equal(worker.terminated,false);
 h.advance(1);assert.equal(worker.terminated,true,'The search budget starts after loading, including for regex');
 assert.equal(h.nodes.get('status').textContent,'检索未完成');
}
{
 const h=boot();h.advance(119000);h.send({type:'phase',phase:'loading',completed:4,total:5});h.advance(1000);
 assert.equal(h.workers[0].terminated,true,'Progress must not reset the 2-minute load deadline');
 assert.match(h.nodes.get('error').p.textContent,/数据加载超过 2 分钟/);
 h.nodes.get('retry').onclick();assert.equal(h.workers.length,2);
 h.advance(20001);assert.equal(h.workers[1].terminated,false,'Retry gets a fresh loading budget');
}
{
 const h=boot(),worker=h.workers[0],oldId=worker.sent[0].id;
 h.nodes.get('search-form').onsubmit({preventDefault(){}});
 h.send({id:oldId,type:'phase',phase:'searching'});
 h.advance(31000);assert.equal(worker.terminated,false,'Stale phase messages cannot start the new request search timer');
 h.send({type:'phase',phase:'searching'});
 h.send({type:'result',rows:[],total:0,page:1,pages:1});
 h.advance(120000);assert.equal(worker.terminated,false,'A result cancels both phase deadlines');
 assert.equal(h.nodes.get('error').hidden,true);
}
{
 const h=boot();h.nodes.get('cancel-search').onclick();
 h.send({type:'phase',phase:'loading',completed:1,total:5});
 assert.equal(h.workers[0].terminated,true);
 assert.match(h.nodes.get('error').p.textContent,/已取消/);
}
console.log('Slow loading, absolute load deadline, separate plain/regex limits, retry, stale phases, result and cancellation passed.');
