const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../frontend/auth.js'), 'utf8');
const response = (status, body) => ({status, ok: status >= 200 && status < 300, json: async () => body});
const profile = (role = 'admin') => ({id:'id',username:'owner',role});
const session = () => ({access_token:'secret-token',user:profile()});
const tick = () => new Promise(resolve => setImmediate(resolve));
function context(fetch, {store = new Map(), initial = async () => response(401, {}), storageDisabled = false, staffLinks = []} = {}) {
  const events = [], handlers = new Map();
  const window = {
    document:{querySelectorAll:selector=>selector==='[data-staff-only]'?staffLinks:[]},
    dispatchEvent: event => events.push(event.type),
    addEventListener: (name, fn) => handlers.set(name, fn),
    localStorage: {
      getItem(key) { if(storageDisabled)throw Error('disabled'); return store.get(key) ?? null; },
      setItem(key, value) { if(storageDisabled)throw Error('disabled'); store.set(key, value); }
    }
  };
  let first = true;
  vm.runInNewContext(source, {window, Headers, CustomEvent: class {constructor(type){this.type=type;}},
    fetch: (...args) => { if(first){first=false; assert.equal(args[0],'/api/v1/auth/me'); return initial(...args);} return fetch(...args); }});
  return {auth:window.signSightAuth,events,handlers,store};
}
async function setup(fetch, options) {const app=context(fetch,options);await app.auth.ready;return app;}

test('browser login uses same-origin cookies; storage never contains a token or password', async () => {
  const calls=[];
  const app=await setup(async(url,options)=>{calls.push({url,options});return response(200,url.endsWith('/login')?session():[]);});
  await app.auth.login('owner','private-password');
  await app.auth.request('/admin/users',{credentials:'include',headers:{Authorization:'Bearer injected'}});
  assert.equal(app.auth.user.role,'admin');
  assert.equal(calls[1].options.credentials,'same-origin');
  assert.equal(calls[1].options.headers.has('Authorization'),false);
  assert.equal(calls[0].options.headers.get('X-SignSight-Web'),'1');
  assert.doesNotMatch(JSON.stringify([...app.store]),/secret-token|private-password|owner/);
  for(const route of ['https://other.example','//other.example','/\\other.example'])await assert.rejects(app.auth.request(route),/Invalid API path/);
});

test('reload and a different page restore the real profile from the server cookie', async () => {
  const app=await setup(async()=>response(200,{}),{initial:async(_,options)=>{
    assert.equal(options.credentials,'same-origin');return response(200,profile('manager'));
  }});
  assert.equal(app.auth.user.role,'manager');
});

test('remember me is sent as a flag without persisting the password',async()=>{
  let body;
  const app=await setup(async(url,options)=>{body=JSON.parse(options.body);return response(200,session());});
  await app.auth.login('owner','private-password',true);
  assert.equal(body.remember_me,true);
  assert.doesNotMatch(JSON.stringify([...app.store]),/private-password|secret-token/);
});

test('staff navigation follows the verified role and disappears on logout',async()=>{
  const links=[{hidden:true},{hidden:true}];
  const app=await setup(async url=>url.endsWith('/logout')?response(204):response(200,session()),{staffLinks:links});
  assert.ok(links.every(link=>link.hidden));
  await app.auth.login('owner','password');assert.ok(links.every(link=>!link.hidden));
  await app.auth.logout();assert.ok(links.every(link=>link.hidden));
  const ordinary=await setup(async()=>response(200,{}),{staffLinks:links,initial:async()=>response(200,profile('user'))});
  assert.equal(ordinary.auth.user.role,'user');assert.ok(links.every(link=>link.hidden));
});

test('register creates an account then signs in without persisting credentials',async()=>{
  const calls=[];
  const app=await setup(async(url,options)=>{calls.push({url,body:JSON.parse(options.body)});return response(url.endsWith('/register')?201:200,url.endsWith('/register')?{}:session());});
  await app.auth.register('rider','rider@example.com','private-password');
  assert.deepEqual(calls.map(c=>c.url),['/api/v1/auth/register','/api/v1/auth/login']);
  assert.equal(calls[0].body.email,'rider@example.com');
  assert.equal(app.auth.user.username,'owner');
});

test('failed registration surfaces the error and stays signed out',async()=>{
  const app=await setup(async()=>response(409,{detail:'Identity unavailable'}));
  await assert.rejects(app.auth.register('rider','rider@example.com','password'),/Identity unavailable/);
  assert.equal(app.auth.user,null);
});

test('expired credentials clear the UI and expose the HTTP status',async()=>{
  const app=await setup(async url=>url.endsWith('/login')?response(200,session()):response(401,{detail:'Expired'}));
  await app.auth.login('owner','password');
  await assert.rejects(app.auth.request('/admin/users'),error=>error.status===401&&error.message==='Expired');
  assert.equal(app.auth.user,null);
});

test('offline logout clears the UI and blocks silent restoration on the next page',async()=>{
  const app=await setup(async url=>{if(url.endsWith('/login'))return response(200,session());throw Error('offline');});
  await app.auth.login('owner','password');
  await assert.rejects(app.auth.logout(),/offline/);
  assert.equal(app.auth.user,null);
  let fetches=0;
  const next=context(async()=>{throw Error('unexpected');},{store:app.store,initial:async()=>{fetches++;return response(200,profile());}});
  await next.auth.ready;
  assert.equal(next.auth.user,null);assert.equal(fetches,0);
});

test('late 401 from an old session cannot sign out a newer login',async()=>{
  let finish;
  const app=await setup(async url=>url.endsWith('/login')?response(200,session()):new Promise(resolve=>finish=resolve));
  await app.auth.login('owner','password');
  const pending=app.auth.request('/admin/users');
  await app.auth.login('owner','new-password');
  finish(response(401,{detail:'Old session expired'}));
  await assert.rejects(pending,/Old session expired/);
  assert.equal(app.auth.user.role,'admin');
});

test('a late profile restore cannot undo logout',async()=>{
  let finish;
  const app=context(async()=>response(204),{initial:()=>new Promise(resolve=>finish=resolve)});
  await app.auth.logout();
  finish(response(200,profile()));await app.auth.ready;
  assert.equal(app.auth.user,null);
});

test('logout and a newer login serialize cookie-changing responses',async()=>{
  let finish,logins=0;
  const app=await setup(async url=>{
    if(url.endsWith('/login')){logins++;return response(200,session());}
    return new Promise(resolve=>finish=resolve);
  });
  await app.auth.login('owner','password');
  const logout=app.auth.logout();await tick();
  const login=app.auth.login('owner','new-password');await tick();
  assert.equal(logins,1);
  finish(response(204));await logout;await login;
  assert.equal(logins,2);assert.equal(app.auth.user.role,'admin');
});

test('permission changes refresh the profile from the server',async()=>{
  const app=await setup(async url=>url.endsWith('/login')?response(200,session()):url.endsWith('/me')?response(200,profile('user')):response(403,{detail:'Denied'}));
  await app.auth.login('owner','password');
  await assert.rejects(app.auth.request('/admin/users'),/Denied/);
  assert.equal(app.auth.user.role,'user');
});

test('another tab login restores its cookie, and logout clears this tab immediately',async()=>{
  const app=await setup(async()=>response(200,profile('manager')));
  const key='signsight.auth-state',newValue=JSON.stringify({state:'in',nonce:'new'});
  app.store.set(key,newValue);app.handlers.get('storage')({key,newValue});await tick();
  assert.equal(app.auth.user.role,'manager');
  const logout=JSON.stringify({state:'out',nonce:'later'});app.store.set(key,logout);
  app.handlers.get('storage')({key,newValue:logout});
  assert.equal(app.auth.user,null);
});

test('a stale queued storage notification cannot clear a newer login',async()=>{
  const app=await setup(async()=>response(200,session()));await app.auth.login('owner','password');
  app.handlers.get('storage')({key:'signsight.auth-state',newValue:'old-logout'});
  assert.equal(app.auth.user.role,'admin');
});

test('storage-disabled browsers still restore using the cookie',async()=>{
  const app=await setup(async()=>response(200,session()),{storageDisabled:true,initial:async()=>response(200,profile())});
  await app.auth.login('owner','password');assert.equal(app.auth.user.role,'admin');
});

test('returning to a tab rechecks server revocation, without logging out on network failure',async()=>{
  let offline=true;
  const app=await setup(async()=>{if(offline)throw Error('offline');return response(401,{});},{initial:async()=>response(200,profile())});
  app.handlers.get('focus')();await tick();assert.equal(app.auth.user.role,'admin');
  offline=false;app.handlers.get('focus')();await tick();assert.equal(app.auth.user,null);
});

test('evidence blobs and structured API errors still work through the shared cookie',async()=>{
  const app=await setup(async url=>url.endsWith('/missing')?response(404,{detail:'Image not found'}):{status:200,ok:true,blob:async()=> 'image bytes'});
  assert.equal(await app.auth.request('/images/id/content',{responseType:'blob'}),'image bytes');
  await assert.rejects(app.auth.request('/missing',{responseType:'blob'}),/Image not found/);
});

test('map integration JavaScript parses and management controls start disabled',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../frontend/index.html'),'utf8');
  for(const script of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(script[1]);
  assert.match(html,/data-management onclick="submitSign\(\)" disabled/);
  assert.match(html,/\[hidden\]\s*\{\s*display:\s*none\s*!important/);
});
