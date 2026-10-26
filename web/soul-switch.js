'use strict';
(() => {
 function create(env=globalThis){
  let context, buffer, decoding, source, generation=0;
  // Fetch ahead, but create/resume the audio context only after a user click.
  const bytes=env.fetch('assets/soul/audio/snd_great_shine.ogg').then(r=>{
   if(!r.ok)throw new Error('Soul switch audio: '+r.status);
   return r.arrayBuffer();
  });
  bytes.catch(()=>{});
  function stop(){generation++;if(source){source.stop();source.disconnect();source=null;}}
  async function play(){
   stop();const token=generation;
   try{
    context ||= new env.AudioContext();
    const resume=context.resume();
    decoding ||= bytes.then(raw=>context.decodeAudioData(raw)).then(value=>buffer=value);
    await Promise.all([resume,decoding]);
    if(token!==generation)return;
    const voice=context.createBufferSource();
    voice.buffer=buffer;voice.playbackRate.value=0.8;
    voice.connect(context.destination);source=voice;
    voice.onended=()=>{voice.disconnect();if(source===voice)source=null;};
    voice.start();
   }catch(error){env.console.warn('灵魂切换音效未能播放',error);}
  }
  return {play,stop};
 }
 if(typeof module==='object'&&module.exports)module.exports={create};
 else window.SoulSwitch={create};
})();
