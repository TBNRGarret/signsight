const test=require('node:test');
const assert=require('node:assert/strict');
const {RouteController}=require('../frontend/routing.js');

test('draw uses complete provider geometry and preserves upcoming sign order',async()=>{
  let drawn,seen;
  const controller=new RouteController({request:async(path,options)=>{
    seen={path,body:JSON.parse(options.body)};
    return {geometry:[{latitude:0,longitude:0},{latitude:0,longitude:.01},{latitude:.01,longitude:.01}],
      distance_meters:2000,duration_seconds:100,signs:[{sign:{id:'first'}},{sign:{id:'second'}}]};
  }},{clear:()=>{},draw:data=>drawn=data});
  await controller.route({latitude:0,longitude:0},{latitude:.01,longitude:.01},50);
  assert.equal(seen.path,'/navigation/route');
  assert.equal(drawn.geometry.length,3);
  assert.deepEqual(drawn.signs.map(row=>row.sign.id),['first','second']);
  assert.equal(seen.body.buffer_meters,50);
});
test('provider failure clears the previous route and leaves no invented route',async()=>{
  let clears=0,draws=0;
  const controller=new RouteController({request:async()=>{throw new Error('No route');}},
    {clear:()=>clears++,draw:()=>draws++});
  await assert.rejects(controller.route({latitude:0,longitude:0},{latitude:1,longitude:1},50),/No route/);
  assert.equal(clears,1);assert.equal(draws,0);
});
test('logout or a newer route prevents a late result from appearing',async()=>{
  let finish,draws=0;
  const controller=new RouteController({request:()=>new Promise(resolve=>finish=resolve)},
    {clear:()=>{},draw:()=>draws++});
  const pending=controller.route({latitude:0,longitude:0},{latitude:1,longitude:1},50);
  controller.reset();
  finish({geometry:[{latitude:0,longitude:0},{latitude:1,longitude:1}],signs:[]});
  await pending;assert.equal(draws,0);
});
