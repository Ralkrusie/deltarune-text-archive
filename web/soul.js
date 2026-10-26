'use strict';
(() => {
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
 let extra;
 const motion=window.SoulMotion.mount({button,home,isEnabled:()=>enabled,
  isKeyboardEnabled:()=>enabled,
  onDirection(dx,dy){if(isYellow()||souls[index].id==='orange'){angle=Math.atan2(dy,dx);button.style.setProperty('--soul-angle',angle+'rad');}extra?.direction(dx,dy);}
 });
 extra=window.ExtraSouls.mount({button,home,motion,getColor:()=>enabled?souls[index].id:null,getAngle:()=>angle});
 motion.setController(extra);
 const yellow=window.YellowSoul.mount({button,sprite,home,motion,isYellow,getAngle:()=>angle});
 const switchSound=window.SoulSwitch.create();
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
})();
