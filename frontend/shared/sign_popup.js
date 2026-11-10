(function(root){
 'use strict';
 const icons=typeof module!=='undefined'&&module.exports?require('./sign_icons.js'):root.signSightSignIcons;
 function create({api,document,sign,onDetails,urlApi=root.URL}){
  const node=(tag,className,text)=>{const element=document.createElement(tag);element.className=className;if(text!==undefined)element.textContent=text;return element;};
  const box=node('div','popup-box sign-photo-popup'),heading=node('div','sign-popup-heading');
  const icon=node('img','sign-popup-icon');icon.src=icons.resolve(sign.qcvn_code,sign.name_vi).url;icon.alt='';
  const titles=node('div','sign-popup-titles');titles.append(node('h3','',sign.name_vi),node('p','',sign.qcvn_code));heading.append(icon,titles);
  const labels={active:'đang hiệu lực',expired:'quá hạn xác nhận',pending_revalidation:'chờ kiểm tra lại',removed:'đã tháo'};
  const confirmation=sign.verification_status==='needs_confirmation'||sign.status==='expired';
  const state=node('p','',`${labels[sign.status]||sign.status||'Biển đã được ghi nhận'}${confirmation?' · cần xác nhận lại':''}${sign.is_uncertain?' · nhãn cần kiểm tra':''}`);
  const photo=node('img','sign-popup-photo');photo.alt='Ảnh đóng góp đã duyệt của '+sign.name_vi;photo.hidden=true;
  const status=node('p','sign-popup-photo-status','Đang tải ảnh đã duyệt…');status.setAttribute('aria-live','polite');
  const retry=node('button','sign-popup-photo-retry','Thử tải ảnh lại');retry.type='button';retry.hidden=true;
  const details=node('button','btn-reval','Chi tiết & báo cáo');details.type='button';details.onclick=onDetails;
  const content=node('div','sign-popup-content');content.append(heading,state,photo,status,retry);
  box.append(content,details);
  let disposed=false,version=0,url=null;
  const owner=api.user;
  const active=epoch=>!disposed&&epoch===version&&api.user===owner;
  function release(){if(url!==null){urlApi.revokeObjectURL(url);url=null;}}
  async function load(){
   const epoch=++version;release();photo.hidden=true;retry.hidden=true;status.hidden=false;status.textContent='Đang tải ảnh đã duyệt…';
   try{
    const detail=await api.request('/signs/'+encodeURIComponent(sign.id));if(!active(epoch))return;
    const evidence=detail.evidence?.[0];
    if(!evidence){status.textContent='Chưa có ảnh đã duyệt cho bản ghi này.';return;}
    const match=String(evidence.content_url).match(/^\/api\/v1\/images\/([A-Za-z0-9_-]+)\/content$/);
    if(!match)throw Error('Invalid evidence URL');
    const blob=await api.request('/images/'+match[1]+'/content',{responseType:'blob'});if(!active(epoch))return;
    url=urlApi.createObjectURL(blob);photo.onload=()=>{if(active(epoch))status.hidden=true;};
    photo.onerror=()=>{if(active(epoch)){release();photo.hidden=true;status.hidden=false;status.textContent='Không đọc được ảnh đã duyệt.';retry.hidden=false;}};
    photo.src=url;photo.hidden=false;
   }catch(_){if(active(epoch)){status.textContent='Chưa tải được ảnh đã duyệt.';retry.hidden=false;}}
  }
  retry.onclick=load;void load();
  return {element:box,dispose(){disposed=true;version++;release();photo.onload=photo.onerror=null;photo.hidden=true;}};
 }
 const exported={create};if(typeof module!=='undefined'&&module.exports)module.exports=exported;else root.signSightSignPopup=exported;
})(typeof window==='undefined'?globalThis:window);
