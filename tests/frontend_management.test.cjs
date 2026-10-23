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
 const api={user:{username:'mod',role:'manager'},ready,async request(route,options){calls.push(route);return handler(route,options);}};
 const document={getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement:tag=>new Element(tag)};
 const window={signSightAuth:api,location:{replace:url=>redirects.push(url)},addEventListener:(n,f)=>events.set(n,f)};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../frontend/management.js'),'utf8'),{window,document,URLSearchParams,
  createImageBitmap:async()=>({width:100,height:100,close(){}}),URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}}});
 return {api,elements,calls,redirects,get:document.getElementById,changed:events.get('signsight-auth-changed')};
}
const summary={contributions:2,reports:1,duplicates:0,signs:1000};
const empty=async route=>route==='/manager/summary'?summary:page();
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
