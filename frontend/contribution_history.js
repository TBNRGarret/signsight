/* History presentation never trusts HTML in labels or review comments. */
(function(root){
  'use strict';
  const statuses={pending:'Chờ duyệt',accepted:'Đã duyệt',rejected:'Bị từ chối'};
  function createCard({document,observation:row,codes=[]}){
    const node=(tag,text)=>{const item=document.createElement(tag);if(text!==undefined)item.textContent=text;return item;};
    const card=node('article');card.className='history-card';card.dataset.observationId=row.id||'';
    const code=codes[row.proposed_class??row.detection.predicted_class]||row.detection.qcvn_code;
    card.append(node('h3',code+(row.proposed_class==null&&row.detection.name_vi?' · '+row.detection.name_vi:'')));
    const badge=node('p',statuses[row.status]||'Đang cập nhật');badge.className='status-badge';card.append(badge);
    const canvas=node('canvas');canvas.hidden=true;canvas.setAttribute('role','img');canvas.setAttribute('aria-label','Ảnh đóng góp '+code);card.append(canvas);
    const previewStatus=node('p',row.image_id?'Đang tải ảnh…':'');previewStatus.className='history-meta';card.append(previewStatus);
    const details=node('details');details.append(node('summary','Chi tiết đóng góp'));
    let date='Chưa có thời gian';
    if(row.created_at){
      const iso=/(Z|[+-]\d{2}:\d{2})$/i.test(row.created_at)?row.created_at:row.created_at+'Z';
      const parsed=new Date(iso);if(Number.isFinite(parsed.getTime()))date=parsed.toLocaleString('vi-VN');
    }
    details.append(node('p','Gửi lúc: '+date),node('p','Vị trí: '+row.latitude+', '+row.longitude));
    if(row.reviewed_at){
      const iso=/(Z|[+-]\d{2}:\d{2})$/i.test(row.reviewed_at)?row.reviewed_at:row.reviewed_at+'Z';
      const parsed=new Date(iso);if(Number.isFinite(parsed.getTime()))details.append(node('p','Duyệt lúc: '+parsed.toLocaleString('vi-VN')));
    }
    if(row.review_comment)details.append(node('p','Ghi chú duyệt: '+row.review_comment));
    else if(row.status==='rejected')details.append(node('p','Chưa có ghi chú từ người duyệt.'));
    card.append(details);
    if(row.status==='accepted'&&typeof row.sign_record_id==='string'&&row.sign_record_id.length>0&&row.sign_record_id.length<=36){
      const link=node('a','Xem trên bản đồ');link.href='index.html?sign='+encodeURIComponent(row.sign_record_id);card.append(link);
    }else if(row.status==='pending')card.append(node('p','Biển sẽ xuất hiện trên bản đồ sau khi được duyệt.'));
    return {card,canvas,previewStatus};
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={createCard};
  else root.signSightHistory={createCard};
})(typeof window==='undefined'?globalThis:window);
