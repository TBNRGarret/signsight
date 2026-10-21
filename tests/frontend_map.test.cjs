const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { mount } = require('../frontend/map.js');

function setup(store = new Map()) {
  const elements = Object.fromEntries(['map', 'map-notice', 'map-message', 'map-retry', 'map-home', 'map-source']
    .map(id => [id, { hidden: true, textContent: '', clientWidth: 600, clientHeight: 500 }]));
  const mapEvents = {}, timers = new Map(), frames = new Map(), layers = [], removed = [];
  const invalidations = [], views = [];
  let serial = 0, observer, observed, disconnected = false, redraws = 0, tileConfig;
  const map = {
    setView(center, zoom) { views.push({ center, zoom }); return this; },
    getContainer: () => elements.map,
    invalidateSize: options => invalidations.push(options),
    removeLayer(layer) { removed.push(layer); },
    on(name, fn) { mapEvents[name] = fn; return this; }
  };
  const environment = {
    localStorage:{getItem:key=>store.get(key)??null,setItem:(key,value)=>store.set(key,value)},
    ResizeObserver: class {
      constructor(fn) { observer = fn; }
      observe(element) { observed = element; }
      disconnect() { disconnected = true; }
    },
    requestAnimationFrame(fn) { frames.set(++serial, fn); return serial; },
    cancelAnimationFrame(id) { frames.delete(id); },
    setTimeout(fn) { timers.set(++serial, fn); return serial; },
    clearTimeout(id) { timers.delete(id); }
  };
  const L = { map: () => map, tileLayer(url, options) {
    tileConfig = {url,options}; const events={};
    const layer={events,on(name,fn){events[name]=fn;return this;},off(){for(const key of Object.keys(events))delete events[key];},
      addTo(){events.loading();return this;},redraw(){redraws++;events.loading();return this;}};
    layers.push(layer);return layer;
  } };
  const result = mount({ L, document: { getElementById: id => elements[id] }, environment });
  return {
    ...result, elements, mapEvents, timers, frames, invalidations, views, layers, removed,
    get events() { return layers.at(-1).events; },
    get tileConfig() { return tileConfig; }, get redraws() { return redraws; },
    get observed() { return observed; }, get disconnected() { return disconnected; },
    resize: () => observer(),
    flushFrames() { const pending = [...frames.values()]; frames.clear(); pending.forEach(fn => fn()); },
    timeout() { const pending = [...timers.values()]; timers.clear(); pending.forEach(fn => fn()); }
  };
}

test('base map starts in HCMC without login and sends a referrer to the canonical OSM endpoint', () => {
  const s = setup();
  assert.deepEqual(s.views, [{ center: [10.7769, 106.7009], zoom: 15 }]);
  assert.equal(s.tileConfig.url, 'https://tile.openstreetmap.org/{z}/{x}/{y}.png');
  assert.equal(s.tileConfig.options.referrerPolicy, 'strict-origin-when-cross-origin');
  assert.match(s.tileConfig.options.attribution, /https:\/\/www.openstreetmap.org\/copyright/);
  assert.equal(s.observed, s.elements.map);
});

test('a healthy alternate source is remembered so the next visit skips the failing primary',()=>{
  const store=new Map(),first=setup(store);
  first.events.tileerror({tile:{}});first.events.load();
  first.events.tileload({tile:{}});first.events.load();
  const next=setup(store);
  assert.match(next.tileConfig.url,/tile\.openstreetmap\.de/);
  assert.equal(next.layers.length,1);
});

test('a remembered source can fail over once and expired preferences return to the primary',()=>{
  const key='signsight.map-source',store=new Map([[key,JSON.stringify({id:'osm-de',savedAt:Date.now()})]]);
  const current=setup(store);current.events.tileerror({tile:{}});current.events.load();
  assert.match(current.tileConfig.url,/tile\.openstreetmap\.org/);
  current.events.tileerror({tile:{}});current.events.load();assert.equal(current.layers.length,2);
  store.set(key,JSON.stringify({id:'osm-de',savedAt:Date.now()-25*60*60*1000}));
  assert.match(setup(store).tileConfig.url,/tile\.openstreetmap\.org/);
});

test('map source preference works without browser storage and ignores malformed entries',()=>{
  const disabled={get(){throw Error('disabled');},set(){throw Error('disabled');}};
  const s=setup(disabled);s.events.tileload({tile:{}});s.events.load();
  assert.equal(s.elements['map-notice'].hidden,true);
  for(const value of ['{bad',JSON.stringify({id:'https://untrusted.example',savedAt:Date.now()}),JSON.stringify({id:'osm-de',savedAt:Date.now()+10000})]){
    assert.match(setup(new Map([['signsight.map-source',value]])).tileConfig.url,/tile\.openstreetmap\.org/);
  }
});

test('container resize coalesces updates and preserves the chosen view; hidden containers recover', () => {
  const s = setup();
  s.elements.map.clientWidth = 0;
  s.flushFrames();
  assert.equal(s.invalidations.length, 0);
  s.elements.map.clientWidth = 390;
  s.resize(); s.resize(); s.resize(); s.flushFrames();
  assert.deepEqual(s.invalidations, [{ pan: false, debounceMoveend: true }]);
  assert.equal(s.views.length, 1);
  s.elements['map-home'].onclick();
  assert.deepEqual(s.views[1], s.views[0]);
});

test('failed tiles remain visible as an error even when other tiles finish; a manual retry can recover', () => {
  const s = setup(), failed = {}, healthy = {};
  s.events.tileerror({ tile: failed });
  s.events.tileload({ tile: healthy });
  s.events.load();
  assert.equal(s.elements['map-notice'].hidden, false);
  assert.match(s.elements['map-message'].textContent, /Không tải được/);
  assert.equal(s.redraws, 0);
  s.elements['map-retry'].onclick();
  assert.equal(s.redraws, 1);
  s.events.tileload({ tile: {} }); s.events.load();
  assert.equal(s.elements['map-notice'].hidden, true);
  assert.equal(s.timers.size, 0);
});

test('a stalled primary source switches once; a stalled fallback shows an error without looping', () => {
  const stalled = setup(); stalled.timeout();
  assert.equal(stalled.layers.length,2);
  assert.match(stalled.tileConfig.url,/tile\.openstreetmap\.de/);
  stalled.timeout();
  assert.equal(stalled.elements['map-notice'].hidden, false);
  assert.match(stalled.elements['map-message'].textContent, /tải chậm/);
  stalled.events.tileload({ tile: {} });
  assert.equal(stalled.elements['map-notice'].hidden, false, 'one late tile must not hide remaining stalled requests');
  const loaded = setup(); loaded.events.tileload({ tile: {} }); loaded.events.load(); loaded.timeout();
  assert.equal(loaded.elements['map-notice'].hidden, true);
});

test('all primary tiles failing switches to the alternate source without resetting the view',()=>{
  const s=setup(), oldEvents={...s.events};
  s.events.tileerror({tile:{}});s.events.load();
  assert.equal(s.layers.length,2);
  assert.equal(s.removed.length,1);
  assert.match(s.tileConfig.url,/tile\.openstreetmap\.de/);
  assert.equal(s.elements['map-source'].value,'osm-de');
  assert.equal(s.views.length,1);
  oldEvents.tileerror({tile:{}});oldEvents.load();
  assert.equal(s.layers.length,2,'late events from old source are ignored');
  s.events.tileload({tile:{}});s.events.load();
  assert.equal(s.elements['map-notice'].hidden,true);
});

test('manual source change replaces only the basemap and ignores unknown selections',()=>{
  const s=setup();
  s.elements['map-source'].value='osm-de';s.elements['map-source'].onchange();
  assert.equal(s.layers.length,2);assert.equal(s.views.length,1);
  assert.match(s.tileConfig.options.attribution,/FOSSGIS/);
  s.elements['map-source'].value='unknown';s.elements['map-source'].onchange();
  assert.equal(s.layers.length,2);
  s.mapEvents.unload();assert.equal(s.elements['map-source'].onchange,null);
});

test('failed tiles which leave the viewport no longer keep the error on screen', () => {
  const s = setup(), tile = {};
  s.events.tileerror({ tile }); s.events.tileunload({ tile }); s.events.load();
  assert.equal(s.elements['map-notice'].hidden, true);
});

test('map removal releases the observer, pending callbacks and UI handlers', () => {
  const s = setup(); s.mapEvents.unload();
  assert.equal(s.disconnected, true);
  assert.equal(s.frames.size, 0); assert.equal(s.timers.size, 0);
  assert.equal(s.elements['map-retry'].onclick, null);
  assert.equal(s.elements['map-home'].onclick, null);
});

test('the page mounts the shared base map and keeps mobile dimensions on its panel', () => {
  const html = fs.readFileSync(require.resolve('../frontend/index.html'), 'utf8');
  assert.match(html, /src="map\.js\?v=[^"]+"/);
  assert.match(html, /signSightMap\.mount\(\{L,\s*document\}\)/);
  for (const id of ['map-notice', 'map-message', 'map-retry', 'map-home', 'map-source']) assert.ok(html.includes(`id="${id}"`));
  assert.match(html, /\.map-panel\s*\{[^}]*height:\s*55vh/);
  assert.doesNotMatch(html, /L\.tileLayer\(/);
});
