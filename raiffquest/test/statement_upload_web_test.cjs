const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {setImmediate: tick} = require('node:timers/promises');
const source = fs.readFileSync('raiffquest/scripts/frontend/statement_upload.gd', 'utf8');
const bridge = source.match(/const JS_SETUP := """([\s\S]*?)"""/)[1];
function setup(fetchImpl) {
  const inputs=[], timers=new Map(); let id=0;
  const context={window:{}, document:{body:{appendChild(){}}, createElement(){const input={style:{},files:[],listeners:{},addEventListener(n,f){this.listeners[n]=f;},click(){},remove(){this.removed=true;}}; inputs.push(input);return input;}}, AbortController,
    FormData:class {constructor(){this.fields=[];} append(...args){this.fields.push(args);}},
    setTimeout(f){timers.set(++id,f);return id;},clearTimeout(i){timers.delete(i);},fetch:fetchImpl};
  vm.runInNewContext(bridge,context);return {app:context.window.raiffStatementUpload,inputs,timers};
}
async function run(){
  let calls=[];
  const good=setup(async(url,options)=>{calls.push({url,options});return {status:200,text:async()=>'{"profile_fields":{},"missing_fields":[]}'};});
  good.app.pick('',240000); assert.equal(good.app.state,'error');assert.equal(good.inputs.length,0);
  for(const file of [{name:'empty.pdf',size:0},{name:'large.pdf',size:25*1024*1024+1},{name:'bad.exe',size:12}]){
    good.app.pick('session-A',240000);const input=good.inputs.at(-1);input.files=[file];input.onchange();assert.equal(good.app.state,'error');assert.equal(input.removed,true);
  }
  assert.equal(calls.length,0);
  good.app.pick('session-A',240000);good.inputs.at(-1).listeners.cancel();assert.equal(good.app.state,'cancelled');
  good.app.pick('session-A',240000);const input=good.inputs.at(-1);input.files=[{name:'unsafe"\r\n.pdf',size:12}];input.onchange();await tick();
  assert.equal(good.app.state,'done');assert.equal(good.app.status,200);assert.equal(calls[0].url,'/api/onboarding/statement');
  assert.equal(calls[0].options.redirect,'error');assert.equal(calls[0].options.body.fields[0][0],'session_id');assert.equal(calls[0].options.body.fields[0][1],'session-A');
  assert.equal(calls[0].options.body.fields[1][0],'file');assert.equal(calls[0].options.body.fields[1][2],'unsafe___.pdf');assert.equal(good.timers.size,0);
  const slow=setup((_url,opts)=>new Promise((_resolve,reject)=>opts.signal.addEventListener('abort',()=>reject(Object.assign(new Error('abort'),{name:'AbortError'})))));
  slow.app.pick('session-B',240000);slow.inputs[0].files=[{name:'data.csv',size:12}];slow.inputs[0].onchange();await tick();[...slow.timers.values()][0]();await tick();assert.equal(slow.app.errorCode,'timeout');assert.equal(slow.app.state,'error');assert.equal(slow.timers.size,0);
  console.log('[statement-upload-web] PASS: session, validation, cancel, multipart, redirect policy, timeout');
}
run().catch(e=>{console.error(e);process.exitCode=1;});

