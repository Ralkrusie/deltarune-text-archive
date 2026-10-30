'use strict';
const assert=require('node:assert/strict');
const {refs,scenesFor,fileOptions,lanes}=require('../../web/context.js');
const message=id=>({type:'message',key:'same',occurrence_id:id});
const {flowWidth}=require('../../web/context.js');
assert.equal(flowWidth(message('single')),256);
assert.equal(flowWidth({type:'condition',branches:[{body:message('one')},{body:{type:'sequence',children:[]}}]}),256);
assert.equal(flowWidth({type:'choice',branches:[{body:message('one')},{body:{type:'choice',branches:[{body:message('two')},{body:message('three')}]}}]}),808);
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
assert.equal(lanes({type:'choice',branches:[{body:{type:'condition',revisit:{flag:123,from:0,to:1,write_line:8},branches:[{body:message('a')},{body:message('b')}]}},{body:message('c')}]}),2);
assert.deepEqual(refs({type:'blocks',children:[{type:'block',children:[message('block1')]},{type:'block',children:[message('block2')]}]}).map(r=>r.occurrence_id),['block1','block2']);
const prefixedChoice={type:'choice',prefix:{type:'sequence',children:[message('prefix')]},branches:[
 {option:message('option0'),body:message('answer0')},{option:message('option1'),body:message('answer1')}]};
assert.deepEqual(refs({type:'sequence',children:[prefixedChoice,message('tail')]}).map(r=>r.occurrence_id),
 ['option0','option1','prefix','answer0','answer1','tail']);
assert.equal(lanes({...prefixedChoice,prefix:{type:'condition',branches:[1,2,3].map(i=>({body:message(i)}))}}),3);
console.log('Context lookup: chapter isolation, options, repeated uses and missing coverage passed');
const index={files:[{file:'native.gml'},{file:'caller.gml'},{file:'other.gml'}],by_key:{same:[0,2]},related_by_key:{same:[1,0]}};
assert.deepEqual(fileOptions(index,'same').map(x=>[x.file,x.related]),[['native.gml',false],['other.gml',false],['caller.gml',true]]);
assert.deepEqual(fileOptions(index,'missing'),[]);
// A resize ending outside the centered dialog must not dismiss it.
const events={};let closed=0;
const dialog={addEventListener(type,fn){events[type]=fn;},close(){closed++;},
 getBoundingClientRect(){return {left:100,right:600,top:100,bottom:500};}};
require('../../web/context.js').mount({dialog,content:{},title:{},close:{},start:{},cell(){},getState(){return {};}});
events.pointerdown({target:dialog,clientX:598,clientY:498});
events.click({target:dialog,clientX:800,clientY:600});assert.equal(closed,0);
events.pointerdown({target:dialog,clientX:50,clientY:50});
events.click({target:dialog,clientX:50,clientY:50});assert.equal(closed,1);
const panEvents={},viewport={scrollLeft:100,scrollTop:200,addEventListener(t,fn){panEvents[t]=fn;},setPointerCapture(){},classList:{add(){},remove(){}}};
require('../../web/context.js').mount({dialog,content:viewport,title:{},close:{},start:{},cell(){},getState(){return {};}});
panEvents.pointerdown({button:0,pointerType:'mouse',pointerId:1,clientX:200,clientY:200,target:{closest(){return null;}},preventDefault(){}});
panEvents.pointermove({pointerId:1,clientX:150,clientY:170});
assert.deepEqual([viewport.scrollLeft,viewport.scrollTop],[150,230]);
panEvents.pointerup();
panEvents.pointerdown({button:0,pointerType:'mouse',pointerId:2,target:{closest(){return {};}}});
panEvents.pointermove({pointerId:2,clientX:0,clientY:0});
assert.deepEqual([viewport.scrollLeft,viewport.scrollTop],[150,230]);

// Render a shared reply after both option cards, before the answer-specific
// replies. The source-bearing option and prefix cards must not be duplicated.
async function renderSharedPrefix(){
 class Element{
  constructor(tag){this.tagName=tag;this.children=[];this.style={};this.dataset={};this.className='';this.textContent='';}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=[...children];}
  setAttribute(name,value){this[name==='class'?'className':name]=value;}
  querySelector(selector){return flatten(this).find(n=>n.className.split(' ').includes(selector.slice(1)))||null;}
  scrollIntoView(){this.scrolled=true;}
 }
 function flatten(node){return [node,...node.children.flatMap(flatten)];}
 const original={document:global.document,fetch:global.fetch,DialogueText:global.DialogueText,DialogueActions:global.DialogueActions};
 try{
  global.document={createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)};
  global.DialogueText={decodeRow:(_,row)=>row};global.DialogueActions={sourceURL:()=>'/source'};
  const ref=id=>({...message(id),key:id,source:{file:'gml_fixture.gml',line:1}});
  const choice={type:'choice',title:'玩家选择',auto_answer:{condition:'timer >= 30',option:0},join_next:true,prefix:{type:'sequence',children:[ref('prefix')]},branches:[
   {option:ref('option0'),body:{type:'sequence',children:[ref('answer0')]}},
   {option:ref('option1'),body:{type:'sequence',children:[ref('answer1')]}}]};
  const landing={type:'block',anchor:'state-30',label:'L30',children:[]};
  const scene={id:'scene',chapter:4,file:'gml_fixture.gml',body:{type:'sequence',children:[choice,ref('tail'),
   {type:'jump',target:'state-30',label:'接续 L30'},landing]}};
  const pack={schema:1,text_manifest_sha256:'binding',scenes:[scene]};
  global.fetch=async path=>({ok:true,json:async()=>path==='data/contexts.json'?pack:path==='data/manifest.json'?{source_manifest_sha256:'binding'}:
   {rows:refs(scene.body).map(r=>({key:r.key,chapter:4,en:r.key}))}});
  const content=new Element('div');const display={...dialog,showModal(){this.open=true;},scrollTo(){}};
  const view=require('../../web/context.js').mount({dialog:display,content,title:{},close:{},start:{},
   cell(item){const e=new Element('p');e.textContent=item.en;return e;},getState(){return {lang:['en']};}});
  await view.show({chapter:4,key:'prefix'});
  const rendered=flatten(content),cards=rendered.filter(n=>n.tagName==='article');
  assert.deepEqual(cards.map(n=>n.dataset.occurrence),['option0','option1','prefix','answer0','answer1','tail']);
  assert.equal(rendered.filter(n=>n.className==='context-join-lines').length,3);
  assert.equal(rendered.filter(n=>n.className==='context-branch-label'&&n.textContent==='选项 1').length,2);
  assert.ok(rendered.some(n=>n.textContent==='timer >= 30 → 选项 1'));
  const jump=rendered.find(n=>n.className==='context-jump'),target=rendered.find(n=>n.className==='context-block');
  assert.ok(!target.scrolled);jump.onclick();assert.ok(target.scrolled);
  const empty={type:'sequence',children:[]};
  const condition=(label,yes,no)=>({type:'condition',branches:[{label,body:yes},{label:`!(${label})`,body:no}]});
  const nested=condition('outer',condition('inner',ref('answer0'),empty),empty);
  const inverted=condition('false-arm',empty,ref('answer1'));
  const endpoint=condition('exit-path',{type:'end',label:'退出'},ref('tail'));
  const emptyChoice={type:'choice',branches:[{option:ref('option0'),body:empty},{option:ref('option1'),body:empty}]};
  scene.body={type:'sequence',children:[nested,inverted,endpoint,emptyChoice]};
  const originalStructure=JSON.stringify(scene.body);
  assert.equal(lanes(nested),1);
  assert.equal(lanes(inverted),1);
  assert.equal(lanes(endpoint),2);
  assert.equal(lanes(emptyChoice),2);
  await view.show({chapter:4,key:'answer0'});
  const compact=flatten(content);
  assert.deepEqual(compact.filter(n=>n.tagName==='article').map(n=>n.dataset.occurrence),['answer0','answer1','tail','option0','option1']);
  assert.deepEqual(compact.filter(n=>n.className==='context-condition').map(n=>n.textContent),['outer','inner','!(false-arm)','exit-path','!(exit-path)']);
  assert.equal(compact.filter(n=>n.className==='context-empty').length,0);
  assert.ok(compact.some(n=>n.className==='context-end'&&n.textContent==='退出'));
  assert.equal(JSON.stringify(scene.body),originalStructure);
  console.log('Shared response prefix: menu → one common reply → numbered answer branches → one tail passed');
 }finally{for(const [key,value] of Object.entries(original)){if(value===undefined)delete global[key];else global[key]=value;}}
}
renderSharedPrefix().catch(error=>{console.error(error);process.exitCode=1;});
