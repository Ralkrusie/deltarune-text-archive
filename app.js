'use strict';
(() => {
const T=window.DialogueText,M=window.DialogueModel,A=window.DialogueActions,$=id=>document.getElementById(id);
// Local files cannot reliably start the worker or fetch JSON. Explain before any initialization.
if(location.protocol==='file:'){
 $('status').textContent='请通过本地预览启动';
 $('error').hidden=false;
 $('error').querySelector('p').textContent='你正在直接打开 HTML。请双击项目根目录的 preview.cmd，或运行 python -m tools.site.serve --open。浏览器会通过本机 HTTP 地址加载文本，无需联网。';
 const link=document.createElement('a');link.href='http://127.0.0.1:8800/';link.textContent='已有 8800 预览服务？打开页面';$('error').append(link);
 $('retry').hidden=true;$('list').setAttribute('aria-busy','false');
 document.querySelectorAll('button,input').forEach(node=>node.disabled=true);
 return;
}

let preferences={};try{preferences=JSON.parse(localStorage.getItem('dialogue-preferences')||'{}')||{};}catch{}
let compact=preferences.compact===true;
document.documentElement.dataset.compact=String(compact);
$('compact-enabled').checked=compact;
let state=M.stateFrom(new URLSearchParams(location.search),preferences,matchMedia('(max-width:700px)').matches);
let worker,request=0,result=null,debounce,timer,searchTimer,busyRegex=false,restorePromise;
const LOAD_TIMEOUT=120000,SEARCH_TIMEOUT=30000,REGEX_TIMEOUT=8000;
const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(timer);timer=setTimeout(()=>$('toast').hidden=true,2300);}
async function copy(text){
 try{
  if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(text);
  else{const box=el('textarea');box.value=text;box.style.position='fixed';box.style.opacity='0';document.body.append(box);box.select();const ok=document.execCommand('copy');box.remove();if(!ok)throw Error();}
  toast('已复制');return true;
 }catch{toast('复制失败，请选中文本后手动复制');return false;}
}
function persist(historyMode='replace'){
 const url=new URL(location.href);url.search=M.paramsFor(state).toString();url.hash='';
 if(url.href!==location.href)history[historyMode==='push'?'pushState':'replaceState'](null,'',url);
 try{localStorage.setItem('dialogue-preferences',JSON.stringify({lang:state.lang.join(','),zh:state.zh,mode:state.mode,layout:state.layout,highlight:state.highlight,compact}));}catch{}
}
function buttons(container,items,selected,action){
 $(container).replaceChildren();
 for(const [value,label,title] of items){const b=el('button','',label);b.type='button';b.dataset.value=String(value);b.setAttribute('aria-pressed',String(selected(value)));if(title)b.title=title;b.onclick=()=>action(value);$(container).append(b);}
}
function controls(){
 $('results').hidden=state.mode==='restore';$('restore-preview').hidden=state.mode!=='restore';
 if(state.mode==='restore')loadRestorePreview();
 $('search').value=state.q;
 $('match-case').checked=state.caseSensitive;$('whole-word').checked=state.wholeWord;$('highlight').checked=state.highlight;$('regex').checked=state.regex;$('search').placeholder=state.regex?'正则表达式，如 ^(YES|NO)$':'搜索台词或 key';
 buttons('chapters',[[0,'全部'],...M.CHAPTERS.map(ch=>[ch,String(ch),`第 ${ch} 章（可多选）`])],v=>v===0?state.ch.length===5:state.ch.length<5&&state.ch.includes(v),v=>{
  if(v!==0&&state.ch.length===1&&state.ch[0]===v){toast('至少保留一个章节');return;}
  change({ch:M.toggleChapter(state.ch,v),key:'',page:1});
 });
 buttons('languages',[['en','EN'],['ja','日本語'],['zh','中文']],v=>state.lang.includes(v),v=>{
  if(state.lang.length===1&&state.lang.includes(v)){toast('至少保留一种语言');return;}
  const lang=M.LANGUAGES.filter(l=>l===v?!state.lang.includes(l):state.lang.includes(l));change({lang},false);
 });
 buttons('translations',[['default','人名不译','保留原文角色名'],['recruitable','仅译招揽','翻译可招揽角色的人名'],['names','人名翻译','使用人名翻译版本'],['smart','智能','原文相同只显示一次，不同版本分别标注']],v=>state.zh===v,v=>change({zh:v},false));
 $('translation-row').hidden=!state.lang.includes('zh');
 $('translation-hint').textContent=state.zh==='smart'?'相同译文只显示一次':'只显示所选中文版本';
 buttons('modes',[['plain','简洁'],['source','源码'],['restore','还原']],v=>state.mode===v,v=>change({mode:v},false));
 buttons('layouts',[['horizontal','横排','宽度不足时自动纵排，变宽后恢复横排'],['vertical','纵排']],v=>state.layout===v,v=>change({layout:v},false));
}
function change(patch,search=true){
 clearTimeout(debounce);
 const draft=$('search').value;
 if(!Object.prototype.hasOwnProperty.call(patch,'q')&&draft!==state.q){patch={...patch,q:draft,key:'',page:1};search=true;}
 state={...state,...patch};controls();persist('push');
 if(search||state.mode==='restore')runSearch();else if(result&&result.id===request)render(result);else runSearch();
}
function loadRestorePreview(){
 const target=$('restore-text'),key=target.dataset.key;
 // The portable demo has no game artwork or this full-game text entry.
 if(!key||restorePromise)return;
 restorePromise=fetch('data/ch4.json').then(r=>{if(!r.ok)throw Error();return r.json();}).then(data=>{
  const packed=data.rows.find(row=>row[0]===key);if(!packed)throw Error();
  const row=T.decodeRow(data,packed);target.replaceChildren();
  for(const [field,lang] of [['en','en'],['ja','ja'],['zh_default','zh-Hans']]){
   const text=el('p','restore-caption',T.format(row[field],4).plain.split('\n').map(line=>line.trim()).join('\n').trim());
   text.lang=lang;target.append(text);
  }
 }).catch(()=>{restorePromise=null;target.textContent='文本未能加载，切换模式后可重试。';});
}
function armSearchTimeout(id,phase){
 clearTimeout(searchTimer);
 const loading=phase==='loading',regex=state.regex;
 searchTimer=setTimeout(()=>{
  if(id!==request)return;
  request++;worker?.terminate();worker=null;busyRegex=false;
  showError(loading?'台词数据加载超过 2 分钟，已停止。请检查网络后重新加载，或先选择单个章节。':regex?'正则检索耗时过长，已停止。请简化表达式或缩小章节范围。':'检索耗时过长，已停止。请缩小章节范围后重试。',loading?'数据加载未完成':'检索未完成');
 },loading?LOAD_TIMEOUT:regex?REGEX_TIMEOUT:SEARCH_TIMEOUT);
}
function runSearch(){
 clearTimeout(searchTimer);
 if(state.mode==='restore'){request++;worker?.terminate();worker=null;busyRegex=false;result=null;$('list').setAttribute('aria-busy','false');$('cancel-search').hidden=true;return;}
 if(busyRegex||state.regex||!worker){if(!makeWorker())return;}
 busyRegex=state.regex;
 if($('results').getBoundingClientRect().top < $('controls').getBoundingClientRect().height)$('results').scrollIntoView({block:'start'});
 const id=++request;$('list').setAttribute('aria-busy','true');$('status').textContent='正在准备台词数据…';$('error').hidden=true;$('empty').hidden=true;$('pagination').hidden=true;
 $('cancel-search').hidden=false;
 armSearchTimeout(id,'loading');
 worker.postMessage({id,state,progress:true});
}
function makeWorker(){
 if(worker)worker.terminate();
 // A new protocol URL avoids reusing a cached worker with an older result shape.
 try{worker=new Worker('search-worker.js?protocol=4');}catch{worker=null;showError('检索模块未能启动，请重新加载页面后重试。');return false;}
 const activeWorker=worker;
 worker.onmessage=({data})=>{
  if(worker!==activeWorker||data.id!==request)return;
  if(data.type==='phase'){
   if(data.phase==='loading'){
    // Progress is informative; it must not extend the overall loading deadline.
    $('status').textContent=`正在加载台词数据（${data.completed}/${data.total} 章完成）…`;
   }else if(data.phase==='searching'){
    $('status').textContent='数据已就绪，正在检索…';armSearchTimeout(data.id,'searching');
   }
   return;
  }
  clearTimeout(searchTimer);busyRegex=false;$('cancel-search').hidden=true;
  if(data.type==='error'){showError(data.message,data.phase==='searching'?'检索未完成':'数据加载未完成');return;}
  state.page=data.page;result=data;persist();render(data);
 };
 worker.onerror=()=>{
  // A replaced worker may still deliver a queued loading error.
  if(worker!==activeWorker)return;
  activeWorker.terminate();worker=null;showError('检索模块未能启动，请点击重新加载。');
 };
 return true;
}
function showError(message,status='加载未完成'){clearTimeout(searchTimer);busyRegex=false;$('cancel-search').hidden=true;$('pagination').hidden=true;result=null;$('list').replaceChildren();$('range').textContent='';$('status').textContent=status;$('error').hidden=false;$('error').querySelector('p').textContent=message;$('list').setAttribute('aria-busy','false');}
function appendPart(parent,text,cls,start,hits,spaces=false){
 // DOM text nodes only; neither game strings nor search queries become HTML.
 const cuts=new Set([0,text.length]);
 for(const [a,b] of hits){if(a>start&&a<start+text.length)cuts.add(a-start);if(b>start&&b<start+text.length)cuts.add(b-start);}
 const points=[...cuts].sort((a,b)=>a-b);
 for(let n=0;n<points.length-1;n++){
  const lo=points[n],hi=points[n+1],value=text.slice(lo,hi);
  const marked=hits.some(([a,b])=>a<=start+lo&&b>start+lo);
  let wrapper=parent;if(cls){wrapper=el('span',cls);parent.append(wrapper);}
  if(marked){const mark=el('mark');wrapper.append(mark);wrapper=mark;}
  if(!spaces){wrapper.append(document.createTextNode(value));continue;}
  const pieces=value.split(/([ \u00a0\u3000])/);
  for(const piece of pieces){if(!piece)continue;wrapper.append(/^[ \u00a0\u3000]$/.test(piece)?el('span','space'+(piece==='\u3000'?' full':''),piece):document.createTextNode(piece));}
 }
}
function bodyText(raw,ch,lang,highlights={},artwords={}){
 const p=el('div','text'+(state.mode==='source'?' source':''));p.lang=lang==='zh'?'zh-Hans':lang;
 const view=T.format(raw,ch,artwords);
 if(view.state==='missing'||view.state==='empty'||(view.state==='control-only'&&state.mode==='plain')){
  p.classList.add('missing');p.lang='zh-Hans';p.textContent={missing:'暂无此语言文本',empty:'空字符串','control-only':'仅含控制串 · 切换源码查看'}[view.state];return p;
 }
 if(state.mode==='source'){
  const hits=state.highlight?(highlights.source||[]):[];let offset=0;
  for(const token of view.tokens){
   const value=T.sourceText(token.raw);
   if(token.kind==='text'&&token.raw.startsWith('`')&&token.raw.length>1){appendPart(p,'`','control',offset,hits,true);appendPart(p,value.slice(1),'',offset+1,hits,true);}
   else appendPart(p,value,token.kind==='text'?'':'control',offset,hits,true);
   offset+=value.length;
  }
 }else{
  const hits=state.highlight?(highlights.plain||[]):[];
  p.classList.add('plain-flow');
  for(const line of T.readingLines(view.plain)){
   if(line.start)p.append(document.createTextNode('\n'));
   const row=el('span','reading-line'+(line.hanging?' hanging':''));
   if(line.hanging){
    const prefix=el('span','reading-prefix');
    if(line.markerStart!==null){
     appendPart(prefix,view.plain.slice(line.start,line.markerStart),'reading-indent',line.start,hits);
     appendPart(prefix,view.plain.slice(line.markerStart,line.markerStart+1),'',line.markerStart,hits);
     appendPart(prefix,view.plain.slice(line.markerStart+1,line.bodyStart),'',line.markerStart+1,hits);
    }else appendPart(prefix,view.plain.slice(line.start,line.bodyStart),'reading-indent',line.start,hits);
    row.append(prefix);
   }
   const words=el('span','reading-words');let offset=line.bodyStart;
   for(const piece of view.plain.slice(line.bodyStart,line.end).split(/(〔(?:参数|图标|艺术字|行内头像|选择指令) [^〕]*〕)/)){
    const end=offset+piece.length,cuts=new Set([offset,end]);
    for(const [a,b] of view.artwordRanges){if(a>offset&&a<end)cuts.add(a);if(b>offset&&b<end)cuts.add(b);}
    const points=[...cuts].sort((a,b)=>a-b);
    for(let i=0;i<points.length-1;i++){
     const a=points[i],b=points[i+1],artword=view.artwordRanges.some(([lo,hi])=>lo<=a&&hi>=b);
     appendPart(words,view.plain.slice(a,b),artword?'artword':piece.startsWith('〔')?'placeholder':'',a,hits);
    }
    offset=end;
   }
   row.append(words);p.append(row);
  }
 }
 for(const placeholder of p.querySelectorAll('.placeholder')){if(/^〔图标 \d+〕$/.test(placeholder.textContent))placeholder.title='数字是原串 \\I 的场景贴图槽位；具体素材尚未接入，不代表素材编号。';}
 if(view.issues.length)p.title='占位表示尚未接入的数据；未知片段保持原样。源码模式可查看完整原文。';
 return p;
}
async function copyWithFeedback(button,text){const label=button.textContent;button.disabled=true;const ok=await copy(text);button.textContent=ok?'已复制':'复制失败';setTimeout(()=>{button.textContent=label;button.disabled=false;},1200);}
function cell(row,lang){
 const n=el('section','language-cell'),title=el('div','language-title'),h=el('h3','',{en:'English',ja:'日本語',zh:'中文'}[lang]);title.append(h);n.append(title);n.setAttribute('aria-label',h.textContent);
 const content=el('div','language-content');n.append(content);
 const groups=lang==='zh'?M.chineseRows(row,state.zh):[{raw:row[lang],labels:[],fields:[lang]}];
 for(const group of groups){
  const block=el('div','variant');
  if(groups.length>1){const head=el('div','variant-head');head.append(el('span','variant-label',group.labels.join(' · ')));block.append(head);}
  block.append(bodyText(group.raw,row.chapter,lang,row.highlights?.[group.fields[0]],row.artwords?.[group.fields[0]]));content.append(block);
 }
 return n;
}
function actionMenu(...items){
 const menu=el('details','compact-actions'),summary=el('summary','action-button','…'),panel=el('div','compact-menu-panel');
 summary.setAttribute('aria-label','台词操作');summary.title='台词操作';panel.append(...items);menu.append(summary,panel);
 panel.addEventListener('click',e=>{if(e.target.closest('button,a'))menu.open=false;});
 menu.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();menu.open=false;summary.focus();}});
 return menu;
}
addEventListener('click',e=>{for(const menu of document.querySelectorAll('.compact-actions[open]'))if(!menu.contains(e.target))menu.open=false;});
const contextView=window.DialogueContext.mount({dialog:$('context-dialog'),content:$('context-content'),title:$('context-title'),close:$('close-context'),start:$('context-start'),order:$('context-order'),cell,actionMenu,getState:()=>({...state,compact})});
function chapterLabel(row){
 const chapters=[...new Set(row.chapters||[row.chapter])].sort((a,b)=>a-b),ranges=[];
 for(const ch of chapters){const last=ranges.at(-1);if(last&&ch===last[1]+1)last[1]=ch;else ranges.push([ch,ch]);}
 return 'Ch'+ranges.map(([a,b])=>a===b?String(a):`${a}-${b}`).join(',')+(chapters.length>1?'?':'');
}
function render(data){
 $('list').className=state.layout;$('list').style.setProperty('--columns',state.lang.length);$('list').replaceChildren();$('list').setAttribute('aria-busy','false');
 $('empty').hidden=data.total!==0;$('error').hidden=true;
 $('status').replaceChildren(document.createTextNode(state.q?'找到 ':'共 '),el('strong','',data.total.toLocaleString()),document.createTextNode(' 条章节记录'));
 if(data.records>data.total)$('status').replaceChildren(document.createTextNode(`命中 ${data.records.toLocaleString()} 条章节记录 · 跨章去重后 ${data.total.toLocaleString()} 组`));
 $('range').textContent=data.total?`${((data.page-1)*30+1).toLocaleString()} — ${Math.min(data.page*30,data.total).toLocaleString()}`:'';
 for(const row of data.rows){
  const article=el('article','entry');article.dataset.key=row.key;article.dataset.chapter=row.chapter;
  const header=el('header','entry-head'),identity=el('div','entry-identity'),actions=el('div','entry-actions');
  const key=el('code','key');appendPart(key,row.key,'',0,state.highlight?(row.highlights?.key||[]):[]);
  const keyCopy=el('button','action-button key-copy','复制 key');keyCopy.onclick=()=>copyWithFeedback(keyCopy,row.key);
  identity.append(el('span','chapter-tag',chapterLabel(row)),key);if(!compact)identity.append(keyCopy);header.append(identity,actions);
  const sourceArea=el('div','entry-source'),sources=row.sources||[];
  const sourceLink=o=>{const a=el('a','source-link','wiki 源码');a.href=A.sourceURL(row.chapter,o.file,o.line);a.target='_blank';a.rel='noopener noreferrer';a.title=o.file+' : '+o.line+'（本地位置；线上版本可能不同）';return a;};
  if(sources.length===1)sourceArea.append(sourceLink(sources[0]));
  else if(sources.length>1){const menu=el('details','source-menu'),summary=el('summary','',`源码 ${sources.length} 处`);menu.append(summary);const items=el('div','source-options');for(const o of sources){const a=sourceLink(o);a.textContent=o.file.replace(/^gml_/,'').replace(/\.gml$/,'')+' : '+o.line;items.append(a);}menu.append(items);sourceArea.append(menu);}
  else {const missing=el('span','source-missing','暂无源码定位');missing.title='当前导出中没有已核对的源码位置，不代表游戏中不存在。';sourceArea.append(missing);}
  const copies=el('div','entry-copies'),copyAll=el('button','action-button','复制本条');
  copyAll.title='按当前语言、模式和中文译法复制：key + 全部可见版本';copyAll.onclick=()=>copyWithFeedback(copyAll,A.copyEntry(row,state));
  const contextButton=el('button','action-button','查看上下文');contextButton.setAttribute('aria-haspopup','dialog');contextButton.onclick=()=>contextView.show(row);
  copies.append(contextButton,copyAll);if(compact)actions.append(contextButton,actionMenu(keyCopy,copyAll,sourceArea));else actions.append(sourceArea,copies);article.append(header);
  const holder=el('div','entry-body'),grid=el('div','language-grid');
  for(const lang of state.lang)grid.append(cell(row,lang));holder.append(grid);article.append(holder);$('list').append(article);
 }
 $('pagination').hidden=!data.total;$('page-input').value=String(data.page);$('page-label').textContent=`/ ${data.pages}`;
 $('previous').disabled=data.page<=1;$('next').disabled=data.page>=data.pages;
}
function searchNow(){clearTimeout(debounce);state.q=$('search').value;state.key='';state.page=1;persist('push');runSearch();}
$('search-form').onsubmit=e=>{e.preventDefault();searchNow();};
$('search').addEventListener('input',e=>{clearTimeout(debounce);if(!e.isComposing)debounce=setTimeout(searchNow,300);});
$('search').addEventListener('compositionend',()=>{clearTimeout(debounce);debounce=setTimeout(searchNow,300);});
$('page-jump').onsubmit=e=>{e.preventDefault();if(!result||!result.total)return;const input=$('page-input'),raw=input.value.trim();if(!/^\d+$/.test(raw)){input.value=String(result.page);return;}const page=Math.max(1,Math.min(result.pages,Number(raw)));input.value=String(page);input.blur();if(page!==result.page){change({page});$('results').scrollIntoView({block:'start'});}};
$('previous').onclick=()=>{change({page:state.page-1});$('results').scrollIntoView({block:'start'});};
$('next').onclick=()=>{change({page:state.page+1});$('results').scrollIntoView({block:'start'});};
$('reset').onclick=()=>change({q:'',key:'',ch:M.CHAPTERS.slice(),lang:['en','ja','zh'],page:1,caseSensitive:false,wholeWord:false,regex:false});
$('retry').onclick=()=>runSearch();
$('cancel-search').onclick=()=>{clearTimeout(debounce);request++;worker?.terminate();worker=null;showError('检索已取消，可以修改条件后重新搜索。');};
$('match-case').onchange=()=>change({caseSensitive:$('match-case').checked,key:'',page:1});
$('whole-word').onchange=()=>change({wholeWord:$('whole-word').checked,key:'',page:1});
$('regex').onchange=()=>change({regex:$('regex').checked,key:'',page:1});
$('highlight').onchange=()=>change({highlight:$('highlight').checked},false);
$('compact-enabled').onchange=()=>{compact=$('compact-enabled').checked;document.documentElement.dataset.compact=String(compact);persist();if(result)render(result);};
$('about').onclick=()=>$('about-dialog').showModal();$('close-about').onclick=()=>$('about-dialog').close();
$('about-dialog').addEventListener('click',e=>{if(e.target===$('about-dialog')){const b=e.target.getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)e.target.close();}});
addEventListener('popstate',()=>{clearTimeout(debounce);state=M.stateFrom(new URLSearchParams(location.search),{},matchMedia('(max-width:700px)').matches);controls();runSearch();});
const narrowControls=matchMedia('(max-width:700px)');
$('filter-panel').open=!narrowControls.matches;
narrowControls.addEventListener('change',event=>{$('filter-panel').open=!event.matches;});
// Keep keyboard focus and pagination targets below the persistent toolbar.
const sizeToolbar=()=>document.documentElement.style.setProperty('--controls-height',Math.ceil($('controls').getBoundingClientRect().height)+'px');
new ResizeObserver(sizeToolbar).observe($('controls'));sizeToolbar();
controls();runSearch();
})();
