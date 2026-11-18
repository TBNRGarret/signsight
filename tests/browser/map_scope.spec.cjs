const {test,expect}=require('@playwright/test');
const {stubMaps}=require('./map_fixture.cjs');

test('markers show nearby or route signs, never far off-route, and clear old route markers',async({page},testInfo)=>{
 await stubMaps(page);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const sign=(id,latitude,longitude)=>({id,predicted_class:0,qcvn_code:'P.127 (50)',name_vi:id,
  latitude,longitude,status:'active',verification_status:'current',confidence:.9});
 const near=sign('near',10.7769,106.7),shared=sign('shared',10.778,106.701),
  along=sign('along',10.79,106.701),far=sign('far-off-route',10.82,106.75);
 await page.route('**/api/v1/map/signs?*',route=>{
  const query=new URL(route.request().url()).searchParams;
  expect(query.get('radius_meters')).toBeTruthy();expect(query.get('latitude')).toBeTruthy();
  return route.fulfill({json:{items:[near,shared,far],total:3}});
 });
 await page.route('**/api/v1/navigation/route',route=>route.fulfill({json:{
  geometry:[{latitude:10.7769,longitude:106.701},{latitude:10.79,longitude:106.701}],
  distance_meters:1500,duration_seconds:180,buffer_meters:50,
  signs:[shared,along].map((s,i)=>({sign:s,distance_to_route_meters:0,distance_along_route_meters:i*1500}))
 }}));
 await page.goto('/web/index.html');
 await page.getByLabel('Tên đăng nhập',{exact:true}).fill('browser_marker');
 await page.getByLabel('Mật khẩu',{exact:true}).fill('Browser-test-password-123');
 await page.locator('#login-form').getByRole('button',{name:'Đăng nhập',exact:true}).click();
 await expect(page.locator('.sign-map-icon-marker')).toHaveCount(2);
 await page.evaluate(()=>navigationController.route({latitude:10.7769,longitude:106.701},{latitude:10.79,longitude:106.701},50));
 await expect(page.locator('.sign-map-icon-marker')).toHaveCount(3);
 await expect(page.locator('.sign-map-icon-marker[aria-label*="far-off-route"]')).toHaveCount(0);
 await expect(page.locator('#stat-total')).toHaveText('3');
 await page.screenshot({path:testInfo.outputPath('nearby-and-route.png')});
 await page.locator('#nearby-radius').selectOption('100');
 await expect(page.locator('.sign-map-icon-marker')).toHaveCount(3);
 await page.evaluate(()=>navigationController.reset());
 await expect(page.locator('.sign-map-icon-marker')).toHaveCount(1);
 await expect(page.locator('.sign-map-icon-marker[aria-label*="near"]')).toHaveCount(1);
 expect(errors).toEqual([]);
});
