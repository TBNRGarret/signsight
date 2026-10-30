(() => {
  'use strict';
  const api = window.signSightAuth;
  const $ = id => document.getElementById(id);
  const catalog = window.signSightCatalog;
  let codes = {};
  let epoch = 0, image = null, run = null, bitmap = null, historyOffset = 0;
  let historyVersion = 0;
  let imageBusy = false, imageOperation = 0, pendingPhoto = null, captureState = 'idle';
  let locationPicker = null;
  const positionFields = new Map();
  const reviewer = () => ['admin','manager'].includes(api.user?.role);
  const message = value => { $('status').textContent = value; };
  function element(tag, text) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; return node; }
  function setCaptureState(state, text) {
    captureState = state;
    $('capture-stage').textContent = text;
    $('capture-stage').dataset.state = state;
    refreshImageControls();
  }
  function clearImage() {
    locationPicker?.clear(); positionFields.clear();
    image = run = pendingPhoto = null; bitmap?.close(); bitmap = null;
    $('detections').replaceChildren(); $('preview').hidden = true; $('image-info').textContent = '';
    $('photo-choices').hidden = true; $('choose-photo').setAttribute('aria-expanded','false');
    setCaptureState('idle','Chọn một ảnh để bắt đầu. Ảnh sẽ tự được tải lên và nhận diện.');
  }
  function refreshImageControls() {
    for (const id of ['camera','file','choose-photo','take-photo','choose-file']) $(id).disabled = !api.user || imageBusy;
    $('retry-upload').hidden = captureState !== 'upload-error';
    $('retry-upload').disabled = !api.user || imageBusy || !pendingPhoto;
    $('detect').hidden = !['detect-error','preview-error'].includes(captureState);
    $('detect').disabled = !api.user || imageBusy || !image;
    $('submit').disabled = !api.user || imageBusy || !readyToSubmit();
    $('capture-panel').setAttribute('aria-busy',String(imageBusy));
  }
  async function imageAction(button, fn) {
    if (!api.user || imageBusy) return;
    const operation = ++imageOperation;
    imageBusy = true; refreshImageControls();
    try { await fn(); }
    catch (error) {
      if (operation !== imageOperation) return;
      const state = captureState === 'recognizing' ? 'detect-error' : image ? 'preview-error' : 'upload-error';
      const text = error.status === 413 ? 'Ảnh quá lớn. Chọn ảnh JPEG, PNG hoặc WebP không quá 10 MB.'
        : error.status === 415 ? 'Chưa hỗ trợ định dạng ảnh này. Hãy chọn JPEG, PNG hoặc WebP.'
        : error.status === 503 ? 'Nhận diện hiện chưa sẵn sàng. Ảnh đã lưu; bạn có thể thử nhận diện lại.'
        : error.message || 'Không kết nối được. Kiểm tra mạng và thử lại.';
      setCaptureState(state,text); message(text);
    } finally {
      if (operation === imageOperation) { imageBusy = false; refreshImageControls(); }
    }
  }
  async function action(button, fn) {
    button.disabled = true;
    try { await fn(); } catch (error) { message(error.message); }
    finally {
      if (button.id === 'submit') button.disabled = !api.user || !readyToSubmit();
      else button.disabled = false;
    }
  }
  let authInitialized = false;
  function authChanged() {
    authInitialized = true;
    imageOperation++; imageBusy = false; epoch++; codes = {}; clearImage();
    $('history').replaceChildren(); historyOffset = 0;
    $('history-status').value = ''; $('history-status').disabled = !api.user;
    $('history-prev').disabled = $('history-next').disabled = true; $('history-page').textContent = '';
    $('history-refresh').disabled = !api.user; $('history').setAttribute('aria-busy','false');
    $('auth-intro').hidden = !!api.user;
    $('login').hidden = !!api.user; $('logout').hidden = !api.user; $('workspace').hidden = !api.user;
    $('profile').textContent = api.user ? api.user.username : 'Chưa đăng nhập';
    if (reviewer()) { $('workspace').hidden = true; window.location?.replace('management.html'); return; }
    if (api.user) { loadModels(); loadHistory(); }
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
      $('model-status').textContent = status.yolo.ready ? 'Sẵn sàng nhận diện ảnh.' : 'Nhận diện chưa sẵn sàng. Bạn có thể thử lại sau.';
    } catch (error) { if (version === epoch) $('model-status').textContent = 'Chưa kiểm tra được dịch vụ nhận diện.'; }
  }
  $('choose-photo').onclick = () => {
    if (!api.user || imageBusy) return;
    $('photo-choices').hidden = !$('photo-choices').hidden;
    $('choose-photo').setAttribute('aria-expanded',String(!$('photo-choices').hidden));
  };
  for (const [button,input] of [['take-photo','camera'],['choose-file','file']]) {
    $(button).onclick = () => {
      if (!api.user || imageBusy) return;
      $('photo-choices').hidden = true; $('choose-photo').setAttribute('aria-expanded','false');
      $(input).click();
    };
  }
  async function loadPreview(version) {
    setCaptureState('loading-preview','Bước 1/3 · Đang chuẩn bị ảnh xem trước…');
    const blob = await api.request('/images/'+image.id+'/content', {responseType:'blob'});
    const decoded = await createImageBitmap(blob);
    if (version !== epoch) { decoded.close(); return false; }
    bitmap?.close(); bitmap = decoded; draw([]);
    $('image-info').textContent = image.width+' × '+image.height+' · '+(image.size_bytes/1024).toFixed(0)+' KB. '+(image.exif_latitude !== null ? 'Có vị trí gợi ý từ ảnh; cần xác nhận vị trí từng biển.' : 'Bạn sẽ chọn vị trí biển ở bước tiếp theo.');
    return true;
  }
  async function uploadImage(file) {
    if (!file) throw new Error('Chọn ảnh trước.');
    clearImage(); pendingPhoto = file; const version = ++epoch;
    setCaptureState('uploading','Bước 1/3 · Đang tải ảnh lên…'); message('Đang tải ảnh lên…');
    const form = new FormData(); form.append('file', file);
    const uploaded = await api.request('/images', {method:'POST', body:form});
    if (version !== epoch) return false;
    image = uploaded;
    return loadPreview(version);
  }
  for (const id of ['camera','file']) $(id).onchange = async () => {
    const file = $(id).files[0]; if (!file || imageBusy || !api.user) return;
    try { await imageAction($(id),async () => { if (await uploadImage(file)) await infer('detect'); }); }
    finally { $(id).value = ''; }
  };
  $('retry-upload').onclick = () => imageAction($('retry-upload'),async () => {
    if (await uploadImage(pendingPhoto)) await infer('detect');
  });
  $('detect').onclick = () => imageAction($('detect'),async () => {
    if (!bitmap && !await loadPreview(epoch)) return;
    await infer('detect');
  });
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
  function validFields(lat,lon) {
    return lat.value!=='' && lon.value!=='' && lat.checkValidity() && lon.checkValidity()
      && Number.isFinite(Number(lat.value)) && Number.isFinite(Number(lon.value));
  }
  function readyToSubmit() {
    if(!run?.detections.length)return false;
    const cards=Array.from($('detections').children).filter(card=>card.querySelector('.selected')?.checked);
    return cards.length>0 && cards.every(card=>validFields(card.querySelector('.lat'),card.querySelector('.lon')) && card.querySelector('.confirmed').checked);
  }
  function setupLocations(detections) {
    if(!detections.length)return;
    try {
      if(!locationPicker && window.signSightLocation && window.signSightMap && window.maplibregl) {
        locationPicker=window.signSightLocation.mount({document,onChange:change=>{
          const fields=positionFields.get(change.id);if(!fields)return;
          fields.lat.value=change.latitude;fields.lon.value=change.longitude;fields.confirmed.checked=change.confirmed;
          fields.summary.textContent=change.confirmed?'Đã xác nhận vị trí biển.':'Ghim chưa được xác nhận.';
          refreshImageControls();
        }});
      }
      if(!locationPicker)throw new Error('Map unavailable');
      locationPicker.setItems(detections.map((d,index)=>({id:d.id,name:'biển '+(index+1)+' · '+d.qcvn_code,
        latitude:image.exif_latitude,longitude:image.exif_longitude})));
      locationPicker.select(detections[0].id);
    } catch (_) {
      for(const fields of positionFields.values()){
        fields.pin.disabled=true;
        fields.summary.textContent='Bản đồ chưa tải được. Bạn có thể nhập vị trí trong phần tọa độ nâng cao.';
      }
    }
  }
  async function infer(engine) {
    if (!image) throw new Error('Upload ảnh trước.');
    const version = epoch;
    run = null; positionFields.clear(); locationPicker?.clear(); $('detections').replaceChildren(); $('submit').disabled = true;
    setCaptureState('recognizing','Bước 2/3 · Đang nhận diện biển trong ảnh…'); message('Đang nhận diện biển trong ảnh…');
    const result = await api.request(`/images/${image.id}/${engine}`,{method:'POST'}); if (version !== epoch) return;
    const items=await catalog.load(api);if(version!==epoch)return;
    codes=catalog.codes(items);
    run = result; draw(run.detections);
    run.detections.forEach((detection,index) => {
      const card = element('article'); card.dataset.detectionId = detection.id;
      const [checkLabel, check] = input('Chọn biển '+(index+1)+': '+detection.qcvn_code, 'checkbox', '');
      checkLabel.className = 'inline'; check.checked = true; check.className = 'selected'; card.append(checkLabel);
      check.onchange = refreshImageControls;
      card.append(element('p',detection.name_vi+' · AI '+(100*detection.confidence).toFixed(1)+'%'+(detection.is_uncertain?' · cần kiểm tra nhãn':'')));
      const positionSummary=element('p','Chưa xác nhận vị trí biển.');positionSummary.className='position-summary';card.append(positionSummary);
      const pin=element('button','Chọn vị trí biển '+(index+1)+' trên bản đồ');pin.type='button';
      pin.onclick=()=>locationPicker?.select(detection.id);card.append(pin);
      const advanced=element('details'),summary=element('summary','Tọa độ nâng cao / nhập thủ công');advanced.append(summary);
      const [latLabel,lat]=input('Vĩ độ biển '+(index+1),'number',image.exif_latitude??'',{min:'-90',max:'90',step:'any'});lat.className='lat';
      const [lonLabel,lon]=input('Kinh độ biển '+(index+1),'number',image.exif_longitude??'',{min:'-180',max:'180',step:'any'});lon.className='lon';
      const [confirmedLabel,confirmed]=input('Tôi đã kiểm tra vị trí biển '+(index+1),'checkbox','');
      confirmedLabel.className='inline';confirmed.className='confirmed';
      advanced.append(latLabel,lonLabel,confirmedLabel);card.append(advanced);
      positionFields.set(detection.id,{lat,lon,confirmed,summary:positionSummary,pin});
      const changed=()=>{
        confirmed.checked=false;
        if(validFields(lat,lon))locationPicker?.setPosition(detection.id,Number(lat.value),Number(lon.value));
        positionSummary.textContent='Vị trí đã thay đổi; cần xác nhận lại.';refreshImageControls();
      };
      lat.onchange=lon.onchange=changed;
      confirmed.onchange=()=>{
        if(!validFields(lat,lon))confirmed.checked=false;
        if(validFields(lat,lon))locationPicker?.setPosition(detection.id,Number(lat.value),Number(lon.value),confirmed.checked);
        positionSummary.textContent=confirmed.checked?'Đã xác nhận vị trí biển.':'Chưa xác nhận vị trí biển.';
        refreshImageControls();
      };
      const label=element('label','Nhãn đề xuất'),select=element('select');select.className='class';
      catalog.fill(select,items,document,detection.predicted_class);label.append(select);card.append(label);
      const [reasonLabel,reason]=input('Lý do sửa nhãn (nếu có)','text','',{maxLength:1000});reason.className='reason';card.append(reasonLabel);
      $('detections').append(card);
    });
    setupLocations(run.detections);
    const text = run.detections.length ? `Bước 3/3 · Tìm thấy ${run.detections.length} biển. Kiểm tra nhãn và chọn vị trí trước khi gửi.` : 'Không tìm thấy biển. Thử ảnh rõ hơn hoặc chụp gần biển hơn; hệ thống hiện chỉ hỗ trợ một số loại biển.';
    setCaptureState(run.detections.length ? 'review' : 'empty',text); message(text);
  }
  $('submission').onsubmit = event => { event.preventDefault(); action($('submit'),async () => {
    if (!run || !image) throw new Error('Chưa có kết quả nhận diện.');
    const items = [];
    for (const card of $('detections').children) {
      if (!card.querySelector('.selected').checked) continue;
      const latitude = card.querySelector('.lat'), longitude = card.querySelector('.lon');
      if (!latitude.value || !longitude.value || !latitude.checkValidity() || !longitude.checkValidity() || !card.querySelector('.confirmed').checked)
        throw new Error('Xác nhận tọa độ hợp lệ cho từng biển đã chọn.');
      const selectedClass=card.querySelector('.class').value;
      if(selectedClass===''||!Object.hasOwn(codes,selectedClass))throw new Error('Chọn loại biển hợp lệ trước khi gửi.');
      items.push({detection_id:card.dataset.detectionId,latitude:Number(latitude.value),longitude:Number(longitude.value),location_source:'user_confirmed',
                  proposed_class:Number(card.querySelector('.class').value),correction_reason:card.querySelector('.reason').value || null});
    }
    if (!items.length) throw new Error('Chọn ít nhất một biển.');
    const version = epoch;
    await api.request('/observations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image_id:image.id,items})});
    if (version !== epoch) return;
    clearImage(); message('Đã gửi đóng góp. Theo dõi trạng thái ở phần bên dưới.'); await loadHistory();
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
      const [result,items] = await Promise.all([api.request(`/me/observations?${query}`),catalog.load(api)]); if (!current()) return;
      codes=catalog.codes(items);
      const cards=result.items.map(row=>({...window.signSightHistory.createCard({document,observation:row,codes}),row}));
      $('history').replaceChildren(...cards.map(item=>item.card));
      for(const item of cards){
        if(!item.row.image_id)continue;
        (async()=>{
          let decoded=null;
          try{
            const blob=await api.request('/images/'+encodeURIComponent(item.row.image_id)+'/thumbnail',{responseType:'blob'});
            if(!current()||!item.card.isConnected)return;
            decoded=await createImageBitmap(blob);
            if(!current()||!item.card.isConnected)return;
            item.canvas.width=decoded.width;item.canvas.height=decoded.height;
            item.canvas.getContext('2d').drawImage(decoded,0,0);
            item.canvas.hidden=false;item.previewStatus.textContent='';
          }catch(_){if(current()&&item.card.isConnected)item.previewStatus.textContent='Chưa tải được ảnh. Bấm Tải lịch sử để thử lại.';}
          finally{decoded?.close();}
        })();
      }
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
  $('history-refresh').onclick = loadHistory;
  $('history-status').onchange = () => { historyOffset = 0; return loadHistory(); };
  for (const [suffix,delta] of [['prev',-10],['next',10]]) {
    $('history-'+suffix).onclick = () => { historyOffset=Math.max(0,historyOffset+delta); loadHistory(); };
  }
})();
