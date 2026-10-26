'use strict';
((root)=>{
 const SCALE=1.5,STEP=1/30,clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 // Original CH5 charge/release and per-step dash slowdown; direction is a web adaptation.
 function orangeModel(emit=()=>{}){
  let state='idle',charge=0,glow=0,elapsed=0,boost=0,cooldown=0,angle=0,acc=0;
  return {
   press(){if(state!=='idle'||cooldown>0)return;state='charge';charge=0;glow=0;emit('charge');},
   release(facing){if(state!=='charge')return;charge=charge===16?16:8+charge/2;angle=facing;boost=2+charge;elapsed=0;state='dash';emit('dash');},
   advance(dt){acc+=dt;while(acc+1e-9>=STEP){acc-=STEP;cooldown=Math.max(0,cooldown-1);if(state==='charge'){charge=Math.min(16,charge+1);if(charge===16)glow+=0.5;emit('pitch',Math.min(0.5+charge*0.05,1));}if(state==='dash'){elapsed++;boost*=Math.max(0,1-elapsed/(4+charge));if(boost<=1){state='idle';boost=0;cooldown=2;}}}},
   cancel(){state='idle';charge=0;boost=0;cooldown=0;acc=0;emit('stop');},
   get state(){return state;},get charge(){return charge;},get glow(){return glow;},get boost(){return boost;},get angle(){return angle;},get active(){return state!=='idle'||cooldown>0;}
  };
 }
 function greenDelay(){let direction='',held=0;return {reset(){direction='';held=0;},advance(dx,dy,dt){const d=dx+','+dy;if(d!==direction){direction=d;held=0;}const before=held;held+=dt;return dx||dy?Math.max(0,held-1)-Math.max(0,before-1):0;}};}
 function project(r,x,y){return r.axis==='y'?{x:r.x,y:clamp(y,r.top,r.bottom)}:{x:clamp(x,r.left,r.right),y:r.y};}
 function nearest(rails,x,y){return rails.reduce((best,r)=>{const p=project(r,x,y),distance=Math.hypot(x-p.x,y-p.y);return !best||distance<best.distance?{...r,distance}:best;},null);}
 function visibleContentRail(r,top,bottom){
  if(r.element?.id==='controls')return null;
  if(r.axis==='y'){const low=Math.max(r.top,top),high=Math.min(r.bottom,bottom);return low<=high?{...r,top:low,bottom:high}:null;}
  return r.y>=top&&r.y<=bottom?r:null;
 }
 function toolbarExit(rails,point,top,bottom){
  const visible=rails.map(r=>visibleContentRail(r,top,bottom)).filter(Boolean);
  // After wheel scrolling, re-enter the content in view, not the first record in the document.
  // With no visible separator, permit scrolling to the next one below the viewport.
  const below=rails.filter(r=>r.element?.id!=='controls'&&(r.axis==='y'?r.top:r.y)>bottom);
  return nearest(visible.length?visible:below,point.x,point.y);
 }
 // Document order survives sticky occlusion. Parallel vertical rules in one row share a group.
 function neighbor(rails,current,direction,point={x:current.x??current.left,y:current.y},axis='y'){
  if(axis==='x')return rails.filter(r=>r!==current&&r.axis==='y'&&r.group===current.group&&direction*(r.x-point.x)>2).sort((a,b)=>Math.abs(a.x-point.x)-Math.abs(b.x-point.x))[0]||null;
  const index=rails.findIndex(r=>r.element===current.element&&r.edge===current.edge);
  if(index>=0&&current.element){
   const group=r=>r.group??r;
   let i=index+direction;while(i>=0&&i<rails.length&&group(rails[i])===group(rails[index]))i+=direction;
   if(i<0||i>=rails.length)return null;
   const candidates=rails.filter(r=>group(r)===group(rails[i]));
   const closest=nearest(candidates,point.x,point.y);return candidates.find(r=>r.element===closest.element&&r.edge===closest.edge);
  }
  return rails.filter(r=>direction*(r.y-current.y)>2).sort((a,b)=>direction*(a.y-b.y))[0]||null;
 }
 function emitsTrail(color,state,jumping){return color==='orange'?state==='dash':color==='purple'&&jumping;}
 function soundBank(){
  const names={wing:'snd_wing',dash:'snd_explosion_mmx3',charge:'snd_chargeshot_charge'};
  const raw=Promise.all(Object.entries(names).map(async([key,name])=>{const r=await fetch('assets/soul/audio/'+name+'.wav');if(!r.ok)throw Error(name);return [key,await r.arrayBuffer()];}));raw.catch(()=>{});
  let context,ready,loop,epoch=0,loopToken=0;const buffers={},voices=new Set();
  function unlock(){if(!context){context=new (root.AudioContext||root.webkitAudioContext)();ready=raw.then(items=>Promise.all(items.map(async([key,data])=>{buffers[key]=await context.decodeAudioData(data);})));}context.resume().catch(()=>{});return ready;}
  function voice(key,volume,pitch,repeat){const source=context.createBufferSource(),gain=context.createGain();source.buffer=buffers[key];source.playbackRate.value=pitch;source.loop=repeat;gain.gain.value=volume;source.connect(gain);gain.connect(context.destination);voices.add(source);source.onended=()=>{voices.delete(source);source.disconnect();gain.disconnect();};source.start();return source;}
  function stopLoop(){loopToken++;if(loop){loop.stop();loop=null;}}
  return {
   unlock(){unlock().catch(e=>console.warn('Soul audio:',e.message));},
   effect(key,volume=1,pitch=1){const token=epoch,at=performance.now();unlock().then(()=>{if(token===epoch&&performance.now()-at<250&&voices.size<12)voice(key,volume,pitch,false);}).catch(e=>console.warn('Soul audio:',e.message));},
   charge(){stopLoop();const token=loopToken;unlock().then(()=>{if(token===loopToken)loop=voice('charge',0.5,0.25,true);}).catch(e=>console.warn('Soul audio:',e.message));},
   pitch(value){if(loop)loop.playbackRate.value=value;},stopLoop,
   stop(){epoch++;stopLoop();for(const v of voices)v.stop();voices.clear();}
  };
 }
 function mount({button,home,motion,getColor,getAngle}){
  const art=button.querySelector('.soul-art'),axe=document.createElement('img');
  axe.className='soul-axe';axe.src='assets/soul/sprites/spr_spearblocker_0.png';axe.alt='';axe.setAttribute('aria-hidden','true');button.append(axe);
  const canvas=document.createElement('canvas');canvas.className='soul-effects soul-extra-effects';canvas.hidden=true;canvas.setAttribute('aria-hidden','true');document.body.append(canvas);const ctx=canvas.getContext('2d');
  // Local charge canvas shares the sprite's CSS rotation and center, just like the yellow soul.
  const chargeCanvas=document.createElement('canvas');chargeCanvas.className='soul-charge-effects soul-orange-charge';chargeCanvas.hidden=true;chargeCanvas.setAttribute('aria-hidden','true');art.append(chargeCanvas);const chargeCtx=chargeCanvas.getContext('2d');
  const images={};for(const [key,path] of Object.entries({orange:'spr_orangeheart2_0.png',purple:'spr_purpleheart_0.png',particle:'spr_yheart_charge_0.png',outline:'spr_orangeheart_outline_0.png',white:'spr_orangeheart_outline_1.png',inner:'spr_orangeheart_white_0.png',...Object.fromEntries(Array.from({length:5},(_,i)=>['dust'+i,'spr_pinkdust_'+i+'.png']))})){const img=new Image();img.src='assets/soul/sprites/'+path;images[key]=img;}
  const tinted={};
  function tint(key,fill){const id=key+fill;if(tinted[id])return tinted[id];const img=images[key];if(!img.complete||!img.naturalWidth)return null;const c=document.createElement('canvas');c.width=img.naturalWidth;c.height=img.naturalHeight;const g=c.getContext('2d');g.drawImage(img,0,0);g.globalCompositeOperation='source-in';g.fillStyle=fill;g.fillRect(0,0,c.width,c.height);return tinted[id]=c;}
  const sounds=soundBank(),delay=greenDelay();
  let angle=-Math.PI/2,lastDir='',trails=[],dust=[],trailClock=0,rail=null,jump=null,dirty=false,bump=0,repeat=0,command='',newDirection=false;
  const orange=orangeModel((kind,value)=>{if(kind==='charge')sounds.charge();if(kind==='pitch')sounds.pitch(value);if(kind==='dash'){sounds.stopLoop();sounds.effect('dash',0.5,2);}if(kind==='stop')sounds.stopLoop();});
  const color=()=>getColor();
  function rails(){
   const list=[],controls=document.getElementById('controls'),c=controls.getBoundingClientRect();
   if(c.width&&c.height){const style=getComputedStyle(controls);list.push({element:controls,edge:'top',left:c.left,right:c.right,y:c.top+parseFloat(style.borderTopWidth)/2},{element:controls,edge:'bottom',left:c.left,right:c.right,y:c.bottom-parseFloat(style.borderBottomWidth)/2});}
   // Only existing theme-colored borders; grey card edges are not tracks.
   for(const element of document.querySelectorAll('#list .language-cell')){
    const style=getComputedStyle(element),r=element.getBoundingClientRect();
    if(parseFloat(style.borderTopWidth)>0&&r.width&&r.height)list.push({element,edge:'top',left:r.left,right:r.right,y:r.top+parseFloat(style.borderTopWidth)/2});
    if(parseFloat(style.borderLeftWidth)>0&&r.width&&r.height)list.push({element,group:element.parentElement,edge:'left',axis:'y',x:r.left+parseFloat(style.borderLeftWidth)/2,top:r.top,bottom:r.bottom});
   }
   return list;
  }
  function locate(ref,list){return ref&&list.find(r=>r.element===ref.element&&r.edge===ref.edge);}
  function image(key,x,y,rotation=0,alpha=1){const img=images[key];if(!img?.complete||!img.naturalWidth)return;ctx.save();ctx.globalAlpha=alpha;ctx.translate(x,y);ctx.rotate(rotation);ctx.drawImage(img,-15,-15,30,30);ctx.restore();}
  function clear(){trails=[];dust=[];canvas.hidden=true;chargeCanvas.hidden=true;canvas.dataset.trails='0';ctx.clearRect(0,0,canvas.width,canvas.height);art.classList.remove('orange-charging');art.style.removeProperty('translate');button.dataset.extraState='idle';}
  function cancel(){orange.cancel();sounds.stop();delay.reset();jump=null;command='';newDirection=false;repeat=0;dirty=false;bump=0;clear();}
  function beginJump(target,position,screenEntry=false){
   const p=project(target,position.x+22,position.y+22),dist=Math.hypot(p.x-position.x-22,p.y-position.y-22);
   jump={target,screenEntry,remaining:clamp(dist/1800,0.1,0.26)};rail=target;repeat=0.3;
   sounds.effect('wing');dust.push({x:position.x+22,y:position.y+22+scrollY,age:0,dir:Math.sign(p.y-position.y-22)});
  }
  function visibleRails(list,height){const bottom=document.getElementById('controls').getBoundingClientRect().bottom;return list.filter(r=>r.axis==='y'?r.bottom>=bottom+15&&r.top<=height-22:r.y>=22&&r.y<=height-22&&(r.element.id==='controls'||r.y>=bottom+15));}
  function purpleStep({position,dx,dy,dt,bounds}){
   const list=rails();dirty=false;
   if(!list.length){rail=null;jump=null;return {...position,scroll:0};}
   if(!jump){
    const entering=!rail;
    const attached=locate(rail,list),visible=visibleRails(list,bounds.height);
    rail=attached&&visible.includes(attached)?attached:nearest(visible.length?visible:list,position.x+22,position.y+22);
    const cmd=dx+','+dy;if(cmd!==command){command=cmd;repeat=0;}
    repeat=Math.max(0,repeat-dt);
    const point={x:position.x+22,y:position.y+22};
    const axis=rail.axis==='y'&&dx?'x':'y',dir=axis==='x'?dx:dy;
    const atEnd=rail.axis!=='y'||(dy<0?point.y<=rail.top+1:point.y>=rail.bottom-1);
    if(entering&&(dx||dy))beginJump(rail,position);
    else if(dir&&(axis==='x'||atEnd)&&(newDirection||repeat===0)){
     const screenEntry=axis==='y'&&dir>0&&rail.element.id==='controls'&&rail.edge==='bottom';
     const target=screenEntry?toolbarExit(list,point,document.getElementById('controls').getBoundingClientRect().bottom+22,bounds.height-22):neighbor(list,rail,dir,point,axis);
     if(target)beginJump(target,position,screenEntry);else repeat=0.3;
    }
    newDirection=false;
   }
   if(jump){
    let target=locate(jump.target,list);
    if(!target){jump=null;rail=null;dirty=true;return {...position,scroll:0};}
    if(jump.screenEntry)target=visibleContentRail(target,document.getElementById('controls').getBoundingClientRect().bottom+22,bounds.height-22)||target;
    const t=Math.min(1,dt/Math.max(dt,jump.remaining));jump.remaining-=dt;
    const point=project(target,position.x+22,position.y+22),x=point.x-22;
    const controls=document.getElementById('controls').getBoundingClientRect();
    const targetY=point.y-22;
    let n;
    if(target.element.id==='controls'){
     // Reveal the header on the final upward hop; an affixed top border is off-screen otherwise.
     const scroll=target.edge==='top'?-bounds.scrollY*t:0;
     n={x:clamp(position.x+(x-position.x)*t,0,bounds.width-44),y:clamp(position.y+(targetY-position.y)*t,0,bounds.height-44),scroll};
    }else n=root.SoulMotion.advance(position,{dx:(x-position.x)*t,dy:(targetY-position.y)*t},{...bounds,topMargin:controls.bottom+36});
    if(jump.remaining<=0){bump=Math.sign(point.y-22-position.y)*5;jump=null;rail=target;}
    return n;
   }
   const p=project(rail,position.x+22+dx*360*dt,position.y+22+dy*360*dt);
   // Vertical rules use the same camera handoff as free movement. Horizontal rules follow the DOM.
   if(rail.axis==='y')return root.SoulMotion.advance(position,{dx:p.x-22-position.x,dy:p.y-22-position.y},{...bounds,topMargin:document.getElementById('controls').getBoundingClientRect().bottom+36});
   return {x:clamp(p.x-22,0,bounds.width-44),y:p.y-22,scroll:0};
  }
  function step(input){
   const {position,dx,dy,dt,bounds}=input,c=color(),length=Math.hypot(dx,dy)||1;
   trailClock+=dt;trails=trails.map(p=>({...p,age:p.age+dt})).filter(p=>p.age<0.3);dust=dust.map(p=>({...p,age:p.age+dt})).filter(p=>p.age<5/30);
   let next;
   if(c==='purple')next=purpleStep(input);
   else{
    let seconds=dt,speed=360;
    if(c==='green')seconds=delay.advance(dx,dy,dt);
    let mx=dx/length*speed*seconds,my=dy/length*speed*seconds;
    if(c==='orange'){
     orange.advance(dt);
     if(orange.state==='charge'){mx*=5/6;my*=5/6;}
     if(orange.state==='dash'){mx+=Math.cos(orange.angle)*orange.boost*45*dt;my+=Math.sin(orange.angle)*orange.boost*45*dt;}
     button.dataset.extraState=orange.state;
    }
    next=root.SoulMotion.advance(position,{dx:mx,dy:my},bounds);
   }
   if(trailClock>=STEP){trailClock%=STEP;if(emitsTrail(c,orange.state,!!jump)&&Math.hypot(next.x-position.x,next.y-position.y+(next.scroll||0))>0.1)trails.push({x:position.x+22,y:position.y+22+scrollY,angle:c==='orange'?getAngle():0,age:0,color:c});}
   return next;
  }
  function paintCharge(){
   const charging=color()==='orange'&&orange.state==='charge'&&['outline','white','inner'].every(k=>images[k].complete&&images[k].naturalWidth);chargeCanvas.hidden=!charging;art.classList.toggle('orange-charging',charging);if(!charging)return;
   const size=Math.round(160*(devicePixelRatio||1));if(chargeCanvas.width!==size){chargeCanvas.width=size;chargeCanvas.height=size;}
   chargeCtx.setTransform(size/160,0,0,size/160,0,0);chargeCtx.clearRect(0,0,160,160);chargeCtx.imageSmoothingEnabled=false;
   const draw=(img,x=65,y=65,alpha=1)=>{if(!img||!img.width)return;chargeCtx.globalAlpha=clamp(alpha,0,1);chargeCtx.drawImage(img,x,y,img.width*SCALE,img.height*SCALE);};
   // Original 7x7 particle, origin (3,3), orbit around local (9,10), rather than a stretched heart-sized square.
   if(orange.charge<16&&images.particle.complete&&images.particle.naturalWidth){
    const phase=orange.charge*2,dist=35-phase,scale=(4-phase*2/35)*SCALE;
    for(let i=0;i<4;i++){const a=(i*90+phase*5)*Math.PI/180;chargeCtx.globalAlpha=clamp(0.25+(orange.charge/10-0.2)*0.75,0,1);chargeCtx.drawImage(images.particle,80+(-1-Math.sin(a)*dist)*SCALE-3*scale,80-Math.cos(a)*dist*SCALE-3*scale,7*scale,7*scale);}
   }
   if(images.outline.complete&&images.outline.naturalWidth)draw(images.outline);
   // GML clips the white silhouette left-to-right, tints gold, then draws orange interior over it.
   // Rotating the entire local canvas makes this top-to-bottom when facing down.
   chargeCtx.save();chargeCtx.beginPath();chargeCtx.rect(65,65,Math.min(20,orange.charge*1.25)*SCALE,30);chargeCtx.clip();draw(tint('white','#ffd020'));chargeCtx.restore();
   draw(tint('inner','#ffa040')); // GML c_orange = BGR 0x40a0ff; gold is its 50% blend with c_yellow.
   if(orange.charge===16&&images.white.complete&&images.white.naturalWidth)draw(images.white,65,65,0.5+Math.sin(orange.glow)*0.5);
   chargeCanvas.dataset.charge=String(orange.charge);
  }
  function paint(position){
   if(bump){art.style.translate='0 '+bump+'px';bump=Math.abs(bump)<1?0:-bump*0.5;}else art.style.removeProperty('translate');
   paintCharge();canvas.dataset.trails=String(trails.length);
   const active=trails.length||dust.length;canvas.hidden=!active;if(!active)return;
   // CSS viewport excludes the scrollbar. Use the actual displayed box, including fractional pixels.
   const dpr=devicePixelRatio||1,rect=canvas.getBoundingClientRect(),w=rect.width,h=rect.height;
   if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);}
   ctx.setTransform(canvas.width/w,0,0,canvas.height/h,0,0);ctx.clearRect(0,0,w,h);ctx.imageSmoothingEnabled=false;
   for(const p of trails)image(p.color,p.x,p.y-scrollY,p.angle,Math.max(0,0.5-p.age*(p.color==='purple'?1.875:1.5)));
   for(const p of dust){const img=images['dust'+Math.min(4,Math.floor(p.age*30))];if(!img.complete||!img.naturalWidth)continue;ctx.save();ctx.translate(p.x,p.y-scrollY);ctx.rotate(p.dir<0?0:Math.PI);for(const mirror of [-1,1]){ctx.save();ctx.scale(mirror,1);ctx.globalAlpha=1-p.age*4;ctx.drawImage(img,-30,0,30,30);ctx.restore();}ctx.restore();}
  }
  function schedule(){
   if(color()!=='purple'||!motion.roaming())return;
   if(motion.canInteract()){dirty=true;motion.wake();return;}
   // Reflow also happens while typing a new query. Repair the attachment without consuming input.
   const list=visibleRails(rails(),innerHeight);
   const p=motion.pose(),target=locate(rail,list)||nearest(list,p.x+22,p.y+22);
   if(target){rail=target;const projected=project(target,p.x+22,p.y+22);motion.relocate({x:projected.x-22,y:projected.y-22});}
  }
  addEventListener('scroll',schedule,{passive:true});addEventListener('resize',schedule);
  new ResizeObserver(schedule).observe(document.getElementById('results'));
  new ResizeObserver(schedule).observe(document.getElementById('controls'));
  new MutationObserver(schedule).observe(document.getElementById('list'),{childList:true,subtree:true});
  addEventListener('keydown',e=>{
   if(color()!=='orange'||e.code!=='KeyZ'||e.repeat||e.isComposing||e.ctrlKey||e.metaKey||e.altKey||!motion.canInteract())return;
   e.preventDefault();sounds.unlock();orange.press();motion.prepare();motion.wake();
  });
  addEventListener('keyup',e=>{if(e.code==='KeyZ'&&color()==='orange'){if(!motion.canInteract()){cancel();return;}orange.release(getAngle());motion.wake();}});
  home.addEventListener('click',()=>{cancel();rail=null;});
  button.addEventListener('soul-return',()=>{rail=null;});
  return {
   step,paint,cancel,depart(){rail=null;},
   get active(){return ['green','orange','purple'].includes(color())&&(orange.active||!!jump||dirty||!!bump||trails.length>0||dust.length>0);},
   direction(dx,dy){if(color()!=='green')return;const dir=Math.atan2(dy,dx);axe.style.transform='translate(-50%,-50%) rotate('+dir+'rad)';const label=dx+','+dy;if(label!==lastDir){sounds.effect('wing',0.8);lastDir=label;}angle=dir;},
   key(key,down){if(!down)delay.reset();if(down){sounds.unlock();newDirection=true;}},
   drop(){if(color()==='purple'){rail=null;dirty=true;motion.wake();}},
   sync(){cancel();rail=null;lastDir='';angle=-Math.PI/2;axe.hidden=color()!=='green';axe.style.transform='translate(-50%,-50%) rotate('+angle+'rad)';if(color()==='purple'&&motion.roaming())schedule();}
  };
 }
 const api={mount,orangeModel,greenDelay,nearest,neighbor,project,emitsTrail,visibleContentRail,toolbarExit,createSoundBank:soundBank};
 if(typeof module==='object'&&module.exports)module.exports=api;else root.ExtraSouls=api;
})(typeof window==='undefined'?globalThis:window);
