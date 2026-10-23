/* One staff workspace. Only the selected section loads rows; decisions use one inspector. */
(() => {
 'use strict';
 const api=window.signSightAuth,$=id=>document.getElementById(id);
 const names=['contributions','reports','duplicates','signs','accounts','policy'];
 const states=Object.fromEntries(names.map(name=>[name,{offset:0,limit:name==='signs'||name==='accounts'?25:10,version:0}]));
 const panels={policy:'policy-panel'};
 const canManage=()=>['manager','admin'].includes(api.user?.role);
 const admin=()=>api.user?.role==='admin';
 const actions={confirm_existing:'Xác nhận còn',report_removed:'Đã tháo',report_damaged:'Hư hỏng',correct_class:'Sửa loại biển',correct_location:'Sửa vị trí',update_evidence:'Bổ sung ảnh'};
 const statuses={active:'Đang hiệu lực',expired:'Quá hạn xác nhận',pending_revalidation:'Chờ kiểm tra lại',removed:'Đã tháo',current:'Đã xác minh',unverified:'Chưa xác minh',needs_confirmation:'Cần xác nhận lại'};
 const codes=['P.127 (50)','P.127 (60)','P.127 (80)','P.125','P.122','P.102','W.245a','W.227','R.301a','R.301e'];
 let epoch=0,active='contributions',selected=null,detailVersion=0,summaryVersion=0,reviewBusy=false,initialized=false;
 const node=(tag,text)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=text;return element;};
 const message=text=>{$('message').textContent=text;};
 const date=value=>value?new Date(value.endsWith('Z')?value:value+'Z').toLocaleString('vi-VN'):'—';
 const coords=row=>Number(row.latitude).toFixed(5)+', '+Number(row.longitude).toFixed(5);
 const rows=new Map();
 function clearDetail(){
  detailVersion++;selected=null;$('review-detail').hidden=true;
  $('detail-title').textContent='';$('detail-meta').replaceChildren();$('detail-evidence').replaceChildren();$('review-comment').value='';
 }
 function updateDecisions(){
  const pending=selected&&selected.reviewable!==false;
  $('review-actions').hidden=!pending;$('review-note').hidden=!pending;
  $('review-accept').disabled=!pending||reviewBusy||selected?.mergeAllowed===false;
  $('review-reject').disabled=!pending||reviewBusy;
 }
 function inspect(type,row,title,paragraphs,reviewable=true){
  clearDetail();selected={type,id:row.id,row,reviewable};const version=detailVersion;
  $('review-detail').hidden=false;$('review-detail').dataset.observationId=type==='contributions'?row.id:'';
  $('detail-title').textContent=title;$('detail-meta').replaceChildren(...paragraphs.filter(Boolean).map(text=>node('p',text)));
  $('review-accept').textContent=type==='duplicates'?'Gộp vào biển giữ lại':'Chấp nhận';
  $('review-reject').textContent=type==='duplicates'?'Hai biển khác nhau':'Từ chối';
  for(const [id,element]of rows.get(type)||[])element.setAttribute('aria-selected',String(id===row.id));
  updateDecisions();return {version,auth:epoch};
 }
 const current=token=>token.auth===epoch&&token.version===detailVersion&&canManage();
 async function showImage(container,imageId,token,detection=null){
  const blob=await api.request('/images/'+encodeURIComponent(imageId)+'/content',{responseType:'blob'});
  if(!current(token))return;
  if(detection&&typeof createImageBitmap==='function'){
   const bitmap=await createImageBitmap(blob);
   try{
    if(!current(token))return;
    const canvas=node('canvas'),scale=Math.min(1,900/bitmap.width);
    canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);
    canvas.setAttribute('aria-label','Ảnh minh chứng và biển được chọn');
    const ctx=canvas.getContext('2d');ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);
    if(detection.bbox){
     const b=detection.bbox;ctx.strokeStyle='#ef4444';ctx.lineWidth=3;
     ctx.strokeRect(b.x1*scale,b.y1*scale,(b.x2-b.x1)*scale,(b.y2-b.y1)*scale);
    }
    container.append(canvas);
   }finally{bitmap.close();}
  }else{
   const image=node('img');image.alt='Ảnh minh chứng';
   const url=URL.createObjectURL(blob);image.onload=image.onerror=()=>URL.revokeObjectURL(url);image.src=url;container.append(image);
  }
 }
 async function contribution(row){
  const token=inspect('contributions',row,codes[row.proposed_class??row.detection.predicted_class]||row.detection.qcvn_code,
   [row.detection.name_vi,'Vị trí: '+coords(row),'Gửi lúc: '+date(row.created_at),
    'AI: '+Math.round(row.detection.confidence*100)+'% · '+row.detection.qcvn_code,row.correction_reason,row.review_comment],row.status==='pending');
  try{await showImage($('detail-evidence'),row.image_id,token,row.detection);}
  catch(error){if(current(token))$('detail-evidence').append(node('p','Chưa tải được ảnh: '+error.message));}
 }
 async function report(row){
  const token=inspect('reports',row,actions[row.action]||row.action,
   [row.comment,row.proposed_class!==null?'Loại đề xuất: '+codes[row.proposed_class]:null,row.latitude!==null?'Vị trí đề xuất: '+coords(row):null]);
  try{
   const detail=await api.request('/signs/'+encodeURIComponent(row.record_id));if(!current(token))return;
   $('detail-meta').append(node('p','Biển hiện tại: '+detail.sign.qcvn_code+' · '+coords(detail.sign)+' · '+(statuses[detail.sign.status]||detail.sign.status)));
   if(detail.sign.revision!==row.base_revision)$('detail-meta').append(node('p','Biển đã thay đổi sau khi gửi báo cáo. Kiểm tra lại trước khi duyệt.'));
   await showImage($('detail-evidence'),row.image_id,token);
   if(current(token))evidenceHistory(row.record_id,detail.evidence,token);
  }catch(error){if(current(token))$('detail-evidence').append(node('p',error.message));}
 }
 function evidenceHistory(id,evidence,token){
  const details=node('details'),contents=node('div');details.append(node('summary','Ảnh và lịch sử của biển'),contents);$('detail-evidence').append(details);
  let loaded=false;
  details.ontoggle=async()=>{
   if(!details.open||loaded||!current(token))return;loaded=true;
   try{
    for(const item of evidence.slice(0,3)){
     const match=item.content_url.match(/^\/api\/v1\/images\/([^/]+)\/content$/);if(match)await showImage(contents,match[1],token);
    }
    const history=await api.request('/signs/'+encodeURIComponent(id)+'/history?limit=25');if(!current(token))return;
    if(!history.items.length)contents.append(node('p','Chưa có thay đổi được duyệt.'));
    for(const entry of history.items)contents.append(node('p',entry.action+' · '+date(entry.created_at)+' · '+entry.before.status+' → '+entry.after.status));
   }catch(error){if(current(token)){contents.append(node('p',error.message));loaded=false;}}
  };
 }
 async function duplicate(row){
  const token=inspect('duplicates',row,row.new_record.qcvn_code+' ↔ '+row.existing_record.qcvn_code,
   ['Khoảng cách: '+Math.round(row.distance_meters)+' m','Biển mới: '+coords(row.new_record),
    'Biển giữ lại: '+coords(row.existing_record)]);
  selected.mergeAllowed=row.class_match;updateDecisions();
  for(const [label,sign]of [['Biển mới',row.new_record],['Biển giữ lại',row.existing_record]]){
   const group=node('div'),button=node('button','Xem ảnh '+label.toLowerCase()),images=node('div');button.className='secondary';group.append(button,images);$('detail-evidence').append(group);
   button.onclick=async()=>{
    if(!current(token))return;button.disabled=true;
    try{
     const evidence=await api.request('/signs/'+sign.id+'/evidence');if(!current(token))return;images.replaceChildren();
     if(!evidence.length)images.append(node('p','Chưa có ảnh minh chứng.'));
     for(const item of evidence.slice(0,3)){const match=item.content_url.match(/^\/api\/v1\/images\/([^/]+)\/content$/);if(match)await showImage(images,match[1],token);}
    }catch(error){if(current(token))message(error.message);}finally{button.disabled=false;}
   };
  }
 }
 async function signDetail(row){
  const token=inspect('signs',row,row.qcvn_code+' · '+row.name_vi,
   [statuses[row.status]||row.status,statuses[row.verification_status]||row.verification_status,'Vị trí: '+coords(row),'ID: '+row.id,'Hạn xác nhận: '+date(row.expires_at)],false);
  const link=node('a','Xem vị trí trên bản đồ');link.href='index.html?sign='+encodeURIComponent(row.id)+'&staff_view=1';link.target='_blank';link.rel='noopener';$('detail-meta').append(link);
  try{
   const detail=await api.request('/signs/'+row.id);if(!current(token))return;
   for(const item of detail.evidence.slice(0,1)){const match=item.content_url.match(/^\/api\/v1\/images\/([^/]+)\/content$/);if(match)await showImage($('detail-evidence'),match[1],token);}
   if(current(token))evidenceHistory(row.id,detail.evidence,token);
  }catch(error){if(current(token))$('detail-evidence').append(node('p',error.message));}
 }
 function pagination(name,page){
  $(name+'-prev').disabled=page.offset===0;$(name+'-next').disabled=page.offset+page.limit>=page.total;
  $(name+'-page').textContent=(page.total?page.offset+1:0)+'–'+Math.min(page.offset+page.items.length,page.total)+' / '+page.total;
 }
 function table(name,page,columns,select,emptyText,autoSelect=true){
  const tbody=$(name),entries=new Map();tbody.replaceChildren();rows.set(name,entries);pagination(name,page);
  if(!page.items.length){const tr=node('tr'),td=node('td',emptyText);td.setAttribute('colspan',String(name==='signs'||name==='accounts'?5:3));tr.append(td);tbody.append(tr);return;}
  for(const item of page.items){
   const tr=node('tr');tr.dataset[name==='contributions'?'observationId':name==='signs'?'signId':'recordId']=item.id;
   const values=columns(item);
   values.forEach((value,index)=>{
    const td=node('td');
    if(index===0&&select){const button=node('button',value);button.className='row-open';button.onclick=()=>select(item);td.append(button);}
    else td.textContent=value;
    tr.append(td);
   });
   entries.set(item.id,tr);tbody.append(tr);
  }
  if(autoSelect&&select)select(page.items[0]);
 }
 async function loadSummary(){
  if(!canManage())return;const auth=epoch,version=++summaryVersion;
  try{const counts=await api.request('/manager/summary');if(auth!==epoch||version!==summaryVersion||!canManage())return;
   for(const name of ['contributions','reports','duplicates','signs'])$('count-'+name).textContent=counts[name];
  }catch(error){if(auth===epoch)message(error.message);}
 }
 async function list(name,path,render){
  if(!canManage()||active!==name||(name==='accounts'&&!admin()))return;
  const state=states[name],auth=epoch,version=++state.version;
  const valid=()=>auth===epoch&&version===state.version&&active===name&&canManage();
  clearDetail();rows.delete(name);
  const loadingRow=node('tr'),loadingCell=node('td','Đang tải danh sách…');
  loadingCell.setAttribute('colspan',String(name==='signs'||name==='accounts'?5:3));loadingRow.append(loadingCell);$(name).replaceChildren(loadingRow);
  $(name).setAttribute('aria-busy','true');$(name+'-prev').disabled=$(name+'-next').disabled=true;
  try{
   const page=await api.request(path);if(!valid())return;
   if(state.offset>0&&page.total<=state.offset){state.offset=Math.max(0,Math.floor((page.total-1)/state.limit)*state.limit);return loaders[name]();}
   render(page);
  }catch(error){if(valid()){$(name).replaceChildren();message('Không tải được danh sách: '+error.message);}}
  finally{if(valid())$(name).setAttribute('aria-busy','false');}
 }
 const params=name=>new URLSearchParams({offset:states[name].offset,limit:states[name].limit});
 const loaders={
  contributions:()=>list('contributions','/manager/observations?'+params('contributions')+'&status='+($('contribution-status').value||'pending'),
   page=>table('contributions',page,r=>[codes[r.proposed_class??r.detection.predicted_class]||r.detection.qcvn_code,coords(r),date(r.created_at)],contribution,'Không có đóng góp trong trạng thái này.')),
  reports:()=>list('reports','/manager/reports?'+params('reports'),
   page=>table('reports',page,r=>[actions[r.action]||r.action,r.comment,date(r.created_at)],report,'Không có báo cáo chờ duyệt.')),
  duplicates:()=>list('duplicates','/manager/duplicates?'+params('duplicates'),
   page=>table('duplicates',page,r=>[r.new_record.qcvn_code+' ↔ '+r.existing_record.qcvn_code,Math.round(r.distance_meters)+' m',r.class_match?'Cùng loại':'Khác loại'],duplicate,'Không có cặp nghi trùng.')),
  signs:()=>{
   const query=params('signs');query.set('q',$('sign-query').value.trim());
   if($('sign-status').value)query.set('status',$('sign-status').value);
   if($('sign-verification').value)query.set('verification_status',$('sign-verification').value);
   return list('signs','/manager/signs?'+query,page=>{
    $('signs-count').textContent=page.total+' biển khớp bộ lọc · toàn bộ khu vực';
    table('signs',page,r=>[r.qcvn_code,r.name_vi,statuses[r.status]||r.status,coords(r),date(r.expires_at)],signDetail,'Không có biển khớp bộ lọc.',false);
   });
  },
  accounts:()=>list('accounts','/admin/users?'+params('accounts'),renderAccounts),
  policy:loadPolicy
 };
 async function selectTab(name){
  if(!canManage()||!names.includes(name)||(['accounts','policy'].includes(name)&&!admin()))return;
  active=name;clearDetail();message('');
  for(const section of names){
   $(panels[section]||'panel-'+section).hidden=section!==name;
   $('tab-'+section).setAttribute('aria-selected',String(section===name));
   $('tab-'+section).setAttribute('tabindex',section===name?'0':'-1');
  }
  return loaders[name]();
 }
 async function decide(decision){
  if(!canManage()||!selected||!selected.reviewable||reviewBusy||(decision==='accept'&&selected.mergeAllowed===false))return;
  const choice=selected,auth=epoch;reviewBusy=true;updateDecisions();
  const resource=choice.type==='contributions'?'observations':choice.type;
  const action=choice.type==='duplicates'?(decision==='accept'?'merge':'dismiss'):decision;
  const body=choice.type==='duplicates'?{action}:{action,comment:$('review-comment').value.trim()||null};
  try{
   await api.request('/manager/'+resource+'/'+encodeURIComponent(choice.id)+'/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
   if(auth!==epoch||!canManage())return;
   message(action==='accept'?'Đã duyệt. Biển đã được công bố.':'Đã xử lý mục đang chọn.');
   await loadSummary();if(active===choice.type)await loaders[active]();
  }catch(error){if(auth===epoch)message(error.status===409?'Mục này vừa được người khác xử lý. Bấm Làm mới để cập nhật.':error.message);}
  finally{if(auth===epoch){reviewBusy=false;updateDecisions();}}
 }
 function renderAccounts(page){
  table('accounts',page,r=>[r.username,r.email,r.role,r.is_active?'Hoạt động':'Đã khóa',''],null,'Chưa có tài khoản.',false);
  for(const account of page.items){
   const tr=rows.get('accounts').get(account.id);
   if(account.role==='admin')continue;
   const role=node('select');role.setAttribute('aria-label','Vai trò của '+account.username);
   for(const value of ['user','manager']){const option=node('option',value==='manager'?'Điều hành':'Người dùng');option.value=value;role.append(option);}
   role.value=account.role;tr.children[2].replaceChildren(role);
   const enabled=node('input');enabled.type='checkbox';enabled.checked=account.is_active;enabled.setAttribute('aria-label','Kích hoạt '+account.username);
   tr.children[3].replaceChildren(enabled);
   const save=node('button','Lưu');save.className='secondary';tr.children[4].append(save);
   save.onclick=async()=>{
    if(!admin())return;const auth=epoch;save.disabled=true;
    try{
     await api.request('/admin/users/'+account.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({role:role.value,is_active:enabled.checked})});
     if(auth===epoch&&admin()){message('Đã lưu tài khoản.');await loaders.accounts();}
    }catch(error){if(auth===epoch)message(error.message);}finally{save.disabled=false;}
   };
  }
 }
 async function loadPolicy(){
  if(!admin()||active!=='policy')return;const auth=epoch,version=++states.policy.version;
  try{
   const policy=await api.request('/policy'),history=await api.request('/admin/policy/history?limit=10');
   if(auth!==epoch||version!==states.policy.version||!admin())return;
   $('days').value=policy.confirmation_days;$('policy-history').replaceChildren(...history.items.map(row=>node('p',row.before_days+' → '+row.after_days+' ngày · '+date(row.created_at))));
  }catch(error){if(auth===epoch)message(error.message);}
 }
 function changed(){
  initialized=true;epoch++;clearDetail();reviewBusy=false;
  $('contribution-status').value='pending';
  $('sign-query').value=$('sign-status').value=$('sign-verification').value='';
  $('sign-limit').value='25';states.signs.limit=25;
  for(const name of names){states[name].offset=0;states[name].version++;if(name!=='policy')$(name).replaceChildren();}
  rows.clear();$('policy-history').replaceChildren();$('days').value='';$('signs-count').textContent='';
  for(const name of ['contributions','reports','duplicates','signs'])$('count-'+name).textContent='';
  $('login').hidden=!!api.user;$('logout').hidden=!api.user;$('workspace').hidden=!canManage();
  $('tab-accounts').hidden=$('tab-policy').hidden=!admin();$('policy-panel').hidden=true;
  $('profile').textContent=api.user?api.user.username+' · '+(admin()?'Quản trị viên':'Điều hành'):'Chưa đăng nhập';
  if(!canManage()){window.location?.replace('index.html?staff='+(api.user?'forbidden':'login'));return;}
  loadSummary();selectTab('contributions');
 }
 for(const name of names){
  $('tab-'+name).onclick=()=>selectTab(name);
  $('tab-'+name).onkeydown=event=>{
   const visible=names.filter(item=>!['accounts','policy'].includes(item)||admin()),index=visible.indexOf(name);
   let next;
   if(event.key==='ArrowRight')next=visible[(index+1)%visible.length];
   if(event.key==='ArrowLeft')next=visible[(index-1+visible.length)%visible.length];
   if(event.key==='Home')next=visible[0];
   if(event.key==='End')next=visible.at(-1);
   if(!next)return;event.preventDefault();$('tab-'+next).focus();selectTab(next);
  };
  if(name==='policy')continue;
  $('refresh-'+name).onclick=async()=>{if(!canManage())return;await loadSummary();return loaders[name]();};
  for(const [suffix,delta]of [['prev',-1],['next',1]])$(name+'-'+suffix).onclick=()=>{
   if(!canManage())return;states[name].offset=Math.max(0,states[name].offset+delta*states[name].limit);return loaders[name]();
  };
 }
 $('review-accept').onclick=()=>decide('accept');$('review-reject').onclick=()=>decide('reject');
 $('contribution-status').onchange=()=>{states.contributions.offset=0;return loaders.contributions();};
 $('sign-filters').onsubmit=event=>{event.preventDefault();states.signs.offset=0;return loaders.signs();};
 for(const id of ['sign-status','sign-verification','sign-limit'])$(id).onchange=()=>{
  states.signs.offset=0;states.signs.limit=[25,50,100].includes(Number($('sign-limit').value))?Number($('sign-limit').value):25;return loaders.signs();
 };
 $('sign-reset').onclick=()=>{$('sign-query').value=$('sign-status').value=$('sign-verification').value='';states.signs.offset=0;return loaders.signs();};
 $('policy-form').onsubmit=async event=>{
  event.preventDefault();if(!admin())return;const auth=epoch;event.submitter.disabled=true;
  try{await api.request('/admin/policy',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmation_days:Number($('days').value)})});if(auth===epoch&&admin()){message('Đã lưu cấu hình.');await loadPolicy();}}
  catch(error){if(auth===epoch)message(error.message);}finally{event.submitter.disabled=false;}
 };
 $('login').onsubmit=async event=>{event.preventDefault();await api.login($('username').value,$('password').value);$('password').value='';};
 $('logout').onclick=async()=>{try{await api.logout();}catch(error){message(error.message);}};
 window.addEventListener('signsight-auth-changed',changed);
 api.ready?.then(()=>{if(!initialized)changed();});
})();
