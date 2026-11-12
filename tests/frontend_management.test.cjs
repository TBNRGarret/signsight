const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
class Element{
 constructor(tag='div'){this.tag=tag;this.children=[];this.isConnected=true;this.value='';this.dataset={};this.hidden=false;this.attributes={};}
 set textContent(v){this.text=String(v);this.children=[];}get textContent(){return (this.text||'')+this.children.map(n=>n.textContent||'').join('');}
 append(...nodes){this.children.push(...nodes);}replaceChildren(...nodes){this.children.forEach(n=>n.isConnected=false);this.children=nodes;this.text='';}
 focus(){this.focused=true;}
 setAttribute(k,v){this.attributes[k]=v;}getContext(){return {drawImage(){},strokeRect(){},fillText(){}};}
 set innerHTML(_){throw Error('Untrusted HTML rendering');}
}
const tick=()=>new Promise(r=>setImmediate(r)),page=(items=[],offset=0,total=items.length,limit=10)=>({items,total,offset,limit});
function setup(handler,ready){
 const elements=new Map(),events=new Map(),calls=[],redirects=[];
 const api={user:{username:'mod',role:'manager'},ready,async request(route,options){calls.push(route);if(route==='/taxonomy')return require('./catalog_fixture.cjs');return handler(route,options);}};
 const document={getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement:tag=>new Element(tag)};
 const window={signSightAuth:api,crypto:require('node:crypto').webcrypto,location:{replace:url=>redirects.push(url)},addEventListener:(n,f)=>events.set(n,f)};
 window.signSightCatalog=require('../frontend/shared/catalog.js');
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../frontend/staff/management.js'),'utf8'),{window,document,URLSearchParams,AbortController,
  createImageBitmap:async()=>({width:100,height:100,close(){}}),URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}}});
 return {api,elements,calls,redirects,get:document.getElementById,changed:events.get('signsight-auth-changed')};
}
const summary={contributions:2,reports:1,duplicates:0,signs:1000};
const empty=async route=>route==='/manager/summary'?summary:page();
const contributionRow=id=>({id,image_id:'i1',status:'pending',detection:{qcvn_code:'P.102',name_vi:'Cấm',confidence:.9,predicted_class:5},latitude:10,longitude:106});

for(const type of ['contributions','reports','duplicates'])test('committed '+type+' retry remains reachable after item leaves pending queue',async()=>{
 const sign={id:'s',qcvn_code:'P.102',latitude:10,longitude:106,status:'active',revision:0};
 const row={...contributionRow('vanished'),status:type==='duplicates'?'pending_review':'pending',action:'confirm_existing',record_id:'s',base_revision:0,comment:'Road proof',new_record:sign,existing_record:sign,class_match:true,distance_meters:3};
 let committed=false,posts=0;
 const a=setup(async(route)=>{
  if(route==='/manager/summary')return summary;
  if(route.endsWith('/review')){posts++;committed=true;if(posts===1)throw Object.assign(Error('lost after commit'),{outcomeUnknown:true});return {status:'accepted'};}
  if(route.startsWith('/manager/observations')||route.startsWith('/manager/reports')||route.startsWith('/manager/duplicates'))return page(committed?[]:[row]);
  if(route==='/signs/s')return {sign,evidence:[]};return new Blob();
 });a.changed();await tick();await tick();if(type!=='contributions')await a.get('tab-'+type).onclick();
 a.get('review-comment').value='frozen note';await a.get('review-accept').onclick();await a.get('refresh-'+type).onclick();
 assert.equal(a.get('review-detail').hidden,true);assert.equal(a.get('pending-review-list').hidden,false);
 await a.get('pending-review-list').children[0].onclick();await tick();assert.equal(a.get('review-detail').hidden,false);
 assert.equal(a.get('review-comment').value,'frozen note');await a.get('review-retry').onclick();assert.equal(posts,2);
 assert.equal(a.get('pending-review-list').hidden,true);
});

test('conflict read for an unselected row remains authoritative when reopened',async()=>{
 const items=[contributionRow('a'),contributionRow('b')];let fail;
 const a=setup(async route=>{
  if(route==='/manager/summary')return summary;if(route.endsWith('/review'))return new Promise((_,reject)=>fail=reject);
  if(route==='/observations/a')return {...items[0],status:'accepted',review_comment:'Already handled'};
  return route.startsWith('/manager/observations')?page(items):new Blob();
 });a.changed();await tick();await tick();const pending=a.get('review-accept').onclick();await tick();
 a.get('contributions').children[1].children[0].children[0].onclick();fail(Object.assign(Error('conflict'),{status:409}));await pending;
 a.get('contributions').children[0].children[0].children[0].onclick();await tick();
 assert.equal(a.get('review-actions').hidden,true);assert.match(a.get('detail-meta').textContent,/Already handled/);
});

test('policy network failure states that completion is unknown and keeps the edited value',async()=>{
 const a=setup(async(route,options)=>{
  if(options?.method==='PATCH')throw Object.assign(Error('Failed to fetch'),{outcomeUnknown:true});
  if(route==='/policy')return {confirmation_days:30};return empty(route);
 });a.api.user.role='admin';a.changed();await tick();await a.get('tab-policy').onclick();a.get('days').value='45';
 const submitter=new Element('button');await a.get('policy-form').onsubmit({preventDefault(){},submitter});
 assert.match(a.get('message').textContent,/Chưa xác nhận/);assert.equal(a.get('days').value,'45');assert.equal(submitter.disabled,false);
});

test('unknown review keeps immutable request and note through queue refresh until manual replay',async()=>{
 const row=contributionRow('recovery'),attempts=[];let completed=false;
 const a=setup(async(route,options)=>{
  if(route==='/manager/summary')return summary;
  if(route.endsWith('/review')){attempts.push(options);if(attempts.length===1)throw Object.assign(Error('lost'),{status:0,outcomeUnknown:true});completed=true;return {...row,status:'accepted'};}
  return route.startsWith('/manager/observations')?page(completed?[]:[row]):new Blob();
 });a.changed();await tick();await tick();a.get('review-comment').value='my note';
 await a.get('review-accept').onclick();
 assert.equal(a.get('review-retry').hidden,false);assert.equal(a.get('review-accept').disabled,true);assert.equal(a.get('review-reject').disabled,true);
 await a.get('refresh-contributions').onclick();await tick();
 assert.equal(a.get('review-comment').value,'my note');assert.equal(a.get('review-comment').readOnly,true);
 a.get('review-comment').value='accidental change';await a.get('review-reject').onclick();assert.equal(attempts.length,1);
 await a.get('review-retry').onclick();assert.equal(attempts.length,2);
 assert.ok(attempts[0].headers['Idempotency-Key']);assert.equal(attempts[1].headers['Idempotency-Key'],attempts[0].headers['Idempotency-Key']);assert.equal(attempts[1].body,attempts[0].body);
 assert.equal(JSON.parse(attempts[1].body).comment,'my note');
});
test('row switching preserves separate comments and cancels obsolete evidence reads',async()=>{
 const items=[contributionRow('a'),contributionRow('b')],signals=[];
 const a=setup(async(route,options)=>{if(route==='/manager/summary')return summary;if(route.startsWith('/manager/observations'))return page(items);signals.push(options?.signal);return new Blob();});
 a.changed();await tick();await tick();a.get('review-comment').value='note A';
 a.get('contributions').children[1].children[0].children[0].onclick();await tick();a.get('review-comment').value='note B';
 a.get('contributions').children[0].children[0].children[0].onclick();await tick();
 assert.equal(a.get('review-comment').value,'note A');assert.equal(signals[0]?.aborted,true);
 a.api.user=null;a.changed();assert.equal(a.get('review-comment').value,'');
});
test('conflict reads exact current decision and preserves scratch comment',async()=>{
 const row=contributionRow('conflict');let reconciles=0;
 const a=setup(async(route)=>{
  if(route==='/manager/summary')return summary;
  if(route.endsWith('/review'))throw Object.assign(Error('already reviewed'),{status:409});
  if(route==='/observations/conflict'){reconciles++;return {...row,status:'accepted',review_comment:'Other moderator'};}
  return route.startsWith('/manager/observations')?page([row]):new Blob();
 });a.changed();await tick();await tick();a.get('review-comment').value='unsent note';await a.get('review-reject').onclick();await tick();
 assert.equal(reconciles,1);assert.equal(a.get('review-comment').value,'unsent note');assert.equal(a.get('review-comment').readOnly,true);
 assert.equal(a.get('review-actions').hidden,true);assert.match(a.get('detail-meta').textContent,/Other moderator/);
});
test('review shows the proposed extended catalog label rather than the original AI label',async()=>{
 const row={id:'extended',image_id:'photo',status:'pending',proposed_class:42,
  detection:{qcvn_code:'P.102',predicted_class:5,name_vi:'Original',confidence:.9},latitude:10,longitude:106};
 const a=setup(async route=>route==='/manager/summary'?summary:route.startsWith('/manager/observations')?page([row]):new Blob());
 a.changed();await tick();await tick();
 assert.equal(a.get('detail-title').textContent,'FIXTURE.42');
 assert.ok(a.get('contributions').textContent.includes('FIXTURE.42'));
});
test('restored staff session lands on contributions and loads other sections only when selected',async()=>{
 let finish;const a=setup(empty,new Promise(r=>finish=r));finish();await tick();
 assert.ok(a.calls.includes('/manager/summary'));
 assert.ok(a.calls.some(p=>p.startsWith('/manager/observations?')));
 assert.equal(a.calls.some(p=>p.startsWith('/manager/reports')),false);
 assert.equal(a.get('tab-accounts').hidden,true);assert.equal(a.get('tab-policy').hidden,true);
 await a.get('tab-signs').onclick();assert.ok(a.calls.some(p=>p.startsWith('/manager/signs?')));
 assert.equal(a.get('panel-contributions').hidden,true);assert.equal(a.get('panel-signs').hidden,false);
});
test('catalogue search resets offset and a stale response cannot overwrite newer filters',async()=>{
 let old;const a=setup(async route=>{
  if(route==='/manager/summary')return summary;
  if(route.includes('q=old'))return new Promise(r=>old=r);
  if(route.startsWith('/manager/signs')&&!route.includes('q=P.102'))return page([{id:'s1',qcvn_code:'P.102',latitude:10,longitude:106}],Number(new URLSearchParams(route.split('?')[1]).get('offset')),100,25);
  return page();
 });a.changed();await tick();await a.get('tab-signs').onclick();
 await a.get('signs-next').onclick();assert.ok(a.calls.at(-1).includes('offset=25'));
 a.get('sign-query').value='old';const pending=a.get('sign-filters').onsubmit({preventDefault(){}});await tick();
 a.get('sign-query').value='P.102';a.get('sign-status').value='removed';await a.get('sign-filters').onsubmit({preventDefault(){}});
 assert.match(a.calls.at(-1),/offset=0/);assert.match(a.calls.at(-1),/status=removed/);
 old(page([{id:'private-old',qcvn_code:'Old'}]));await pending;
 assert.equal(a.get('signs').textContent.includes('Old'),false);
});
test('contribution review stays in the workspace and locks both decisions during submission',async()=>{
 let finish;const row={id:'o1',image_id:'i1',status:'pending',detection:{qcvn_code:'P.102',name_vi:'Cấm',confidence:.9,predicted_class:5},latitude:10,longitude:106};
 const a=setup(async(route,options)=>{
  if(route==='/manager/summary')return summary;
  if(route.endsWith('/review'))return new Promise(r=>finish=r);
  return route.startsWith('/manager/observations')?page([row]):new Blob();
 });a.changed();await tick();await tick();
 assert.match(a.get('detail-title').textContent,/P.102/);
 const pending=a.get('review-accept').onclick();await tick();
 assert.equal(a.get('review-accept').disabled,true);assert.equal(a.get('review-reject').disabled,true);
 finish({status:'accepted'});await pending;assert.equal(a.redirects.length,0);
});
test('report comments are text and reports remain separate from new contributions',async()=>{
 const comment='<img src=x onerror=alert(1)>';
 const a=setup(async route=>{
  if(route==='/manager/summary')return summary;
  if(route.startsWith('/manager/reports'))return page([{id:'r1',record_id:'s1',image_id:'i1',action:'report_removed',comment,proposed_class:null,latitude:null,base_revision:0}]);
  if(route.startsWith('/signs/'))return {sign:{qcvn_code:'P.125',latitude:0,longitude:0,status:'active',revision:0},evidence:[]};
  return page();
 });a.changed();await tick();await a.get('tab-reports').onclick();await tick();
 assert.ok(a.get('detail-meta').textContent.includes(comment));assert.equal(a.get('policy-panel').hidden,true);
});
test('logout clears rows, inspector and counters and ignores late catalogue responses',async()=>{
 let finish;const a=setup(async route=>route.startsWith('/manager/signs')?new Promise(r=>finish=r):empty(route));
 a.changed();await tick();const pending=a.get('tab-signs').onclick();await tick();
 a.api.user=null;a.changed();finish(page([{id:'private',qcvn_code:'Secret'}]));await pending;
 assert.equal(a.get('signs').children.length,0);assert.equal(a.get('review-detail').hidden,true);
 assert.equal(a.get('workspace').hidden,true);assert.equal(a.get('count-signs').textContent,'');
});
test('guest/user cannot trigger staff loaders and managers cannot load admin settings or accounts',async()=>{
 const a=setup(empty);
 for(const user of [null,{username:'rider',role:'user'}]){
  a.api.user=user;a.changed();for(const name of ['contributions','reports','duplicates','signs','accounts','policy'])await a.get('tab-'+name).onclick();
 }
 assert.deepEqual(a.calls,[]);
 a.api.user={username:'mod',role:'manager'};a.changed();await tick();
 await a.get('tab-accounts').onclick();await a.get('tab-policy').onclick();
 assert.equal(a.calls.some(p=>p.startsWith('/admin/')),false);
});
test('the staff page has one compact catalogue and no capture or personal-report flow',()=>{
 const html=fs.readFileSync(path.join(__dirname,'../frontend/management.html'),'utf8');
 assert.match(html,/<table/);assert.match(html,/id="sign-filters"/);assert.match(html,/id="sign-limit"/);
 assert.doesNotMatch(html,/href="observations.html|id="camera"|id="my-reports"/);
});

test('tab keyboard navigation reaches visible staff sections and skips admin-only sections',async()=>{
 const a=setup(empty);a.changed();await tick();
 a.get('tab-contributions').onkeydown({key:'ArrowRight',preventDefault(){}});await tick();
 assert.equal(a.get('tab-reports').attributes['aria-selected'],'true');
 a.get('tab-reports').onkeydown({key:'End',preventDefault(){}});await tick();
 assert.equal(a.get('tab-signs').attributes['aria-selected'],'true');
});
