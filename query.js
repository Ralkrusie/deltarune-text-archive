(function(root){
'use strict';
const word=/[\p{L}\p{N}\p{M}_]/u;
function compile(state){
 const q=state.q.trim();if(!q)return null;
 if(state.regex&&q.length>256)throw Error('正则表达式最多 256 个字符。');
 const pattern=state.regex?q:q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 let re;try{re=new RegExp(pattern,'gu'+(state.caseSensitive?'':'i'));}catch{throw Error('正则表达式有误，请检查括号、转义和字符范围。');}
 function scan(text,first=false){
  re.lastIndex=0;const spans=[];let m;
  while((m=re.exec(text))!==null){
   const start=m.index,end=start+m[0].length;
   const before=Array.from(text.slice(Math.max(0,start-2),start)).pop()||'';
   const after=end<text.length?String.fromCodePoint(text.codePointAt(end)):'';
   if(!state.wholeWord||(!word.test(before)&&!word.test(after))){
    if(first)return true;
    if(end>start)spans.push([start,end]);
    if(spans.length>=2000)break;
   }
   if(!m[0].length){if(end>=text.length)break;re.lastIndex=end+(text.codePointAt(end)>0xffff?2:1);}
  }
  return first?false:spans;
 }
 return {test:text=>scan(text,true),ranges:text=>scan(text,false)};
}
const api={compile};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.DialogueQuery=api;
})(typeof globalThis!=='undefined'?globalThis:this);
