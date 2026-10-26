'use strict';
const assert=require('node:assert/strict');
const {refs,scenesFor,fileOptions,lanes}=require('../web/context.js');
const message=id=>({type:'message',key:'same',occurrence_id:id});
const pack={scenes:[{id:'a',chapter:4,body:{type:'choice',branches:[
 {option:message('option'),body:{type:'sequence',children:[message('use1'),message('use2')]}},
 {option:{...message('other'),key:'other'},body:{type:'end',label:'End'}}]}},
 {id:'b',chapter:5,body:message('use3')}]};
assert.deepEqual(scenesFor(pack,4,'same').map(s=>s.id),['a']);
assert.deepEqual(scenesFor(pack,5,'same').map(s=>s.id),['b']);
assert.deepEqual(scenesFor(pack,4,'missing'),[]);
assert.deepEqual(scenesFor({scenes:[]},4,'same'),[]);
assert.deepEqual(refs(pack.scenes[0].body).map(r=>r.occurrence_id),['option','use1','use2','other']);
assert.equal(lanes({type:'choice',branches:[{body:{type:'condition',branches:[{body:message('a')},{body:message('b')}]}},{body:message('c')}]}),3);
assert.deepEqual(refs({type:'blocks',children:[{type:'block',children:[message('block1')]},{type:'block',children:[message('block2')]}]}).map(r=>r.occurrence_id),['block1','block2']);
console.log('Context lookup: chapter isolation, options, repeated uses and missing coverage passed');
const index={files:[{file:'native.gml'},{file:'caller.gml'},{file:'other.gml'}],by_key:{same:[0,2]},related_by_key:{same:[1,0]}};
assert.deepEqual(fileOptions(index,'same').map(x=>[x.file,x.related]),[['native.gml',false],['other.gml',false],['caller.gml',true]]);
assert.deepEqual(fileOptions(index,'missing'),[]);
// A resize ending outside the centered dialog must not dismiss it.
const events={};let closed=0;
const dialog={addEventListener(type,fn){events[type]=fn;},close(){closed++;},
 getBoundingClientRect(){return {left:100,right:600,top:100,bottom:500};}};
require('../web/context.js').mount({dialog,content:{},title:{},close:{},start:{},cell(){},getState(){return {};}});
events.pointerdown({target:dialog,clientX:598,clientY:498});
events.click({target:dialog,clientX:800,clientY:600});assert.equal(closed,0);
events.pointerdown({target:dialog,clientX:50,clientY:50});
events.click({target:dialog,clientX:50,clientY:50});assert.equal(closed,1);
