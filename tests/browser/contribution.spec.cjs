const {test,expect}=require('@playwright/test');
const path=require('node:path'),crypto=require('node:crypto');
const photo=path.join(__dirname,'fixtures/sign.png');
const password='Browser-test-password-123';
const {stubMaps}=require('./map_fixture.cjs');
async function setup(page){
  await stubMaps(page);
  const username='browser_'+crypto.randomUUID().slice(0,8);
  const created=await page.request.post('/api/v1/auth/register',{data:{username,email:username+'@example.com',password}});
  expect(created.status()).toBe(201);
  await page.goto('/web/observations.html');
  await page.getByLabel('Tên đăng nhập',{exact:true}).fill(username);
  await page.getByLabel('Mật khẩu',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
  await expect(page.locator('#workspace')).toBeVisible();
}
async function choose(page){
  await page.getByRole('button',{name:'Chụp hoặc chọn ảnh',exact:true}).click();
  await expect(page.getByRole('button',{name:'Chọn từ thư viện',exact:true})).toBeVisible();
  await page.locator('#file').setInputFiles(photo);
}
test('photo selection automatically uploads and detects without publishing',async({page})=>{
  await setup(page);
  let uploads=0,detects=0;
  page.on('request',r=>{
    if(r.method()==='POST'&&r.url().endsWith('/api/v1/images'))uploads++;
    if(r.method()==='POST'&&r.url().endsWith('/detect'))detects++;
  });
  await choose(page);
  await expect(page.locator('#capture-stage')).toContainText('Tìm thấy 1 biển');
  expect(uploads).toBe(1);expect(detects).toBe(1);
  expect((await (await page.request.get('/api/v1/me/observations')).json()).total).toBe(0);
  await expect(page.getByRole('button',{name:'Upload ảnh',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Phân loại ảnh cắt bằng CNN'})).toHaveCount(0);
  const size=await page.evaluate(()=>({width:document.documentElement.scrollWidth,viewport:innerWidth}));
  expect(size.width).toBeLessThanOrEqual(size.viewport);
});
test('failed detection retries the saved photo without another upload',async({page})=>{
  await setup(page);
  let uploads=0,attempts=0;
  page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/v1/images'))uploads++;});
  await page.route('**/api/v1/images/*/detect',async route=>{
    if(++attempts===1)return route.fulfill({status:503,json:{detail:'fixture unavailable'}});
    return route.continue();
  });
  await choose(page);
  await expect(page.getByRole('button',{name:'Thử nhận diện lại',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Thử nhận diện lại',exact:true}).click();
  await expect(page.locator('#capture-stage')).toContainText('Tìm thấy 1 biển');
  expect(uploads).toBe(1);expect(attempts).toBe(2);
});

test('a pin is explicitly confirmed before submitting the observation',async({page})=>{
  await setup(page);await choose(page);
  await expect(page.locator('#capture-stage')).toContainText('Tìm thấy 1 biển');
  await expect(page.locator('#submit')).toBeDisabled();
  await expect(page.locator('#location-panel')).toBeVisible();
  await page.locator('#location-map').click({position:{x:150,y:110}});
  await expect(page.locator('#location-confirm')).toBeEnabled();
  await page.locator('#location-confirm').click();
  await expect(page.locator('#submit')).toBeEnabled();
  await page.locator('#submit').click();
  await expect(page.locator('#status')).toContainText('Đã gửi đóng góp');
  const history=await (await page.request.get('/api/v1/me/observations')).json();
  expect(history.total).toBe(1);expect(history.items[0].status).toBe('pending');
  expect(history.items[0].location_source).toBe('user_confirmed');
});

test('approved contribution shows a private thumbnail then opens its exact map record',async({page,browser},testInfo)=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await setup(page);await choose(page);
  await expect(page.locator('#capture-stage')).toContainText('Tìm thấy 1 biển');
  await page.locator('#location-map').click({position:{x:150,y:110}});
  await page.locator('#location-confirm').click();await page.locator('#submit').click();
  await expect(page.locator('#history .history-card')).toHaveCount(1);
  await expect(page.locator('#history canvas')).toBeVisible();
  await expect(page.locator('#history').getByRole('link',{name:'Xem trên bản đồ'})).toHaveCount(0);
  const submitted=(await (await page.request.get('/api/v1/me/observations')).json()).items[0];
  const staff=await browser.newContext({baseURL:'http://127.0.0.1:8765'});
  try{
    const manager=await staff.newPage();
    await manager.goto('/web/observations.html');
    await manager.getByLabel('Tên đăng nhập',{exact:true}).fill('browser_manager');
    await manager.getByLabel('Mật khẩu',{exact:true}).fill(password);
    await manager.getByRole('button',{name:'Đăng nhập',exact:true}).click();
    const target=manager.locator('#queue article[data-observation-id="'+submitted.id+'"]');
    await expect(target).toHaveCount(1);
    await target.getByRole('textbox',{name:'Ghi chú duyệt'}).fill('Đã kiểm tra vị trí trong test.');
    await target.getByRole('button',{name:'Chấp nhận',exact:true}).click();
    await expect(target).toHaveCount(0);
    await page.getByRole('button',{name:'Tải lịch sử',exact:true}).click();
    await expect(page.locator('#history .status-badge')).toHaveText('Đã duyệt');
    const accepted=(await (await page.request.get('/api/v1/me/observations')).json()).items[0];
    const link=page.locator('#history').getByRole('link',{name:'Xem trên bản đồ'});
    await expect(link).toHaveAttribute('href','index.html?sign='+accepted.sign_record_id);
    if(process.env.SIGNSIGHT_SCREENSHOT_DIR){
      require('node:fs').mkdirSync(process.env.SIGNSIGHT_SCREENSHOT_DIR,{recursive:true});
      await page.screenshot({path:path.join(process.env.SIGNSIGHT_SCREENSHOT_DIR,'history-'+testInfo.project.name+'.png'),fullPage:true});
    }
    await link.click();
    await expect(page).toHaveURL(new RegExp('sign='+accepted.sign_record_id));
    await expect(page.locator('#selected-title')).toContainText('P.102');
    await expect(page.locator('#sign-link-status')).toHaveText('Đã mở biển từ đóng góp.');
    await expect(page.locator('.maplibregl-canvas')).toBeVisible();
    await expect(page.locator('#map-notice')).toBeHidden();
    await page.locator('.sign-map-marker:not(.sign-map-highlight)').first().click();
    await expect(page.locator('.maplibregl-popup-content')).toContainText('P.102');
    expect(errors).toEqual([]);
    if(process.env.SIGNSIGHT_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SIGNSIGHT_SCREENSHOT_DIR,'map-'+testInfo.project.name+'.png'),fullPage:true});
    await page.locator('#logout-button').click();
    await expect(page.locator('.maplibregl-popup')).toHaveCount(0);
    await expect(page.locator('.sign-map-marker')).toHaveCount(0);
  }finally{await staff.close();}
});
