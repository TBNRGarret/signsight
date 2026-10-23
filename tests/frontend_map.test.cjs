const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {mount}=require('../frontend/map.js');
function setup(store=new Map(),{fail=false}={}){
 const elements=Object.fromEntries(['map','map-notice','map-message','map-retry','map-home','map-source'].map(id=>[id,{hidden:true,textContent:'',clientWidth:600,clientHeight:500}]));
 const events={},frames=new Map(),timers=new Map(),markers=[],popups=[],routes=new Map(),layers=new Map(),styles=[],views=[],controls=[];
 let config,serial=0,resizeCount=0,disconnected=false,observer,loaded=false,removed=false;
 const native={on(n,f){(events[n]??=[]).push(f);return this;},addControl(c){controls.push(c);},getContainer:()=>elements.map,
  resize(){resizeCount++;},flyTo(o){views.push(o);},getZoom:()=>15,getBounds:()=>({}),
  setStyle(s){styles.push(s);routes.clear();layers.clear();loaded=false;},
  isStyleLoaded:()=>loaded,areTilesLoaded:()=>loaded,
  addSource(id,s){routes.set(id,s);},getSource:id=>routes.get(id),removeSource:id=>routes.delete(id),
  addLayer(l){layers.set(l.id,l);},getLayer:id=>layers.get(id),removeLayer:id=>layers.delete(id),
  fitBounds(b,o){this.fitted={b,o};},remove(){removed=true;emit('remove');}};
 function emit(n,e={}){for(const f of events[n]||[])f(e);}
 const maplibregl={Map:class{constructor(o){if(fail)throw Error('WebGL unavailable');config=o;return native;}},
  NavigationControl:class{},Marker:class{constructor(o){this.options=o;this.events={};markers.push(this);}
   setLngLat(p){this.point=p;return this;}addTo(){return this;}getLngLat(){return {lng:this.point[0],lat:this.point[1]};}
   on(n,f){this.events[n]=f;return this;}remove(){this.removed=true;}},
  Popup:class{constructor(){popups.push(this);}setDOMContent(){return this;}setLngLat(){return this;}addTo(){return this;}remove(){this.removed=true;} }};
 const document={getElementById:id=>elements[id],createElement(){return {style:{},dataset:{},events:{},setAttribute(){},addEventListener(n,f){this.events[n]=f;}};}};
 const environment={localStorage:{getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v)},
  ResizeObserver:class{constructor(fn){observer=fn;}observe(){}disconnect(){disconnected=true;}},
  requestAnimationFrame(fn){frames.set(++serial,fn);return serial;},cancelAnimationFrame:id=>frames.delete(id),
  setTimeout(fn){timers.set(++serial,fn);return serial;},clearTimeout:id=>timers.delete(id)};
 const result=mount({maplibregl,document,environment});
 return {...result,elements,styles,views,controls,markers,popups,routes,layers,native,emit,store,
  get config(){return config;},get resizeCount(){return resizeCount;},get disconnected(){return disconnected;},get removed(){return removed;},
  resize:()=>observer(),ready(){loaded=true;emit('style.load');emit('idle');},
  timeout(){const pending=[...timers.values()];timers.clear();pending.forEach(fn=>fn());},
  flush(){const pending=[...frames.values()];frames.clear();pending.forEach(fn=>fn());},frames,timers};
}
test('MapLibre starts at HCMC with interactive OFM vector tiles without a login or key',()=>{
 const a=setup();assert.deepEqual(a.config.center,[106.7009,10.7769]);assert.equal(a.config.zoom,15);
 assert.equal(a.config.style,'https://tiles.openfreemap.org/styles/liberty');assert.equal(a.config.renderWorldCopies,false);
 assert.equal(a.controls.length,1);a.ready();assert.equal(a.elements['map-notice'].hidden,true);
});
test('application latitude/longitude is converted correctly for native camera, clicks and draggable markers',()=>{
 const a=setup();a.map.flyTo([10.8,106.8],17);assert.deepEqual(a.views.at(-1).center,[106.8,10.8]);
 let point;a.map.on('click',e=>point=e.latlng);a.emit('click',{lngLat:{lng:106.9,lat:10.9}});
 assert.deepEqual(point,{lat:10.9,lng:106.9});
 const pin=a.map.addMarker([10.7,106.7],{draggable:true});assert.deepEqual(a.markers[0].point,[106.7,10.7]);
 assert.equal(a.markers[0].options.draggable,true);assert.deepEqual(pin.getLatLng(),{lat:10.7,lng:106.7});
 a.map.removeLayer(pin);assert.equal(a.markers[0].removed,true);
});
test('style changes preserve markers, restore pending route geometry and never reset the camera',()=>{
 const a=setup();const route=a.map.addRoute([{latitude:10,longitude:106},{latitude:11,longitude:107}]);
 assert.equal(a.routes.size,0);a.ready();assert.equal(a.routes.size,1);
 const source=[...a.routes.values()][0];assert.deepEqual(source.data.geometry.coordinates,[[106,10],[107,11]]);
 a.elements['map-source'].value='dark';a.elements['map-source'].onchange();a.ready();
 assert.equal(a.routes.size,1);assert.equal(a.views.length,0);assert.match(a.styles.at(-1),/styles\/dark$/);
 a.map.removeLayer(route);assert.equal(a.routes.size,0);a.elements['map-source'].value='bright';a.elements['map-source'].onchange();a.ready();
 assert.equal(a.routes.size,0,'removed/private routes must not reappear on a style reload');
});
test('only allowlisted OFM styles can be saved and disabled browser storage remains usable',()=>{
 const store=new Map(),a=setup(store);a.elements['map-source'].value='bright';a.elements['map-source'].onchange();
 assert.match(setup(store).config.style,/styles\/bright$/);
 a.elements['map-source'].value='https://untrusted.example';a.elements['map-source'].onchange();assert.equal(a.styles.length,1);
 assert.match(setup(new Map([['signsight.map-style','evil']])).config.style,/liberty$/);
 const disabled={get(){throw Error('disabled');},set(){throw Error('disabled');}};
 setup(disabled).ready();
});
test('network errors and stalls remain visible without automatic provider switching; retry recovers',()=>{
 const a=setup();a.emit('error',{error:Error('tile blocked')});a.ready();
 assert.equal(a.elements['map-notice'].hidden,false);assert.equal(a.styles.length,0);
 a.elements['map-retry'].onclick();a.ready();assert.equal(a.elements['map-notice'].hidden,true);
 assert.match(a.styles.at(-1),/openfreemap.org/);
 const b=setup();b.timeout();assert.match(b.elements['map-message'].textContent,/tải chậm/);assert.equal(b.styles.length,0);
});
test('resizing hidden containers does not reset the camera and removal releases observers, timers and handlers',()=>{
 const a=setup();a.elements.map.clientWidth=0;a.flush();assert.equal(a.resizeCount,0);
 a.elements.map.clientWidth=390;a.resize();a.resize();a.flush();assert.equal(a.resizeCount,1);assert.equal(a.views.length,0);
 a.elements['map-home'].onclick();assert.deepEqual(a.views.at(-1).center,[106.7009,10.7769]);
 a.map.remove();assert.equal(a.disconnected,true);assert.equal(a.timers.size,0);assert.equal(a.frames.size,0);
 assert.equal(a.elements['map-retry'].onclick,null);assert.equal(a.elements['map-source'].onchange,null);
});
test('WebGL initialization failure shows a usable message and leaves authentication/manual coordinates available',()=>{
 const a=setup(new Map(),{fail:true});assert.equal(a.map.enabled,false);
 assert.match(a.elements['map-message'].textContent,/WebGL/);assert.equal(a.elements['map-notice'].hidden,false);
 assert.doesNotThrow(()=>a.map.flyTo([10,106],17));assert.equal(a.map.addMarker([10,106]),null);
});
test('both map pages load local MapLibre assets and expose OFM styles without Leaflet',()=>{
 for(const name of ['index.html','observations.html']){
  const html=fs.readFileSync(require.resolve('../frontend/'+name),'utf8');
  assert.match(html,/vendor\/maplibre\/maplibre-gl.js/);assert.match(html,/vendor\/maplibre\/maplibre-gl.css/);
  assert.doesNotMatch(html,/vendor\/leaflet|value="osm-de"/);assert.match(html,/value="liberty"/);assert.match(html,/value="dark"/);
 }
});

test('style.load restores route overlays while base tile requests are still pending',()=>{
 const a=setup();a.map.addRoute([{latitude:10,longitude:106},{latitude:11,longitude:107}]);
 a.emit('style.load');assert.equal(a.routes.size,1);
});


test('removing a private sign marker closes its popup without closing a different marker popup',()=>{
 const a=setup();const marker=a.map.addMarker([10,106],{popup:()=>({})}),highlight=a.map.addMarker([10,106],{highlight:true});
 a.markers[0].options.element.events.click({stopPropagation(){}});
 assert.equal(a.popups.length,1);
 highlight.remove();assert.equal(a.popups[0].removed,undefined);
 marker.remove();assert.equal(a.popups[0].removed,true);
});
