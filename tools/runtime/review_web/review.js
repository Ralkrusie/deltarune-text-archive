'use strict';
(() => {
 const data=window.REVIEW_DATA,$=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const labels={source_unknown:'来源未绑定',unbacked_face_state:'头像状态缺少绘制佐证',partial_page:'消息未闭合'};
 const key='deltarune-review-drafts-v1';let drafts={},active=null,filtered=[];
 try{drafts=JSON.parse(localStorage.getItem(key)||'{}');if(!drafts||Array.isArray(drafts)||typeof drafts!=='object')drafts={};}catch{}
 const validDraft=r=>drafts[r.id]?.variant===r.variant&&drafts[r.id]?.partition===r.partition;
 const clean=t=>String(t).replace(/\\[A-Za-z][A-Za-z0-9]/g,'').replace(/\^\d+/g,'').replace(/\/%?$|%$/g,'').replace(/&/g,'\n');
 const types={text:'正文',control:'控制页',child_container:'附属文本载体'};
 const nameList=v=>v.length?v.join(' / '):'待判断';
 const badge=s=>'<span class="tag">'+esc(s)+'</span>';
 const raw=(title,obj)=>'<details><summary>'+esc(title)+'</summary><pre>'+esc(JSON.stringify(obj,null,2))+'</pre></details>';
 const sprite=(name,frame)=>{const f=name+'_'+Math.trunc(frame)+'.png';return '<figure class="sprite">'+(data.assets[f]?'<img src="assets/'+encodeURIComponent(f)+'" alt="'+esc(name)+'">':'<span class="muted">素材未导出</span>')+'<figcaption>'+esc(f)+'</figcaption></figure>';};
 function notice(text){$('notice').textContent=text;}
 function persist(){try{localStorage.setItem(key,JSON.stringify(drafts));notice('草稿已保存在当前浏览器；完成后请导出 JSON。不会改写原始采集或正式归因。');}catch{notice('浏览器存储不可用，草稿仅留在内存，请立即导出。');}}
 for(const s of data.sessions){const opt=document.createElement('option');opt.value=s.id;opt.textContent=(s.mode==='mechanism_selftest'?'机制测试 · ':'自然游玩 · ')+s.run.slice(0,8)+' · '+s.summary.messages+' 页';$('session').append(opt);}
 for(const c of data.characters){const opt=document.createElement('option');opt.value=c.en;opt.label=c.zh+' · '+c.en;$('characters').append(opt);}
 function renderList(){
  const sid=$('session').value,q=$('query').value.toLowerCase(),filter=$('filter').value,all=data.rows.filter(r=>r.session===sid);
  filtered=all.filter(r=>($('controls').checked||r.view.kind!=='control')&&(!q||JSON.stringify([r.body.text,r.source?.key,r.view.candidates,r.body.smallfaces,r.interaction?.snapshot]).toLowerCase().includes(q))&&
   (filter==='all'||filter==='issue'&&r.view.issues.length||filter==='source'&&r.view.issues.includes('source_unknown')||filter==='identity'&&r.view.suppressed||filter==='unknown'&&r.view.identity_status==='unknown'||filter==='smallface'&&r.body.smallfaces?.length||filter==='choice'&&(r.choices.length||r.after_choice)||filter==='interaction'&&r.interaction||filter==='draft'&&validDraft(r)));
  const session=data.sessions.find(s=>s.id===sid),s=session.summary;
  $('stats').innerHTML=[[all.filter(r=>r.view.kind!=='control').length,'正文／插话载体'],[s.interactions,'交互'],[s.choices,'选择'],[s.smallfaces,'插话'],[all.filter(r=>r.view.issues.length).length,'优先核对']].map(([n,t])=>'<div class="stat"><strong>'+n+'</strong>'+esc(t)+'</div>').join('');
  $('count').textContent='筛选 '+filtered.length+' / '+all.length+' 页 · '+(session.mode==='mechanism_selftest'?'机制测试不计自然覆盖':'自然记录');
  if(!filtered.some(r=>r.id===active))active=filtered[0]?.id||null;
  $('list').innerHTML=filtered.map(r=>'<button class="row'+(r.id===active?' active':'')+'" data-row="'+esc(r.id)+'"><small>#'+r.message+' · '+esc(types[r.view.kind])+' · '+esc(nameList(r.view.candidates))+(validDraft(r)?' · 有草稿':'')+'</small><span class="preview">'+esc(clean(r.body.text)||'（无主句文字）')+'</span>'+r.view.issues.map(v=>badge(labels[v])).join('')+'</button>').join('');
  $('list').querySelectorAll('[data-row]').forEach(b=>b.onclick=()=>select(b.dataset.row));
  if(!filtered.some(r=>r.id===active))active=filtered[0]?.id||null;
  renderDetail();
 }
 function select(id){active=id;history.replaceState(null,'','#'+encodeURIComponent(id));renderList();}
 function renderDetail(){
  const r=data.rows.find(r=>r.id===active);if(!r){$('detail').textContent='没有匹配的记录。';return;}
  const b=r.body,v=r.view,i=filtered.findIndex(x=>x.id===r.id),ix=r.interaction?.snapshot,chars=b.assets.filter(a=>a.role==='portrait');
  const styles=b.text_styles?.states||[],fonts=[...new Set(styles.map(s=>s.font_name))],motions=[...new Set(styles.map(s=>s.motion))];
  const colors=[...new Set(styles.flatMap(s=>s.colors_bgr))].map(c=>'#'+[(c&255),(c>>8&255),(c>>16&255)].map(n=>n.toString(16).padStart(2,'0')).join(''));
  let content='<div class="title"><h1>#'+r.message+' '+esc(types[v.kind])+'</h1><div><button id="prev" '+(i===0?'disabled':'')+'>上一条</button> <button id="next" '+(i===filtered.length-1?'disabled':'')+'>下一条</button></div></div><p class="muted">'+esc(b.room)+'</p>';
  if(v.suppressed)content+='<p class="warning">解释修正：旧头像候选 '+esc(nameList(v.raw_candidates))+' → 待判断。未观察到足以支持这些状态的头像绘制；可能是前句残留。原始状态保留在证据中。</p>';
  if(!r.source&&v.kind==='text')content+='<p class="warning">当前旧记录未绑定源码。新采集器的来源修复不会反向补写这条旧日志。</p>';
  content+='<div class="text">'+esc(clean(b.text)||'（本页主串没有正文；请查看插话／选择。）')+'</div>'+raw('原始控制串',b.text);
  content+='<div class="tracks"><section class="card"><h2>① 消息与人物证据</h2><p>'+esc(v.identity_status==='portrait_supported'?'头像支持候选：'+nameList(v.candidates):'人物：'+(v.kind==='text'?'待判断':'不适用于主串'))+'</p><div class="sprites">'+chars.map(a=>sprite(a.sprite_name,a.subimage)).join('')+'</div><p class="muted">头像证据不等于最终人工结论；无头像也不自动归为旁白。</p>'+raw('原始人物状态',b.identity)+'</section><section class="card"><h2>② 主动交互对象</h2>';
  if(ix)content+='<p>'+esc(ix.object)+'</p><div class="sprites">'+sprite(ix.sprite.name,ix.sprite.frame)+'</div><p class="muted">触发对象用于定位线索，不把后续整段对话归给它。图片为素材帧，不保证是游戏中的完整组合造型。</p>'+raw('对象快照',ix);
  else content+='<p class="muted">无已证明的主动交互关联。自动剧情和战斗文本不一定来自按 Z 交互。</p>';
  content+='</section></div>';
  if(b.smallfaces?.length)content+='<section class="card"><h2>附属插话 · '+b.smallfaces.length+' 条</h2>'+b.smallfaces.map(sf=>'<h3>'+esc(nameList(sf.identity?.candidates||[]))+'</h3><p>'+esc(sf.text)+'</p><div class="sprites">'+sf.sprites.map(a=>sprite(a.sprite_name,a.subimage)).join('')+'</div><small class="muted">'+esc(sf.source_key||'来源未知')+' · '+(sf.coverage?.all_observed_text_states_complete?'文字已完整画出':'显示需核对')+'</small>').join('')+'</section>';
  if(r.choices.length||r.after_choice)content+='<section class="card"><h2>选择关系</h2>'+[...r.choices,...(r.after_choice&&!r.choices.includes(r.after_choice)?[r.after_choice]:[])].map(c=>'<p>选择 #'+c.choice_id+' · '+c.options.map(o=>esc(o.text)+(o.slot===c.selected_slot?' ✓ 已选':'')).join(' / ')+'</p>').join('')+'<p class="muted">只证明本次选项与关联，不推定未游玩的分支。</p></section>';
  content+='<section class="card"><h2>字体、颜色、运动与行内图</h2><p>字体：'+esc(fonts.join(' / ')||'未观察到')+' · 运动参数：'+esc(motions.join(' / ')||'未观察到')+'</p><p>'+colors.map(c=>'<span class="color" style="background:'+c+'"></span>'+c+' ').join('')+'</p><p class="muted">颜色包含阴影／描边层；素材预览不是游戏画面还原。</p><div class="sprites">'+b.assets.filter(a=>a.role==='inline').map(a=>sprite(a.sprite_name,a.subimage)).join('')+'</div>'+raw('完整样式区段与配置',b.text_styles)+'</section>';
  const src=r.source;content+='<section class="card"><h2>源码与附近消息</h2><p>'+esc(src?.key||'源码用法未知')+'</p><small class="muted">'+esc(src?src.path+':'+src.line:'')+'</small>'+(r.snippet?'<details><summary>展开源码证据</summary><pre>'+esc(r.snippet)+'</pre></details>':'');
  const all=data.rows.filter(x=>x.session===r.session),pos=all.findIndex(x=>x.id===r.id);content+=all.slice(Math.max(0,pos-2),pos+3).filter(x=>x.id!==r.id).map(x=>'<button class="context" data-context="'+esc(x.id)+'">#'+x.message+' '+esc(clean(x.body.text))+'</button>').join('')+'<p class="muted">此处是本次运行邻近消息，不是完整静态分支图。</p></section>';
  const draft=validDraft(r)?drafts[r.id]:{};
  content+='<section class="card"><h2>主消息人工审阅草稿</h2><div class="fields"><label>用途<select id="purpose">'+['待判断','角色发言','调查描述','菜单/界面文本','旁白（调查描述之外）','其他'].map(p=>'<option '+(p===draft.purpose?'selected':'')+'>'+p+'</option>').join('')+'</select></label><label>角色（可从名称表选，也可自填）<input id="character" list="characters" value="'+esc(draft.character||'')+'" placeholder="选择角色发言后填写"></label><label>审阅状态<select id="decision">'+['待核对','已核对','需要补证据'].map(p=>'<option '+(p===draft.decision?'selected':'')+'>'+p+'</option>').join('')+'</select></label></div><label>备注／依据<textarea id="note">'+esc(draft.note||'')+'</textarea></label><p><button id="save">保存本条草稿</button> <span class="muted">插话另列证据，本表仅修改主消息。草稿绑定本条观察及属性变体；不会自动合并到正式库。</span></p></section>'+raw('运行诊断',r.telemetry);
  $('detail').innerHTML=content;
  $('prev').onclick=()=>select(filtered[i-1].id);$('next').onclick=()=>select(filtered[i+1].id);
  $('detail').querySelectorAll('[data-context]').forEach(e=>e.onclick=()=>{if(!filtered.some(x=>x.id===e.dataset.context)){$('filter').value='all';$('query').value='';$('controls').checked=true;}select(e.dataset.context);});
  const toggle=()=>{$('character').disabled=$('purpose').value!=='角色发言';};$('purpose').onchange=toggle;toggle();
  $('save').onclick=()=>{drafts[r.id]={id:r.id,variant:r.variant,partition:r.partition,occurrence:b.occurrence_id,purpose:$('purpose').value,character:$('purpose').value==='角色发言'?$('character').value:'',decision:$('decision').value,note:$('note').value};persist();renderList();};
 }
 ['session','query','filter','controls'].forEach(id=>$(id).addEventListener(id==='query'?'input':'change',renderList));
 $('export').onclick=()=>{const rows=data.rows.filter(validDraft).map(r=>drafts[r.id]);const blob=new Blob([JSON.stringify({schema:'runtime-review-draft-1',interpretation:data.interpretation,rows},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='采集审阅草稿.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);notice('已导出当前工作台的 '+rows.length+' 条草稿。');};
 $('import').onclick=()=>$('draft-file').click();
 $('draft-file').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;if(file.size>5e6)throw Error('文件过大');const value=JSON.parse(await file.text());if(value.schema!=='runtime-review-draft-1'||!Array.isArray(value.rows))throw Error('格式不匹配');const seen=new Set();for(const d of value.rows){const r=data.rows.find(r=>r.id===d.id);if(!r||seen.has(d.id)||r.variant!==d.variant||r.partition!==d.partition||r.body.occurrence_id!==d.occurrence||!['待判断','角色发言','调查描述','菜单/界面文本','旁白（调查描述之外）','其他'].includes(d.purpose)||!['待核对','已核对','需要补证据'].includes(d.decision)||typeof d.character!=='string'||typeof d.note!=='string')throw Error('草稿与当前记录不匹配');seen.add(d.id);}for(const d of value.rows)drafts[d.id]=d;persist();renderList();notice('已导入 '+value.rows.length+' 条草稿。');}catch(err){notice('未导入：'+err.message);}finally{e.target.value='';}};
 try{const hash=decodeURIComponent(location.hash.slice(1));const r=data.rows.find(r=>r.id===hash);if(r){active=r.id;$('session').value=r.session;if(r.view.kind==='control')$('controls').checked=true;}}catch{}
 renderList();
})();
