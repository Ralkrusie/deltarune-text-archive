'use strict';
(function(root){
 const VERSION='local-scene-1';
 function bgr(n){return '#'+[n&255,n>>8&255,n>>16&255].map(v=>v.toString(16).padStart(2,'0')).join('');}
 // Retain the recorded formatted-string index, including consumed control codes.
 // This is a bounded preview tokenizer, not the game's complete text interpreter.
 function tokenize(text){
  const glyphs=[],unknown=[];
  for(let i=0;i<text.length;){
   const rest=text.slice(i),index=i+1;
   const control=rest.match(/^\\([A-Za-z])([A-Za-z0-9])/);
   if(control){if(!'EFfTcCMGSDI'.includes(control[1]))unknown.push(control[0]);i+=control[0].length;continue;}
   const pause=rest.match(/^\^\d+/);if(pause){i+=pause[0].length;continue;}
   const c=text[i++];
   if((c==='/'||c==='%')&&/^[/%\s]*$/.test(rest))continue;
   if(c==='\\'){unknown.push(rest.slice(0,3));}
   glyphs.push({char:c==='&'?'\n':c==='|'?' ':c,index});
  }
  return {glyphs,unknown:[...new Set(unknown)]};
 }
 function scene(row,assets={}){
  const b=row.body,issues=['布局为本地预览模板；不代表原游戏窗口或气泡的精确位置。','字体暂用浏览器等宽字体；实际字体名保留，字宽与行距待接入。'];
  const supported=b.language==='en'&&(!row.source||row.source.chapter===2);
  if(!supported)issues.push('此语言或章节尚未适配，仅展示原文证据。');
  const text=b.formatted_text??b.text,parsed=tokenize(text),styles=b.text_styles||{},spans=styles.spans||[],states=styles.states||[];
  const indexSupported=b.index_space==='formatted_mystring_1based';
  const recipeSupported=styles.source_sha256==='7597703c209cce4e007419710fb30c86027f183ee8b5f5a6d7bbfb3c9235cc0c';
  if(!indexSupported||!recipeSupported)issues.push('缺少匹配的绘制配方或字符索引；颜色不推定，使用白色。');
  const glyphs=parsed.glyphs.map(g=>{
   const candidates=indexSupported&&recipeSupported?spans.filter(s=>g.index>=s.start_index&&g.index<=s.end_index).map(s=>states[s.state_index]).filter(s=>s&&[1,3,5,6].includes(s.site)):[];
   const colors=[...new Set(candidates.map(s=>bgr(s.colors_bgr?.[0]??16777215)))];
   if(colors.length>1)issues.push('同一字符有竞争颜色状态；该处显示白色，待选择明确时刻。');
   return {...g,color:colors.length===1?colors[0]:'#ffffff'};
  });
  if(parsed.unknown.length)issues.push('尚未解释的控制串：'+parsed.unknown.join('、'));
  if(text.includes('|'))issues.push('缩进标记按空格预览，尚未使用游戏字宽。');
  if(states.some(s=>s.motion&&s.motion!=='none'))issues.push('已采到运动参数，本阶段只显示静止文本。');
  if(states.some(s=>new Set(s.colors_bgr||[]).size>1))issues.push('渐变／阴影层尚未重现，当前只使用明确前景色。');
  function asset(a){const file=a.sprite_name+'_'+Math.trunc(a.subimage)+'.png';return {...a,file,available:Object.hasOwn(assets,file)};}
  const portraits=(b.assets||[]).filter(a=>a.role==='portrait').map(asset);
  if(portraits.length>1)issues.push('采到多个头像帧／绘制状态；可手动切换，不推定它们的播放顺序或合成关系。');
  const inline=(b.assets||[]).filter(a=>a.role==='inline').map(asset);
  if(inline.length)issues.push('行内图先列出实际素材，精确字符锚点待接入。');
  const smallfaces=(b.smallfaces||[]).map(sf=>({...sf,assets:(sf.sprites||[]).map(asset)}));
  if(smallfaces.length)issues.push('插话按记录顺序排布示意；进出时间、重叠关系与位置待还原。');
  if(row.choices?.length)issues.push('选项按记录文本列出，布局为示意；勾选仅表示当次已选结果。');
  if(!row.source)issues.push('这条观察没有源码绑定；预览成功不等于来源已确认。');
  if(b.partial||b.coverage?.overflow)issues.push('采集含 partial／overflow 标记，请结合原始覆盖字段核对。');
  if([...portraits,...inline,...smallfaces.flatMap(s=>s.assets)].some(a=>!a.available))issues.push('有素材未导出，已用缺失提示代替。');
  return {version:VERSION,id:row.id,variant:row.variant,partition:row.partition,occurrence:b.occurrence_id,language:b.language,supported,raw:b.text,
   glyphs:supported?glyphs:[],portraits,inline,smallfaces,choices:row.choices||[],fonts:[...new Set(states.map(s=>s.font_name))],
   candidates:row.view?.candidates||[],kind:row.view?.kind||'text',issues:[...new Set(issues)]};
 }
 const api={VERSION,bgr,tokenize,scene};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.RestoreModel=api;
})(typeof window==='undefined'?globalThis:window);
