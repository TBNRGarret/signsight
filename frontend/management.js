(() => {
  'use strict';
  const api=window.signSightAuth,$=id=>document.getElementById(id);
  let epoch=0,reportOffset=0,duplicateOffset=0,reportVersion=0,duplicateVersion=0;
  const canManage=()=>['manager','admin'].includes(api.user?.role);
  const message=text=>{$('message').textContent=text;};
  const node=(tag,text)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=text;return element;};
  const actions={confirm_existing:'Xác nhận còn',report_removed:'Đã tháo',report_damaged:'Hư hỏng',correct_class:'Sửa loại biển',correct_location:'Sửa vị trí',update_evidence:'Ảnh minh chứng mới'};
  async function act(button,operation){button.disabled=true;try{await operation();}catch(error){message(error.message);}finally{button.disabled=false;}}
  let authInitialized=false;
  function authChanged(){
    authInitialized=true;
    epoch++;reportOffset=duplicateOffset=0;$('reports').replaceChildren();$('duplicates').replaceChildren();$('policy-history').replaceChildren();
    $('login').hidden=!!api.user;$('logout').hidden=!api.user;$('workspace').hidden=!canManage();$('policy-panel').hidden=api.user?.role!=='admin';
    $('profile').textContent=api.user?`${api.user.username} · ${api.user.role}${canManage()?'':' · Cần tài khoản manager/admin để quản lý.'}`:'Chưa đăng nhập';
    if (!canManage()) window.location?.replace('index.html?staff='+(api.user?'forbidden':'login'));
    if(canManage()){loadReports();loadDuplicates();if(api.user.role==='admin')loadPolicy();}
  }
  window.addEventListener('signsight-auth-changed',authChanged);
  api.ready?.then(()=>{if(!authInitialized)authChanged();});
  $('login').onsubmit=event=>{event.preventDefault();act(event.submitter,async()=>{await api.login($('username').value,$('password').value);$('password').value='';message('Đã đăng nhập.');});};
  $('logout').onclick=()=>act($('logout'),async()=>{await api.logout();message('Đã đăng xuất.');});
  function pagination(prefix,page){$(prefix+'-prev').disabled=page.offset===0;$(prefix+'-next').disabled=page.offset+page.limit>=page.total;$(prefix+'-page').textContent=`${page.total?page.offset+1:0}–${Math.min(page.offset+page.limit,page.total)} / ${page.total}`;}
  async function showImage(card,imageId,version){
    const blob=await api.request(`/images/${imageId}/content`,{responseType:'blob'});
    if(version!==epoch||!card.isConnected)return;
    const image=node('img');image.alt='Ảnh minh chứng';const url=URL.createObjectURL(blob);image.onload=image.onerror=()=>URL.revokeObjectURL(url);image.src=url;card.append(image);
  }
  async function loadReports(){
    if(!canManage())return;
    const version=epoch,generation=++reportVersion;
    try{
      const page=await api.request(`/manager/reports?offset=${reportOffset}&limit=10`);if(version!==epoch||generation!==reportVersion)return;
      $('reports').replaceChildren();pagination('reports',page);
      if(!page.items.length)$('reports').append(node('p','Không có báo cáo chờ duyệt.'));
      for(const report of page.items){
        const card=node('article');card.append(node('h3',actions[report.action]),node('p',report.comment));
        if(report.proposed_class!==null)card.append(node('p',`Loại đề xuất: ${['P.127 (50)','P.127 (60)','P.127 (80)','P.125','P.122','P.102','W.245a','W.227','R.301a','R.301e'][report.proposed_class]}`));
        if(report.latitude!==null)card.append(node('p',`Vị trí đề xuất: ${report.latitude}, ${report.longitude}`));
        const current=node('p','Đang tải biển hiện tại…');card.append(current);
        const comment=node('textarea');comment.maxLength=1000;comment.setAttribute('aria-label','Ghi chú duyệt');card.append(comment);
        for(const action of ['accept','reject']){const button=node('button',action==='accept'?'Chấp nhận':'Từ chối');if(action==='reject')button.className='reject';
          button.onclick=()=>act(button,async()=>{await api.request(`/manager/reports/${report.id}/review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,comment:comment.value||null})});if(version!==epoch)return;message('Đã xử lý báo cáo.');await loadReports();});card.append(button);}
        $('reports').append(card);
        try{const detail=await api.request(`/signs/${report.record_id}`);if(version!==epoch||generation!==reportVersion||!card.isConnected)return;
          current.textContent=`Biển hiện tại: ${detail.sign.qcvn_code} · ${detail.sign.latitude}, ${detail.sign.longitude} · ${detail.sign.status}`;
          const evidence=node('details');evidence.append(node('summary','Ảnh và lịch sử của biển hiện tại'));
          const contents=node('div');evidence.append(contents);card.append(evidence);
          let evidenceLoaded=false;
          evidence.ontoggle=async()=>{
            if(!evidence.open||evidenceLoaded)return;evidenceLoaded=true;
            try{
              for(const row of detail.evidence){const match=row.content_url.match(/^\/api\/v1\/images\/([^/]+)\/content$/);if(match)await showImage(contents,match[1],version);}
              const history=await api.request(`/signs/${report.record_id}/history?limit=25`);
              if(version!==epoch||!card.isConnected)return;
              if(!history.items.length)contents.append(node('p','Chưa có thay đổi được duyệt.'));
              for(const row of history.items)contents.append(node('p',`${row.action} · ${row.created_at} · ${row.before.status} → ${row.after.status}`));
            }catch(error){if(version===epoch&&card.isConnected){contents.append(node('p',error.message));evidenceLoaded=false;}}
          };
          if(detail.sign.revision!==report.base_revision)card.append(node('p','Biển đã có thay đổi mới hơn. Kiểm tra lịch sử; có thể từ chối và yêu cầu báo cáo mới.'));
          await showImage(card,report.image_id,version);
        }catch(error){if(version===epoch&&card.isConnected)card.append(node('p',error.message));}
      }
    }catch(error){if(version===epoch)message(error.message);}
  }
  async function loadDuplicates(){
    if(!canManage())return;
    const version=epoch,generation=++duplicateVersion;
    try{const page=await api.request(`/manager/duplicates?offset=${duplicateOffset}&limit=10`);if(version!==epoch||generation!==duplicateVersion)return;
      $('duplicates').replaceChildren();pagination('duplicates',page);
      if(!page.items.length)$('duplicates').append(node('p','Không có cặp nghi trùng.'));
      for(const pair of page.items){
        const card=node('article');card.append(node('h3',`${pair.new_record.qcvn_code} ↔ ${pair.existing_record.qcvn_code}`),node('p',`Khoảng cách quan sát: ${pair.distance_meters} m`));
        for(const [title,sign] of [['Biển mới',pair.new_record],['Biển giữ lại khi gộp',pair.existing_record]]){
          card.append(node('p',`${title}: ${sign.latitude}, ${sign.longitude} · ${sign.status}`));
          const images=node('div');const load=node('button',`Xem ảnh ${title.toLowerCase()}`);
          load.onclick=()=>act(load,async()=>{const evidence=await api.request(`/signs/${sign.id}/evidence`);if(version!==epoch||!card.isConnected)return;images.replaceChildren();
            if(!evidence.length)images.append(node('p','Chưa có ảnh minh chứng.'));
            for(const item of evidence.slice(0,3)){const match=item.content_url.match(/^\/api\/v1\/images\/([^/]+)\/content$/);if(match)await showImage(images,match[1],version);}
          });card.append(load,images);
        }
        for(const action of ['merge','dismiss']){const button=node('button',action==='merge'?'Gộp vào biển giữ lại':'Hai biển khác nhau');if(action==='merge')button.disabled=!pair.class_match;
          button.onclick=()=>act(button,async()=>{await api.request(`/manager/duplicates/${pair.id}/review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});if(version!==epoch)return;message('Đã xử lý cặp nghi trùng.');await loadDuplicates();});card.append(button);}
        $('duplicates').append(card);
      }
    }catch(error){if(version===epoch)message(error.message);}
  }
  async function loadPolicy(){const version=epoch;
    try{const policy=await api.request('/policy');const history=await api.request('/admin/policy/history?limit=10');if(version!==epoch||api.user?.role!=='admin')return;
      $('days').value=policy.confirmation_days;$('policy-history').replaceChildren(...history.items.map(row=>node('p',`${row.before_days} → ${row.after_days} ngày · ${row.created_at}`)));
    }catch(error){if(version===epoch)message(error.message);}
  }
  $('policy-form').onsubmit=event=>{event.preventDefault();act(event.submitter,async()=>{const version=epoch;await api.request('/admin/policy',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmation_days:Number($('days').value)})});if(version!==epoch)return;message('Đã lưu thời hạn xác nhận.');await loadPolicy();});};
  $('refresh-reports').onclick=loadReports;$('refresh-duplicates').onclick=loadDuplicates;
  for(const prefix of ['reports','duplicates'])for(const [suffix,delta]of [['prev',-10],['next',10]])$(prefix+'-'+suffix).onclick=()=>{if(prefix==='reports'){reportOffset=Math.max(0,reportOffset+delta);loadReports();}else{duplicateOffset=Math.max(0,duplicateOffset+delta);loadDuplicates();}};
})();
