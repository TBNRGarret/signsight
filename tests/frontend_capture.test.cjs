const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const tick = () => new Promise(resolve => setImmediate(resolve));
function app(request) {
  const elements = new Map(), calls = [], events = new Map();
  function element(id) {
    return {id, value:'', files:[], children:[], dataset:{}, disabled:false,
      append(...nodes){this.children.push(...nodes);}, replaceChildren(...nodes){this.children=nodes;},
      querySelector(selector){
        const name=selector.slice(1);
        const find=nodes=>{for(const node of nodes){if((node.className||'').split(' ').includes(name))return node;const child=find(node.children||[]);if(child)return child;}return null;};
        return find(this.children);
      },
      checkValidity(){const n=Number(this.value);return this.value!==''&&Number.isFinite(n)&&n>=Number(this.min??-Infinity)&&n<=Number(this.max??Infinity);},
      click(){this.clicks=(this.clicks||0)+1;}, addEventListener(){}, setAttribute(){}, getContext(){return {drawImage(){},strokeRect(){},fillText(){}};}};
  }
  const document = {getElementById(id){if(!elements.has(id))elements.set(id,element(id));return elements.get(id);},createElement:()=>element('')};
  const api = {user:{id:'u',username:'rider',role:'user'}, ready:Promise.resolve(),
    async request(route, options){calls.push(route);if(route==='/ai/status')return {yolo:{ready:true},cnn:{ready:false}};
      if(route.startsWith('/me/'))return {items:[],total:0,offset:0,limit:10};return request(route,options);}};
  const context = {window:{signSightAuth:api,addEventListener:(name,fn)=>events.set(name,fn)}, document, URLSearchParams,
    navigator:{}, FormData:class{append(){}}, createImageBitmap:async()=>({width:640,height:360,close(){}})};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../frontend/contribution_history.js'),'utf8'), context);
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
  for(const id of ['camera','file','choose-photo','take-photo','choose-file','detect','retry-upload'])assert.equal(a.get(id).disabled,true,id);
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
test('a detected camera photo renders a review card but waits for location confirmation',async()=>{
  const detection={id:'d',qcvn_code:'P.102',name_vi:'Cấm đi ngược chiều',confidence:0.9,predicted_class:5,bbox:{x1:5,y1:6,x2:50,y2:60}};
  const a=app(async route=>route==='/images'?image:route.endsWith('/content')?{}:{detections:[detection]});await tick();
  a.get('camera').files=[{}];await a.get('camera').onchange();
  assert.equal(a.get('detections').children.length,1);
  assert.equal(a.get('detections').children[0].dataset.detectionId,'d');
  assert.equal(a.get('submit').disabled,true);
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

test('choosing a library photo automatically uploads then detects without publishing',async()=>{
  const a=app(async route=>route==='/images'?image:route.endsWith('/content')?{}:{detections:[]});await tick();
  a.get('file').files=[{name:'street.png',type:'image/png',size:100}];await a.get('file').onchange();
  assert.deepEqual(a.calls.filter(route=>route.startsWith('/images')),['/images','/images/photo/content','/images/photo/detect']);
  assert.equal(a.calls.includes('/observations'),false);
  assert.equal(a.get('file').value,'');
  assert.match(a.get('capture-stage').textContent,/Không tìm thấy/);
});
test('photo chooser opens one source selection and routes to the correct hidden input',async()=>{
  const a=app(async()=>({}));await tick();
  a.get('choose-photo').onclick();assert.equal(a.get('photo-choices').hidden,false);
  a.get('choose-file').onclick();assert.equal(a.get('file').clicks,1);
  a.get('take-photo').onclick();assert.equal(a.get('camera').clicks,1);
});
test('failed upload can retry the selected photo without choosing it again',async()=>{
  let uploads=0;
  const a=app(async route=>{
    if(route==='/images'){if(++uploads===1)throw Error('Mất kết nối');return image;}
    return route.endsWith('/content')?{}:{detections:[]};
  });await tick();
  a.get('file').files=[{name:'street.jpg'}];await a.get('file').onchange();
  assert.equal(a.get('retry-upload').hidden,false);
  await a.get('retry-upload').onclick();
  assert.equal(uploads,2);
  assert.equal(a.calls.filter(r=>r.endsWith('/detect')).length,1);
  assert.equal(a.get('retry-upload').hidden,true);
});
test('detect retry uses the saved image and never uploads a second copy',async()=>{
  let attempts=0;
  const a=app(async route=>{
    if(route==='/images')return image;if(route.endsWith('/content'))return {};
    if(++attempts===1)throw Error('Tạm thời lỗi');return {detections:[]};
  });await tick();
  a.get('file').files=[{}];await a.get('file').onchange();
  assert.equal(a.get('detect').hidden,false);
  await a.get('detect').onclick();
  assert.equal(a.calls.filter(r=>r==='/images').length,1);
  assert.equal(attempts,2);
});
test('a second selection cannot start a competing pipeline while upload is pending',{timeout:1000},async()=>{
  let finish;
  const a=app(async route=>route==='/images'?new Promise(resolve=>finish=resolve):route.endsWith('/content')?{}:{detections:[]});await tick();
  a.get('file').files=[{}];const pending=a.get('file').onchange();await tick();
  a.get('camera').files=[{}];await a.get('camera').onchange();
  assert.equal(a.calls.filter(r=>r==='/images').length,1);
  finish(image);await pending;
});

test('submission stays disabled until coordinates are valid and explicitly confirmed',async()=>{
  const detection={id:'d',qcvn_code:'P.102',name_vi:'Cấm đi ngược chiều',confidence:.9,predicted_class:5};
  const a=app(async route=>route==='/images'?image:route.endsWith('/content')?{}:{detections:[detection]});await tick();
  a.get('file').files=[{}];await a.get('file').onchange();
  const card=a.get('detections').children[0],lat=card.querySelector('.lat'),lon=card.querySelector('.lon'),confirmed=card.querySelector('.confirmed');
  assert.equal(a.get('submit').disabled,true);
  lat.value='10.77';lon.value='106.7';lat.onchange();
  assert.equal(a.get('submit').disabled,true);
  confirmed.checked=true;confirmed.onchange();
  assert.equal(a.get('submit').disabled,false);
  lat.value='91';lat.onchange();
  assert.equal(confirmed.checked,false);assert.equal(a.get('submit').disabled,true);
});
