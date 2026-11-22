const test=require('node:test'),assert=require('node:assert/strict');
const routing=require('../frontend/routing.js');
const sign=(id,latitude,longitude)=>({id,latitude,longitude,qcvn_code:'P.102',name_vi:id,status:'active'});
const near=sign('near',10.777,106.701),along=sign('along',10.8,106.71),far=sign('far',11,107);

test('map scope keeps nearby OR route and deduplicates IDs',()=>{
 assert.equal(typeof routing.visibleSigns,'function');
 const rows=routing.visibleSigns({nearby:[near,far],route:[near,along],center:[10.7769,106.7009],radius:500});
 assert.deepEqual(new Set(rows.map(r=>r.id)),new Set(['near','along']));
 assert.equal(rows.length,2);
});
test('route clearing cannot leave far route-only markers behind',()=>{
 assert.equal(typeof routing.visibleSigns,'function');
 const scope={nearby:[near,far],route:[along],center:[10.7769,106.7009],radius:500};
 assert.equal(routing.visibleSigns(scope).length,2);
 assert.deepEqual(routing.visibleSigns({...scope,route:[]}).map(s=>s.id),['near']);
});
test('shrinking radius removes a near candidate but retains far on-route signs',()=>{
 assert.equal(typeof routing.visibleSigns,'function');
 const middle=sign('middle',10.779,106.7009);
 const scope={nearby:[middle],route:[along],center:[10.7769,106.7009],radius:500};
 assert.equal(routing.visibleSigns(scope).length,2);
 assert.deepEqual(routing.visibleSigns({...scope,radius:100}).map(s=>s.id),['along']);
});
test('the map shows every sign returned for the current view, including ones far from the selected pin',()=>{
 assert.equal(typeof routing.markersInView,'function');
 const rows=routing.markersInView({viewport:[near,far],route:[along],classId:'',status:''});
 assert.deepEqual(new Set(rows.map(row=>row.id)),new Set(['near','far','along']));
 assert.equal(rows.length,3);
 assert.deepEqual(routing.markersInView({viewport:[near,far],route:[along],classId:'',status:'removed'}),[]);
});

test('invalid positions do not bypass nearby scope and longitude wrap works',()=>{
 assert.equal(typeof routing.visibleSigns,'function');
 const wrapped=sign('wrap',0,-179.999);
 const rows=routing.visibleSigns({nearby:[wrapped,sign('bad',NaN,0)],route:[],center:[0,179.999],radius:300});
 assert.deepEqual(rows.map(s=>s.id),['wrap']);
});
