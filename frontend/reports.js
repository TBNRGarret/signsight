/* User reports: every change carries a server-stored photo and waits for manager review. */
(function(root){
  'use strict';
  const ACTIONS={confirm_existing:'Xác nhận biển vẫn còn',report_removed:'Biển đã bị tháo',report_damaged:'Biển hư hỏng',
    correct_class:'Sai loại biển',correct_location:'Sai vị trí',update_evidence:'Bổ sung ảnh mới'};
  const CODES=['P.127 (50)','P.127 (60)','P.127 (80)','P.125','P.122','P.102','W.245a','W.227','R.301a','R.301e'];
  const REPORT_STATUS={pending:'chờ duyệt',accepted:'đã chấp nhận',rejected:'bị từ chối'};
  const VERIFICATION={unverified:'chưa xác minh',current:'đã xác minh',needs_confirmation:'cần xác nhận lại'};
  const SIGN_STATUS={active:'đang hiệu lực',expired:'quá hạn xác nhận',pending_revalidation:'chờ kiểm tra lại',removed:'đã tháo'};

  function buildReportPayload({action,comment,imageId,proposedClass,location}){
    if(!Object.hasOwn(ACTIONS,action))throw new Error('Chọn loại báo cáo.');
    const text=(comment||'').trim();
    if(text.length<3)throw new Error('Mô tả điều bạn thấy (ít nhất 3 ký tự).');
    if(!imageId)throw new Error('Cần ảnh chụp biển để làm bằng chứng.');
    const payload={action,image_id:imageId,comment:text};
    if(action==='correct_class'){
      if(!Number.isInteger(proposedClass)||proposedClass<0||proposedClass>9)throw new Error('Chọn loại biển đúng.');
      payload.proposed_class=proposedClass;
    }
    if(action==='correct_location'){
      const [latitude,longitude]=location||[];
      if(!Number.isFinite(latitude)||!Number.isFinite(longitude)||Math.abs(latitude)>90||Math.abs(longitude)>180)
        throw new Error('Chạm bản đồ để chọn vị trí đúng của biển.');
      Object.assign(payload,{latitude,longitude});
    }
    return payload;
  }

  async function submitReport(api,signId,file,fields){
    if(!file)throw new Error('Chụp hoặc chọn ảnh biển trước khi gửi.');
    buildReportPayload({...fields,imageId:'pending-upload'});
    const form=new FormData();form.append('file',file);
    const image=await api.request('/images',{method:'POST',body:form});
    return api.request(`/signs/${encodeURIComponent(signId)}/reports`,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(buildReportPayload({...fields,imageId:image.id}))});
  }

  function mount({api,map,document,getPinned}){
    const $=id=>document.getElementById(id);
    const staff=()=>['admin','manager'].includes(api.user?.role);
    const node=(tag,text)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=text;return element;};
    let epoch=0,selected=null,selectGeneration=0;
    const status=text=>{$('report-status').textContent=text;};

    for(const [value,label] of Object.entries(ACTIONS)){const option=node('option',label);option.value=value;$('report-action').append(option);}
    CODES.forEach((code,id)=>{const option=node('option',code);option.value=id;$('report-class').append(option);});

    function refreshPin(){
      const [latitude,longitude]=getPinned();
      $('report-location').textContent=`Vị trí đúng: ${latitude.toFixed(5)}, ${longitude.toFixed(5)}. Chạm bản đồ để đổi.`;
    }
    function showActionFields(){
      $('report-class-group').hidden=$('report-action').value!=='correct_class';
      $('report-location-group').hidden=$('report-action').value!=='correct_location';
      refreshPin();
    }
    $('report-action').onchange=showActionFields;

    async function select(signId){
      const version=epoch,generation=++selectGeneration;
      $('selected-sign').hidden=false;$('selected-title').textContent='Đang tải biển…';$('selected-meta').replaceChildren();
      $('selected-evidence').replaceChildren();$('report-form').hidden=true;status('');
      $('selected-sign').scrollIntoView({behavior:'smooth',block:'start'});
      try{
        const detail=await api.request(`/signs/${encodeURIComponent(signId)}`);
        if(version!==epoch||generation!==selectGeneration)return;
        selected=detail;const sign=detail.sign;
        $('selected-title').textContent=`${sign.qcvn_code} · ${sign.name_vi}`;
        $('selected-meta').append(
          node('p',`Trạng thái: ${SIGN_STATUS[sign.status]||sign.status} · Dữ liệu: ${VERIFICATION[sign.verification_status]||sign.verification_status}`),
          node('p',`Cần xác nhận lại trước: ${new Date(sign.expires_at).toLocaleDateString('vi-VN')}`),
          node('p',sign.is_uncertain?'Nhãn AI có độ tin cậy thấp hoặc đã được sửa; cần người kiểm tra.':`AI: ${(sign.confidence*100).toFixed(1)}%`),
          node('p',`${detail.evidence.length} ảnh bằng chứng · ${sign.latitude.toFixed(5)}, ${sign.longitude.toFixed(5)}`));
        $('selected-evidence-button').hidden=!detail.evidence.length;
        $('report-form').hidden=staff()||Boolean(sign.merged_into_id)||sign.status==='removed';
        if(sign.merged_into_id)$('selected-meta').append(node('p','Biển này đã được gộp vào bản ghi khác; hãy báo cáo trên biển hiện tại.'));
        showActionFields();map.flyTo([sign.latitude,sign.longitude],Math.max(map.getZoom(),17));return detail;
      }catch(error){if(version===epoch&&generation===selectGeneration){$('selected-title').textContent=error.message;selected=null;}}
    }

    $('selected-evidence-button').onclick=async()=>{
      if(!selected)return;const version=epoch,current=selected,button=$('selected-evidence-button');
      button.disabled=true;$('selected-evidence').replaceChildren();
      try{
        for(const row of current.evidence.slice(0,3)){
          const match=row.content_url.match(/^\/api\/v1\/images\/([^/]+)\/content$/);if(!match)continue;
          const blob=await api.request(`/images/${match[1]}/content`,{responseType:'blob'});
          if(version!==epoch||selected!==current)return;
          const image=node('img');image.alt='Ảnh bằng chứng của biển';image.className='evidence-image';
          const url=URL.createObjectURL(blob);image.onload=image.onerror=()=>URL.revokeObjectURL(url);image.src=url;$('selected-evidence').append(image);
        }
      }catch(error){if(version===epoch)$('selected-evidence').append(node('p',error.message));}
      finally{button.disabled=false;}
    };

    $('report-form').onsubmit=async event=>{
      event.preventDefault();if(!selected)return;
      const version=epoch,button=$('report-submit');button.disabled=true;status('Đang gửi ảnh và báo cáo…');
      try{
        await submitReport(api,selected.sign.id,$('report-file').files[0],{action:$('report-action').value,comment:$('report-comment').value,
          proposedClass:Number($('report-class').value),location:getPinned()});
        if(version!==epoch)return;
        $('report-form').reset();showActionFields();status('Đã gửi; manager sẽ duyệt trước khi dữ liệu thay đổi.');await loadLists();
      }catch(error){if(version===epoch)status(error.message);}
      finally{button.disabled=false;}
    };

    function signButton(text,signId){const button=node('button',text);button.type='button';button.className='btn btn-secondary list-button';button.onclick=()=>select(signId);return button;}
    async function loadLists(){
      if(!api.user||staff())return;const version=epoch;
      try{
        const [confirmations,reports]=await Promise.all([api.request('/me/confirmation-requests?limit=25'),api.request('/me/reports?limit=25')]);
        if(version!==epoch)return;
        $('confirmation-list').replaceChildren(...confirmations.items.map(sign=>signButton(`${sign.qcvn_code} · ${sign.name_vi}`,sign.id)));
        if(!confirmations.items.length)$('confirmation-list').append(node('p','Không có biển cần xác nhận.'));
        $('confirmation-count').textContent=`${confirmations.total} biển`;
        $('my-reports').replaceChildren(...reports.items.map(report=>signButton(
          `${ACTIONS[report.action]||report.action} · ${REPORT_STATUS[report.status]||report.status}${report.review_comment?' · '+report.review_comment:''}`,report.record_id)));
        if(!reports.items.length)$('my-reports').append(node('p','Chưa gửi báo cáo nào.'));
      }catch(error){if(version===epoch)status(error.message);}
    }
    $('lists-refresh').onclick=loadLists;

    root.addEventListener('signsight-auth-changed',()=>{
      epoch++;selected=null;$('selected-sign').hidden=true;$('report-form').reset();
      $('confirmation-list').replaceChildren();$('my-reports').replaceChildren();$('confirmation-count').textContent='';
      $('user-lists').hidden=!api.user||staff();if(api.user&&!staff())loadLists();
    });
    $('user-lists').hidden=!api.user||staff();
    return {select,refreshPin,loadLists};
  }

  const exported={ACTIONS,buildReportPayload,submitReport,mount};
  if(typeof module!=='undefined'&&module.exports)module.exports=exported;
  else root.signSightReports=exported;
})(typeof window==='undefined'?globalThis:window);
