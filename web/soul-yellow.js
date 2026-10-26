'use strict';
((root)=>{
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
 const api={create,mount};if(typeof module==='object'&&module.exports)module.exports={...api,createAudio:audio};else root.YellowSoul=api;
})(typeof window==='undefined'?globalThis:window);
