const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const modulePath=require('node:path').join(__dirname,'../frontend/shared/sign_popup.js');
const popup=fs.existsSync(modulePath)?require(modulePath):null;
function setup(request,signOverrides={}){
 const document={createElement:tag=>({tag,children:[],attrs:{},hidden:false,setAttribute(k,v){this.attrs[k]=v;},append(...nodes){this.children.push(...nodes);}})};
 const user={id:'reader'},calls=[],created=[],revoked=[];
 const api={user,request:async(route,options)=>{calls.push(route);return request(route,options);}};
 const urlApi={createObjectURL(blob){created.push(blob);return 'blob:reviewed';},revokeObjectURL(url){revoked.push(url);}};
 const sign={id:'s1',qcvn_code:'P.127 (50)',name_vi:'Tốc độ 50',status:'active',...signOverrides};
 assert.ok(popup,'Reviewed sign popup is missing');
 const handle=popup.create({document,api,sign,onDetails:()=>{},urlApi});
 const find=cls=>{const search=n=>n.className===cls?n:n.children?.map(search).find(Boolean);return search(handle.element);};
 return {handle,api,calls,created,revoked,find};
}
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));};
test('photo popup retains expiry, removal and uncertain-label information',()=>{
 for(const [sign,label] of [[{status:'expired'},'quá hạn xác nhận · cần xác nhận lại'],[{status:'removed',is_uncertain:true},'đã tháo · nhãn cần kiểm tra']]){
  const a=setup(async()=>({evidence:[]}),sign);
  assert.ok(a.handle.element.children[0].children.some(node=>node.textContent===label));
  a.handle.dispose();
 }
});
test('selecting a marker loads only the first reviewed photo with authenticated API transport',async()=>{
 const a=setup(async route=>route==='/signs/s1'?{evidence:[{content_url:'/api/v1/images/first/content'},{content_url:'/api/v1/images/second/content'}]}:new Blob(['jpeg']));
 await settle();assert.deepEqual(a.calls,['/signs/s1','/images/first/content']);
 assert.equal(a.find('sign-popup-photo').src,'blob:reviewed');
 assert.equal(a.created.length,1);a.handle.dispose();assert.deepEqual(a.revoked,['blob:reviewed']);
});
test('no evidence and external evidence paths keep explanatory text without fetching other origins',async()=>{
 for(const evidence of [[],[{content_url:'https://outside.invalid/photo'}]]){
  const a=setup(async()=>({evidence}));await settle();
  assert.deepEqual(a.calls,['/signs/s1']);assert.equal(a.created.length,0);
  assert.ok(a.find('sign-popup-photo-status').textContent);assert.equal(a.find('sign-popup-photo').hidden,true);
 }
});
test('closing or switching accounts before detail resolves does not fetch or expose stale evidence',async()=>{
 for(const mode of ['close','account']){
  let finish;const a=setup(()=>new Promise(resolve=>finish=resolve));
  if(mode==='close')a.handle.dispose();else a.api.user={id:'other'};
  finish({evidence:[{content_url:'/api/v1/images/private/content'}]});await settle();
  assert.deepEqual(a.calls,['/signs/s1']);assert.equal(a.created.length,0);
 }
});
test('photo failure has retry and image decoding failure revokes its URL',async()=>{
 let failed=true;const a=setup(async route=>{if(failed)throw Error('offline');return route==='/signs/s1'?{evidence:[{content_url:'/api/v1/images/first/content'}]}:new Blob(['jpeg']);});
 await settle();const retry=a.find('sign-popup-photo-retry');assert.equal(retry.hidden,false);
 failed=false;await retry.onclick();await settle();assert.equal(a.created.length,1);
 a.find('sign-popup-photo').onerror();assert.deepEqual(a.revoked,['blob:reviewed']);
 assert.equal(a.find('sign-popup-photo').hidden,true);assert.equal(retry.hidden,false);
});
