'use strict';
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const sources=[],gains=[];
class AudioContext{
 currentTime=0;
 destination={};
 resume(){return Promise.resolve();}
 decodeAudioData(data){return Promise.resolve(data);}
 createGain(){const gain={gain:{setValueAtTime(v){gain.initial=v;},linearRampToValueAtTime(v,t){gain.ramp=[v,t];}},connect(){},disconnect(){}};gains.push(gain);return gain;}
 createBufferSource(){const source={started:false,stopped:false,playbackRate:{setValueAtTime(v){source.pitch=v;}},connect(){},disconnect(){},start(){source.started=true;},stop(){source.stopped=true;source.onended?.();}};sources.push(source);return source;}
}
const sandbox={module:{exports:{}},AudioContext,performance:{now:()=>0},console,
 fetch:async()=>({ok:true,arrayBuffer:async()=>new ArrayBuffer(8)})};
vm.runInNewContext(fs.readFileSync(require.resolve('../web/soul-yellow.js'),'utf8'),sandbox);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 const a=sandbox.module.exports.createAudio();await a.unlock();
 a.effect('small');await flush();assert.equal(sources.length,1);assert(sources[0].started);
 a.charge(10);const charge=sources[1];assert(charge.loop&&charge.started);assert.equal(charge.pitch,0.1);
 assert.deepEqual(gains[1].ramp,[0.3,20/30]);
 a.charge(19);assert.equal(charge.pitch,1);a.charge(20);assert.equal(charge.pitch,1);
 assert.equal(sources.length,2,'one persistent charge loop, not one sound per animation frame');
 a.stopCharge();assert(charge.stopped);assert(!sources[0].stopped,'release does not cut off unrelated shot tails');
 a.effect('big');await flush();assert(sources[2].started);
 a.stop();assert(sources.every(s=>s.stopped),'switch/disable/focus cancellation stops every sound');
 const count=sources.length;a.effect('small');a.stop();await flush();
 assert.equal(sources.length,count,'an async decode completion cannot play after cancellation');
 console.log('Soul audio: one charge loop, original pitch/envelope, shot tails, and cancellation (including pending playback) passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
