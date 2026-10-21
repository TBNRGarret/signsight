const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const tick = () => new Promise(resolve => setImmediate(resolve));
function app(request) {
  const elements = new Map(), calls = [], events = new Map();
  function element(id) {
    return {id, value:'', files:[], children:[], dataset:{}, disabled:false,
      append(...nodes){this.children.push(...nodes);}, replaceChildren(...nodes){this.children=nodes;},
      addEventListener(){}, setAttribute(){}, getContext(){return {drawImage(){},strokeRect(){},fillText(){}};}};
  }
  const document = {getElementById(id){if(!elements.has(id))elements.set(id,element(id));return elements.get(id);},createElement:()=>element('')};
  const api = {user:{id:'u',username:'rider',role:'user'}, ready:Promise.resolve(),
    async request(route, options){calls.push(route);if(route==='/ai/status')return {yolo:{ready:true},cnn:{ready:false}};
      if(route.startsWith('/me/'))return {items:[],total:0,offset:0,limit:10};return request(route,options);}};
  const context = {window:{signSightAuth:api,addEventListener:(name,fn)=>events.set(name,fn)}, document, URLSearchParams,
    navigator:{}, FormData:class{append(){}}, createImageBitmap:async()=>({width:640,height:360,close(){}})};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../frontend/observations.js'),'utf8'), context);
  return {calls, api, get:document.getElementById, events};
}
const image = {id:'photo',width:640,height:360,size_bytes:5000,exif_latitude:null,exif_longitude:null};
test('camera photo uploads and runs YOLO automatically without publishing observations', async()=>{
  const a=app(async route=>route==='/images'?image:route.endsWith('/content')?{}:{detections:[]});await tick();
  a.get('camera').files=[{name:'photo.jpg'}];await a.get('camera').onchange();
  assert.deepEqual(a.calls.filter(route=>route.startsWith('/images')),['/images','/images/photo/content','/images/photo/detect']);
  assert.equal(a.calls.includes('/observations'),false);
  assert.match(a.get('status').textContent,/Không tìm thấy/);
  assert.equal(a.get('camera').disabled,false);
  assert.equal(a.get('detect').disabled,false);
  assert.equal(a.get('submit').disabled,true);
});
test('failed camera upload shows error and permits retry without running inference', async()=>{
  const a=app(async()=>{throw new Error('Ảnh không hợp lệ');});await tick();
  a.get('camera').files=[{}];await a.get('camera').onchange();
  assert.match(a.get('status').textContent,/Ảnh không hợp lệ/);
  assert.equal(a.calls.some(route=>route.endsWith('/detect')),false);
  assert.equal(a.get('camera').disabled,false);
  assert.equal(a.get('camera').value,'');
});
test('camera operation locks competing image actions and ignores a result after logout', async()=>{
  let finishUpload;
  const a=app(async route=>route==='/images'?new Promise(resolve=>finishUpload=resolve):{});await tick();
  a.get('camera').files=[{}];const pending=a.get('camera').onchange();await tick();
  for(const id of ['camera','file','upload','detect','classify'])assert.equal(a.get(id).disabled,true,id);
  a.api.user=null;a.events.get('signsight-auth-changed')();
  finishUpload(image);await pending;
  assert.equal(a.calls.some(route=>route.endsWith('/detect')),false);
  assert.equal(a.get('camera').disabled,true);
  assert.equal(a.get('preview').hidden,true);
});
test('canceling the camera makes no request',async()=>{
  const a=app(async()=>{throw Error('unexpected request');});await tick();
  const before=a.calls.length;a.get('camera').files=[];await a.get('camera').onchange();
  assert.equal(a.calls.length,before);
});
test('a detected camera photo renders a review card and enables explicit submission',async()=>{
  const detection={id:'d',qcvn_code:'P.102',name_vi:'Cấm đi ngược chiều',confidence:0.9,predicted_class:5,bbox:{x1:5,y1:6,x2:50,y2:60}};
  const a=app(async route=>route==='/images'?image:route.endsWith('/content')?{}:{detections:[detection]});await tick();
  a.get('camera').files=[{}];await a.get('camera').onchange();
  assert.equal(a.get('detections').children.length,1);
  assert.equal(a.get('detections').children[0].dataset.detectionId,'d');
  assert.equal(a.get('submit').disabled,false);
  assert.equal(a.calls.includes('/observations'),false);
});
test('inference failure keeps the uploaded photo available for manual retry',async()=>{
  const a=app(async route=>{if(route==='/images')return image;if(route.endsWith('/content'))return {};throw Error('YOLO tạm lỗi');});await tick();
  a.get('camera').files=[{}];await a.get('camera').onchange();
  assert.match(a.get('status').textContent,/YOLO tạm lỗi/);
  assert.equal(a.get('detect').disabled,false);
  assert.equal(a.get('preview').hidden,false);
  assert.equal(a.get('submit').disabled,true);
});
