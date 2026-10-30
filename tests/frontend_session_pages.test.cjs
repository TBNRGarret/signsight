const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const tick = () => new Promise(resolve => setImmediate(resolve));
const read = name => fs.readFileSync(path.join(__dirname, '../frontend', name), 'utf8');
class Element {
  constructor() { this.value=''; this.children=[]; this.textContent=''; this.hidden=false; this.dataset={}; }
  get textContent(){return (this._text||'')+this.children.map(node=>node.textContent||'').join('');}
  set textContent(value){this._text=String(value);this.children=[];}
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children=nodes; }
  addEventListener() {}
  setAttribute() {}
}
function app(request) {
  const elements=new Map(), events=new Map(), calls=[];
  let finish;
  const api={user:null,ready:new Promise(resolve=>finish=resolve),request:async(...args)=>{calls.push(args[0]);if(args[0]==='/taxonomy')return require('./catalog_fixture.cjs');return request(...args);}};
  const document={getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},
    createElement:()=>new Element(),querySelectorAll:()=>[]};
  const window={signSightAuth:api,addEventListener(name,fn){if(!events.has(name))events.set(name,[]);events.get(name).push(fn);},
    dispatchEvent(event){for(const fn of events.get(event.type)||[])fn(event);}};
  const context=vm.createContext({window,document,URLSearchParams,clearTimeout,setTimeout,navigator:{},
    CustomEvent:class{constructor(type){this.type=type;}}});
  vm.runInContext(read('catalog.js'),context);
  return {api,window,document,elements,context,calls,finish,
    get:id=>document.getElementById(id), run:name=>{if(name==='observations.js')vm.runInContext(read('contribution_history.js'),context);return vm.runInContext(read(name),context);}};
}
function mapApp(request) {
  const a=app(request), map={on(){},removeLayer(){},getBounds:()=>({getSouth:()=>10.7,getNorth:()=>10.9,getWest:()=>106.6,getEast:()=>106.8})};
  a.window.signSightMap={mount:()=>({map})};
  a.window.signSightReports={mount:()=>({refreshPin(){},select(){}})};
  a.get('nearby-radius').value='1000';
  a.run('routing.js');a.run('sign_link.js');
  for(const script of read('index.html').matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))vm.runInContext(script[1],a.context);
  return a;
}
const page = {items:[],total:0,offset:0,limit:50};

test('restored map session enables destination search and loads nearby data without another login',async()=>{
  const a=mapApp(async()=>page);
  assert.equal(a.get('route-search-button').disabled,true);
  a.api.user={id:'u',username:'rider',role:'user'};a.finish();await tick();
  assert.equal(a.get('route-search-button').disabled,false);
  assert.equal(a.get('login-form').hidden,true);
  assert.ok(a.calls.some(route=>route.startsWith('/map/signs?')));
  assert.ok(a.calls.some(route=>route.startsWith('/signs/nearby?')));
  assert.match(a.get('sign-list').children[0].textContent,/Chưa có biển được ghi nhận/);
});

test('logged-out map explains authentication instead of pretending the area has zero signs',async()=>{
  const a=mapApp(async()=>page);a.finish();await tick();
  assert.equal(a.get('signs-count-badge').textContent,'Chưa đăng nhập');
  assert.match(a.get('sign-list').children[0].textContent,/Đăng nhập/);
  await a.get('route-search').onsubmit({preventDefault(){}});
  assert.equal(a.calls.length,0);
});

test('destination lookup works independently of uploaded images and surfaces provider failure',async()=>{
  const a=mapApp(async route=>{
    if(route.startsWith('/places/search')){const error=new Error('Provider unavailable');error.status=502;throw error;}
    return page;
  });
  a.api.user={id:'u',username:'rider',role:'user'};a.finish();await tick();
  a.get('route-query').value='Nguyễn Huệ';
  await a.get('route-search').onsubmit({preventDefault(){}});
  assert.match(a.get('nav-summary').textContent,/không kết nối được/);
  assert.equal(a.get('route-search-button').disabled,false);
  assert.equal(a.get('route-go').disabled,true);
  assert.equal(a.calls.some(route=>route.startsWith('/images')),false);
});

test('a restored session can choose a search result and enable routing without uploading an image',async()=>{
  const a=mapApp(async route=>route.startsWith('/places/search')
    ?{items:[{id:'place',name:'Nguyễn Huệ, TP.HCM',latitude:10.77,longitude:106.70}]}:page);
  a.api.user={id:'u',username:'rider',role:'user'};a.finish();await tick();
  a.get('route-query').value='Nguyễn Huệ';
  await a.get('route-search').onsubmit({preventDefault(){}});
  const button=a.get('route-places').children[0];
  assert.match(button.textContent,/Nguyễn Huệ/);
  assert.equal(a.get('route-go').disabled,true);
  button.onclick();
  assert.equal(a.get('route-go').disabled,false);
  assert.equal(a.calls.some(route=>route.startsWith('/images')),false);
});

test('restored session initializes the image workspace and loads history',async()=>{
  const a=app(async route=>route==='/ai/status'?{yolo:{ready:true},cnn:{ready:false}}:page);
  a.run('observations.js');
  a.api.user={id:'u',username:'rider',role:'user'};a.finish();await tick();
  assert.equal(a.get('login').hidden,true);
  assert.equal(a.get('workspace').hidden,false);
  assert.equal(a.get('auth-intro').hidden,true);
  assert.equal(a.calls.some(route=>route.startsWith('/manager/')),false);
  assert.ok(a.calls.some(route=>route.startsWith('/me/observations?')));
});

test('contribution status filter resets pagination and renders a localized empty state',async()=>{
  const a=app(async route=>route==='/ai/status'?{yolo:{ready:true},cnn:{ready:false}}:{items:[],total:0,offset:0,limit:10});
  a.run('observations.js');
  a.api.user={id:'u',username:'rider',role:'user'};a.finish();await tick();
  a.get('history-next').onclick();await tick();
  a.get('history-status').value='rejected';
  await a.get('history-status').onchange();
  assert.match(a.calls.filter(route=>route.startsWith('/me/observations?')).at(-1),/offset=0&limit=10&status=rejected/);
  assert.match(a.get('history').children[0].textContent,/Chưa có đóng góp bị từ chối/);
  assert.equal(a.get('history-prev').disabled,true);
  assert.equal(a.get('history-next').disabled,true);
});

test('an older history response cannot replace the current status filter results',async()=>{
  let finishOld;
  const a=app(async route=>{
    if(route==='/ai/status')return {yolo:{ready:true},cnn:{ready:false}};
    if(route.includes('status=pending'))return new Promise(resolve=>finishOld=resolve);
    if(route.includes('status=accepted'))return {items:[{detection:{qcvn_code:'P.102'},latitude:10,longitude:106,status:'accepted',review_comment:'Đã kiểm tra'}],total:1,offset:0,limit:10};
    return {items:[],total:0,offset:0,limit:10};
  });
  a.run('observations.js');a.api.user={id:'u',username:'rider',role:'user'};a.finish();await tick();
  a.get('history-status').value='pending';const old=a.get('history-status').onchange();await tick();
  a.get('history-status').value='accepted';await a.get('history-status').onchange();
  finishOld({items:[],total:0,offset:0,limit:10});await old;
  assert.match(a.get('history').children[0].textContent,/P.102.*Đã duyệt.*Đã kiểm tra/);
});

test('history shows loading and error feedback while disabling stale pagination',async()=>{
  let fail;
  const a=app(async route=>route==='/ai/status'?{yolo:{ready:true},cnn:{ready:false}}:new Promise((resolve,reject)=>fail=reject));
  a.run('observations.js');a.api.user={id:'u',username:'rider',role:'user'};a.finish();await tick();
  assert.match(a.get('history').children[0].textContent,/Đang tải/);
  assert.equal(a.get('history-next').disabled,true);
  fail(new Error('Network unavailable'));await tick();
  assert.match(a.get('history').children[0].textContent,/Không tải được.*Network unavailable/);
  assert.equal(a.get('history-prev').disabled,true);
});

test('staff map login goes directly to management instead of loading personal user tasks',async()=>{
 const a=mapApp(async()=>page),redirects=[];a.window.location={replace:path=>redirects.push(path)};
 a.api.user={id:'admin',username:'owner',role:'admin'};a.finish();await tick();
 assert.deepEqual(redirects,['management.html']);assert.equal(a.calls.length,0);
});
test('staff photo page redirects to management and does not run the user capture workspace',async()=>{
 const a=app(async()=>page),redirects=[];a.window.location={replace:path=>redirects.push(path)};
 a.run('observations.js');a.api.user={id:'mod',username:'mod',role:'manager'};a.finish();await tick();
 assert.deepEqual(redirects,['management.html']);assert.equal(a.get('workspace').hidden,true);assert.equal(a.calls.length,0);
});
