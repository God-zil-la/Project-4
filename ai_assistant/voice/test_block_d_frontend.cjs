// Run: node --test ai_assistant/voice/test_block_d_frontend.cjs
// Executes the actual U6.3 scripts with browser/media/fetch boundaries replaced locally.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const SID = '11111111-1111-4111-8111-111111111111';
const CID = '22222222-2222-4222-8222-222222222222';
const RID = '33333333-3333-4333-8333-333333333333';
class Events {
  constructor() { this.listeners = new Map(); }
  addEventListener(type, fn, options) {
    const list = this.listeners.get(type) || [];
    list.push({fn, capture: options === true || options?.capture});
    this.listeners.set(type, list);
  }
  removeEventListener(type, fn) {
    this.listeners.set(type, (this.listeners.get(type) || []).filter(x => x.fn !== fn));
  }
  dispatchEvent(event) {
    for (const {fn} of [...(this.listeners.get(event.type) || [])].sort((a,b) => Number(b.capture)-Number(a.capture))) {
      fn(event);
      if (event.stopped) break;
    }
    return true;
  }
}
class Event {
  constructor(type, options = {}) { this.type=type; Object.assign(this, options); }
  preventDefault() {}
  stopImmediatePropagation() { this.stopped = true; }
}
class Element extends Events {
  constructor() { super(); this.dataset = {}; this.disabled = false; this.textContent=''; this.classList={add(){},remove(){}}; }
  matches() { return true; }
  pause() { this.paused=true; }
  load() {}
  removeAttribute(name) { delete this[name]; }
  play() { return Promise.resolve(); }
}
function env({upload=false, storage=new Map(), controlledTimeouts=false} = {}) {
  const root=new Element();
  root.dataset={assistantId:'1',conversationId:CID};
  const fields = new Map(['[data-voice-start]','[data-voice-stop]','[data-voice-end]','[data-voice-play]','[data-voice-audio]','[data-voice-remaining]','[data-voice-reply]','[data-voice-recover]','.u63-status'].map(k=>[k,new Element()]));
  root.querySelector=k=>fields.get(k);
  const document=new Events();
  Object.assign(document,{hidden:false,cookie:'csrftoken=test',querySelectorAll:()=>[root]});
  const window=new Events();
  const calls=[], intervals=[], voiceTimeouts=new Set();
  function schedule(fn, ms) {
    if (controlledTimeouts && ms === 45000) {
      const token={expire:fn}; voiceTimeouts.add(token); return token;
    }
    return setTimeout(fn, ms);
  }
  function unschedule(token) {
    if (!voiceTimeouts.delete(token)) clearTimeout(token);
  }
  let time=0, stops=0, microphoneRequests=0;
  const navigator={onLine:true,mediaDevices:{getUserMedia:async()=>{microphoneRequests++;return {getTracks:()=>[{stop(){stops++;}}]};}}};
  class Context {
    constructor(){this.sampleRate=16000;this.state='running';}
    createMediaStreamSource(){return {connect(){},disconnect(){}};}
    createScriptProcessor(){return {connect(){},disconnect(){}};}
    close(){this.state='closed';return Promise.resolve();}
  }
  window.AudioContext=Context;
  const state={fetch:async(url)=> response(url.endsWith('/stop/')?snapshot({active:false,remaining_ms:0}):snapshot())};
  const context=vm.createContext({window,document,navigator,HTMLElement:Element,CustomEvent:Event,
    sessionStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    crypto:{randomUUID:()=>RID},performance:{now:()=>time}, Date,Number,Math,String,Promise,Set,Map,JSON,Error,
    Blob,FormData,AbortController,DOMException,URL,Audio:Element,Uint8Array,Float32Array,ArrayBuffer,DataView,
    setTimeout:schedule,clearTimeout:unschedule,setInterval:fn=>{intervals.push(fn);return intervals.length;},clearInterval(){},
    fetch:async(url,options)=>{calls.push({url,options});return state.fetch(url,options);},console});
  const scripts=['live_voice.js',...(upload?['live_voice_upload.js']:[]),'live_voice_session.js','live_voice_context.js','live_voice_cleanup.js','live_voice_recording_guard.js','live_voice_playback.js'];
  for(const file of scripts) vm.runInContext(fs.readFileSync(path.join(__dirname,'static/voice',file),'utf8'),context,{filename:file});
  document.dispatchEvent(new Event('DOMContentLoaded'));
  const flush=()=>new Promise(resolve=>setImmediate(resolve));
  return {root,document,window,fields,state,calls,storage,navigator,flush,
    controller:root._u63SessionController,voice:root._u63VoiceInstance,
    get stopped(){return stops;},get microphoneRequests(){return microphoneRequests;},
    expireVoiceTimeout(){ for (const token of [...voiceTimeouts]) {voiceTimeouts.delete(token);token.expire();} },
    advance(ms){time+=ms;}};
}
function snapshot(extra={}) {
  return {session_id:SID,assistant_id:1,conversation_id:CID,active:true,remaining_ms:10000,
    server_time:'2026-10-24T12:00:00Z',deadline_at:'2026-10-24T12:00:10Z',...extra};
}
function response(data, status=200) {return {ok:status>=200&&status<300,status,json:async()=>data};}

test('start binds server identity before requesting microphone and displays time',async()=>{
  const e=env();
  await e.controller.start();
  assert.equal(e.root.dataset.voiceSessionId,SID);
  assert.equal(e.voice.isRecording,true);
  assert.equal(e.microphoneRequests,1);
  assert.match(e.fields.get('[data-voice-remaining]').textContent,/0:10/);
  const payload=JSON.parse(e.calls[0].options.body);
  assert.equal(payload.request_id,RID);
  assert.equal(payload.conversation_id,CID);
  assert.equal(payload.duration_ms,undefined);
});
test('server closure stops tracks, discards chunks and blocks new recording',async()=>{
  const e=env();await e.controller.start();
  e.voice.chunks=[new Float32Array([0.1])];
  let audioEvents=0;e.root.addEventListener('u63:audio-ready',()=>audioEvents++);
  e.state.fetch=async()=>response(snapshot({active:false,remaining_ms:0}));
  await e.controller.check();
  assert.equal(e.voice.isRecording,false);
  assert.ok(e.stopped>0);
  assert.equal(e.root.dataset.voiceSessionId,undefined);
  assert.equal(audioEvents,0);
  await e.voice.start();
  assert.equal(e.microphoneRequests,1);
});
test('server grant expires locally even when no further status arrives',async()=>{
  const e=env();await e.controller.start();
  e.advance(10000);e.controller.tick();await e.flush();
  assert.equal(e.voice.isRecording,false);
  assert.equal(e.root.dataset.voiceSessionId,undefined);
  assert.equal(e.calls.filter(x=>x.url.endsWith('/stop/')).length,1);
});
test('offline pauses hardware; reconnect verifies same session without automatic microphone restart',async()=>{
  const e=env();await e.controller.start();
  e.navigator.onLine=false;e.window.dispatchEvent(new Event('offline'));
  assert.equal(e.voice.isRecording,false);
  assert.equal(e.root.dataset.voiceSessionId,SID);
  e.navigator.onLine=true;await e.controller.check();
  assert.equal(e.controller.canRecord(),true);
  assert.equal(e.microphoneRequests,1);
  assert.equal(e.calls.filter(x=>x.url.endsWith('/start/')).length,1);
});
test('network status failure pauses and preserves identity for a later check',async()=>{
  const e=env();await e.controller.start();
  e.state.fetch=async()=>{throw new Error('network');};
  await e.controller.check();
  assert.equal(e.controller.canRecord(),false);
  assert.equal(e.root.dataset.voiceSessionId,SID);
  assert.ok(e.stopped>0);
  e.state.fetch=async()=>response(snapshot());await e.controller.check();
  assert.equal(e.controller.canRecord(),true);
});
test('lost start response retries same request identity, never assigns extra time',async()=>{
  const e=env();let first=true;
  e.state.fetch=async()=>{if(first){first=false;throw new Error('lost response');}return response(snapshot());};
  await e.controller.start();await e.controller.start();
  const starts=e.calls.filter(x=>x.url.endsWith('/start/'));
  assert.equal(starts.length,2);
  assert.equal(JSON.parse(starts[0].options.body).request_id,JSON.parse(starts[1].options.body).request_id);
  assert.equal(e.voice.isRecording,true);
});
test('late status cannot re-open a stopped session',async()=>{
  const e=env();await e.controller.start();let release;
  e.state.fetch=async url=>url.endsWith('/stop/')?response(snapshot({active:false,remaining_ms:0})):new Promise(resolve=>release=resolve);
  const checking=e.controller.check();
  await e.controller.stop();release(response(snapshot()));await checking;
  assert.equal(e.root.dataset.voiceSessionId,undefined);
  assert.equal(e.voice.isRecording,false);
});
test('failed stops survive reload and are removed only after confirmed closure',async()=>{
  const storage=new Map();const e=env({storage});await e.controller.start();
  e.state.fetch=async()=>response({error:'unavailable'},503);
  await e.controller.stop();
  assert.equal(e.window.MyAIStudioVoiceSessions.isPending(SID),true);
  const reload=env({storage});await reload.flush();
  assert.equal(reload.calls.filter(x=>x.url.endsWith('/stop/')).length,1);
  assert.equal(reload.window.MyAIStudioVoiceSessions.isPending(SID),false);
});
test('overlapping stops coalesce and failed requests remain retryable',async()=>{
  const e=env();let release;
  e.state.fetch=async()=>new Promise(resolve=>release=resolve);
  const a=e.window.MyAIStudioVoiceSessions.closeSession(SID);
  const b=e.window.MyAIStudioVoiceSessions.closeSession(SID);
  assert.equal(a,b);
  release(response({error:'busy'},503));assert.equal(await a,false);
  e.state.fetch=async()=>response(snapshot({active:false,remaining_ms:0}));
  assert.equal(await e.window.MyAIStudioVoiceSessions.closeSession(SID),true);
  assert.equal(e.calls.length,2);
});
test('status refresh cannot extend the previous monotonic grant',async()=>{
  const e=env();await e.controller.start();e.advance(3000);
  const before=e.controller.remaining();await e.controller.check();
  assert.ok(e.controller.remaining()<=before);
  e.state.fetch=async()=>response(snapshot({remaining_ms:9000000}));await e.controller.check();
  assert.equal(e.controller.canRecord(),false);
});
test('backgrounding stops capture, foregrounding only checks server status',async()=>{
  const e=env();await e.controller.start();
  e.document.hidden=true;e.document.dispatchEvent(new Event('visibilitychange'));
  assert.equal(e.voice.isRecording,false);
  e.document.hidden=false;e.document.dispatchEvent(new Event('visibilitychange'));await e.flush();
  assert.equal(e.microphoneRequests,1);
  assert.equal(e.controller.canRecord(),true);
});
test('conversation change closes only the old session and never creates a conversation',async()=>{
  const e=env();await e.controller.start();
  e.window.MyAIStudioVoiceContext.set(e.root,1,'44444444-4444-4444-8444-444444444444');
  await e.flush();
  assert.equal(e.root.dataset.voiceSessionId,undefined);
  assert.equal(e.voice.isRecording,false);
  assert.equal(e.calls.filter(x=>x.url.endsWith('/stop/')).length,1);
  assert.equal(e.calls.every(x=>x.url.startsWith('/api/live-voice/')),true);
});
test('normal recording stop requests the server-owned voice pipeline',async()=>{
  const e=env({upload:true});
  e.state.fetch=async url=>url.endsWith('/upload/')?response({session_id:SID,request_id:RID,result:{state:'completed'}}):response(snapshot());
  await e.controller.start();e.voice.chunks=[new Float32Array([0.1,0.2])];
  await e.voice.stop();await e.flush();
  const upload=e.calls.find(x=>x.url.endsWith('/upload/'));
  assert.ok(upload);
  assert.equal(upload.options.body.get('process_voice'),'true');
  assert.equal(upload.options.body.get('prepare_only'),null);
  assert.equal(e.root.dataset.voiceSessionId,SID);
  await e.controller.stop(); // End the pending mocked reply poll without re-uploading.
  assert.equal(e.calls.filter(x=>x.url.endsWith('/upload/')).length,1);
});
test('microphone permission returning after server closure is immediately released',async()=>{
  const e=env();let release;
  e.navigator.mediaDevices.getUserMedia=()=>new Promise(resolve=>release=resolve);
  const starting=e.controller.start();await e.flush();
  e.state.fetch=async()=>response(snapshot({active:false,remaining_ms:0}));await e.controller.check();
  let stops=0;release({getTracks:()=>[{stop(){stops++;}}]});await starting;
  assert.equal(stops,1);assert.equal(e.voice.isRecording,false);
});

test('late start response after conversation switch is closed without opening microphone',async()=>{
  const e=env();let release;
  e.state.fetch=async url=>url.endsWith('/start/')?new Promise(resolve=>release=resolve):response(snapshot({active:false,remaining_ms:0}));
  const starting=e.controller.start();
  e.window.MyAIStudioVoiceContext.set(e.root,1,'44444444-4444-4444-8444-444444444444');
  release(response(snapshot()));await starting;await e.flush();
  assert.equal(e.microphoneRequests,0);
  assert.equal(e.root.dataset.voiceSessionId,undefined);
  assert.equal(e.calls.filter(x=>x.url.endsWith('/stop/')).length,1);
});
test('server closure aborts an upload and stale audio cannot create another turn',async()=>{
  const e=env({upload:true});let uploadSignal;
  e.state.fetch=async(url,options)=>{
    if(url.endsWith('/upload/')) {
      uploadSignal=options.signal;
      return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('Cancelled','AbortError'))));
    }
    return response(snapshot());
  };
  await e.controller.start();e.voice.chunks=[new Float32Array([0.1])];await e.voice.stop();
  assert.ok(uploadSignal);
  e.state.fetch=async()=>response(snapshot({active:false,remaining_ms:0}));
  await e.controller.check();await e.flush();
  assert.equal(uploadSignal.aborted,true);
  e.root.dispatchEvent(new Event('u63:audio-ready',{detail:{sessionId:SID,conversationId:CID,wav:new Blob(['audio'])}}));
  await e.flush();
  assert.equal(e.calls.filter(x=>x.url.endsWith('/upload/')).length,1);
});

// Block E playback and recovery cases, sharing the existing browser boundary harness.
function replyRoutes(url) {
  if (url.endsWith('/audio/')) return {...response({}),headers:{get:()=> 'audio/mpeg'},blob:async()=>new Blob(['ID3local-test'],{type:'audio/mpeg'})};
  if (url.includes('/turns/')) return response({session_id:SID,request_id:RID,state:'completed',has_assistant_answer:true});
  if (url.endsWith('/upload/')) return response({session_id:SID,request_id:RID,result:{state:'completed',audio_available:true}});
  return response(snapshot());
}
test('Block E uploads speech, observes saved answer and plays generated audio',async()=>{
  const e=env({upload:true});e.state.fetch=async url=>replyRoutes(url);
  await e.controller.start();e.voice.chunks=[new Float32Array([0.1,0.2])];await e.voice.stop();await e.flush();
  const turn=e.root._u63TurnClient;
  assert.ok(turn.player);
  assert.equal(e.fields.get('[data-voice-reply]').disabled,false);
  assert.match(e.fields.get('.u63-status').textContent,/Svarar/);
  assert.equal(turn.pending,null);
  assert.equal(e.root._u63VoiceTurnBusy,false);
  assert.equal(e.calls.filter(x=>x.url.endsWith('/upload/')).length,1);
  assert.equal(e.calls.filter(x=>x.url.endsWith('/audio/')).length,1);
  assert.equal(e.microphoneRequests,1);
});
test('Block E manual play recovers autoplay denial without regeneration',async()=>{
  const e=env({upload:true});e.state.fetch=async url=>replyRoutes(url);
  await e.controller.start();e.voice.chunks=[new Float32Array([0.1])];await e.voice.stop();await e.flush();
  const turn=e.root._u63TurnClient;
  turn.player.play=async()=>{throw new Error('Autoplay blocked');};
  await turn.play();
  assert.match(e.fields.get('.u63-status').textContent,/Tap Play AI reply/);
  const before=e.calls.length;
  turn.player.play=async()=>{};await turn.play();
  assert.match(e.fields.get('.u63-status').textContent,/Svarar/);
  assert.equal(e.calls.length,before);
});
test('Block E stopping session cancels generated playback and prevents later play',async()=>{
  const e=env({upload:true});e.state.fetch=async url=>replyRoutes(url);
  await e.controller.start();e.voice.chunks=[new Float32Array([0.1])];await e.voice.stop();await e.flush();
  const turn=e.root._u63TurnClient,player=turn.player;
  e.state.fetch=async()=>response(snapshot({active:false,remaining_ms:0}));
  await e.controller.stop();
  assert.equal(player.paused,true);assert.equal(turn.audioUrl,null);
  assert.equal(e.fields.get('[data-voice-reply]').disabled,true);
  const before=e.calls.length;await turn.play();assert.equal(e.calls.length,before);
});
test('Block E lost upload response recovers by GET without repeating STT AI or TTS POST',async()=>{
  const e=env({upload:true});
  e.state.fetch=async url=>{if(url.endsWith('/upload/'))throw new Error('Lost response');return replyRoutes(url);};
  await e.controller.start();e.voice.chunks=[new Float32Array([0.1])];await e.voice.stop();await e.flush();
  const turn=e.root._u63TurnClient;
  assert.ok(turn.pending);
  assert.equal(e.fields.get('[data-voice-recover]').disabled,false);
  await turn.recover();
  assert.equal(turn.pending,null);assert.ok(turn.player);
  assert.equal(e.calls.filter(x=>x.url.endsWith('/upload/')).length,1);
  assert.equal(e.calls.filter(x=>x.url.endsWith('/audio/')).length,1);
});
test('Block E uncertain processing clears recovery and never automatically re-dispatches',async()=>{
  const e=env({upload:true});
  e.state.fetch=async url=>url.includes('/turns/')?response({session_id:SID,request_id:RID,state:'uncertain',has_assistant_answer:true}):replyRoutes(url);
  await e.controller.start();e.voice.chunks=[new Float32Array([0.1])];await e.voice.stop();await e.flush();
  const turn=e.root._u63TurnClient;assert.equal(turn.pending,null);
  assert.match(e.fields.get('.u63-status').textContent,/stopped safely/);
  const before=e.calls.length;await turn.recover();assert.equal(e.calls.length,before);
  assert.equal(e.calls.some(x=>x.url.endsWith('/audio/')),false);
});
test('Block E denied microphone access produces no voice upload or turn',async()=>{
  const e=env({upload:true});
  e.navigator.mediaDevices.getUserMedia=async()=>{throw new Error('Microphone permission denied');};
  await e.controller.start();
  assert.equal(e.voice.isRecording,false);
  assert.match(e.fields.get('.u63-status').textContent,/permission denied/);
  assert.equal(e.calls.some(x=>x.url.endsWith('/upload/')),false);
  assert.equal(e.root._u63TurnClient.pending,null);
});


// Block F profiles below simulate mobile browser boundaries, NOT physical devices.
for (const platform of ['Android Chrome (simulated)','iOS Safari (simulated)']) {
  test(`Block F ${platform}: permission, capture, upload, playback, background and restart`,async()=>{
    const e=env({upload:true});
    e.navigator.userAgent=platform;
    if(platform.startsWith('iOS')) {
      e.window.webkitAudioContext=e.window.AudioContext;
      e.window.AudioContext=undefined;
    }
    e.state.fetch=async url=>replyRoutes(url);
    await e.controller.start();
    assert.equal(e.voice.isRecording,true);
    assert.ok(e.voice.context);
    e.voice.chunks=[new Float32Array([0.1,0.2])];await e.voice.stop();await e.flush();
    assert.ok(e.root._u63TurnClient.player);
    assert.match(e.fields.get('.u63-status').textContent,/Svarar/);
    e.document.hidden=true;e.document.dispatchEvent(new Event('visibilitychange'));
    assert.equal(e.root._u63TurnClient.player,null);
    assert.equal(e.voice.isRecording,false);
    e.document.hidden=false;e.document.dispatchEvent(new Event('visibilitychange'));await e.flush();
    assert.equal(e.voice.isRecording,false);
    await e.controller.start();assert.equal(e.voice.isRecording,true);
    assert.equal(e.calls.filter(x=>x.url.endsWith('/start/')).length,1);
    e.state.fetch=async()=>response(snapshot({active:false,remaining_ms:0}));await e.controller.stop();
    assert.equal(e.voice.isRecording,false);assert.ok(e.stopped>0);
  });
  test(`Block F ${platform}: denied permission sends no audio`,async()=>{
    const e=env({upload:true});e.navigator.userAgent=platform;
    e.navigator.mediaDevices.getUserMedia=async()=>{throw new Error('Microphone permission denied');};
    await e.controller.start();
    assert.equal(e.voice.isRecording,false);
    assert.equal(e.calls.filter(x=>x.url.endsWith('/upload/')).length,0);
    assert.match(e.fields.get('.u63-status').textContent,/permission denied/);
  });
}
test('Block F simulated request timeout recovers the same turn with GET only',async()=>{
  const e=env({upload:true,controlledTimeouts:true});
  let uploadSignal;
  e.state.fetch=async(url,options)=>{
    if(url.endsWith('/upload/')) {
      uploadSignal=options.signal;
      return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('Timed out','AbortError'))));
    }
    return replyRoutes(url);
  };
  await e.controller.start();e.voice.chunks=[new Float32Array([0.1])];await e.voice.stop();
  e.expireVoiceTimeout();await e.flush();
  assert.equal(uploadSignal.aborted,true);
  assert.ok(e.root._u63TurnClient.pending);
  assert.match(e.fields.get('.u63-status').textContent,/timed out/);
  await e.root._u63TurnClient.recover();
  assert.ok(e.root._u63TurnClient.player);
  assert.equal(e.calls.filter(x=>x.url.endsWith('/upload/')).length,1);
});
test('Block F simulated network reconnection resumes reply status without microphone restart or POST retry',async()=>{
  const e=env({upload:true});let uploadSignal;
  e.state.fetch=async(url,options)=>{
    if(url.endsWith('/upload/')) {
      uploadSignal=options.signal;
      return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('Offline','AbortError'))));
    }
    return replyRoutes(url);
  };
  await e.controller.start();e.voice.chunks=[new Float32Array([0.1])];await e.voice.stop();
  e.navigator.onLine=false;e.window.dispatchEvent(new Event('offline'));await e.flush();
  assert.equal(uploadSignal.aborted,true);
  assert.ok(e.root._u63TurnClient.pending);
  e.navigator.onLine=true;await e.controller.check();await e.flush();
  assert.ok(e.root._u63TurnClient.player);
  assert.equal(e.microphoneRequests,1);
  assert.equal(e.calls.filter(x=>x.url.endsWith('/upload/')).length,1);
  assert.equal(e.calls.filter(x=>x.url.endsWith('/start/')).length,1);
});
