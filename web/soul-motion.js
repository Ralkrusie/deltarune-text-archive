'use strict';
// Movement uses viewport coordinates; scroll consumes vertical travel at the camera margins.
((root) => {
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
 if(typeof module==='object'&&module.exports)module.exports=api;else root.SoulMotion=api;
})(typeof window==='undefined'?globalThis:window);
