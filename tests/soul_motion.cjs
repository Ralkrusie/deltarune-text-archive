'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {advance}=require('../web/soul-motion.js');
const b={width:800,height:600,scrollY:100,scrollMax:2000};
assert.deepEqual(advance({x:50,y:480},{dx:0,dy:10},b),{x:50,y:484,scroll:6});
assert.deepEqual(advance({x:50,y:484},{dx:0,dy:240},b),{x:50,y:484,scroll:240});
assert.deepEqual(advance({x:50,y:75},{dx:0,dy:-10},b),{x:50,y:72,scroll:-7});
assert.deepEqual(advance({x:50,y:484},{dx:0,dy:10},{...b,scrollY:1997}),{x:50,y:491,scroll:3});
assert.deepEqual(advance({x:50,y:72},{dx:0,dy:-10},{...b,scrollY:3}),{x:50,y:65,scroll:-3});
assert.deepEqual(advance({x:750,y:540},{dx:100,dy:60},{...b,scrollY:0,scrollMax:0}),{x:756,y:556,scroll:0});
// Starting beyond the camera margin (e.g. after dragging) must not snap the soul back.
assert.deepEqual(advance({x:50,y:530},{dx:0,dy:10},b),{x:50,y:530,scroll:10});
assert.deepEqual(advance({x:-100,y:2000},{dx:0,dy:0},b),{x:0,y:556,scroll:0});
// 60 small steps and one large step consume the same movement and camera distance.
let p={x:50,y:450},scrollY=0;
for(let i=0;i<60;i++){const n=advance(p,{dx:0,dy:4},{...b,scrollY});p={x:n.x,y:n.y};scrollY+=n.scroll;}
const once=advance({x:50,y:450},{dx:0,dy:240},{...b,scrollY:0});
assert.deepEqual({...p,scroll:scrollY},once);
// Exercise the real mount listeners: modifier order must not leave an arrow held.
function mounted(){
 const events={},frames=new Map();let frameId=0,time=0,cancels=0;
 class Element{closest(){return null;}}
 const button=new Element();Object.assign(button,{style:{removeProperty(){}},classList:{add(){},remove(){}},
  addEventListener(){},getBoundingClientRect(){return {left:100,top:100};},blur(){},hasPointerCapture(){return false;}});
 const home={hidden:true,addEventListener(){}};
 const document={documentElement:{clientWidth:1000,scrollHeight:2000},body:{},activeElement:new Element(),hidden:false,
  querySelector(){return null;},addEventListener(){}};
 const context={module:{exports:{}},Element,document,window:{scrollY:0,scrollBy(){},scrollTo(){}},innerHeight:800,
  matchMedia:()=>({matches:true,addEventListener(){}}),performance:{now:()=>time},
  addEventListener:(name,listener)=>(events[name]??=[]).push(listener),
  requestAnimationFrame:callback=>{frames.set(++frameId,callback);return frameId;},cancelAnimationFrame:id=>frames.delete(id),
  MutationObserver:class{observe(){}},setTimeout,Event};
 vm.runInNewContext(fs.readFileSync(require.resolve('../web/soul-motion.js'),'utf8'),context);
 const motion=context.module.exports.mount({button,home,isEnabled:()=>true,isKeyboardEnabled:()=>true});
 motion.setController({key(){},step(){},paint(){},cancel(){cancels++;}});
 return {
  motion,button,events,get cancels(){return cancels;},get pending(){return frames.size;},
  emit(type,fields){const event={defaultPrevented:false,preventDefault(){this.defaultPrevented=true;},...fields};
   for(const listener of events[type]||[])listener(event);return event;},
  tick(){time+=16;const callbacks=[...frames.values()];frames.clear();for(const callback of callbacks)callback(time);}
 };
}
for(const [key,flag] of [['Shift','shiftKey'],['Control','ctrlKey'],['Alt','altKey'],['Meta','metaKey']]){
 const moving=mounted();moving.emit('keydown',{key:'ArrowRight'});moving.tick();
 const left=moving.button.style.left;assert.ok(parseFloat(left)>100);
 let observed=0;moving.events.keydown.push(event=>{if(event.key===key)observed++;});
 const modifier=moving.emit('keydown',{key,[flag]:true});
 assert.equal(modifier.defaultPrevented,false,'modifier stays available to browser and color switch');
 assert.equal(observed,1);assert.equal(moving.cancels,1);assert.equal(moving.pending,0);
 moving.tick();assert.equal(moving.button.style.left,left,`${key} stops a previously held arrow`);
 assert.equal(moving.emit('keydown',{key:'ArrowRight',repeat:true,[flag]:true}).defaultPrevented,false);
 moving.emit('keyup',{key});moving.tick();assert.equal(moving.button.style.left,left,'modifier release does not revive movement');
 const first=mounted();first.emit('keydown',{key,[flag]:true});
 assert.equal(first.emit('keydown',{key:'ArrowRight',[flag]:true}).defaultPrevented,false);
 first.tick();assert.equal(first.button.style.left,undefined,`${key} then arrow remains a browser shortcut`);
}
const bare=mounted();
assert.equal(bare.emit('keydown',{key:'Shift',code:'ShiftLeft',shiftKey:true}).defaultPrevented,false);
assert.equal(bare.emit('keyup',{key:'Shift',code:'ShiftLeft'}).defaultPrevented,false);
assert.equal(bare.motion.canInteract(),true,'bare Shift remains eligible for color switching');
assert.equal(bare.cancels,0);
console.log('Soul motion: camera, limits, frame rate, modifier ordering and bare Shift handoff passed.');
