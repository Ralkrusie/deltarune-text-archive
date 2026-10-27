'use strict';
// Exercise the actual controller across several animation frames, including idle scroll repair.
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const {advance}=require('../../web/soul.js').movement;
const noop=()=>{};
function element(id='',rect={}){return {id,rect,dataset:{},style:{removeProperty:noop},classList:{remove:noop},append:noop,setAttribute:noop,addEventListener:noop,getBoundingClientRect(){return this.rect;},getContext:()=>({clearRect:noop})};}
const art=element(),button=element(),home=element(),controls=element('controls'),results=element('results'),list=element('list');
button.dataset={};button.querySelector=()=>art;
let cells=[],scroll=0;
const env={module:{exports:{}},console,SoulMotion:{advance},Image:class{},
 performance:{now:()=>0},AudioContext:class{resume(){return Promise.resolve();}decodeAudioData(){return Promise.resolve({});}createGain(){return {gain:{},connect:noop,disconnect:noop};}createBufferSource(){return {playbackRate:{},connect:noop,disconnect:noop,start:noop,stop:noop};}},
 fetch:async()=>({ok:true,arrayBuffer:async()=>new ArrayBuffer(0)}),
 document:{createElement:()=>element(),body:element(),getElementById:id=>({controls,results,list}[id]),querySelectorAll:()=>cells},
 getComputedStyle:e=>e.borders||{borderTopWidth:'2px',borderBottomWidth:'2px',borderLeftWidth:'0px'},
 addEventListener:noop,ResizeObserver:class{observe(){}},MutationObserver:class{observe(){}},
 get scrollY(){return scroll;}};
vm.runInNewContext(fs.readFileSync(require.resolve('../../web/soul.js'),'utf8'),env);
const {mount,toolbarExit}=env.module.exports.variants;
const soul=mount({button,home,motion:{roaming:()=>false},getColor:()=>'purple',getAngle:()=>0});
let position={x:478,y:31};
function tick(dy=0){const n=soul.step({position,dx:0,dy,dt:1/60,bounds:{width:1000,height:720,scrollY:scroll,scrollMax:3000}});position={x:n.x,y:n.y};scroll+=n.scroll||0;}
function settle(){for(let i=0;i<60;i++)tick();}
function down(){soul.key('ArrowDown',true);tick(1);soul.key('ArrowDown',false);settle();}
function horizontal(y){const e=element('',{left:20,right:980,top:y,bottom:y+80,width:960,height:80});e.borders={borderTopWidth:'2px',borderLeftWidth:'0px'};return e;}
function vertical(x,top,bottom){const e=element('',{left:x,right:x+200,top,bottom,width:200,height:bottom-top});e.borders={borderTopWidth:'0px',borderLeftWidth:'2px'};e.parentElement={};return e;}
function resetHome(){soul.cancel();soul.depart();scroll=0;controls.rect={left:0,right:1000,top:188,bottom:354,width:1000,height:166};position={x:478,y:31};}
resetHome();cells=[horizontal(490)];down();
assert(Math.abs(position.y+22-189)<0.01,'first press lands on upper border, without skipping to lower');
down();assert(Math.abs(position.y+22-353)<0.01,'second press reaches lower border');
// Simulate a wheel scroll: old content is off screen, later content is visible.
scroll=1000;controls.rect.top=0;controls.rect.bottom=166;position.y=167;
cells=[horizontal(-500),horizontal(-200),horizontal(260),horizontal(510)];
settle();assert(Math.abs(position.y+22-165)<0.01,'soul can rest on the sticky lower border');
down();assert(Math.abs(position.y+22-261)<0.01,'down enters nearest visible separator, not old offscreen content');
assert.equal(scroll,1000,'re-entry must not scroll back up to earlier records');
// Recall/re-depart clears the retained line, even after using a much later record.
resetHome();cells=[horizontal(490)];down();assert(Math.abs(position.y+22-189)<0.01);
// A vertical separator may start under the sticky toolbar. Land on its visible portion.
scroll=1000;controls.rect.top=0;controls.rect.bottom=166;position.y=167;
cells=[vertical(450,-500,-200),vertical(450,100,320),vertical(750,100,320)];
settle();assert(Math.abs(position.y+22-165)<0.01);
down();assert(Math.abs(position.x+22-451)<0.01);assert(position.y+22>=188);
assert.equal(scroll,1000,'partially occluded vertical entry should not pull camera upward');
const far={element:{},left:20,right:980,y:1000},old={element:{},left:20,right:980,y:-500};
assert.equal(toolbarExit([old,far],{x:500,y:165},188,698).y,1000,'if no line is visible, use the next one below, never old content');
console.log('Purple controller: first landing, second step, recall, wheel-scroll re-entry on horizontal/vertical lines passed.');

const {dustRotation}=env.module.exports.variants;
// The dust sprite starts below the origin: its center must point opposite travel.
for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1],[1,-1]]){
 const a=dustRotation(dx,dy),length=Math.hypot(dx,dy);
 assert(Math.abs(-Math.sin(a)+dx/length)<1e-9);
 assert(Math.abs(Math.cos(a)+dy/length)<1e-9);
}
console.log('Purple jump dust points behind horizontal, vertical and diagonal travel.');
