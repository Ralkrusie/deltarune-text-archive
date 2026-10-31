'use strict';
importScripts('text.js','model.js','query.js');
const T=self.DialogueText,M=self.DialogueModel,Q=self.DialogueQuery;
const cache=new Map(), indexes=new Map();let newest=0;
let manifestPromise;
async function json(url){const r=await fetch(url);if(!r.ok)throw new Error(`文本文件加载失败（HTTP ${r.status}）`);return r.json();}
function manifest(){if(!manifestPromise)manifestPromise=json('data/manifest.json').catch(e=>{manifestPromise=null;throw e;});return manifestPromise;}
function chapter(ch){
 if(!cache.has(ch))cache.set(ch,json(`data/ch${ch}.json`).then(data=>{indexes.set(ch,new Map());return data;}).catch(e=>{cache.delete(ch);throw e;}));
 return cache.get(ch);
}
function indexed(data,id,key,field){
 if(id===null)return null;
 const idx=indexes.get(data.chapter);
 const words=data.artwords?.[key]?.[field];
 const identity=words?`${key}:${field}`:id;
 if(!idx.has(identity)){
  const raw=data.strings[id],view=T.format(raw,data.chapter,words);
  idx.set(identity,{raw,source:view.source,plain:view.plain,normalized:view.plain.replace(/\s+/g,' ').trim()});
 }
 return idx.get(identity);
}
self.onmessage=async event=>{
 const {id,state,progress=false}=event.data;newest=id;
 let phase='loading';
 // Older cached pages expect only a terminal response, so progress is opt-in.
 const notify=details=>{if(progress&&id===newest)self.postMessage({id,type:'phase',phase,...details});};
 try{
  const matcher=Q.compile(state),info=await manifest();
  if(id!==newest)return;
  const selected=M.chaptersFor(state.ch).filter(ch=>info.chapters.some(c=>c.chapter===ch));
  let completed=0;notify({completed,total:selected.length});
  let failed=false;
  const datasets=await Promise.all(selected.map(async ch=>{
   const data=await chapter(ch);completed++;
   if(!failed)notify({completed,total:selected.length});
   return data;
  })).catch(error=>{failed=true;throw error;});
  if(id!==newest)return;
  phase='searching';notify({});
  // Display choices never narrow search, including Chinese name variants.
  const fields=M.SEARCH_FIELDS,q=state.q.trim();
  const keyOnly=!state.regex&&(q.includes('_slash_')||q.includes('_gml_'));
  const found=[];let visited=0;
  for(const data of datasets){
   const columns=fields.map(f=>data.languages.indexOf(f)+1);
   for(let index=0;index<data.rows.length;index++){
    const row=data.rows[index];
    let match=state.key?row[0]===state.key:!matcher||matcher.test(row[0]);
    if(!match&&!state.key&&!keyOnly)match=columns.some((col,n)=>{const text=indexed(data,row[col],row[0],fields[n]);return text&&Object.values(text).some(value=>matcher.test(value));});
    if(match)found.push([data,index]);
    if(++visited%1000===0){await new Promise(resolve=>setTimeout(resolve,0));if(id!==newest)return;}
   }
  }
  // Search first, then fold only matching records in the selected chapters.
  // Single-chapter queries always return every matching chapter/key.
  const groups=[],byGroup=new Map();
  for(const ref of found){
   const [data,index]=ref,meta=data.display_dedup;
   const groupId=selected.length>1&&meta?.schema==='key-english-1'?meta.groups[index]:null;
   if(Number.isInteger(groupId)&&groupId>=0&&typeof meta.revision==='string'){
    const identity=`${meta.revision}:${groupId}`;
    if(!byGroup.has(identity)){const group=[];byGroup.set(identity,group);groups.push(group);}
    byGroup.get(identity).push(ref);
   }else groups.push([ref]);
  }
  const pages=Math.max(1,Math.ceil(groups.length/30)),page=Math.min(state.page,pages);
  // Regex and highlight computation stay inside the terminable worker, never on the UI thread.
  const rows=groups.slice((page-1)*30,page*30).map(group=>{
   const [data,i]=group[0];
   const row=T.decodeRow(data,data.rows[i]);row.highlights={key:matcher?matcher.ranges(row.key):[]};
   const meta=data.display_dedup,groupId=meta?.groups[i];
   row.chapters=meta?.schema==='key-english-1'&&meta.chapters?.[groupId]||[row.chapter];
   if(group.length>1){
    row.copies=group.map(([d,n])=>({chapter:d.chapter,key:d.rows[n][0]}));
    row.translationDifference=fields.filter(f=>f!=='en').some(f=>new Set(group.map(([d,n])=>{const v=d.rows[n][d.languages.indexOf(f)+1];return v===null?null:d.strings[v];})).size>1);
   }
   for(const field of fields){const text=indexed(data,data.rows[i][data.languages.indexOf(field)+1],row.key,field);row.highlights[field]={source:matcher&&text?matcher.ranges(text.source):[],plain:matcher&&text?matcher.ranges(text.plain):[]};}
   return row;
  });
  if(id===newest)self.postMessage({id,type:'result',rows,total:groups.length,records:found.length,page,pages,inventory:info.total_rows});
 }catch(e){if(id===newest)self.postMessage({id,type:'error',phase,message:e.message});}
};
