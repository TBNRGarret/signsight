const {test,expect}=require('@playwright/test');
const {stubMaps}=require('./map_fixture.cjs');
const fs=require('node:fs'),path=require('node:path');

test('theme icons stay aligned and persist across pages while system follows the device',async({page,context},testInfo)=>{
 await stubMaps(page);await page.emulateMedia({colorScheme:'dark'});
 const auth=await page.request.post('/api/v1/auth/login',{headers:{'X-SignSight-Web':'1'},data:{username:'browser_admin',password:'Browser-test-password-123'}});
 expect(auth.ok()).toBe(true);await page.goto('/web/management.html');
 await expect(page.locator('#workspace')).toBeVisible();
 const group=page.getByRole('group',{name:'Giao diện',exact:true});
 const system=group.getByRole('button',{name:'Theo thiết bị',exact:true});
 const light=group.getByRole('button',{name:'Sáng',exact:true});
 const dark=group.getByRole('button',{name:'Tối',exact:true});
 await expect(system).toHaveAttribute('aria-pressed','true');
 await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
 for(const button of [system,light,dark]){
  await expect(button).toBeVisible();const box=await button.boundingBox();
  expect(box.width).toBeGreaterThanOrEqual(44);expect(box.height).toBeGreaterThanOrEqual(44);
 }
 const boxes=await Promise.all([system,light,dark].map(b=>b.boundingBox()));
 expect(Math.max(...boxes.map(b=>b.y))-Math.min(...boxes.map(b=>b.y))).toBeLessThan(1);
 const logout=await page.locator('#logout').boundingBox();
 expect(Math.abs((boxes[0].y+boxes[0].height/2)-(logout.y+logout.height/2))).toBeLessThan(1);
 await light.focus();await page.keyboard.press('Enter');
 await expect(light).toHaveAttribute('aria-pressed','true');await expect(system).toHaveAttribute('aria-pressed','false');
 await expect(page.locator('html')).toHaveAttribute('data-theme','light');
 await page.emulateMedia({colorScheme:'dark'});await expect(page.locator('html')).toHaveAttribute('data-theme','light');
 if(process.env.SIGNSIGHT_SCREENSHOT_DIR){
  fs.mkdirSync(process.env.SIGNSIGHT_SCREENSHOT_DIR,{recursive:true});
  await page.screenshot({path:path.join(process.env.SIGNSIGHT_SCREENSHOT_DIR,'theme-light-'+testInfo.project.name+'.png'),fullPage:true});
 }
 await dark.click();await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
 if(process.env.SIGNSIGHT_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SIGNSIGHT_SCREENSHOT_DIR,'theme-dark-'+testInfo.project.name+'.png'),fullPage:true});
 // A second same-origin tab receives storage events. Log out to reach the user page.
 await page.locator('#logout').click();await expect(page).toHaveURL(/index.html\?staff=login/);
 await page.goto('/web/observations.html');
 await expect(page.getByRole('button',{name:'Tối',exact:true})).toHaveAttribute('aria-pressed','true');
 const other=await context.newPage();await stubMaps(other);await other.goto('/web/index.html');
 await other.getByRole('button',{name:'Theo thiết bị',exact:true}).click();
 await expect(page.getByRole('button',{name:'Theo thiết bị',exact:true})).toHaveAttribute('aria-pressed','true');
 await page.emulateMedia({colorScheme:'light'});await expect(page.locator('html')).toHaveAttribute('data-theme','light');
 const width=await page.evaluate(()=>({actual:document.documentElement.scrollWidth,viewport:innerWidth}));
 expect(width.actual).toBeLessThanOrEqual(width.viewport);
 await other.close();
});
