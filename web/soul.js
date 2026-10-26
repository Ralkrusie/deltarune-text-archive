'use strict';
// One entry for the optional soul interaction; each section owns its local state.
((root)=>{

 // Movement, dragging, recall and viewport scrolling
 const movement = (()=>{
 const clamp=(n,lo,hi)=>Math.min(Math.max(n,lo),hi);
 function advance(position, delta, bounds){
  const maxX=Math.max(0,bounds.width-44),maxY=Math.max(0,bounds.height-44);
  const edge=Math.min(72,maxY/3),upper=Math.min(bounds.topMargin??edge,maxY/2),lower=maxY-edge;
  const x=clamp(position.x,0,maxX),y=clamp(position.y,0,maxY);
  let scroll=0;
  if(delta.dy>0){
   const surplus=Math.max(0,delta.dy-Math.max(0,lower-y));
   scroll=Math.min(surplus,Math.max(0,bounds.scrollMax-bounds.scrollY));
  }else if(delta.dy<0){
   const surplus=Math.max(0,-delta.dy-Math.max(0,y-upper));
   scroll=-Math.min(surplus,Math.max(0,bounds.scrollY));
  }
  return {x:clamp(x+delta.dx,0,maxX),y:clamp(y+delta.dy-scroll,0,maxY),scroll};
 }
 function mount({button,home,isEnabled,isKeyboardEnabled,onDirection=()=>{}}){
  const desktop=matchMedia('(hover: hover) and (pointer: fine)');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const keys=new Set();
  let position=null,drag=null,frame=0,lastTime=0,flight=null,suppressClick=false,controller=null;
  const bounds=()=>({width:document.documentElement.clientWidth,height:innerHeight,
   scrollY:window.scrollY,scrollMax:Math.max(0,document.documentElement.scrollHeight-innerHeight)});
  const allowed=()=>desktop.matches&&isEnabled();
  const editing=target=>target instanceof Element&&!!target.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"]),dialog,[role="textbox"],[role="combobox"],[role="slider"]');
  const blocked=()=>!allowed()||document.hidden||!!document.querySelector('dialog[open]')||editing(document.activeElement);
  function paint(){
   button.style.left=position.x+'px';button.style.top=position.y+'px';
  }
  function detach(){
   // Tab focus remains visible until actual play starts; it is not part of the game sprite.
   if(document.activeElement===button)button.blur();
   if(position)return;
   controller?.depart?.();
   const r=button.getBoundingClientRect(),b=bounds();
   position=advance({x:r.left,y:r.top},{dx:0,dy:0},b);
   button.classList.add('is-roaming');home.hidden=false;paint();
  }
  function stopKeys(){keys.clear();lastTime=0;if(frame&&!flight){cancelAnimationFrame(frame);frame=0;}}
  function wake(){if(!frame&&!flight&&allowed()){lastTime=performance.now();frame=requestAnimationFrame(tick);}}
  function cancel(){flight=null;stopKeys();cancelDrag();controller?.cancel();}
  function cancelDrag(){
   if(drag&&button.hasPointerCapture(drag.id))button.releasePointerCapture(drag.id);
   drag=null;button.classList.remove('is-dragging');
  }
  function dock(){
   flight=null;cancel();
   position=null;button.classList.remove('is-roaming');button.style.removeProperty('left');button.style.removeProperty('top');home.hidden=true;
  }
  function tick(now){
   frame=0;
   if(!allowed()){dock();return;}
   if(flight){
    const t=Math.min(1,(now-flight.start)/flight.duration),ease=1-Math.pow(1-t,3);
    if(flight.toTop)window.scrollTo({top:flight.scrollFrom*(1-ease),behavior:'instant'});
    const target=home.getBoundingClientRect();
    // The home target covers the book; the original soul button starts at (28, 1).
    // For top recall, fly toward the book's final viewport position. Its current scrolled
    // position can be thousands of pixels above the viewport and must not pull the soul off-screen.
    const end={x:target.left+28,y:target.top+1+(flight.toTop?window.scrollY:0)};
    position={x:flight.from.x+(end.x-flight.from.x)*ease,y:flight.from.y+(end.y-flight.from.y)*ease};paint();
    if(t===1){dock();button.focus({preventScroll:true});return;}
   }else{
    if(blocked()||!isKeyboardEnabled()||drag){cancel();return;}
    if(!keys.size&&!controller?.active){stopKeys();return;}
    const dt=Math.min(0.05,(now-lastTime)/1000);lastTime=now;
    let dx=Number(keys.has('ArrowRight'))-Number(keys.has('ArrowLeft'));
    let dy=Number(keys.has('ArrowDown'))-Number(keys.has('ArrowUp'));
    const length=Math.hypot(dx,dy)||1;
    if(dx||dy)onDirection(dx,dy);
    detach();
    const next=controller?.step({position,dx,dy,dt,now,bounds:bounds()})||advance(position,{dx:dx/length*360*dt,dy:dy/length*360*dt},bounds());
    position={x:next.x,y:next.y};paint();
    if(next.scroll)window.scrollBy({top:next.scroll,behavior:'instant'});
    controller?.paint(position);
   }
   frame=requestAnimationFrame(tick);
  }
  function returnHome(toTop=false){
   if(!allowed()||(!position&&!toTop))return;
   cancel();
   button.dispatchEvent(new Event('soul-return'));
   detach();
   if(reduced.matches){if(toTop)window.scrollTo({top:0,behavior:'instant'});dock();button.focus({preventScroll:true});return;}
   flight={from:{...position},start:performance.now(),duration:toTop?600:300,toTop,scrollFrom:window.scrollY};frame=requestAnimationFrame(tick);
  }
  button.addEventListener('dragstart',event=>event.preventDefault());
  button.addEventListener('pointerdown',event=>{
   if(!allowed()||flight||event.pointerType!=='mouse'||event.button!==0)return;
   stopKeys();controller?.cancel();
   const r=button.getBoundingClientRect();
   drag={id:event.pointerId,x:event.clientX,y:event.clientY,lastX:event.clientX,lastY:event.clientY,offsetX:event.clientX-r.left,offsetY:event.clientY-r.top,moved:false};
   button.setPointerCapture(event.pointerId);
  });
  button.addEventListener('pointermove',event=>{
   if(!drag||event.pointerId!==drag.id)return;
   if(!drag.moved&&Math.hypot(event.clientX-drag.x,event.clientY-drag.y)<4)return;
   if(!drag.moved)button.blur();
   const dx=event.clientX-drag.lastX,dy=event.clientY-drag.lastY;
   if(dx||dy)onDirection(dx,dy);
   drag.lastX=event.clientX;drag.lastY=event.clientY;
   drag.moved=true;suppressClick=true;detach();button.classList.add('is-dragging');
   position=advance({x:event.clientX-drag.offsetX,y:event.clientY-drag.offsetY},{dx:0,dy:0},bounds());paint();event.preventDefault();
  });
  function release(){const moved=drag?.moved;cancelDrag();if(moved)controller?.drop();setTimeout(()=>{suppressClick=false;},0);}
  button.addEventListener('pointerup',release);
  button.addEventListener('pointercancel',release);
  button.addEventListener('lostpointercapture',()=>{drag=null;button.classList.remove('is-dragging');});
  button.addEventListener('click',event=>{
   if(suppressClick||flight){event.preventDefault();event.stopImmediatePropagation();suppressClick=false;}
  },true);
  home.addEventListener('click',()=>returnHome());
  button.addEventListener('contextmenu',event=>{if(!allowed())return;event.preventDefault();returnHome(true);});
  addEventListener('keydown',event=>{
   // A modifier may arrive after an arrow is already held. Hand that combination
   // back to the browser without swallowing bare Shift's color-switch events.
   if(['Shift','Control','Alt','Meta'].includes(event.key)){if(keys.size)cancel();return;}
   if(!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key))return;
   if(blocked()||!isKeyboardEnabled()||flight||drag||event.shiftKey||event.ctrlKey||event.altKey||event.metaKey)return;
   event.preventDefault();keys.add(event.key);
   if(!event.repeat)controller?.key(event.key,true);
   if(!frame){lastTime=performance.now();frame=requestAnimationFrame(tick);}
  });
  addEventListener('keyup',event=>{keys.delete(event.key);if(event.key.startsWith('Arrow'))controller?.key(event.key,false);if(!keys.size&&!controller?.active)stopKeys();});
  addEventListener('blur',cancel);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)cancel();});
  document.addEventListener('focusin',event=>{if(editing(event.target))cancel();});
  new MutationObserver(()=>{if(document.querySelector('dialog[open]'))cancel();}).observe(document.body,{subtree:true,attributes:true,attributeFilter:['open']});
  addEventListener('resize',()=>{if(position&&!flight){position=advance(position,{dx:0,dy:0},bounds());paint();}});
  desktop.addEventListener('change',()=>{if(!desktop.matches)dock();});
  return {
   sync(){cancel();if(!allowed())dock();controller?.sync();},
   setController(value){controller=value;},wake,
   roaming:()=>!!position,
   relocate(next){if(!position||!allowed()||flight||drag)return;position=advance(next,{dx:0,dy:0},bounds());paint();},
   canInteract:()=>!blocked()&&!flight&&!drag,
   prepare:detach,
   pose(){const r=button.getBoundingClientRect();return {x:r.left,y:r.top};}
  };
 }
 const api={advance,mount};
 return api;
 })();

 // Yellow soul: projectiles, charging and audio
 const yellowModule = (()=>{
 const SCALE=1.5, FRAME=1/30, BASE='assets/soul/sprites/', AUDIO='assets/soul/audio/';
 // CH2 obj_heart / obj_yheart_shot: 30 game steps per second, f=2.
 // Pose and projectiles use document coordinates so camera scrolling preserves their relationship.
 function create(emit=()=>{}){
  let held=0,down=false,delay=0,accumulator=0,bullets=[];
  function shoot(big,pose){
   if(!big&&(delay>0||bullets.length>=3))return;
   // The small sprite origin is 18px from its tail; place that tail at the soul's forward edge.
   const muzzle=big?0:(18+8)*SCALE;
   bullets.push({x:pose.x+Math.cos(pose.angle)*muzzle,y:pose.y+Math.sin(pose.angle)*muzzle,angle:pose.angle,big,speed:(big?8:16)*SCALE,
    sx:big?0.1:1,sy:big?2:1,alpha:big?0.5:1});
   emit(big?'big':'small');
  }
  return {
   press(pose){if(down)return;down=true;held=0;shoot(false,pose);},
   release(pose){
    if(!down)return;
    if(held>=20){shoot(true,pose);delay=5;}
    else if(held>=5)shoot(false,pose);
    down=false;held=0;emit('charge-stop');
   },
   advance(dt,view){
    accumulator+=dt;
    while(accumulator+1e-9>=FRAME){
     accumulator-=FRAME;if(delay>0)delay--;
     if(down){held++;if(held===10)emit('charge-start');}
     for(const p of bullets){
      if(p.big){p.alpha+=0.2;if(p.sx<1)p.sx+=0.2;if(p.sy>1)p.sy-=0.2;p.speed+=0.4*SCALE;}
      p.x+=Math.cos(p.angle)*p.speed;p.y+=Math.sin(p.angle)*p.speed;
     }
     bullets=bullets.filter(p=>p.x>=-90&&p.x<=view.width+90&&p.y>=view.scrollY-90&&p.y<=view.scrollY+view.height+90);
    }
   },
   cancel(){down=false;held=0;delay=0;accumulator=0;bullets=[];emit('cancel');},
   get held(){return held;},get down(){return down;},get bullets(){return bullets;},
   get active(){return down||bullets.length>0||delay>0;}
  };
 }
 function audio(){
  const files={small:'snd_heartshot_dr_b',charge:'snd_chargeshot_charge',big:'snd_chargeshot_fire'};
  let context=null,loading=null,bytes=null,loop=null,epoch=0;
  const buffers={},voices=new Set();
  function preload(){
   if(!bytes)bytes=Promise.all(Object.entries(files).map(async([key,file])=>{
    const response=await fetch(AUDIO+file+'.wav');if(!response.ok)throw new Error('Missing soul audio: '+file);
    return [key,await response.arrayBuffer()];
   }));
   // Keep failed optional audio from breaking movement/search; report the missing asset.
   bytes.catch(()=>{});
  }
  function unlock(){
   preload();
   if(!context){
    const Audio=root.AudioContext||root.webkitAudioContext;if(!Audio)return Promise.resolve();
    context=new Audio();
    loading=bytes.then(entries=>Promise.all(entries.map(async([key,data])=>{buffers[key]=await context.decodeAudioData(data);})))
     .catch(error=>console.warn('Soul audio unavailable:',error.message));
   }
   context.resume().catch(()=>{});return loading;
  }
  function start(key){
   if(!buffers[key]||!context)return null;
   // Bound overlapping sound tails when tapping rapidly.
   if(voices.size>=16){const oldest=voices.values().next().value;oldest.stop();voices.delete(oldest);}
   const source=context.createBufferSource(),gain=context.createGain();
   source.buffer=buffers[key];source.connect(gain);gain.connect(context.destination);voices.add(source);
   source.onended=()=>{voices.delete(source);source.disconnect();gain.disconnect();};
   return {source,gain};
  }
  function stopCharge(){if(loop){loop.source.stop();loop=null;}}
  return {
   preload,unlock,
   effect(key){
    const token=epoch,at=performance.now();
    unlock().then(()=>{if(token!==epoch||performance.now()-at>180)return;const voice=start(key);if(voice)voice.source.start();});
   },
   charge(held){
    if(!context||held<10)return;
    if(!loop){loop=start('charge');if(!loop)return;loop.source.loop=true;loop.gain.gain.setValueAtTime(0,context.currentTime);
     loop.gain.gain.linearRampToValueAtTime(0.3,context.currentTime+20/30);loop.source.start();}
    // Original z_hold advances by two: final pitch before the ready state is 1.0.
    loop.source.playbackRate.setValueAtTime(0.1+(Math.min(held,19)-10)/10,context.currentTime);
   },
   stopCharge,
   stop(){epoch++;stopCharge();for(const source of voices)source.stop();voices.clear();}
  };
 }
 function mount({button,sprite,home,motion,isYellow,getAngle}){
  const canvas=document.createElement('canvas');canvas.className='soul-effects';canvas.hidden=true;
  canvas.setAttribute('aria-hidden','true');document.body.append(canvas);
  // Charge art shares the soul's DOM transform: separate animation loops cannot leave a trailing halo.
  const chargeCanvas=document.createElement('canvas');chargeCanvas.className='soul-charge-effects';chargeCanvas.hidden=true;
  chargeCanvas.setAttribute('aria-hidden','true');sprite.before(chargeCanvas);
  const chargeCtx=chargeCanvas.getContext('2d');
  const ctx=canvas.getContext('2d'),sound=audio(),images={};
  let raf=0,last=0,active=false,ready=false,normalSource='',chargeSource='';
  for(const name of ['spr_yellowheart_0','spr_yellowheart_2','spr_yheart_charge_0','spr_yheart_shot_0','spr_yheart_bigshot_0']){
   const img=new Image();img.src=BASE+name+'.png';images[name]=img;
  }
  const model=create(event=>{
   if(event==='small'||event==='big')sound.effect(event);
   if(event==='charge-stop')sound.stopCharge();
   if(event==='cancel')sound.stop();
  });
  const view=()=>({width:document.documentElement.clientWidth,height:innerHeight,scrollY});
  const pose=()=>{const p=motion.pose();return {x:p.x+22,y:p.y+22+scrollY,angle:getAngle()};};
  function showCharge(){
   const next=model.down&&model.held>=20;
   if(next!==ready){ready=next;if(isYellow())sprite.src=next?chargeSource:normalSource;}
   button.dataset.charge=model.down?(ready?'ready':'charging'):'idle';
  }
  function resize(){
   const v=view(),ratio=Math.min(devicePixelRatio||1,2);
   const width=Math.round(v.width*ratio),height=Math.round(v.height*ratio);
   if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}
   ctx.setTransform(ratio,0,0,ratio,0,0);ctx.imageSmoothingEnabled=false;
   const chargeSize=Math.round(160*ratio);
   if(chargeCanvas.width!==chargeSize){chargeCanvas.width=chargeSize;chargeCanvas.height=chargeSize;}
   chargeCtx.setTransform(chargeSize/160,0,0,chargeSize/160,0,0);chargeCtx.imageSmoothingEnabled=false;
  }
  function image(name,x,y,ox,oy,sx=1,sy=sx,alpha=1,target=ctx){
   const img=images[name];if(!img.complete||!img.naturalWidth)return;
   target.save();target.globalAlpha=Math.min(1,Math.max(0,alpha));target.translate(x,y);target.scale(SCALE*sx,SCALE*sy);
   target.drawImage(img,-ox,-oy);target.restore();
  }
  function render(){
   resize();const v=view();ctx.clearRect(0,0,v.width,v.height);
   for(const p of model.bullets){
    ctx.save();ctx.translate(p.x,p.y-v.scrollY);ctx.rotate(p.angle);
    image(p.big?'spr_yheart_bigshot_0':'spr_yheart_shot_0',0,0,p.big?32:18,p.big?14:4,p.sx,p.sy,p.alpha);ctx.restore();
   }
   const z=model.held*2;
   chargeCanvas.hidden=!(model.down&&z>=15);
   chargeCtx.clearRect(0,0,160,160);
   if(model.down&&z>=15){
    chargeCtx.save();chargeCtx.translate(80,80);
    if(z>=35){
     let s=Math.abs(Math.sin((z-35)/10));image('spr_yellowheart_0',0,0,10,10,1+s,1+s,0.3,chargeCtx);
     s=Math.abs(Math.sin((z-35)/14));image('spr_yellowheart_0',0,0,10,10,1.2+s,1.2+s,0.3,chargeCtx);
    }
    const charge=Math.min(35,z-15);
    for(let i=0;i<4;i++){
     const a=(i*90+charge*5)*Math.PI/180,r=35-charge;
     image('spr_yheart_charge_0',(-1-Math.sin(a)*r)*SCALE,-Math.cos(a)*r*SCALE,3,3,4-charge*2/35,4-charge*2/35,charge/5,chargeCtx);
    }
    chargeCtx.restore();
   }
   canvas.dataset.projectiles=String(model.bullets.length);
  }
  function advance(now){model.advance(Math.min(0.1,Math.max(0,(now-last)/1000)),view());last=now;}
  function tick(now){
   raf=0;if(!active||!isYellow()||!motion.canInteract()){cancel();return;}
   advance(now);showCharge();sound.charge(model.held);render();
   if(model.active)raf=requestAnimationFrame(tick);else canvas.hidden=true;
  }
  function wake(){canvas.hidden=false;if(!raf){last=performance.now();raf=requestAnimationFrame(tick);}}
  function cancel(){
   if(raf)cancelAnimationFrame(raf);raf=0;model.cancel();showCharge();canvas.hidden=true;chargeCanvas.hidden=true;canvas.dataset.projectiles='0';
  }
  addEventListener('keydown',event=>{
   if(event.code!=='KeyZ'||event.isComposing||event.ctrlKey||event.altKey||event.metaKey)return;
   if(!active||!isYellow()||!motion.canInteract())return;
   event.preventDefault();if(event.repeat||model.down)return;
   motion.prepare();sound.unlock();if(raf)advance(performance.now());model.press(pose());showCharge();render();wake();
  });
  addEventListener('keyup',event=>{
   if(event.code!=='KeyZ'||!model.down)return;
   if(!active||!isYellow()||!motion.canInteract()){cancel();return;}
   event.preventDefault();advance(performance.now());model.release(pose());showCharge();render();wake();
  });
  addEventListener('blur',cancel);document.addEventListener('visibilitychange',()=>{if(document.hidden)cancel();});
  document.addEventListener('focusin',()=>{if(!motion.canInteract())cancel();});
  // Also stop when a modal opens without moving focus; callback is event driven, not an idle polling loop.
  for(const dialog of document.querySelectorAll('dialog'))new MutationObserver(()=>{if(dialog.open)cancel();}).observe(dialog,{attributes:true,attributeFilter:['open']});
  home.addEventListener('click',cancel);button.addEventListener('pointerdown',cancel);button.addEventListener('soul-return',cancel);
  return {sync(){
   cancel();active=isYellow();
   if(active){
    normalSource=BASE+'spr_yellowheart_0.png';chargeSource=BASE+'spr_yellowheart_2.png';sprite.src=normalSource;sound.preload();
    // Clicking into yellow mode can decode the effects before the first shot, without playing them.
    if(navigator.userActivation?.isActive)sound.unlock();
   }
   else{canvas.width=1;canvas.height=1;}
  }};
 }
 return {create,mount,createAudio:audio};
 })();

 // Color-switch audio
 const switchAudio = (()=>{
 function create(env=globalThis){
  let context, buffer, decoding, source, generation=0;
  // Fetch ahead, but create/resume the audio context only after a user click.
  const bytes=env.fetch('assets/soul/audio/snd_great_shine.ogg').then(r=>{
   if(!r.ok)throw new Error('Soul switch audio: '+r.status);
   return r.arrayBuffer();
  });
  bytes.catch(()=>{});
  function stop(){generation++;if(source){source.stop();source.disconnect();source=null;}}
  async function play(){
   stop();const token=generation;
   try{
    context ||= new env.AudioContext();
    const resume=context.resume();
    decoding ||= bytes.then(raw=>context.decodeAudioData(raw)).then(value=>buffer=value);
    await Promise.all([resume,decoding]);
    if(token!==generation)return;
    const voice=context.createBufferSource();
    voice.buffer=buffer;voice.playbackRate.value=0.8;
    voice.connect(context.destination);source=voice;
    voice.onended=()=>{voice.disconnect();if(source===voice)source=null;};
    voice.start();
   }catch(error){env.console.warn('灵魂切换音效未能播放',error);}
  }
  return {play,stop};
 }
 return {create};
 })();

 // Green, orange and purple: shared effects and movement controller
 const variants = (()=>{
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
    }else n=movement.advance(position,{dx:(x-position.x)*t,dy:(targetY-position.y)*t},{...bounds,topMargin:controls.bottom+36});
    if(jump.remaining<=0){bump=Math.sign(point.y-22-position.y)*5;jump=null;rail=target;}
    return n;
   }
   const p=project(rail,position.x+22+dx*360*dt,position.y+22+dy*360*dt);
   // Vertical rules use the same camera handoff as free movement. Horizontal rules follow the DOM.
   if(rail.axis==='y')return movement.advance(position,{dx:p.x-22-position.x,dy:p.y-22-position.y},{...bounds,topMargin:document.getElementById('controls').getBoundingClientRect().bottom+36});
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
    next=movement.advance(position,{dx:mx,dy:my},bounds);
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
 return api;
 })();

 // Theme preferences, color switching and page event wiring.
 function mount(){
 const souls = [
  {id:'red', name:'红色', sprite:'spr_dodgeheart_0.png'},
  {id:'yellow', name:'黄色', sprite:'spr_yellowheart_0.png'},
  {id:'green', name:'绿色', sprite:'spr_greenheart_0.png'},
  {id:'orange', name:'橙色', sprite:'spr_orangeheart2_0.png'},
  {id:'purple', name:'紫色', sprite:'spr_purpleheart_0.png'},
 ];
 const storageKey='dialogue-soul-preferences';
 let saved;try{saved=JSON.parse(localStorage.getItem(storageKey)||'null');}catch{}
 let enabled=saved?.enabled!==false;
 let index=Math.max(0,souls.findIndex(s=>s.id===saved?.color));
 const button=document.getElementById('soul-button');
 const sprite=document.getElementById('soul-sprite');
 const toggle=document.getElementById('soul-enabled');
 const dialog=document.getElementById('settings-dialog');
 const status=document.getElementById('soul-status');
 let angle=Math.PI/2;
 const isYellow=()=>enabled&&souls[index].id==='yellow';
 const home=document.getElementById('soul-home');
 let special;
 const motion=movement.mount({button,home,isEnabled:()=>enabled,
  isKeyboardEnabled:()=>enabled,
  onDirection(dx,dy){if(isYellow()||souls[index].id==='orange'){angle=Math.atan2(dy,dx);button.style.setProperty('--soul-angle',angle+'rad');}special?.direction(dx,dy);}
 });
 special=variants.mount({button,home,motion,getColor:()=>enabled?souls[index].id:null,getAngle:()=>angle});
 motion.setController(special);
 const yellow=yellowModule.mount({button,sprite,home,motion,isYellow,getAngle:()=>angle});
 const switchSound=switchAudio.create();
 // Original sprite silhouettes, shared local coordinates with the moving/rotating soul.
 const flashCanvas=document.createElement('canvas');
 flashCanvas.className='soul-switch-flash';flashCanvas.hidden=true;flashCanvas.setAttribute('aria-hidden','true');
 button.querySelector('.soul-art').append(flashCanvas);
 const flashCtx=flashCanvas.getContext('2d'),flashFrames=new Map(),reducedFlash=matchMedia('(prefers-reduced-motion: reduce)');
 let flashFrame=0;
 for(const soul of souls){
  const img=new Image();img.onload=()=>{
   const colored=document.createElement('canvas');colored.width=img.naturalWidth;colored.height=img.naturalHeight;
   const g=colored.getContext('2d');g.drawImage(img,0,0);
   const pixels=g.getImageData(0,0,colored.width,colored.height);
   // Black outline is not luminous. Preserve the original colored pixels and their alpha.
   for(let i=0;i<pixels.data.length;i+=4)if(pixels.data[i]+pixels.data[i+1]+pixels.data[i+2]<24)pixels.data[i+3]=0;
   g.putImageData(pixels,0,0);
   const white=document.createElement('canvas');white.width=colored.width;white.height=colored.height;
   const w=white.getContext('2d');w.drawImage(colored,0,0);w.globalCompositeOperation='source-in';w.fillStyle='#fff';w.fillRect(0,0,white.width,white.height);
   flashFrames.set(soul.id,{colored,white});
  };img.src='assets/soul/sprites/'+soul.sprite;
 }
 function stopFlash(){cancelAnimationFrame(flashFrame);flashFrame=0;flashCanvas.hidden=true;}
 function playFlash(){
  stopFlash();if(reducedFlash.matches)return;
  const id=souls[index].id,start=performance.now(),size=Math.round(160*(devicePixelRatio||1));
  flashCanvas.width=size;flashCanvas.height=size;flashCanvas.hidden=false;
  function paint(now){
   const t=Math.min(1,(now-start)/450);if(t===1){stopFlash();return;}
   flashCtx.setTransform(size/160,0,0,size/160,0,0);flashCtx.clearRect(0,0,160,160);flashCtx.imageSmoothingEnabled=false;
   const frames=flashFrames.get(id);
   if(frames){
    const draw=(img,scale,alpha)=>{const s=30*scale;flashCtx.globalAlpha=Math.max(0,alpha);flashCtx.drawImage(img,80-s/2,80-s/2,s,s);};
    draw(frames.colored,1+2.2*t,0.7*Math.pow(1-t,0.8));
    draw(frames.colored,1+1.3*t,0.8*(1-t));
    draw(frames.white,1,Math.min(1,(0.75-t)/0.6));
   }
   flashFrame=requestAnimationFrame(paint);
  }
  flashFrame=requestAnimationFrame(paint);
 }
 button.addEventListener('soul-return',stopFlash);home.addEventListener('click',stopFlash);
 window.addEventListener('blur',stopFlash);window.addEventListener('pagehide',stopFlash);
 document.addEventListener('visibilitychange',()=>{if(document.hidden)stopFlash();});
 reducedFlash.addEventListener('change',stopFlash);
 function apply(announce=false){
  stopFlash();
  const soul=souls[enabled?index:0];
  if(enabled)document.documentElement.dataset.soulTheme=soul.id;
  else delete document.documentElement.dataset.soulTheme;
  sprite.src='assets/soul/sprites/'+soul.sprite;
  button.dataset.soul=soul.id;
  button.disabled=!enabled;
  button.hidden=!enabled;
  motion.sync();
  angle=Math.PI/2;button.style.setProperty('--soul-angle',angle+'rad');yellow.sync();
  const label=enabled?`${soul.name}灵魂：点击切换为${souls[(index+1)%souls.length].name}`:'红色灵魂：互动已关闭';
  button.setAttribute('aria-label',label);
  toggle.checked=enabled;
  if(announce)status.textContent=enabled?`已切换为${soul.name}灵魂与主题`:'灵魂互动已关闭，已恢复蓝色主题';
 }
 function save(){try{localStorage.setItem(storageKey,JSON.stringify({enabled,color:souls[index].id}));}catch{}}
 function nextSoul(){if(!enabled)return;index=(index+1)%souls.length;apply(true);save();switchSound.play();playFlash();}
 button.addEventListener('click',nextSoul);
 // A bare Shift release only: do not consume the browser's modifier key or its shortcuts.
 const heldKeys=new Set();let shiftOnly=false;
 window.addEventListener('keydown',event=>{
  heldKeys.add(event.code||event.key);
  if(event.key!=='Shift'){shiftOnly=false;return;}
  if(event.repeat)return;
  shiftOnly=heldKeys.size===1&&!event.ctrlKey&&!event.altKey&&!event.metaKey&&!event.isComposing&&motion.canInteract();
 });
 window.addEventListener('keyup',event=>{
  heldKeys.delete(event.code||event.key);
  if(event.key!=='Shift')return;
  const change=shiftOnly&&!heldKeys.size&&!event.ctrlKey&&!event.altKey&&!event.metaKey&&!event.isComposing&&motion.canInteract();
  shiftOnly=false;if(change)nextSoul();
 });
 const cancelShift=()=>{shiftOnly=false;};
 window.addEventListener('pointerdown',cancelShift);
 window.addEventListener('wheel',cancelShift,{passive:true});
 document.addEventListener('focusin',cancelShift);
 window.addEventListener('blur',()=>{cancelShift();heldKeys.clear();});
 document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelShift();heldKeys.clear();}});
 toggle.addEventListener('change',()=>{enabled=toggle.checked;switchSound.stop();apply(true);save();});
 window.addEventListener('pagehide',()=>switchSound.stop());
 document.getElementById('settings').addEventListener('click',()=>dialog.showModal());
 document.getElementById('close-settings').addEventListener('click',()=>dialog.close());
 dialog.addEventListener('click',e=>{
  if(e.target!==dialog)return;
  const b=dialog.getBoundingClientRect();
  if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)dialog.close();
 });
 // Theme settings stay separate from search preferences and shared query URLs.
 apply();
 }
 const api={movement,yellow:yellowModule,switchAudio,variants,mount};
 if(typeof module==='object'&&module.exports)module.exports=api;else mount();
})(typeof window==='undefined'?globalThis:window);
