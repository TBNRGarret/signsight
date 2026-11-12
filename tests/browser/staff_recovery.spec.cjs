const {test,expect}=require('@playwright/test');
const {stubMaps}=require('./map_fixture.cjs');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const password='Browser-test-password-123';

async function contribution(browser){
 const context=await browser.newContext({baseURL:'http://127.0.0.1:8765',extraHTTPHeaders:{'X-SignSight-Web':'1'}});
 try{
  const username='recovery_'+crypto.randomUUID().slice(0,8),api=context.request;
  expect((await api.post('/api/v1/auth/register',{data:{username,email:username+'@example.com',password}})).status()).toBe(201);
  expect((await api.post('/api/v1/auth/login',{data:{username,password}})).ok()).toBeTruthy();
  const uploaded=await api.post('/api/v1/images',{multipart:{file:{name:'sign.png',mimeType:'image/png',buffer:fs.readFileSync(path.join(__dirname,'fixtures/sign.png'))}}});
  expect(uploaded.status()).toBe(201);const image=await uploaded.json();
  const run=await (await api.post('/api/v1/images/'+image.id+'/detect')).json();
  const result=await api.post('/api/v1/observations',{data:{image_id:image.id,items:[{detection_id:run.detections[0].id,latitude:10.78,longitude:106.70}]}});
  expect(result.status()).toBe(201);return (await result.json())[0];
 }finally{await context.close();}
}
async function login(page){
 await stubMaps(page);await page.goto('/web/index.html');
 await page.getByLabel('Tên đăng nhập',{exact:true}).fill('browser_manager');
 await page.getByLabel('Mật khẩu',{exact:true}).fill(password);
 await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
 await expect(page).toHaveURL(/management.html$/);
}

test('lost committed staff decision preserves note and retries the identical intent',async({page,browser},info)=>{
 const row=await contribution(browser);await login(page);
 await page.locator(`[data-observation-id="${row.id}"] .row-open`).click();
 await page.locator('#review-comment').fill('Evidence checked before response loss');
 const attempts=[];
 await page.route('**/api/v1/manager/observations/'+row.id+'/review',async route=>{
  const result=await route.fetch();expect(result.status()).toBe(200);
  attempts.push({key:route.request().headers()['idempotency-key'],body:route.request().postData()});
  if(attempts.length===1)return route.abort('failed');
  await route.fulfill({response:result});
 });
 await page.locator('#review-accept').click();
 await expect(page.locator('#review-retry')).toBeVisible();
 await expect(page.locator('#review-comment')).toHaveValue('Evidence checked before response loss');
 await expect(page.locator('#review-comment')).toHaveJSProperty('readOnly',true);
 await expect(page.locator('#review-accept')).toBeDisabled();await expect(page.locator('#review-reject')).toBeDisabled();
 // The committed item disappears from the pending queue; recovery remains reachable.
 await page.locator('#refresh-contributions').click();await expect(page.locator(`[data-observation-id="${row.id}"]`)).toHaveCount(0);
 await page.locator('#pending-review-list button').click();
 await expect(page.locator('#review-comment')).toHaveValue('Evidence checked before response loss');
 await expect(page.locator('#review-retry')).toBeVisible();
 if(process.env.SIGNSIGHT_SCREENSHOT_DIR){
  fs.mkdirSync(process.env.SIGNSIGHT_SCREENSHOT_DIR,{recursive:true});
  await page.locator('#review-detail').screenshot({path:path.join(process.env.SIGNSIGHT_SCREENSHOT_DIR,'staff-unknown-'+info.project.name+'.png')});
 }
 await page.locator('#review-retry').click();await expect(page.locator('#message')).toContainText('Đã duyệt');
 expect(attempts).toHaveLength(2);expect(attempts[0].key).toBeTruthy();expect(attempts[1]).toEqual(attempts[0]);
 const current=await (await page.request.get('/api/v1/observations/'+row.id)).json();
 expect(current.status).toBe('accepted');expect(current.review_comment).toBe('Evidence checked before response loss');
 const sign=await (await page.request.get('/api/v1/signs/'+current.sign_record_id)).json();expect(sign.evidence).toHaveLength(1);
});

test('read deadline releases loading state and staff can continue in another section',async({page})=>{
 await login(page);
 await page.evaluate(()=>{const send=window.signSightAuth.request;window.signSightAuth.request=(p,o={})=>send(p,{...o,timeoutMs:100});});
 const pattern=/\/api\/v1\/manager\/signs\?/;
 await page.route(pattern,()=>{});
 await page.locator('#tab-signs').click();
 await expect(page.locator('#signs')).toHaveAttribute('aria-busy','false');
 await expect(page.locator('#message')).toContainText('Kết nối quá lâu');
 await page.unroute(pattern);await page.locator('#refresh-signs').click();await expect(page.locator('#signs tr .row-open').first()).toBeVisible();
 await page.locator('#tab-contributions').click();await expect(page.locator('#panel-contributions')).toBeVisible();
});

test('another moderator decision is read back without erasing the scratch comment',async({page,browser})=>{
 const row=await contribution(browser);await login(page);
 await page.locator(`[data-observation-id="${row.id}"] .row-open`).click();await page.locator('#review-comment').fill('My unsent evidence note');
 const other=await browser.newContext({baseURL:'http://127.0.0.1:8765',extraHTTPHeaders:{'X-SignSight-Web':'1'}});
 try{
  await other.request.post('/api/v1/auth/login',{data:{username:'browser_admin',password}});
  expect((await other.request.post('/api/v1/manager/observations/'+row.id+'/review',{data:{action:'reject',comment:'Reviewed in another session'}})).status()).toBe(200);
 }finally{await other.close();}
 await page.locator('#review-accept').click();await expect(page.locator('#message')).toContainText('Đã từ chối');
 await expect(page.locator('#review-comment')).toHaveValue('My unsent evidence note');await expect(page.locator('#review-actions')).toBeHidden();
 await expect(page.locator('#detail-meta')).toContainText('Reviewed in another session');
});
