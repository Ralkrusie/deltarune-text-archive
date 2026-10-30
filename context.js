(function(root){
'use strict';
function refs(node){
 const out=node.type==='message'?[node]:[];
 for(const c of node.children||[])out.push(...refs(c));
 if(node.prefix){
  for(const b of node.branches||[])out.push(b.option);
  out.push(...refs(node.prefix));
  for(const b of node.branches||[])out.push(...refs(b.body));
  return out;
 }
 for(const b of node.branches||[]){if(b.option)out.push(b.option);out.push(...refs(b.body));}
 return out;
}
function scenesFor(pack,chapter,key){return pack.scenes.filter(s=>s.chapter===chapter&&refs(s.body).some(r=>r.key===key));}
function fileOptions(index,key){
 const native=index.by_key[key]||[],related=index.related_by_key[key]||[];
 return [...new Set([...native,...related])].map(i=>({...index.files[i],related:!native.includes(i)}));
}
function emptySequence(n){
 return n.type==='sequence'&&!(n.entry_guards||[]).length&&(n.children||[]).every(emptySequence);
}
function displayBranches(n){
 // Only omit empty condition arms. An option or control-flow endpoint is content.
 return n.type==='condition'&&!n.revisit?n.branches.filter(b=>b.option||!emptySequence(b.body)):n.branches;
}
function lanes(n){
 if(n.revisit)return Math.max(1,...n.branches.map(b=>lanes(b.body)));
 if(n.branches)return Math.max(n.prefix?lanes(n.prefix):1,displayBranches(n).reduce((sum,b)=>sum+lanes(b.body),0));
 return Math.max(1,...(n.children||[]).map(lanes));
}
function flowWidth(n){
 if(n.branches){
  const widths=displayBranches(n).map(b=>flowWidth(b.body));
  return Math.max(256,n.prefix?flowWidth(n.prefix):0,n.revisit?Math.max(0,...widths):widths.reduce((a,b)=>a+b,0)+Math.max(0,widths.length-1)*20);
 }
 return Math.max(256,...(n.children||[]).map(flowWidth));
}
function mount({dialog,content,title,close,start,cell,actionMenu,getState}){
 const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 let serial=0,packPromise,observer;const chapters=new Map(),indexes=new Map(),chunks=new Map();
 async function json(path,options){const r=await fetch(path,options);if(!r.ok)throw Error('上下文数据未能加载');return r.json();}
 function stopObserver(){observer?.disconnect();observer=null;}
 async function load(){
  if(!packPromise)packPromise=Promise.all(['data/contexts.json','data/manifest.json'].map(path=>json(path,{cache:'no-cache'}))).then(([p,m])=>{if(![1,2].includes(p.schema)||p.text_manifest_sha256!==m.source_manifest_sha256)throw Error('上下文与当前文本版本不一致，请重新构建');return p;}).catch(e=>{packPromise=null;throw e;});
  return packPromise;
 }
 async function chapter(ch){
  if(!chapters.has(ch))chapters.set(ch,fetch(`data/ch${ch}.json`).then(r=>{if(!r.ok)throw Error('章节文本未能加载');return r.json();}).then(data=>new Map(data.rows.map(row=>{const decoded=root.DialogueText.decodeRow(data,row);return [decoded.key,decoded];}))).catch(e=>{chapters.delete(ch);throw e;}));
  return chapters.get(ch);
 }
 async function chunk(meta){
  if(!/^(?:index-ch[1-5]|files\/[a-f0-9]{24})\.json$/.test(meta.path))throw Error('上下文文件路径无效');
  if(!chunks.has(meta.path)){
   if(chunks.size>=4)chunks.delete(chunks.keys().next().value);
   chunks.set(meta.path,json('data/context/'+meta.path+'?v='+encodeURIComponent(meta.sha256)).catch(e=>{chunks.delete(meta.path);throw e;}));
  }
  return chunks.get(meta.path);
 }
 async function chapterIndex(pack,ch){
  if(!indexes.has(ch))indexes.set(ch,chunk(pack.chapters[ch]).then(index=>{if(index.chapter!==ch||index.text_manifest_sha256!==pack.text_manifest_sha256)throw Error('上下文索引版本不一致');return index;}).catch(e=>{indexes.delete(ch);throw e;}));
  return indexes.get(ch);
 }
 close.onclick=()=>dialog.close();start.onclick=()=>content.scrollTo({top:0,left:0});dialog.addEventListener('close',()=>{serial++;stopObserver();});
 let pan=null;
 content.addEventListener?.('pointerdown',e=>{
  if(e.button!==0||e.pointerType==='touch'||e.target.closest('article,button,a,input,select,label,p,code,h3'))return;
  pan={id:e.pointerId,x:e.clientX,y:e.clientY,left:content.scrollLeft,top:content.scrollTop};
  content.setPointerCapture(e.pointerId);content.classList.add('context-panning');e.preventDefault();
 });
 content.addEventListener?.('pointermove',e=>{
  if(!pan||pan.id!==e.pointerId)return;
  content.scrollLeft=pan.left+pan.x-e.clientX;content.scrollTop=pan.top+pan.y-e.clientY;
 });
 const endPan=()=>{pan=null;content.classList.remove('context-panning');};
 for(const event of ['pointerup','pointercancel','lostpointercapture'])content.addEventListener?.(event,endPan);
 const outside=e=>{const r=dialog.getBoundingClientRect();return e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom;};
 let backdropPress=false;
 dialog.addEventListener('pointerdown',e=>{backdropPress=e.target===dialog&&outside(e);});
 // Resizing may end outside the recentered dialog; it is not a backdrop click.
 dialog.addEventListener('click',e=>{if(backdropPress&&e.target===dialog&&outside(e))dialog.close();backdropPress=false;});
 async function show(row){
  const ticket=++serial;stopObserver();title.textContent='查看上下文';content.replaceChildren(el('p','context-note','正在加载…'));if(!dialog.open)dialog.showModal();
  try{
   const pack=await load();if(ticket!==serial)return;
   const index=pack.schema===2?await chapterIndex(pack,row.chapter):null;if(ticket!==serial)return;
   const options=index?fileOptions(index,row.key):scenesFor(pack,row.chapter,row.key).map(scene=>({file:scene.file,scene}));
   if(!options.length){content.replaceChildren(el('p','context-note',index?'当前章节源码中未找到这条文本的引用，暂时无法定位上下文。':'这个文件尚未生成上下文。'));return;}
   const table=await chapter(row.chapter);if(ticket!==serial)return;
   content.replaceChildren();const state=getState();
   const fileArea=el('div','context-file-area');
   if(options.length>1){
    const label=el('label','context-file-picker','源码文件 '),select=el('select');select.id='context-file-select';select.setAttribute('aria-label','上下文源码文件');
    options.forEach((option,i)=>{const item=el('option','',(option.related?'关联调用 · ':'')+option.file);item.value=String(i);select.append(item);});
    select.onchange=()=>renderFile(options[Number(select.value)]);label.append(select);content.append(label);
   }
   content.append(fileArea);
   function message(ref,option=false){
    const item=table.get(ref.key)|| (ref.binding==='missing_key'?{key:ref.key,chapter:row.chapter,en:ref.source_english,ja:null,zh_default:null,zh_names:null,zh_recruitable:null}:null);if(!item)throw Error('上下文引用的台词缺失');
    const card=el('article','context-message'+(option?' context-option':'')+(ref.key===row.key?' context-current':''));card.dataset.key=ref.key;card.dataset.occurrence=ref.occurrence_id;
    if(ref.key===row.key)card.append(el('span','context-current-label','当前台词'));
    if(ref.binding)card.append(el('p','context-binding',ref.binding==='missing_key'?'源码引用未收录于当前文本库':'源码原串与当前文本库不同；正文显示文本库版本'));
    const languages=el('div','context-languages');card.append(languages);
    const fill=()=>{languages.replaceChildren();languages.style.minHeight='';for(const lang of state.lang)languages.append(cell(item,lang));card.dataset.loaded='true';};
    if(ref.key===row.key||!observer)fill();
    else{languages.style.minHeight=(state.lang.length*(state.compact?40:85))+'px';languages.append(el('span','context-note','…'));pending.set(card,fill);observer.observe(card);}
    const evidence=el('div','context-source');
    evidence.append(el('code','',ref.key));const link=el('a','','wiki 源码 · L'+ref.source.line);link.href=root.DialogueActions.sourceURL(row.chapter,ref.source.file,ref.source.line);link.target='_blank';link.rel='noopener noreferrer';evidence.append(link);if(state.compact&&actionMenu){const tools=el('div','context-tools');tools.append(actionMenu(evidence));card.append(tools);}else card.append(evidence);return card;
   }
   const landings=new Map();
   function node(n){
    const guards=(n.entry_guards||[]).filter(g=>g.visible);
    if(guards.length){
     const wrapper=el('div','context-guarded');
     for(const guard of guards){
      const label=el('p','context-condition','前置：'+guard.condition);
      label.title=`L${guard.source.line} 的退出检查未触发；此处记录通过检查时的条件，不代表后续变量不变。`;
      wrapper.append(label);
     }
     wrapper.append(node({...n,entry_guards:[]}));return wrapper;
    }
    if(n.type==='message')return message(n);
    if(n.type==='jump'){
     const link=el('button','context-jump',n.label);link.type='button';link.title=n.condition||'';
     link.onclick=()=>landings.get(n.target)?.scrollIntoView({block:'start',behavior:'smooth'});return link;
    }
    if(n.type==='end'||n.type==='join')return el('p','context-end',n.label);
    if(n.type==='blocks'){
     const blocks=el('div','context-blocks');for(const c of n.children)blocks.append(node(c));return blocks;
    }
    if(n.type==='block'){
     const block=el('section','context-block');if(n.label)block.append(el('div','context-block-label',n.label));
     if(n.anchor)landings.set(n.anchor,block);
     if(n.guard)block.append(el('p','context-condition',n.guard));
     block.append(node({type:'sequence',children:n.children}));return block;
    }
    if(n.type==='sequence'){
     const seq=el('div','context-sequence');for(const [i,c] of n.children.entries()){if(i&&c.usage!=='reference'&&n.children[i-1].usage!=='reference')seq.append(el('div','context-connector','↓'));seq.append(node(c));}if(!n.children.length)seq.append(el('p','context-empty','—'));return seq;
    }
    const group=el('section','context-fork '+n.type+(n.revisit?' context-revisit':''));if(n.title)group.append(el('h3','context-fork-title',n.title));
    if(n.auto_answer)group.append(el('p','context-note',n.auto_answer.condition+' → 选项 '+(n.auto_answer.option+1)));
    const shown=displayBranches(n);
    const columns=n.revisit?'minmax(256px,1fr)':shown.map(b=>`minmax(${flowWidth(b.body)}px,${lanes(b.body)}fr)`).join(' ');
    function lines(reverse=false){
     const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
     svg.dataset.columns=shown.length;
     svg.setAttribute('class','context-join-lines');svg.setAttribute('viewBox','0 0 100 24');
     svg.setAttribute('preserveAspectRatio','none');svg.setAttribute('aria-hidden','true');
     const weights=shown.map(b=>lanes(b.body)),total=weights.reduce((a,b)=>a+b,0);let left=0;
     for(const weight of weights){
      const x=(left+weight/2)/total*100;left+=weight;
      const path=document.createElementNS(svg.namespaceURI,'path');
      path.setAttribute('d',reverse?`M 50 0 V 14 H ${x} V 24`:`M ${x} 0 V 10 H 50 V 24`);path.setAttribute('fill','none');
      path.setAttribute('stroke','currentColor');path.setAttribute('vector-effect','non-scaling-stroke');svg.append(path);
     }
     return svg;
    }
    if(n.prefix){
     const options=el('div','context-branches context-options');options.style.gridTemplateColumns=columns;
     options.dataset.columns=shown.length;
     for(const [i,b] of n.branches.entries()){
      const option=el('section','context-branch');option.append(el('span','context-branch-label','选项 '+(i+1)),message(b.option,true));options.append(option);
     }
     group.append(options,lines(),node(n.prefix),lines(true));
    }
    const branches=el('div','context-branches');
    branches.style.gridTemplateColumns=columns;
    branches.dataset.columns=shown.length;
    for(const [i,b] of shown.entries()){
     const branch=el('section','context-branch');
     if(b.option){
      branch.append(el('span','context-branch-label',n.prefix?'选项 '+(i+1):'选择'));
      if(!n.prefix)branch.append(message(b.option,true));
     }
     else if(n.revisit){
      const label=el('p','context-branch-label',i?'再次选择':'首次选择');
      label.title=b.label+(i?'（期间未重置该 flag）':`；L${n.revisit.write_line} 写入 ${n.revisit.to}`);
      branch.append(label,el('div','context-note',b.label));
     }else branch.append(el('p','context-condition',b.label));
     if(!(b.option&&b.body.type==='sequence'&&!b.body.children.length))branch.append(el('div','context-connector','↓'),node(b.body));
     branches.append(branch);
    }
    group.append(branches);
    if(n.join_next&&shown.length>1)group.append(lines());
    return group;
   }
   let pending=new WeakMap();
   async function renderFile(option){
    const current=++serial;stopObserver();pending=new WeakMap();landings.clear();fileArea.replaceChildren(el('p','context-note','正在加载文件…'));
    try{
     const data=option.scene?{scenes:[option.scene]}:await chunk(option);if(current!==serial)return;
     if(!option.scene&&(data.text_manifest_sha256!==pack.text_manifest_sha256||data.scenes[0].chapter!==row.chapter||data.scenes[0].file!==option.file))throw Error('上下文文件版本或身份不一致');
     observer=typeof IntersectionObserver==='undefined'?null:new IntersectionObserver(entries=>{for(const entry of entries){if(!entry.isIntersecting)continue;pending.get(entry.target)?.();pending.delete(entry.target);observer?.unobserve(entry.target);}},{root:dialog,rootMargin:'800px 0px'});
     fileArea.replaceChildren();
     for(const scene of data.scenes){
      const area=el('section','context-scene');area.append(el('h3','context-scene-title',scene.file||scene.title));
      area.style.minWidth=flowWidth(scene.body)+'px';
      area.append(node(scene.body));fileArea.append(area);
     }
     const target=fileArea.querySelector('.context-current');if(target)target.scrollIntoView({block:'center'});
    }catch(e){if(current===serial)fileArea.replaceChildren(el('p','context-note',e.message));}
   }
   await renderFile(options[0]);
  }catch(e){if(ticket===serial)content.replaceChildren(el('p','context-note',e.message),el('p','','关闭后可重试；未用源码行序代替缺失上下文。'));}
 }
 return {show};
}
const api={refs,scenesFor,fileOptions,lanes,flowWidth,mount};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.DialogueContext=api;
})(typeof globalThis!=='undefined'?globalThis:this);
