const {test,expect}=require('@playwright/test');
const {stubMaps,style}=require('./map_fixture.cjs');
test('interactive OFM map loads in a guest session and changes styles without losing camera or route',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));await stubMaps(page);await page.goto('/web/index.html');
 await expect(page.locator('.maplibregl-canvas')).toBeVisible();await expect(page.locator('#map-notice')).toBeHidden();
 const before=await page.evaluate(()=>{
  map.native.jumpTo({center:[106.71,10.78],zoom:16,bearing:30,pitch:25});
  map.addRoute([{latitude:10.77,longitude:106.70},{latitude:10.79,longitude:106.72}]);
  return {center:map.native.getCenter().toArray(),zoom:map.native.getZoom(),bearing:map.native.getBearing(),pitch:map.native.getPitch()};
 });
 await page.locator('#map-source').selectOption('dark');await expect(page.locator('#map-notice')).toBeHidden();
 const after=await page.evaluate(()=>({center:map.native.getCenter().toArray(),zoom:map.native.getZoom(),bearing:map.native.getBearing(),pitch:map.native.getPitch()}));
 expect(after).toEqual(before);
 await expect.poll(()=>page.evaluate(()=>map.native.getStyle().layers.filter(l=>l.id.startsWith('signsight-route-')).length)).toBe(1);
 expect(await page.evaluate(()=>localStorage.getItem('signsight.map-style'))).toBe('dark');
 await page.locator('#map-home').click();
 await expect.poll(()=>page.evaluate(()=>Math.round(map.native.getBearing()))).toBe(0);
 const size=await page.evaluate(()=>({width:document.documentElement.scrollWidth,viewport:innerWidth}));expect(size.width).toBeLessThanOrEqual(size.viewport);
 expect(errors).toEqual([]);
});
test('blocked OFM shows retry, then recovers without requesting a raster fallback',async({page})=>{
 let blocked=true,raster=0;await stubMaps(page);
 await page.route('https://tiles.openfreemap.org/styles/*',route=>blocked?route.abort():route.fulfill({json:style}));
 page.on('request',r=>{if(/tile.openstreetmap/.test(r.url()))raster++;});
 await page.goto('/web/index.html');await expect(page.locator('#map-message')).toContainText('Không tải được');
 blocked=false;await page.locator('#map-retry').click();await expect(page.locator('#map-notice')).toBeHidden();expect(raster).toBe(0);
});
test('lack of WebGL keeps login available and explains the manual location alternative',async({page})=>{
 await page.addInitScript(()=>{
  const original=HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext=function(type,...args){return String(type).includes('webgl')?null:original.call(this,type,...args);};
 });
 await stubMaps(page);await page.goto('/web/index.html');await expect(page.locator('#map-message')).toContainText('WebGL');
 await expect(page.locator('#login-form')).toBeVisible();await expect(page.locator('#map-retry')).toBeEnabled();
});
