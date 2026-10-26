(function(root){
'use strict';
const T=typeof module!=='undefined'&&module.exports?require('./text.js'):root.DialogueText;
const M=typeof module!=='undefined'&&module.exports?require('./model.js'):root.DialogueModel;
function copyValue(raw,ch,mode){
 if(raw===null||raw===undefined)return '〔缺少此语言文本〕';
 if(raw==='')return '〔空字符串〕';
 if(mode==='source')return T.sourceText(raw);
 const view=T.format(raw,ch);
 if(view.state==='control-only')return '〔仅含控制串〕';
 return view.plain.replace(/[ \t]*[\r\n]+[ \t\u3000]*/g,' ').replace(/[ \t]+$/g,'');
}
function copyEntry(row,state){
 const languages=M.LANGUAGES.filter(l=>state.lang.includes(l)),multi=languages.length>1;
 const blocks=languages.map(lang=>{
  const groups=lang==='zh'?M.chineseRows(row,state.zh):[{raw:row[lang],labels:[]}];
  return groups.map(group=>{
   let label=multi?lang.toUpperCase():'';
   if(groups.length>1)label+=(label?' ':'')+'['+group.labels.join('·')+']';
   return (label?label+': ':'')+copyValue(group.raw,row.chapter,state.mode);
  }).join('\n');
 });
 return row.key+'\n\n'+blocks.join('\n\n');
}
function sourceURL(ch,file,line){
 if(!Number.isInteger(ch)||ch<1||ch>5||!/^gml_[A-Za-z0-9_]+\.gml$/.test(file)||!Number.isInteger(line)||line<1)return null;
 return 'https://code.deltarune.wiki/ch'+ch+'/'+file.slice(0,-4).toLowerCase()+'#L'+line;
}
const api={copyValue,copyEntry,sourceURL};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.DialogueActions=api;
})(typeof globalThis!=='undefined'?globalThis:this);
