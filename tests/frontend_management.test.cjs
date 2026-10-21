const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const path=require('node:path');
class Element {
  constructor(tag='div'){this.tag=tag;this.children=[];this.textContent='';this.isConnected=true;}
  append(...elements){this.children.push(...elements);}
  replaceChildren(...elements){this.children.forEach(child=>child.isConnected=false);this.children=elements;}
  setAttribute(){}
  set innerHTML(_){throw new Error('Untrusted HTML rendering');}
}
function setup(request,ready){
  const elements=new Map(),events=new Map();
  const api={user:{username:'manager',role:'manager'},request,ready};
  const document={getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement:tag=>new Element(tag)};
  const window={signSightAuth:api,addEventListener:(name,fn)=>events.set(name,fn)};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../frontend/management.js'),'utf8'),{window,document,URL:{createObjectURL:()=> 'blob:test',revokeObjectURL:()=>{}}});
  return {api,elements,changed:events.get('signsight-auth-changed')};
}
const page=items=>({items,total:items.length,offset:0,limit:10});
const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('manager renders a user report comment as text, and gates admin policy',async()=>{
  const comment='<img src=x onerror=alert(1)>';
  const app=setup(async route=>{
    if(route.startsWith('/manager/reports'))return page([{id:'r1',record_id:'s1',image_id:'i1',action:'report_removed',comment,proposed_class:null,latitude:null,base_revision:0}]);
    if(route.startsWith('/manager/duplicates'))return page([]);
    if(route.startsWith('/signs/'))return {sign:{qcvn_code:'P.125',latitude:0,longitude:0,status:'active',revision:0},evidence:[]};
    return new Blob();
  });
  app.changed();await tick();await tick();
  const card=app.elements.get('reports').children[0];
  assert.equal(card.children.find(node=>node.textContent===comment).tag,'p');
  assert.equal(app.elements.get('policy-panel').hidden,true);
});
test('a report queue response arriving after logout cannot repopulate private cards',async()=>{
  let finish;
  const app=setup(async route=>route.startsWith('/manager/reports')?new Promise(resolve=>finish=resolve):page([]));
  app.changed();app.api.user=null;app.changed();
  finish(page([{id:'r1',comment:'private'}]));await tick();
  assert.equal(app.elements.get('reports').children.length,0);
  assert.equal(app.elements.get('duplicates').children.length,0);
  assert.equal(app.elements.get('workspace').hidden,true);
});

test('a restored session initializes management without a second login',async()=>{
  let finish;const ready=new Promise(resolve=>finish=resolve),calls=[];
  const app=setup(async route=>{calls.push(route);return page([]);},ready);
  app.api.user=null;
  app.api.user={username:'manager',role:'manager'};finish();await tick();
  assert.equal(app.elements.get('login').hidden,true);
  assert.ok(calls.some(route=>route.startsWith('/manager/reports')));
});

test('guest and user management refresh controls never request staff data',async()=>{
  const calls=[];const app=setup(async route=>{calls.push(route);return page([]);});
  for(const user of [null,{username:'rider',role:'user'}]){
    app.api.user=user;app.changed();
    await app.elements.get('refresh-reports').onclick();await app.elements.get('refresh-duplicates').onclick();
    assert.equal(app.elements.get('workspace').hidden,true);
  }
  assert.deepEqual(calls,[]);
});
