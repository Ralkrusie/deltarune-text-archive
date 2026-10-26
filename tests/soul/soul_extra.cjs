'use strict';
const assert=require('node:assert/strict');
const {orangeModel,greenDelay,nearest,neighbor,project,emitsTrail}=require('../../web/soul.js').variants;
const {advance}=require('../../web/soul.js').movement;
const close=(a,b)=>assert(Math.abs(a-b)<1e-8,`${a} != ${b}`);
for(const fps of [30,60,144]){
 const delay=greenDelay();let moved=0;
 for(let i=0;i<fps*2;i++){moved+=delay.advance(1,0,1/fps);if(i<fps-1)close(moved,0);}
 close(moved,1);
 close(delay.advance(0,1,0.5),0); // new direction waits a full second again
 delay.reset();close(delay.advance(1,0,0.75),0);close(delay.advance(1,0,0.5),0.25);
 const sounds=[],orange=orangeModel((...args)=>sounds.push(args));
 orange.press();for(let i=0;i<fps;i++)orange.advance(1/fps);
 assert.equal(orange.state,'charge');assert.equal(orange.charge,16);
 close(orange.glow,7.5); // Full-charge breathing continues at game time, not browser frame rate.
 orange.release(Math.PI);assert.equal(orange.state,'dash');assert.equal(orange.angle,Math.PI);assert.equal(orange.boost,18);
 orange.press();assert.equal(orange.state,'dash','no recharging during dash');
 let old=orange.boost;for(let i=0;i<fps;i++){orange.advance(1/fps);assert(orange.boost<=old);old=orange.boost;}
 assert.equal(orange.state,'idle');assert.equal(sounds.filter(s=>s[0]==='dash').length,1);
 orange.press();orange.cancel();orange.release(0);assert.equal(orange.state,'idle');assert.equal(orange.active,false);
}
const tap=orangeModel();tap.press();tap.release(0);assert.equal(tap.charge,8,'tap still dashes');
const partial=orangeModel();partial.press();partial.advance(8/30);partial.release(0);assert.equal(partial.charge,12);
const a={left:0,right:100,y:100},b={left:200,right:400,y:250},c={left:0,right:500,y:800};
assert.equal(nearest([a,b,c],300,245).y,250);assert.equal(nearest([],0,0),null);
assert.equal(neighbor([c,a,b],a,1),b);assert.equal(neighbor([a,b,c],c,1),null);
assert.equal(neighbor([a,b,c],b,-1),a);
const controls={},first={},second={};
const rails=[{element:controls,edge:'bottom',y:180},{element:first,edge:'top',y:-20},{element:second,edge:'top',y:300}];
assert.equal(neighbor(rails,rails[2],-1),rails[1],'upward travel reaches occluded document rail, not sticky toolbar');
const p=advance({x:200,y:230},{dx:0,dy:-70},{width:800,height:600,scrollY:500,scrollMax:2000,topMargin:220});
assert.equal(p.y,220);assert.equal(p.scroll,-60,'camera keeps purple soul below sticky toolbar');
console.log('Extra souls: green delay/reset at 30/60/144Hz; orange tap/full/cancel/cooldown; real-rail selection and sticky camera passed.');
// Horizontal layout: choose the nearest column, walk its length, hop across rows, then return upward
// to an occluded previous row rather than getting trapped against the sticky toolbar.
const row1={},row2={},top={element:{id:'controls'},edge:'bottom',left:0,right:1000,y:180};
const v1={element:{},group:row1,edge:'left',axis:'y',x:340,top:250,bottom:400};
const v2={element:{},group:row1,edge:'left',axis:'y',x:660,top:250,bottom:400};
const v3={element:{},group:row2,edge:'left',axis:'y',x:340,top:520,bottom:700};
const v4={element:{},group:row2,edge:'left',axis:'y',x:660,top:520,bottom:700};
const tracks=[top,v1,v2,v3,v4];
assert.deepEqual(project(v1,390,310),{x:340,y:310});
assert.deepEqual(project(v1,390,900),{x:340,y:400});
assert.equal(nearest(tracks,650,330).element,v2.element);
assert.equal(neighbor(tracks,top,1,{x:680,y:180}),v2);
assert.equal(neighbor(tracks,v2,1,{x:660,y:400}),v4);
assert.equal(neighbor(tracks,v4,-1,{x:660,y:520}),v2);
assert.equal(neighbor(tracks,v2,-1,{x:660,y:300},'x'),v1);
assert.equal(neighbor(tracks,v1,1,{x:340,y:300},'x'),v2);
assert.equal(neighbor(tracks,v4,1,{x:660,y:700}),null);
assert.equal(neighbor(tracks,v1,-1,{x:340,y:250}),top);
assert.equal(neighbor(tracks,v1,-1,{x:340,y:300},'x'),null);
assert.equal(emitsTrail('orange','idle',false),false);
assert.equal(emitsTrail('orange','charge',false),false);
assert.equal(emitsTrail('orange','dash',false),true);
assert.equal(emitsTrail('purple','idle',true),true);
assert.equal(emitsTrail('purple','idle',false),false);
console.log('Vertical rails: projection, row/column transitions, endpoints; dash-only trails and full-charge pulse passed.');
