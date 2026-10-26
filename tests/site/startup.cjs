'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map();
const node=()=>({hidden:true,textContent:'',children:[],attrs:{},append(n){this.children.push(n)},setAttribute(k,v){this.attrs[k]=v},querySelector(){return this.p??=node()}});
const buttons=[node(),node()];
const document={getElementById(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id)},createElement:node,querySelectorAll(){return buttons}};
// None of these browser facilities may be required to explain direct-file startup.
const deny=new Proxy({}, {get(){throw Error('File startup must exit before initialization')}});
vm.runInNewContext(fs.readFileSync('web/app.js','utf8'),{window:{DialogueText:deny,DialogueModel:deny},document,location:{protocol:'file:'},Worker:deny});
assert.match(nodes.get('status').textContent,/本地预览/);
assert.match(nodes.get('error').p.textContent,/preview\.cmd/);
assert.equal(nodes.get('error').hidden,false);
assert.equal(nodes.get('list').attrs['aria-busy'],'false');
assert.ok(buttons.every(b=>b.disabled));
console.log('Direct-file startup reports the launch instructions before model, storage, or worker initialization.');
