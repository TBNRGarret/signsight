const test=require('node:test');
const assert=require('node:assert/strict');
const {buildReportPayload,submitReport}=require('../frontend/reports.js');

test('only class and location corrections carry their extra fields',()=>{
  assert.deepEqual(buildReportPayload({action:'confirm_existing',comment:'  Vẫn còn ở góc đường  ',imageId:'img',proposedClass:3,location:[10,106]}),
    {action:'confirm_existing',image_id:'img',comment:'Vẫn còn ở góc đường'});
  assert.deepEqual(buildReportPayload({action:'correct_class',comment:'Là biển 60',imageId:'img',proposedClass:1,catalogItems:[{new_id:1}]}),
    {action:'correct_class',image_id:'img',comment:'Là biển 60',proposed_class:1});
  assert.deepEqual(buildReportPayload({action:'correct_location',comment:'Lệch sang đối diện',imageId:'img',location:[10.5,106.5]}),
    {action:'correct_location',image_id:'img',comment:'Lệch sang đối diện',latitude:10.5,longitude:106.5});
});

test('class corrections support noncontiguous server catalog IDs and reject unknown IDs before upload',async()=>{
  assert.equal(buildReportPayload({action:'correct_class',comment:'Correct sign',imageId:'img',proposedClass:42,
    catalogItems:[{new_id:42}]}).proposed_class,42);
  const calls=[];
  const api={request:async route=>{calls.push(route);return {items:[{new_id:42,qcvn_code:'FIXTURE.42',name_vi:'Synthetic'}]};}};
  await assert.rejects(submitReport(api,'sign',new Blob(['x']),{action:'correct_class',comment:'Wrong sign',proposedClass:41}),/loại biển đúng/);
  assert.deepEqual(calls,['/taxonomy']);
});

test('invalid reports are rejected before reaching the server',()=>{
  const base={action:'report_removed',comment:'Đã bị tháo',imageId:'img'};
  assert.throws(()=>buildReportPayload({...base,action:'delete_sign'}),/loại báo cáo/);
  assert.throws(()=>buildReportPayload({...base,comment:' a '}),/ít nhất 3 ký tự/);
  assert.throws(()=>buildReportPayload({...base,imageId:''}),/ảnh/);
  assert.throws(()=>buildReportPayload({...base,action:'correct_class',proposedClass:10}),/loại biển đúng/);
  assert.throws(()=>buildReportPayload({...base,action:'correct_location',location:null}),/vị trí đúng/);
  assert.throws(()=>buildReportPayload({...base,action:'correct_location',location:[91,106]}),/vị trí đúng/);
});

test('submit uploads the photo first, then files the report against that image',async()=>{
  const calls=[];
  const api={request:async(path,options)=>{calls.push({path,options});return path==='/images'?{id:'uploaded-image'}:{id:'report',status:'pending'};}};
  const report=await submitReport(api,'sign-1',new Blob(['jpeg']),{action:'report_damaged',comment:'Biển bị cong'});
  assert.equal(report.status,'pending');
  assert.deepEqual(calls.map(call=>call.path),['/images','/signs/sign-1/reports']);
  assert.ok(calls[0].options.body instanceof FormData);
  assert.deepEqual(JSON.parse(calls[1].options.body),{action:'report_damaged',image_id:'uploaded-image',comment:'Biển bị cong'});
});

test('missing photo or invalid fields never upload an orphan image',async()=>{
  const calls=[];
  const api={request:async path=>{calls.push(path);return {id:'x'};}};
  await assert.rejects(submitReport(api,'sign-1',null,{action:'confirm_existing',comment:'Vẫn còn'}),/ảnh/);
  await assert.rejects(submitReport(api,'sign-1',new Blob(['x']),{action:'correct_location',comment:'Lệch vị trí',location:null}),/vị trí đúng/);
  assert.deepEqual(calls,[]);
});

test('server rejection of the report surfaces its message',async()=>{
  const api={request:async path=>{if(path==='/images')return {id:'img'};throw new Error('Sign merged; submit evidence to the linked current record');}};
  await assert.rejects(submitReport(api,'old',new Blob(['x']),{action:'confirm_existing',comment:'Vẫn còn'}),/Sign merged/);
});

test('account changes during catalog lookup or photo upload stop subsequent report writes',async()=>{
  for(const stage of ['/taxonomy','/images']){
    let finish;const calls=[];
    const api={user:{id:'first'},request:async route=>{
      calls.push(route);
      if(route===stage)return new Promise(resolve=>finish=resolve);
      if(route==='/images')return {id:'uploaded-photo'};
      return {items:[{new_id:42,qcvn_code:'FIXTURE.42',name_vi:'Synthetic'}]};
    }};
    const pending=submitReport(api,'sign',new Blob(['x']),{action:'correct_class',comment:'Correct label',proposedClass:42});
    while(!finish)await new Promise(resolve=>setImmediate(resolve));
    api.user={id:'second'};
    finish(stage==='/taxonomy'?{items:[{new_id:42,qcvn_code:'FIXTURE.42',name_vi:'Synthetic'}]}:{id:'private-photo'});
    await assert.rejects(pending,/Phiên/);
    assert.equal(calls.some(route=>route.includes('/reports')),false);
    if(stage==='/taxonomy')assert.deepEqual(calls,['/taxonomy']);
  }
});
