'use strict';
const assert=require('node:assert/strict');
const {create}=require('../web/soul-switch.js');
(async()=>{
 let contexts=0,decoded=0,voices=[];
 class AudioContext{
  constructor(){contexts++;this.destination={};}
  resume(){return Promise.resolve();}
  decodeAudioData(){decoded++;return Promise.resolve({});}
  createBufferSource(){const v={playbackRate:{},connect(){},disconnect(){},start(){this.started=true;},stop(){this.stopped=true;}};voices.push(v);return v;}
 }
 const env={AudioContext,fetch:async()=>({ok:true,arrayBuffer:async()=>new ArrayBuffer(1)}),console};
 const sound=create(env);
 assert.equal(contexts,0,'initialization is silent');
 for(let i=0;i<5;i++)await sound.play();
 assert.equal(voices.length,5);
 assert.equal(decoded,1);
 assert(voices.every(v=>v.started&&v.playbackRate.value===0.8));
 assert(voices.slice(0,-1).every(v=>v.stopped),'rapid switches replace previous sound');
 sound.stop();assert(voices.at(-1).stopped);
 const pending=sound.play();sound.stop();await pending;
 assert.equal(voices.length,5,'disable cancels pending playback');
 await Promise.all([sound.play(),sound.play()]);
 assert.equal(voices.length,6,'only latest pending switch plays');
 console.log('Soul switch: silent initialization, five switches, pitch, reuse and cancellation passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
