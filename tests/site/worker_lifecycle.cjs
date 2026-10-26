'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const M=require('../../web/model.js');
const nodes=new Map();
function node(){return {value:'',hidden:true,textContent:'',children:[],attrs:{},style:{setProperty(){}},
 append(...items){this.children.push(...items)},replaceChildren(...items){this.children=items},
 setAttribute(k,v){this.attrs[k]=v},querySelector(){return this.p??=node()},
 addEventListener(type,fn){this[type]=fn},getBoundingClientRect(){return {top:400,height:120}},scrollIntoView(){},dataset:{}};}
const document={getElementById(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id)},createElement:node,createTextNode:text=>({textContent:text}),documentElement:node()};
const workers=[];
class Worker {constructor(){this.sent=[];this.terminated=false;workers.push(this)} terminate(){this.terminated=true} postMessage(message){this.sent.push(message)}}
const context={window:{DialogueModel:M,DialogueContext:{mount(){return {show(){}}}}},document,location:{protocol:'http:',href:'http://localhost/?regex=1',search:'?regex=1'},Worker,
 URL,URLSearchParams,localStorage:{getItem(){return null},setItem(){}},history:{pushState(){},replaceState(){}},
 matchMedia(){return {matches:false,addEventListener(){}}},addEventListener(){},
 ResizeObserver:class{observe(){}},setTimeout(){return 1},clearTimeout(){}};
vm.runInNewContext(fs.readFileSync('web/app.js','utf8'),context);
assert.equal(workers.length,1,'Opening a regex URL starts just one worker');
const first=workers[0],staleError=first.onerror;
const form=nodes.get('search-form');
form.onsubmit({preventDefault(){}});
const current=workers[1];
assert.ok(first.terminated);
assert.equal(current.sent.length,1);
staleError();
assert.equal(current.terminated,false,'A queued error from the old worker must not terminate its replacement');
assert.equal(nodes.get('error').hidden,true);
assert.equal(nodes.get('list').attrs['aria-busy'],'true');
current.onerror();
assert.equal(current.terminated,true);
assert.equal(nodes.get('error').hidden,false,'A current worker failure is still reported');
nodes.get('retry').onclick();
assert.equal(workers.length,3);
assert.equal(workers[2].sent.length,1,'Retry starts a fresh request');
console.log('Worker replacement ignores stale loading errors; regex startup and retry remain usable.');
