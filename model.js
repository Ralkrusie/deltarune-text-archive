(function(root){
'use strict';
const LANGUAGES=['en','ja','zh'];
const CHINESE=[['zh_default','人名不译'],['zh_recruitable','仅译招揽'],['zh_names','人名翻译']];
const CHAPTERS=[1,2,3,4,5];
const SEARCH_FIELDS=['en','ja',...CHINESE.map(x=>x[0])];
function chaptersFor(value){
 const wanted=(Array.isArray(value)?value:String(value??0).split(',')).map(Number);
 const selected=CHAPTERS.filter(ch=>wanted.includes(ch));
 return wanted.includes(0)||!selected.length?CHAPTERS.slice():selected;
}
function toggleChapter(value,ch){
 const selected=chaptersFor(value);
 if(ch===0)return CHAPTERS.slice();
 if(selected.length===CHAPTERS.length)return [ch];
 if(selected.length===1&&selected[0]===ch)return selected;
 return CHAPTERS.filter(n=>n===ch?!selected.includes(n):selected.includes(n));
}
function stateFrom(params, preferences={}, narrow=false){
 const get=(name,fallback)=>params.has(name)?params.get(name):preferences[name]??fallback;
 const ch=chaptersFor(get('ch',0));
 const wanted=String(get('lang','en,ja,zh')).split(',');
 const languages=LANGUAGES.filter(l=>wanted.includes(l));
 return {q:params.get('q')||'',key:params.get('key')||'',ch,
 lang:languages.length?languages:LANGUAGES.slice(),zh:['default','recruitable','names','smart'].includes(get('zh','smart'))?get('zh','smart'):'smart',
 mode:['plain','source','restore'].includes(get('mode','plain'))?get('mode','plain'):'plain',layout:get('layout',narrow?'vertical':'horizontal')==='vertical'?'vertical':'horizontal',
 caseSensitive:params.get('case')==='1',wholeWord:params.get('word')==='1',regex:params.get('regex')==='1',highlight:get('highlight','1')!==false&&get('highlight','1')!=='0',
 page:Math.max(1,Math.min(100000,parseInt(params.get('page'),10)||1))};
}
function paramsFor(state){
 const p=new URLSearchParams();
 if(state.q)p.set('q',state.q);if(state.key)p.set('key',state.key);
 const chapters=chaptersFor(state.ch);
 p.set('ch',chapters.length===CHAPTERS.length?'0':chapters.join(','));p.set('lang',state.lang.join(','));p.set('zh',state.zh);
 p.set('mode',state.mode);p.set('layout',state.layout);if(state.page>1)p.set('page',state.page);
 if(state.caseSensitive)p.set('case','1');if(state.wholeWord)p.set('word','1');if(state.regex)p.set('regex','1');if(state.highlight===false)p.set('highlight','0');
 return p;
}
function fieldsFor(state){
 const fields=[];
 if(state.lang.includes('en'))fields.push('en');if(state.lang.includes('ja'))fields.push('ja');
 if(state.lang.includes('zh')){
  if(state.zh==='smart')fields.push(...CHINESE.map(x=>x[0]));
  else fields.push({default:'zh_default',recruitable:'zh_recruitable',names:'zh_names'}[state.zh]);
 }
 return fields;
}
function chineseRows(row,selection){
 if(selection!=='smart'){
  const field={default:'zh_default',recruitable:'zh_recruitable',names:'zh_names'}[selection];
  return [{raw:row[field],labels:[CHINESE.find(x=>x[0]===field)[1]],fields:[field]}];
 }
 const groups=[];
 for(const [field,label] of CHINESE){
  const group=groups.find(g=>g.raw===row[field]);
  if(group){group.labels.push(label);group.fields.push(field);}
  else groups.push({raw:row[field],labels:[label],fields:[field]});
 }
 return groups;
}
const api={LANGUAGES,CHINESE,CHAPTERS,SEARCH_FIELDS,chaptersFor,toggleChapter,stateFrom,paramsFor,fieldsFor,chineseRows};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.DialogueModel=api;
})(typeof globalThis!=='undefined'?globalThis:this);
