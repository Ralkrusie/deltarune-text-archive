'use strict';
(()=>{
 const data=window.REVIEW_DATA,$=id=>document.getElementById(id);let active=null;
 const models=new Map(data.rows.map(r=>[r.id,RestoreModel.scene(r,data.assets)]));
 for(const s of data.sessions){const o=document.createElement('option');o.value=s.id;o.textContent=(s.mode==='mechanism_selftest'?'机制验证 · ':'自然游玩 · ')+s.run.slice(0,8);$('session').append(o);}
 const natural=new Set(data.sessions.filter(s=>s.mode!=='mechanism_selftest').map(s=>s.id));
 for(const [name,predicate] of [['普通头像',s=>s.portraits.length&&!s.smallfaces.length],['主句＋插话',s=>s.smallfaces.length===1&&s.portraits.length],['多条插话载体',s=>s.kind==='child_container'&&s.smallfaces.length>1],['选择题',s=>s.choices.length],['无头像正文',s=>s.kind==='text'&&!s.portraits.length]]){
  const row=data.rows.find(r=>natural.has(r.session)&&predicate(models.get(r.id)));if(!row)continue;
  const button=document.createElement('button');button.textContent=name+' · #'+row.message;
  button.onclick=()=>{$('session').value=row.session;$('type').value='all';$('search').value='';select(row);};$('samples').append(button);
 }
 function select(row){active=row.id;history.replaceState(null,'','#'+encodeURIComponent(active));render();}
 function render(){
  const q=$('search').value.trim().toLowerCase(),type=$('type').value;
  const rows=data.rows.filter(r=>{const s=models.get(r.id);return r.session===$('session').value&&s.kind!=='control'&&(!q||JSON.stringify([r.body.text,r.source?.key,r.interaction?.snapshot,r.view?.candidates]).toLowerCase().includes(q))&&(type==='all'||type==='portrait'&&s.portraits.length||type==='plain'&&!s.portraits.length&&s.kind==='text'||type==='smallface'&&s.smallfaces.length||type==='carrier'&&s.kind==='child_container'||type==='choice'&&s.choices.length);});
  if(!rows.some(r=>r.id===active))active=rows[0]?.id||null;
  $('count').textContent=rows.length+' 条记录 · 用法／变体分别保留';$('rows').replaceChildren();
  for(const r of rows){const s=models.get(r.id),b=document.createElement('button'),small=document.createElement('small'),text=document.createElement('span');small.textContent='#'+r.message+' · '+(s.candidates.join(' / ')||'待判断');text.textContent=s.glyphs.map(g=>g.char).join('')||'（插话／选择载体）';b.append(small,text);b.className=r.id===active?'active':'';b.onclick=()=>select(r);$('rows').append(b);}
  const r=rows.find(r=>r.id===active);if(!r){$('title').textContent='没有匹配的记录';$('preview').replaceChildren();for(const id of ['binding','evidence','raw','scene'])$(id).textContent='';$('review-link').href='review.html';return;}
  const s=models.get(r.id);$('title').textContent='#'+r.message+' · '+(s.kind==='child_container'?'插话载体':'台词预览');$('binding').textContent=r.source?.key||'来源尚未绑定';
  RestorePreview.mount($('preview'),s);$('review-link').href='review.html#'+encodeURIComponent(r.id);
  $('evidence').textContent=`实际头像状态 ${s.portraits.length} 个，插话 ${s.smallfaces.length} 条，选择 ${s.choices.length} 次。主动交互对象：${r.interaction?.snapshot?.object||'没有已证明关联'}。预览不自动确定说话人。`;
  $('raw').textContent=r.body.text;$('scene').textContent=JSON.stringify(s,null,2);
 }
 for(const id of ['session','type'])$(id).onchange=render;$('search').oninput=render;
 try{const r=data.rows.find(r=>r.id===decodeURIComponent(location.hash.slice(1)));if(r){active=r.id;$('session').value=r.session;}}catch{}
 render();
})();
