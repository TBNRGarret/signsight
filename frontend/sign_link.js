/* Open an approved contribution only after the browser profile is verified. */
(function(root){
  'use strict';
  function mount({api,environment=root,selectSign,createMarker,removeMarker,onMessage}){
    const id=new URLSearchParams(environment.location?.search||'').get('sign');
    let generation=0,marker=null,initialized=false,disposed=false;
    function clear(){generation++;if(marker){removeMarker(marker);marker=null;}}
    async function changed(){
      initialized=true;clear();if(disposed||!id)return;
      if(!/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(id)){onMessage('Liên kết biển không hợp lệ.');return;}
      if(!api.user){onMessage('Đăng nhập để xem biển từ đóng góp.');return;}
      const version=generation;onMessage('Đang mở biển từ đóng góp…');
      try{
        const detail=await selectSign(id);
        if(disposed||version!==generation||!api.user)return;
        if(detail?.sign){marker=createMarker(detail.sign);onMessage('Đã mở biển từ đóng góp.');}
        else onMessage('Chưa mở được biển. Kiểm tra trạng thái hoặc quyền truy cập.');
      }catch(_){if(version===generation)onMessage('Không mở được biển. Bạn có thể thử lại sau.');}
    }
    environment.addEventListener('signsight-auth-changed',changed);
    api.ready.then(()=>Promise.resolve().then(()=>{if(!initialized&&!disposed)changed();}));
    return {dispose(){disposed=true;clear();environment.removeEventListener?.('signsight-auth-changed',changed);}};
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={mount};
  else root.signSightSignLink={mount};
})(typeof window==='undefined'?globalThis:window);
