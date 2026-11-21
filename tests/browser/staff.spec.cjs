const {test,expect}=require('@playwright/test');
const {stubMaps,style}=require('./map_fixture.cjs');
const fs=require('node:fs'),path=require('node:path');
async function login(page,username){
 await page.goto('/web/index.html');
 await page.getByLabel('Tên đăng nhập',{exact:true}).fill(username);
 await page.getByLabel('Mật khẩu',{exact:true}).fill('Browser-test-password-123');
 await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
 await expect(page).toHaveURL(/management.html$/);
 await expect(page.locator('#workspace')).toBeVisible();
}
test('manager lands on work queue and searches the global sign table with server pagination',async({page,context},testInfo)=>{
 await stubMaps(page);await login(page,'browser_manager');
 await expect(page.locator('#tab-contributions')).toHaveAttribute('aria-selected','true');
 await expect(page.locator('#tab-accounts')).toBeHidden();await expect(page.locator('#tab-policy')).toBeHidden();
 await expect(page.getByRole('button',{name:'Chụp hoặc chọn ảnh'})).toHaveCount(0);
 await page.locator('#tab-signs').click();await expect(page.locator('#signs tr')).toHaveCount(25);
 const first=(await page.locator('#signs tr').evaluateAll(rows=>rows.map(r=>r.dataset.signId)));
 await page.locator('#signs-next').click();await expect(page.locator('#signs-page')).toContainText('26–50');
 const second=await page.locator('#signs tr').evaluateAll(rows=>rows.map(r=>r.dataset.signId));
 expect(second.some(id=>first.includes(id))).toBe(false);
 await page.locator('#sign-query').fill('P.127');await page.locator('#sign-status').selectOption('removed');
 await expect(page.locator('#signs-page')).toContainText('1–25');
 const response=await (await page.request.get('/api/v1/manager/signs?q=P.127&status=removed&limit=25')).json();
 await expect(page.locator('#signs-count')).toContainText(response.total+' biển');
 await page.locator('#signs tr').first().getByRole('button').click();
 await expect(page.locator('#detail-title')).toContainText('P.127');
 await expect(page.locator('#review-actions')).toBeHidden();
 if(testInfo.project.name==='desktop')await expect(page.locator('#signs-next')).toBeInViewport();
 const link=page.locator('#detail-meta a');await expect(link).toHaveAttribute('href',/staff_view=1/);
 await context.route('https://**/*',route=>route.abort());
 await context.route('https://tiles.openfreemap.org/styles/*',route=>route.fulfill({json:style}));
 const popupPromise=page.waitForEvent('popup');await link.click();const popup=await popupPromise;
 await expect(popup).toHaveURL(/staff_view=1/);await expect(popup.locator('#selected-title')).toContainText('P.127');
 // The selected removed record must still have its sign icon, independent of
 // the user map's active-only filter and nearby request.
 const selectedId=new URL(popup.url()).searchParams.get('sign');
 const selectedMarker=popup.locator('.sign-map-icon-marker[data-sign-id="'+selectedId+'"]');
 await expect(selectedMarker).toHaveCount(1);
 await expect(selectedMarker.locator('img')).toHaveAttribute('src',/speed_limit_50\.svg$/);
 await expect.poll(()=>selectedMarker.locator('img').evaluate(img=>img.complete&&img.naturalWidth>0)).toBe(true);
 await popup.evaluate(()=>loadSigns());
 await expect(selectedMarker).toHaveCount(1);
 await expect(popup.locator('.sign-map-icon-marker')).toHaveCount(34);
 await expect(selectedMarker).toHaveClass(/sign-map-selected/);
 await expect(selectedMarker).toBeInViewport();
 await selectedMarker.click();
 await expect(popup.locator('.sign-photo-popup')).toContainText('đã tháo');
 await popup.screenshot({path:testInfo.outputPath('staff-selected-sign-map.png')});
 await expect(popup.locator('#report-form')).toBeHidden();await popup.close();
 if(process.env.SIGNSIGHT_SCREENSHOT_DIR){
  fs.mkdirSync(process.env.SIGNSIGHT_SCREENSHOT_DIR,{recursive:true});
  await page.screenshot({path:path.join(process.env.SIGNSIGHT_SCREENSHOT_DIR,'staff-catalogue-'+testInfo.project.name+'.png'),fullPage:true});
 }
 const width=await page.evaluate(()=>({actual:document.documentElement.scrollWidth,viewport:innerWidth}));
 expect(width.actual).toBeLessThanOrEqual(width.viewport);
});
test('owner has accounts and policy in the same workspace while user cannot access it',async({page})=>{
 await stubMaps(page);await login(page,'browser_admin');
 await page.locator('#tab-accounts').click();await expect(page.locator('#accounts tr')).not.toHaveCount(0);
 await page.locator('#tab-policy').click();await expect(page.locator('#days')).toHaveValue('30');
 await page.locator('#logout').click();await expect(page).toHaveURL(/index.html\?staff=login/);
 const denied=await page.request.get('/web/management.html',{maxRedirects:0});expect(denied.status()).toBe(303);
});

test('owner inspection deduplicates the selected active sign and clears it on logout',async({page,context})=>{
 await stubMaps(page);await login(page,'browser_admin');
 await page.locator('#tab-signs').click();
 await page.locator('#sign-status').selectOption('active');
 const listing=await (await page.request.get('/api/v1/manager/signs?status=active&limit=1')).json();
 await expect(page.locator('#signs-count')).toContainText(listing.total+' biển');
 await page.locator('#signs tr').first().getByRole('button').click();
 // Other browser flows may publish more synthetic signs. Return only this
 // active record to guarantee that it appears in both selection and map data.
 await context.route('**/api/v1/map/signs?*',route=>route.fulfill({json:{items:listing.items,total:1}}));
 await context.route('https://**/*',route=>route.abort());
 await context.route('https://tiles.openfreemap.org/styles/*',route=>route.fulfill({json:style}));
 const opened=page.waitForEvent('popup');await page.locator('#detail-meta a').click();const popup=await opened;
 await expect(popup).toHaveURL(/staff_view=1/);
 const selectedId=new URL(popup.url()).searchParams.get('sign');
 expect(selectedId).toBe(listing.items[0].id);
 await expect(popup.locator('#selected-title')).toContainText(listing.items[0].qcvn_code);
 await expect.poll(()=>popup.evaluate(id=>markerCache.has(id),selectedId)).toBe(true);
 await expect.poll(()=>popup.evaluate(id=>nearbyMapSigns.some(sign=>sign.id===id),selectedId)).toBe(true);
 await expect(popup.locator('.sign-map-icon-marker')).toHaveCount(1);
 await popup.evaluate(()=>loadSigns());
 await expect(popup.locator('.sign-map-icon-marker')).toHaveCount(1);
 await expect(popup.locator('.sign-map-highlight')).toHaveCount(0);
 await popup.evaluate(()=>api.logout());
 await expect(popup.locator('.sign-map-icon-marker')).toHaveCount(0);
 await popup.close();
});
