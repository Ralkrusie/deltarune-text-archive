'use strict';
// Both hosts call mount with the same scene; this renderer never mutates evidence.
window.RestorePreview={mount(host,scene,{assetBase='assets/'}={}){
 host.replaceChildren();host.classList.add('restore-component');
 const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
 const status=el('p','静态预览 · 布局与字体近似','restore-status');host.append(status);
 const stage=el('div',undefined,'restore-stage');host.append(stage);
 function sprite(a){const f=el('figure');if(a.available){const img=el('img');img.src=assetBase+encodeURIComponent(a.file);img.alt=a.file;img.onerror=()=>{img.replaceWith(el('span','素材加载失败：'+a.file));};f.append(img);}else f.append(el('span','素材缺失：'+a.file));return f;}
 const main=el('div',undefined,'restore-main');stage.append(main);
 const portrait=el('div',undefined,'restore-portrait');
 if(scene.portraits.length){portrait.append(sprite(scene.portraits[0]));main.append(portrait);}
 const text=el('div',undefined,'restore-dialogue');main.append(text);
 for(const g of scene.glyphs){const s=el('span',g.char);s.style.color=g.color;s.dataset.formattedIndex=g.index;text.append(s);}
 if(!scene.supported)text.textContent=scene.raw;
 else if(!scene.glyphs.some(g=>g.char.trim()))text.append(el('span',scene.smallfaces.length?'（主串为插话载体）':'（主串无可见正文）','restore-empty'));
 if(scene.smallfaces.length){const group=el('div',undefined,'restore-children');stage.append(group);for(const [i,sf] of scene.smallfaces.entries()){
  const child=el('article',undefined,'restore-child');if(sf.assets[0])child.append(sprite(sf.assets[0]));
  const body=el('div');body.append(el('small','插话 '+(i+1)),el('p',sf.text));child.append(body);group.append(child);
 }}
 for(const choice of scene.choices){const group=el('div',undefined,'restore-choices');group.append(el('small','本次选择 · #'+choice.choice_id));for(const o of choice.options){group.append(el('div',(o.slot===choice.selected_slot?'✓ ':'○ ')+o.text.replace(/#/g,'\n')));}stage.append(group);}
 if(scene.inline.length){const group=el('div',undefined,'restore-inline');group.append(el('small','已采行内素材（尚未定位）'));scene.inline.forEach(a=>group.append(sprite(a)));stage.append(group);}
 if(scene.portraits.length>1){const label=el('label','头像绘制状态 '),select=el('select');scene.portraits.forEach((a,i)=>{const o=el('option',`${i+1} · ${a.file} · site ${a.site}`);o.value=i;select.append(o);});select.onchange=()=>portrait.replaceChildren(sprite(scene.portraits[Number(select.value)]));label.append(select);host.append(label);}
 host.append(el('p','已采字体：'+(scene.fonts.join(' / ')||'未观察到')+' · 人物候选：'+(scene.candidates.join(' / ')||'待判断'),'restore-meta'));
 const details=el('details'),summary=el('summary','本条预览限制（'+scene.issues.length+'）'),ul=el('ul');scene.issues.forEach(s=>ul.append(el('li',s)));details.append(summary,ul);host.append(details);
 return {scene,destroy(){host.replaceChildren();}};
}};
