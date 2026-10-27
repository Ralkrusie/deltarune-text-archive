'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const listeners={},timers=[];let enabled=true,red=true,desktop=true,modal=false,hit=[],coords;
class Element{
 constructor(){this.events={};this.children=[];this.style={removeProperty(){}};this.classList={add(){},remove(){}};}
 addEventListener(name,fn){(this.events[name]??=[]).push(fn)}
 contains(node){return this.children.includes(node)}
 closest(selector){if(selector.startsWith(':disabled'))return this.disabled?this:null;if(selector.includes('dialog'))return this.editable?this:null;return this.focusable?this:null}
 getBoundingClientRect(){return this.rect||{left:100,top:200,width:44,height:44}}
 blur(){this.blurred=true;document.activeElement=new Element()}
 focus(options){this.focused=options;document.activeElement=this}
 dispatchEvent(event){this.received=event;this.count=(this.count||0)+1;return true}
 hasPointerCapture(){return false}
 setPointerCapture(){}
}
const button=new Element(),sprite=new Element(),home=new Element(),target=new Element();
button.children.push(sprite);target.focusable=true;
const document={activeElement:new Element(),hidden:false,body:{},documentElement:{clientWidth:1000,scrollHeight:2000},
 querySelector:()=>modal?{}:null,addEventListener(){},elementsFromPoint(x,y){coords=[x,y];return hit}};
const context={module:{exports:{}},Element,document,window:{scrollY:900},innerHeight:800,
 matchMedia:()=>({get matches(){return desktop},addEventListener(){}}),addEventListener:(name,fn)=>(listeners[name]??=[]).push(fn),
 MutationObserver:class{observe(){}},MouseEvent:class{constructor(type,options){this.type=type;Object.assign(this,options)}},setTimeout:fn=>timers.push(fn),Event};
vm.runInNewContext(fs.readFileSync(require.resolve('../../web/soul.js'),'utf8'),context);
context.module.exports.movement.mount({button,home,isEnabled:()=>enabled,isKeyboardEnabled:()=>true,isClickEnabled:()=>red});
function press(patch={}){const event={key:'z',code:'KeyZ',target:document.activeElement,preventDefault(){this.defaultPrevented=true},...patch};for(const fn of listeners.keydown)fn(event);return event}
hit=[sprite,button,target];
assert.equal(press().defaultPrevented,true);
assert.deepEqual(coords,[122,222],'Use soul center in viewport coordinates, without adding scroll offset');
assert.equal(target.count,1);assert.equal(button.count,undefined);assert.equal(home.count,undefined);
assert.equal(target.received.type,'click');assert.equal(target.received.button,0);assert.equal(target.received.clientX,122);assert.equal(target.focused.preventScroll,true);
for(const field of ['repeat','isComposing','ctrlKey','altKey','metaKey','shiftKey','defaultPrevented'])press({[field]:true});
assert.equal(target.count,1,'Held keys and modified/composing keystrokes do not click');
red=false;press();red=true;enabled=false;press();enabled=true;desktop=false;press();desktop=true;modal=true;press();modal=false;
assert.equal(target.count,1,'Other colors, disabled interaction, touch-only devices and dialogs are unaffected');
const input=new Element();input.editable=true;document.activeElement=input;press();document.activeElement=target;press({target:input});
assert.equal(target.count,1,'Typing z in a field remains typing');
target.disabled=true;press();assert.equal(target.count,1);target.disabled=false;
button.rect={left:300,top:400,width:44,height:44};press();assert.equal(target.received.clientY,422);
button.rect={left:100,top:-200,width:44,height:44};press();assert.equal(target.count,2,'A docked soul outside the viewport must not click');
button.rect={left:100,top:200,width:44,height:44};
for(const fn of button.events.pointerdown)fn({pointerType:'mouse',button:0,pointerId:1,clientX:120,clientY:220});
press();assert.equal(target.count,2,'Dragging does not activate what lies under the soul');
console.log('Red Z click: center hit-test, overlay exclusion, focus, modifiers, typing, color/desktop guards, disabled targets and dragging passed.');

// Escape exits immediately, while Enter must preserve the form's default submission.
document.activeElement=input;input.tagName='INPUT';
assert.equal(press({key:'Escape',code:'Escape'}).defaultPrevented,true);assert.equal(input.blurred,true);
input.blurred=false;document.activeElement=input;
assert.equal(press({key:'Enter',code:'Enter'}).defaultPrevented,undefined);
assert.equal(document.activeElement,input);timers.shift()();assert.equal(input.blurred,true);
for(const flag of ['isComposing','repeat','ctrlKey','altKey','metaKey','shiftKey','defaultPrevented']){
 input.blurred=false;document.activeElement=input;press({key:'Escape',code:'Escape',[flag]:true});assert.equal(input.blurred,false);
}
input.blurred=false;document.activeElement=input;press({key:'Enter',code:'Enter',keyCode:229});assert.equal(timers.length,0);
modal=true;press({key:'Escape',code:'Escape'});assert.equal(input.blurred,false);modal=false;
red=false;press({key:'Escape',code:'Escape'});assert.equal(input.blurred,false);red=true;
input.tagName='TEXTAREA';press({key:'Enter',code:'Enter'});assert.equal(timers.length,0);
console.log('Red keyboard exit: Escape, deferred Enter, IME, modifiers, dialogs and multiline editing passed.');
