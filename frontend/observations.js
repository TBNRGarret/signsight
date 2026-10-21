(() => {
  'use strict';
  const api = window.signSightAuth;
  const $ = id => document.getElementById(id);
  const codes = ['P.127 (50)','P.127 (60)','P.127 (80)','P.125','P.122','P.102','W.245a','W.227','R.301a','R.301e'];
  let epoch = 0, image = null, run = null, bitmap = null, historyOffset = 0, queueOffset = 0;
  let queueVersion = 0, historyVersion = 0;
  let imageBusy = false;
  const reviewer = () => ['admin','manager'].includes(api.user?.role);
  const message = value => { $('status').textContent = value; };
  function element(tag, text) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; return node; }
  function clearImage() {
    image = run = null; bitmap?.close(); bitmap = null;
    $('detections').replaceChildren(); $('preview').hidden = true; $('image-info').textContent = '';
    for (const id of ['detect','classify','submit']) $(id).disabled = true;
    refreshImageControls();
  }
  function refreshImageControls() {
    for (const id of ['camera','file','upload']) $(id).disabled = !api.user || imageBusy;
    for (const id of ['detect','classify']) $(id).disabled = !api.user || imageBusy || !image;
    $('submit').disabled = !api.user || imageBusy || !run?.detections.length;
  }
  async function imageAction(button, fn) {
    if (!api.user || imageBusy) return;
    imageBusy = true; refreshImageControls();
    try { await action(button, fn); }
    finally { imageBusy = false; refreshImageControls(); }
  }
  async function action(button, fn) {
    button.disabled = true;
    try { await fn(); } catch (error) { message(error.message); }
    finally {
      if (['detect','classify'].includes(button.id)) button.disabled = !api.user || !image;
      else if (button.id === 'submit') button.disabled = !api.user || !run?.detections.length;
      else button.disabled = false;
    }
  }
  let authInitialized = false;
  function authChanged() {
    authInitialized = true;
    epoch++; clearImage();
    $('history').replaceChildren(); $('queue').replaceChildren(); historyOffset = queueOffset = 0;
    $('history-status').value = ''; $('history-status').disabled = !api.user;
    $('history-prev').disabled = $('history-next').disabled = true; $('history-page').textContent = '';
    $('history-refresh').disabled = !api.user; $('history').setAttribute('aria-busy','false');
    $('login').hidden = !!api.user; $('logout').hidden = !api.user; $('workspace').hidden = !api.user;
    $('moderation').hidden = !reviewer(); $('profile').textContent = api.user ? `${api.user.username} · ${api.user.role}` : 'Chưa đăng nhập';
    if (api.user) { loadModels(); loadHistory(); if (reviewer()) loadQueue(); }
  }
  window.addEventListener('signsight-auth-changed', authChanged);
  api.ready.then(() => { if (!authInitialized) authChanged(); });
  $('login').addEventListener('submit', event => {
    event.preventDefault(); action(event.submitter, async () => {
      await api.login($('username').value, $('password').value, $('remember').checked); $('password').value = ''; message('Đã đăng nhập.');
    });
  });
  $('logout').onclick = () => action($('logout'), async () => { await api.logout(); message('Đã đăng xuất.'); });
  async function loadModels() {
    const version = epoch;
    try {
      const status = await api.request('/ai/status'); if (version !== epoch) return;
      $('model-status').textContent = `YOLO: ${status.yolo.ready ? 'sẵn sàng' : status.yolo.reason}. CNN: ${status.cnn.ready ? 'sẵn sàng' : 'chưa có checkpoint'}.`;
    } catch (error) { if (version === epoch) message(error.message); }
  }
  $('file').onchange = () => { epoch++; clearImage(); };
  async function uploadImage(file) {
    if (!file) throw new Error('Chọn ảnh trước khi upload.');
    clearImage(); const version = ++epoch;
    message('Đang tải ảnh lên...');
    const form = new FormData(); form.append('file', file);
    const uploaded = await api.request('/images', {method:'POST', body:form});
    if (version !== epoch) return false;
    const blob = await api.request(`/images/${uploaded.id}/content`, {responseType:'blob'});
    const decoded = await createImageBitmap(blob);
    if (version !== epoch) { decoded.close(); return false; }
    image = uploaded; bitmap = decoded; draw([]);
    $('image-info').textContent = `${image.width} × ${image.height} · ${(image.size_bytes/1024).toFixed(0)} KB. ${image.exif_latitude !== null ? 'Có GPS gợi ý; cần xác nhận vị trí từng biển.' : 'Chưa có GPS.'}`;
    message('Ảnh đã lưu. Chọn cách nhận diện.');
    return true;
  }
  $('upload').onclick = () => imageAction($('upload'), () => uploadImage($('file').files[0]));
  $('camera').onchange = async () => {
    const file = $('camera').files[0]; if (!file) return;
    try {
      await imageAction($('camera'), async () => {
        $('file').value = '';
        if (await uploadImage(file)) await infer('detect');
      });
    } finally { $('camera').value = ''; }
  };
  function draw(detections) {
    drawPreview($('preview'),bitmap,detections);
  }
  function drawPreview(canvas,source,detections) {
    const scale = Math.min(1, 1280 / source.width);
    canvas.width = Math.round(source.width*scale); canvas.height = Math.round(source.height*scale); canvas.hidden = false;
    const context = canvas.getContext('2d'); context.drawImage(source,0,0,canvas.width,canvas.height);
    context.lineWidth = 2; context.font = '16px system-ui';
    detections.forEach((detection,index) => {
      if (!detection.bbox) return;
      const b = detection.bbox; context.strokeStyle = context.fillStyle = '#fbbf24';
      context.strokeRect(b.x1*scale,b.y1*scale,(b.x2-b.x1)*scale,(b.y2-b.y1)*scale);
      context.fillText(`${index+1} · ${detection.qcvn_code}`,b.x1*scale,Math.max(18,b.y1*scale-4));
    });
  }
  function input(label, type, value, attributes={}) {
    const wrapper = element('label',label); const control = element('input'); control.type = type; control.value = value;
    Object.assign(control,attributes); wrapper.append(control); return [wrapper,control];
  }
  function fillCurrentLocation(button, lat, lon) {
    if (!navigator.geolocation) { message('Trình duyệt không hỗ trợ GPS. Nhập tọa độ thủ công.'); return; }
    button.disabled = true; message('Đang lấy vị trí...');
    navigator.geolocation.getCurrentPosition(position => {
      button.disabled = false;
      lat.value = position.coords.latitude.toFixed(6); lon.value = position.coords.longitude.toFixed(6);
      message(`Đã điền vị trí của bạn (±${Math.round(position.coords.accuracy)} m). Kiểm tra lại nếu biển cách xa chỗ đứng.`);
    }, error => {
      button.disabled = false;
      message(error.code === error.PERMISSION_DENIED ? 'Không có quyền GPS. Nhập tọa độ thủ công.' : 'Không lấy được vị trí. Nhập tọa độ thủ công.');
    }, {enableHighAccuracy:true, timeout:15000, maximumAge:60000});
  }
  async function infer(engine) {
    if (!image) throw new Error('Upload ảnh trước.');
    const version = epoch;
    run = null; $('detections').replaceChildren(); $('submit').disabled = true;
    message('YOLO đang nhận diện ảnh...');
    const result = await api.request(`/images/${image.id}/${engine}`,{method:'POST'}); if (version !== epoch) return;
    run = result; draw(run.detections);
    run.detections.forEach((detection,index) => {
      const card = element('article'); card.dataset.detectionId = detection.id;
      const [checkLabel, check] = input(`Chọn biển ${index+1}: ${detection.qcvn_code}`, 'checkbox', ''); checkLabel.className = 'inline'; check.checked = true; check.className = 'selected'; card.append(checkLabel);
      card.append(element('p',`${detection.name_vi} · AI ${(100*detection.confidence).toFixed(1)}%${detection.is_uncertain ? ' · cần kiểm tra nhãn' : ''}`));
      const [latLabel,lat] = input('Vĩ độ biển','number',image.exif_latitude ?? '',{min:'-90',max:'90',step:'any'}); lat.className = 'lat';
      const [lonLabel,lon] = input('Kinh độ biển','number',image.exif_longitude ?? '',{min:'-180',max:'180',step:'any'}); lon.className = 'lon'; card.append(latLabel,lonLabel);
      const locate = element('button','Điền vị trí hiện tại của tôi'); locate.type = 'button'; locate.onclick = () => fillCurrentLocation(locate,lat,lon); card.append(locate);
      const label = element('label','Nhãn đề xuất'); const select = element('select'); select.className = 'class';
      codes.forEach((code,id) => { const option = element('option',code); option.value = id; select.append(option); }); select.value = detection.predicted_class; label.append(select); card.append(label);
      const [reasonLabel,reason] = input('Lý do sửa nhãn (nếu có)','text','',{maxLength:1000}); reason.className = 'reason'; card.append(reasonLabel);
      const [confirmedLabel,confirmed] = input('Tôi đã kiểm tra vị trí biển (GPS ảnh có thể là vị trí camera)','checkbox',''); confirmedLabel.className = 'inline'; confirmed.className = 'confirmed'; card.append(confirmedLabel);
      $('detections').append(card);
    });
    $('submit').disabled = !run.detections.length;
    message(run.detections.length ? `Đã tìm ${run.detections.length} biển. Xác nhận tọa độ trước khi gửi.` : 'Không tìm thấy biển trong bộ lớp hỗ trợ.');
  }
  for (const id of ['detect','classify']) $(id).onclick = () => imageAction($(id),() => infer(id));
  $('submission').onsubmit = event => { event.preventDefault(); action($('submit'),async () => {
    if (!run || !image) throw new Error('Chưa có kết quả nhận diện.');
    const items = [];
    for (const card of $('detections').children) {
      if (!card.querySelector('.selected').checked) continue;
      const latitude = card.querySelector('.lat'), longitude = card.querySelector('.lon');
      if (!latitude.value || !longitude.value || !latitude.checkValidity() || !longitude.checkValidity() || !card.querySelector('.confirmed').checked)
        throw new Error('Xác nhận tọa độ hợp lệ cho từng biển đã chọn.');
      items.push({detection_id:card.dataset.detectionId,latitude:Number(latitude.value),longitude:Number(longitude.value),location_source:'user_confirmed',
                  proposed_class:Number(card.querySelector('.class').value),correction_reason:card.querySelector('.reason').value || null});
    }
    if (!items.length) throw new Error('Chọn ít nhất một biển.');
    const version = epoch;
    await api.request('/observations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image_id:image.id,items})});
    if (version !== epoch) return;
    clearImage(); message('Đã gửi đóng góp; chờ manager duyệt.'); await loadHistory(); if (reviewer()) await loadQueue();
  }); };
  async function loadHistory() {
    if (!api.user) return;
    const version = epoch, requestVersion = ++historyVersion;
    const status = $('history-status').value || '';
    const query = new URLSearchParams({offset:historyOffset,limit:10});
    if (status) query.set('status',status);
    const current = () => version === epoch && requestVersion === historyVersion;
    $('history-prev').disabled = $('history-next').disabled = true; $('history-refresh').disabled = true;
    $('history-page').textContent = ''; $('history').setAttribute('aria-busy','true');
    $('history').replaceChildren(element('p','Đang tải lịch sử đóng góp...'));
    try {
      const result = await api.request(`/me/observations?${query}`); if (!current()) return;
      const names = {pending:'Chờ duyệt',accepted:'Đã duyệt',rejected:'Bị từ chối'};
      $('history').replaceChildren(...result.items.map(row => element('p',`${row.detection.qcvn_code} · ${row.latitude}, ${row.longitude} · ${names[row.status] || row.status}${row.review_comment ? ' · '+row.review_comment : ''}`)));
      if (!result.items.length) {
        const empty = {pending:'Chưa có đóng góp đang chờ duyệt.',accepted:'Chưa có đóng góp đã được duyệt.',rejected:'Chưa có đóng góp bị từ chối.'};
        $('history').append(element('p',empty[status] || 'Bạn chưa có đóng góp. Upload ảnh và gửi biển để bắt đầu.'));
      }
      paginate('history',result);
    } catch (error) {
      if (current()) {
        $('history').replaceChildren(element('p',`Không tải được lịch sử: ${error.message}. Bấm Tải lịch sử để thử lại.`));
        message(error.message);
      }
    } finally {
      if (current()) { $('history-refresh').disabled = false; $('history').setAttribute('aria-busy','false'); }
    }
  }
  function paginate(prefix,result) {
    $(prefix+'-prev').disabled = result.offset === 0; $(prefix+'-next').disabled = result.offset+result.limit >= result.total;
    $(prefix+'-page').textContent = `${result.total ? result.offset+1 : 0}–${Math.min(result.total,result.offset+result.limit)} / ${result.total}`;
  }
  async function loadQueue() {
    if (!reviewer()) return; const version = epoch, requestVersion = ++queueVersion;
    try {
      const result = await api.request(`/manager/observations?offset=${queueOffset}&limit=10`); if (version !== epoch || requestVersion !== queueVersion) return;
      $('queue').replaceChildren(); paginate('queue',result);
      if (!result.items.length) $('queue').append(element('p','Không có đóng góp chờ duyệt.'));
      for (const row of result.items) {
        const card = element('article'); card.append(element('h3',row.detection.qcvn_code),element('p',`AI ${(100*row.detection.confidence).toFixed(1)}% · ${row.engine} · ${row.latitude}, ${row.longitude}`));
        card.append(element('p',`Nhãn đề xuất: ${codes[row.proposed_class ?? row.detection.predicted_class]}${row.correction_reason ? ' · '+row.correction_reason : ''}`));
        const canvas = element('canvas'); canvas.setAttribute('aria-label','Ảnh minh chứng và biển được chọn'); card.append(canvas);
        const comment = element('textarea'); comment.maxLength = 1000; comment.setAttribute('aria-label','Ghi chú duyệt'); card.append(comment);
        for (const decision of ['accept','reject']) {
          const button = element('button',decision === 'accept' ? 'Chấp nhận' : 'Từ chối'); if (decision === 'reject') button.className = 'reject';
          button.onclick = () => action(button,async () => {
            await api.request(`/manager/observations/${row.id}/review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:decision,comment:comment.value || null})});
            if (version !== epoch) return;
            message(decision === 'accept' ? 'Đã công bố biển báo.' : 'Đã từ chối đóng góp.'); await loadQueue(); await loadHistory();
          }); card.append(button);
        }
        $('queue').append(card);
        try {
          const blob = await api.request(`/images/${row.image_id}/content`,{responseType:'blob'});
          const decoded = await createImageBitmap(blob);
          if (version !== epoch || requestVersion !== queueVersion || !card.isConnected) { decoded.close(); return; }
          drawPreview(canvas,decoded,[row.detection]); decoded.close();
        } catch (error) { if (version === epoch) card.append(element('p',error.message)); }
      }
    } catch (error) { if (version === epoch) message(error.message); }
  }
  $('history-refresh').onclick = loadHistory; $('queue-refresh').onclick = loadQueue;
  $('history-status').onchange = () => { historyOffset = 0; return loadHistory(); };
  for (const prefix of ['history','queue']) for (const [suffix,delta] of [['prev',-10],['next',10]]) {
    $(prefix+'-'+suffix).onclick = () => { if (prefix === 'history') { historyOffset=Math.max(0,historyOffset+delta); loadHistory(); } else { queueOffset=Math.max(0,queueOffset+delta); loadQueue(); } };
  }
})();
