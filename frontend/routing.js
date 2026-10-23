/* Shared route orchestration: stale responses cannot restore a cleared route. */
(function(root){
  'use strict';
  class RouteController {
    constructor(api,view){this.api=api;this.view=view;this.generation=0;}
    reset(){this.generation++;this.view.clear();}
    async route(origin,destination,buffer){
      this.reset();const generation=this.generation;
      try{
        const data=await this.api.request('/navigation/route',{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({origin,destination,buffer_meters:buffer})});
        if(generation!==this.generation)return null;
        if(!Array.isArray(data.geometry)||data.geometry.length<2||!Array.isArray(data.signs)||
          data.geometry.some(p=>!Number.isFinite(p.latitude)||!Number.isFinite(p.longitude)||Math.abs(p.latitude)>90||Math.abs(p.longitude)>180)){
          throw new Error('Dữ liệu tuyến đường không hợp lệ.');
        }
        this.view.draw(data);return data;
      }catch(error){if(generation!==this.generation)return null;throw error;}
    }
  }
  function mount({api,map,getOrigin,document}){
    const $=id=>document.getElementById(id);
    let destination=null,line=null,searchGeneration=0;
    const controller=new RouteController(api,{
      clear(){if(line){map.removeLayer(line);line=null;}$('nav-summary').textContent='';$('route-signs').replaceChildren();},
      draw(data){line=map.addRoute(data.geometry);
        map.fitBounds(line.getBounds(),{padding:[40,40]});
        $('nav-summary').textContent=`${(data.distance_meters/1000).toFixed(1)} km · ${Math.ceil(data.duration_seconds/60)} phút · ${data.signs.length} biển gần tuyến`;
        for(const row of data.signs){const item=document.createElement('button');item.className='btn btn-secondary';
          item.textContent=`${row.sign.qcvn_code} · ${Math.round(row.distance_along_route_meters)} m từ đầu tuyến · ${row.sign.status}`;
          item.onclick=()=>map.flyTo([row.sign.latitude,row.sign.longitude],18);$('route-signs').append(item);}
      }
    });
    const update=()=>{
      $('route-search-button').disabled=!api.user;$('route-go').disabled=!api.user||!destination;
      $('route-auth-status').textContent=api.user?'':'Đăng nhập để tìm điểm đến và tuyến đường. Không cần upload ảnh để tìm địa điểm.';
    };
    root.addEventListener('signsight-auth-changed',()=>{controller.reset();destination=null;searchGeneration++;$('route-places').replaceChildren();update();});
    $('route-search').onsubmit=async event=>{
      event.preventDefault();
      if(!api.user){update();return;}
      const generation=++searchGeneration,q=$('route-query').value.trim();
      controller.reset();
      if(q.length<3){$('nav-summary').textContent='Nhập ít nhất 3 ký tự.';return;}
      $('route-search-button').disabled=true;$('route-places').replaceChildren();destination=null;update();$('route-search-button').disabled=true;
      $('nav-summary').textContent='Đang tìm địa điểm…';
      try{const page=await api.request(`/places/search?q=${encodeURIComponent(q)}`);if(generation!==searchGeneration)return;
        for(const place of page.items){const button=document.createElement('button');button.type='button';button.className='btn btn-secondary';button.textContent=place.name;
          button.onclick=()=>{destination={latitude:place.latitude,longitude:place.longitude};$('route-places').replaceChildren();
            const selected=document.createElement('p');selected.textContent=`Đến: ${place.name}`;$('route-places').append(selected);update();};$('route-places').append(button);}
        $('nav-summary').textContent=page.items.length?'Chọn một điểm đến bên dưới.':'Không tìm thấy địa điểm. Thử tên đường hoặc địa danh kèm quận/thành phố; có thể chưa có số nhà trong dữ liệu OpenStreetMap.';
      }catch(error){if(generation===searchGeneration)$('nav-summary').textContent=error.status===502
        ?'Dịch vụ tìm địa điểm đang không kết nối được. Thử lại sau; lỗi này không liên quan ảnh upload.':error.message;}
      finally{if(generation===searchGeneration)update();}
    };
    $('route-go').onclick=async()=>{
      $('route-go').disabled=true;
      try{const [latitude,longitude]=getOrigin();await controller.route({latitude,longitude},destination,Number($('route-buffer').value));}
      catch(error){$('nav-summary').textContent=error.status===502
        ?'Không kết nối được dịch vụ tính tuyến đường. Kiểm tra kết nối mạng rồi thử lại.':error.message;}
      finally{update();}
    };
    update();return controller;
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={RouteController,mount};
  else root.signSightRouting={RouteController,mount};
})(typeof window==='undefined'?globalThis:window);
