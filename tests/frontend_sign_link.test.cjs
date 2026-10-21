const test=require('node:test'),assert=require('node:assert/strict');
const {mount}=require('../frontend/sign_link.js');
const tick=()=>new Promise(r=>setImmediate(r));
const id='12345678-1234-1234-1234-123456789abc';
function setup(select,search='?sign='+id){
 const events=new Map(),opened=[],removed=[],messages=[];
 const api={user:null,ready:Promise.resolve()};
 const environment={location:{search},addEventListener:(n,f)=>events.set(n,f),removeEventListener:n=>events.delete(n)};
 const controller=mount({api,environment,selectSign:async target=>{opened.push(target);return select(target);},
   createMarker:sign=>({sign}),removeMarker:marker=>removed.push(marker),onMessage:text=>messages.push(text)});
 return {api,events,opened,removed,messages,controller};
}
test('a sign link waits for a verified login then opens the exact record',async()=>{
 const a=setup(async target=>({sign:{id:target}}));await tick();assert.equal(a.opened.length,0);
 a.api.user={id:'u'};a.events.get('signsight-auth-changed')();await tick();
 assert.deepEqual(a.opened,[id]);
});
test('malformed record links never issue a selection request',async()=>{
 const a=setup(async()=>{throw Error('unexpected');},'?sign=https://evil.example');a.api.user={id:'u'};await tick();
 assert.equal(a.opened.length,0);assert.match(a.messages.at(-1),/không hợp lệ/);
});
test('logout removes the highlight and ignores late results',async()=>{
 let finish;const a=setup(()=>new Promise(r=>finish=r));await tick();
 a.api.user={id:'u'};a.events.get('signsight-auth-changed')();await tick();
 a.api.user=null;a.events.get('signsight-auth-changed')();
 finish({sign:{id}});await tick();assert.equal(a.removed.length,0);
});
test('changing auth clears the previous highlight without retaining private state',async()=>{
 const a=setup(async target=>({sign:{id:target}}));await tick();
 a.api.user={id:'u'};a.events.get('signsight-auth-changed')();await tick();
 a.api.user=null;a.events.get('signsight-auth-changed')();
 assert.equal(a.removed.length,1);
});

test('ready plus the page auth notification opens the linked record only once',async()=>{
 const a=setup(async target=>({sign:{id:target}}));a.api.user={id:'u'};
 a.api.ready.then(()=>a.events.get('signsight-auth-changed')());
 await tick();assert.deepEqual(a.opened,[id]);
});
