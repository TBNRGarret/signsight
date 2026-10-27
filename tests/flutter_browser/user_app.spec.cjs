const {test,expect}=require('@playwright/test');
const path=require('node:path'),crypto=require('node:crypto');
const {stubMaps}=require('../browser/map_fixture.cjs');
const photo=path.join(__dirname,'../browser/fixtures/sign.png');
const password='Browser-test-password-123';
async function open(page){
  await stubMaps(page);
  await page.goto('/app/');
  await page.locator('flt-semantics-placeholder').waitFor({state:'attached'});
  await page.locator('flt-semantics-placeholder').evaluate(e=>e.click());
}
async function registerAndLogin(page){
 const username='flutter_'+crypto.randomUUID().slice(0,8);
 expect((await page.request.post('/api/v1/auth/register',{data:{username,email:username+'@example.com',password}})).status()).toBe(201);
 await open(page);
 await page.getByRole('button',{name:'Tài khoản',exact:true}).click();
 const usernameField=page.getByRole('textbox',{name:'Tên đăng nhập',exact:true});
 const passwordField=page.getByRole('textbox',{name:'Mật khẩu',exact:true});
 await usernameField.fill(username);await expect(usernameField).toHaveValue(username);
 await passwordField.fill(password);await expect(passwordField).toHaveValue(password);
 const loginResponse=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/api/v1/auth/login'));
 await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
 expect((await loginResponse).status()).toBe(200);
 await expect(page.getByRole('button',{name:'Danh sách biển',exact:true})).toBeVisible();
}

test('compact guest shell requires login for contribution',async({page})=>{
 await open(page);
 await expect(page.getByRole('region',{name:'Map',exact:true})).toBeVisible();
 await expect(page.getByRole('tab')).toHaveCount(3);
 await page.getByRole('tab',{name:'Đóng góp',exact:true}).click();
 await expect(page.getByText('Đăng nhập để đóng góp',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Gửi đóng góp',exact:true})).toHaveCount(0);
});

test('upload, verify label and pin, approval and exact map record',async({page,browser},testInfo)=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await registerAndLogin(page);
 let uploads=0;page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/v1/images'))uploads++});
 await page.getByRole('tab',{name:'Đóng góp',exact:true}).click();
 const chooser=page.waitForEvent('filechooser');
 await page.getByRole('button',{name:'Chọn từ thư viện',exact:true}).click();
 await (await chooser).setFiles(photo);
 const submit=page.getByRole('button',{name:'Gửi đóng góp',exact:true});
 await expect(submit).toBeVisible();await expect(submit).toBeDisabled();
 await page.getByRole('checkbox',{name:'Đúng biển tôi muốn đóng góp',exact:true}).click();
 await expect(submit).toBeDisabled();
 await page.getByRole('button',{name:'Chọn',exact:true}).click();
 const confirm=page.getByRole('button',{name:'Xác nhận vị trí',exact:true});
 await expect(confirm).toBeDisabled();
 await page.getByRole('region',{name:'Map',exact:true}).click({position:{x:150,y:160}});
 await expect(confirm).toBeEnabled();await confirm.click();
 await expect(submit).toBeEnabled();await submit.click();
 await expect(page.getByText('Đã gửi đóng góp, đang chờ duyệt.',{exact:true})).toBeVisible();
 expect(uploads).toBe(1);
 await page.getByRole('tab',{name:'Của tôi',exact:true}).click();
 await expect(page.getByRole('button',{name:'P.102 Cấm đi ngược chiều Chờ duyệt',exact:true})).toBeVisible();
 let history=await (await page.request.get('/api/v1/me/observations')).json();
 expect(history.total).toBe(1);expect(history.items[0].location_source).toBe('user_confirmed');
 const staff=await browser.newContext({baseURL:'http://127.0.0.1:8765',extraHTTPHeaders:{'X-SignSight-Web':'1'}});
 try{
  expect((await staff.request.post('/api/v1/auth/login',{data:{username:'browser_manager',password}})).ok()).toBeTruthy();
  expect((await staff.request.post('/api/v1/manager/observations/'+history.items[0].id+'/review',{data:{action:'accept',comment:'Fixture review'}})).ok()).toBeTruthy();
 }finally{await staff.close()}
 await page.getByRole('button',{name:'Tải lại đóng góp',exact:true}).click();
 await expect(page.getByRole('button',{name:'P.102 Cấm đi ngược chiều Đã duyệt',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'P.102 Cấm đi ngược chiều Đã duyệt',exact:true}).click();
 await page.getByRole('button',{name:'Xem trên bản đồ',exact:true}).click();
 await expect(page.getByText('P.102',{exact:true})).toBeVisible();
 await expect(page.getByText('Cấm đi ngược chiều',{exact:true})).toBeVisible();
 history=await (await page.request.get('/api/v1/me/observations')).json();
 expect(history.items[0].sign_record_id).toBeTruthy();
 const signId=history.items[0].sign_record_id;
 const before=(await (await page.request.get('/api/v1/signs/'+signId)).json()).sign;
 await page.getByRole('button',{name:'Báo cáo / xác nhận',exact:true}).click();
 const reportSubmit=page.getByRole('button',{name:'Gửi báo cáo',exact:true});
 await expect(reportSubmit).toBeDisabled();
 await page.getByRole('textbox',{name:'Mô tả quan sát'}).click();
 await page.getByRole('textbox',{name:'Mô tả quan sát'}).pressSequentially('Biển vẫn còn tại vị trí này');
 const proofChooser=page.waitForEvent('filechooser');
 await page.getByRole('button',{name:'Chọn ảnh',exact:true}).click();
 await (await proofChooser).setFiles(photo);
 await expect(page.getByText('Đã tải ảnh bằng chứng')).toBeVisible();
 await expect(reportSubmit).toBeEnabled();await reportSubmit.click();
 await expect(page.getByText('Đã gửi báo cáo, đang chờ duyệt.',{exact:true})).toBeVisible();
 const reports=(await (await page.request.get('/api/v1/me/reports')).json()).items;
 expect(reports).toHaveLength(1);expect(reports[0].status).toBe('pending');
 const pendingSign=(await (await page.request.get('/api/v1/signs/'+signId)).json()).sign;
 expect(pendingSign.revision).toBe(before.revision);
 expect(pendingSign.expires_at).toBe(before.expires_at);
 const reportStaff=await browser.newContext({baseURL:'http://127.0.0.1:8765',extraHTTPHeaders:{'X-SignSight-Web':'1'}});
 try{
  expect((await reportStaff.request.post('/api/v1/auth/login',{data:{username:'browser_manager',password}})).ok()).toBeTruthy();
  expect((await reportStaff.request.post('/api/v1/manager/reports/'+reports[0].id+'/review',{data:{action:'accept'}})).ok()).toBeTruthy();
  // A damaged sign enters the same revalidation queue used by TTL expiry.
  const damage=await page.request.post('/api/v1/signs/'+signId+'/reports',{headers:{'X-SignSight-Web':'1'},data:{action:'report_damaged',image_id:reports[0].image_id,comment:'Synthetic damaged sign evidence'}});
  expect(damage.status()).toBe(201);
  expect((await reportStaff.request.post('/api/v1/manager/reports/'+(await damage.json()).id+'/review',{data:{action:'accept'}})).ok()).toBeTruthy();
 }finally{await reportStaff.close()}
 await page.getByRole('tab',{name:'Của tôi',exact:true}).click();
 await page.getByRole('button',{name:'Báo cáo & xác nhận lại',exact:true}).click();
 await expect(page.getByText('Biển vẫn còn tại vị trí này')).toBeVisible();
 await page.getByRole('button',{name:'Cần xác nhận',exact:true}).click();
 const confirmations=(await (await page.request.get('/api/v1/me/confirmation-requests?limit=20')).json()).items;
 const targetIndex=confirmations.findIndex(s=>s.id===signId);expect(targetIndex).toBeGreaterThanOrEqual(0);
 const confirmationRows=page.getByRole('button',{name:'P.102 Cấm đi ngược chiều',exact:true});
 await expect(confirmationRows.nth(targetIndex)).toBeVisible();
 await confirmationRows.nth(targetIndex).click();
 await expect(page.getByText('Cần xác nhận lại',{exact:true})).toBeVisible();
 expect(errors).toEqual([]);
 if(process.env.SIGNSIGHT_SCREENSHOT_DIR) {
  const fs=require('node:fs');fs.mkdirSync(process.env.SIGNSIGHT_SCREENSHOT_DIR,{recursive:true});
  await page.screenshot({path:path.join(process.env.SIGNSIGHT_SCREENSHOT_DIR,'flutter-approved-'+testInfo.project.name+'.png')});
 }
 await page.getByRole('button',{name:'Tài khoản',exact:true}).click();
 await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();
 await expect(page.getByText('P.102',{exact:true})).toHaveCount(0);
 await page.reload();await page.locator('flt-semantics-placeholder').waitFor({state:'attached'});
 await page.locator('flt-semantics-placeholder').evaluate(e=>e.click());
 await page.getByRole('tab',{name:'Của tôi',exact:true}).click();
 await expect(page.getByText('Theo dõi đóng góp của bạn',{exact:true})).toBeVisible();
});
