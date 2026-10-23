const test=require('node:test'),assert=require('node:assert/strict');
const {mount}=require('../frontend/location_picker.js');
function setup(){
  const nodes=new Map(),events={},changes=[],views=[],removed=[];
  const get=id=>{if(!nodes.has(id))nodes.set(id,{hidden:true,disabled:false,textContent:''});return nodes.get(id);};
  let marker,gpsSuccess,gpsError,mountCount=0;
  const map={on:(name,fn)=>events[name]=fn,flyTo:(point,zoom)=>views.push([point,zoom]),
    removeLayer:layer=>removed.push(layer),invalidateSize(){}};
  const L={marker(point){const handlers={};marker={point,handlers,on(n,f){handlers[n]=f;return this;},
    addTo(){return this;},getLatLng(){return {lat:this.point[0],lng:this.point[1]};}};return marker;}};
  const environment={navigator:{geolocation:{getCurrentPosition(success,error){gpsSuccess=success;gpsError=error;}}}};
  map.addMarker=(point,options)=>L.marker(point,options);
  const picker=mount({document:{getElementById:get},environment,
    baseMap:{mount(options){assert.equal(options.idPrefix,'location-');mountCount++;return {map};}},
    onChange:change=>changes.push(change)});
  return {picker,get,events,changes,views,removed,get marker(){return marker;},get mountCount(){return mountCount;},
    gpsSuccess:value=>gpsSuccess(value),gpsError:value=>gpsError(value)};
}
test('a pin must be placed and explicitly confirmed before it becomes ready',()=>{
  const a=setup();a.picker.setItems([{id:'a',name:'Biển 1'}]);a.picker.select('a');
  assert.equal(a.get('location-confirm').disabled,true);
  a.events.click({latlng:{lat:10.77,lng:106.70}});
  assert.equal(a.changes.at(-1).confirmed,false);
  a.get('location-confirm').onclick();
  assert.deepEqual(a.changes.at(-1),{id:'a',latitude:10.77,longitude:106.70,confirmed:true});
});
test('changing the selected sign does not copy coordinates into another sign',()=>{
  const a=setup();a.picker.setItems([{id:'a',name:'A'},{id:'b',name:'B'}]);a.picker.select('a');
  a.events.click({latlng:{lat:10.7,lng:106.7}});a.get('location-confirm').onclick();
  const count=a.changes.length;a.picker.select('b');
  assert.equal(a.changes.length,count);assert.equal(a.get('location-confirm').disabled,true);
  a.picker.select('a');assert.equal(a.mountCount,1);
  assert.match(a.get('location-status').textContent,/Đã xác nhận/);
});
test('GPS failure keeps manual map selection available',()=>{
  const a=setup();a.picker.setItems([{id:'a',name:'A'}]);a.picker.select('a');
  a.get('location-gps').onclick();a.gpsError({code:1});
  assert.match(a.get('location-status').textContent,/Chạm bản đồ/);
  assert.equal(a.get('location-gps').disabled,false);
  a.events.click({latlng:{lat:10,lng:106}});a.get('location-confirm').onclick();
  assert.equal(a.changes.at(-1).confirmed,true);
});
test('a late GPS result cannot set coordinates for a different sign or after clear',()=>{
  const a=setup();a.picker.setItems([{id:'a',name:'A'},{id:'b',name:'B'}]);a.picker.select('a');
  a.get('location-gps').onclick();a.picker.select('b');
  a.gpsSuccess({coords:{latitude:11,longitude:107,accuracy:12}});
  assert.equal(a.changes.length,0);
  a.get('location-gps').onclick();a.picker.clear();
  a.gpsSuccess({coords:{latitude:11,longitude:107,accuracy:12}});
  assert.equal(a.changes.length,0);assert.equal(a.get('location-panel').hidden,true);
});
test('GPS/EXIF coordinates are suggestions and moving a pin invalidates confirmation',()=>{
  const a=setup();a.picker.setItems([{id:'a',name:'A',latitude:10,longitude:106}]);a.picker.select('a');
  a.get('location-confirm').onclick();assert.equal(a.changes.at(-1).confirmed,true);
  a.marker.point=[10.2,106.2];a.marker.handlers.dragend();
  assert.equal(a.changes.at(-1).confirmed,false);
  assert.equal(a.changes.at(-1).latitude,10.2);
});
test('coordinates outside the valid range are rejected',()=>{
  const a=setup();a.picker.setItems([{id:'a',name:'A'}]);a.picker.select('a');
  assert.equal(a.picker.setPosition('a',91,106),false);
  assert.equal(a.picker.setPosition('a',10,Infinity),false);
  assert.equal(a.changes.length,0);assert.equal(a.get('location-confirm').disabled,true);
});

test('a late GPS suggestion cannot overwrite a pin the user already moved and confirmed',()=>{
 const a=setup();a.picker.setItems([{id:'a',name:'A'}]);a.picker.select('a');a.get('location-gps').onclick();
 a.events.click({latlng:{lat:10.1,lng:106.1}});a.get('location-confirm').onclick();
 const count=a.changes.length;
 a.gpsSuccess({coords:{latitude:11,longitude:107,accuracy:5}});
 assert.equal(a.changes.length,count);assert.equal(a.changes.at(-1).latitude,10.1);assert.equal(a.changes.at(-1).confirmed,true);
 assert.equal(a.get('location-gps').disabled,false);
});
