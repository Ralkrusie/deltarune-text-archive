'use strict';
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
let contexts=0;const voices=[];
class AudioContext{
 constructor(){contexts++;this.destination={};}
 resume(){return Promise.resolve();}
 decodeAudioData(){return Promise.resolve({});}
 createGain(){return {gain:{value:0},connect(){},disconnect(){}};}
 createBufferSource(){const source={playbackRate:{value:1},connect(){},disconnect(){},start(){this.started=true;},stop(){this.stopped=true;}};voices.push(source);return source;}
}
const sandbox={module:{exports:{}},AudioContext,console,performance:{now:()=>0},fetch:async()=>({ok:true,arrayBuffer:async()=>new ArrayBuffer(4)})};
vm.runInNewContext(fs.readFileSync(require.resolve('../web/soul-extra.js'),'utf8'),sandbox);
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 const bank=sandbox.module.exports.createSoundBank();assert.equal(contexts,0);
 bank.charge();bank.stop();await flush();assert.equal(voices.length,0,'pending loop cannot resurrect after cancel');
 bank.charge();await flush();assert.equal(voices.length,1);assert.equal(voices[0].loop,true);
 assert.equal(voices[0].playbackRate.value,0.25);bank.pitch(0.9);assert.equal(voices[0].playbackRate.value,0.9);
 bank.stopLoop();bank.effect('dash',0.5,2);await flush();assert(voices[0].stopped);assert.equal(voices[1].playbackRate.value,2);
 bank.effect('wing');bank.stop();await flush();assert.equal(voices.length,2,'cancel pending one-shot');assert(voices[1].stopped);
 console.log('Extra soul audio: lazy context, charge loop/pitch, dash pitch and cancellation passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
