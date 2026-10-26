'use strict';
const assert=require('node:assert/strict');
const {create}=require('../web/soul-yellow.js');
const view={width:20000,height:20000,scrollY:0},pose={x:1000,y:1000,angle:0};
for(let i=0;i<8;i++){
 const angle=i*Math.PI/4,s=create();s.press({...pose,angle});const b=s.bullets[0];
 const forward=(b.x-pose.x)*Math.cos(angle)+(b.y-pose.y)*Math.sin(angle);
 const side=-(b.x-pose.x)*Math.sin(angle)+(b.y-pose.y)*Math.cos(angle);
 assert(Math.abs(side)<1e-8,'spawn remains on the firing axis');
 assert(forward-18*1.5>=12-1e-8,'small-shot tail starts at the soul tip in all eight directions');
}
function trial(frames){const events=[],s=create(e=>events.push(e));s.press(pose);s.advance(frames/30,view);s.release(pose);return {s,events};}
assert.deepEqual(trial(4).events,['small','charge-stop'],'quick tap is one small shot');
assert.deepEqual(trial(5).events,['small','small','charge-stop'],'partial hold emits a release shot');
assert.deepEqual(trial(19).events,['small','charge-start','small','charge-stop'],'not yet charged');
assert.deepEqual(trial(20).events,['small','charge-start','big','charge-stop'],'20 steps completes charge');
{
 const events=[],s=create(e=>events.push(e));s.press(pose);s.press(pose);s.advance(3,view);
 assert.deepEqual(events,['small','charge-start'],'holding/repeated keydowns never auto-fire');
 s.release({...pose,angle:Math.PI/2});
 const big=s.bullets.find(b=>b.big);assert.equal(big.angle,Math.PI/2,'release uses current facing');
 const small=s.bullets.find(b=>!b.big);assert.equal(small.angle,0,'existing projectile keeps its direction');
 s.press(pose);assert.equal(events.filter(e=>e==='small').length,1,'big-shot recovery blocks small shot');
 s.release(pose);s.advance(5/30,view);s.press(pose);
 assert.equal(events.filter(e=>e==='small').length,2,'small shot returns after recovery');
}
{
 const s=create();for(let i=0;i<5;i++){s.press(pose);s.release(pose);}
 assert.equal(s.bullets.length,3,'small shot cap counts all live projectiles');
 s.press(pose);s.advance(20/30,view);s.release(pose);
 assert.equal(s.bullets.length,4,'charged release is not subject to the small-shot cap');
 assert.equal(s.bullets.filter(b=>b.big).length,1);
 s.cancel();assert.equal(s.active,false);assert.equal(s.bullets.length,0);assert.equal(s.down,false);
 s.press(pose);assert.equal(s.bullets.length,1,'cancel also clears recovery and held state');
}
{
 const s=create();s.press(pose);s.advance(20/30,view);s.release(pose);
 const big=s.bullets.find(b=>b.big),before={...big};s.advance(1/30,view);
 assert(big.speed>before.speed&&big.sx>before.sx&&big.sy<before.sy&&big.alpha>before.alpha,'big shot accelerates and unfolds');
}
for(const angle of [0,Math.PI/2,Math.PI,-Math.PI/2]){
 const s=create();s.press({x:100,y:100,angle});s.release(pose);s.advance(1,{width:200,height:200,scrollY:0});
 assert.equal(s.bullets.length,0,'projectiles are removed past every viewport edge');
}
{
 const a=create(),b=create();a.press(pose);b.press(pose);
 a.advance(1,view);for(let i=0;i<144;i++)b.advance(1/144,view);
 assert.equal(a.held,b.held);assert.deepEqual(a.bullets,b.bullets,'refresh rate does not change the game simulation');
 const c=create();c.press(pose);c.release(pose);c.advance(1/30,view);
 const y=c.bullets[0].y;c.advance(1/30,{...view,scrollY:300});
 assert.equal(c.bullets[0].y,y,'scroll changes camera, not projectile world position');
}
console.log('Yellow soul: tap/partial/full charge, cap/recovery, facing, acceleration, cancellation, edges and refresh-rate independence passed.');
