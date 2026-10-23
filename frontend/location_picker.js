/* One shared map; each detected sign owns its own unconfirmed/confirmed position. */
(function(root){
  'use strict';
  function mount({document,environment=root,baseMap=root.signSightMap,onChange}){
    const $=id=>document.getElementById('location-'+id);
    let items=new Map(),active=null,map=null,marker=null,generation=0;
    const valid=(lat,lon)=>typeof lat==='number'&&typeof lon==='number'&&Number.isFinite(lat)&&Number.isFinite(lon)&&Math.abs(lat)<=90&&Math.abs(lon)<=180;
    function removeMarker(){if(marker){map.removeLayer(marker);marker=null;}}
    function render(){
      const item=items.get(active);if(!item)return;
      $('title').textContent='Vị trí của '+item.name;
      $('confirm').disabled=!valid(item.latitude,item.longitude)||item.confirmed;
      $('status').textContent=item.confirmed?'Đã xác nhận vị trí biển này.':
        valid(item.latitude,item.longitude)?'Ghim mới là vị trí gợi ý. Kéo ghim nếu cần, rồi xác nhận.':'Chạm bản đồ để đặt ghim tại vị trí biển.';
      if(!map||map.enabled===false)return;
      removeMarker();
      if(valid(item.latitude,item.longitude)){
        const id=active;
        const current=map.addMarker([item.latitude,item.longitude],{draggable:true});
        marker=current;
        current.on('dragend',()=>{
          if(marker!==current||active!==id)return;
          const point=current.getLatLng();setPosition(id,point.lat,point.lng);
        });
      }
    }
    function emit(item){onChange({id:item.id,latitude:item.latitude,longitude:item.longitude,confirmed:item.confirmed});}
    function setPosition(id,latitude,longitude,confirmed=false){
      const item=items.get(id);
      if(!item||!valid(latitude,longitude))return false;
      generation++;$('gps').disabled=false;
      Object.assign(item,{latitude,longitude,confirmed:confirmed===true});
      if(active===id)render();emit(item);return true;
    }
    function select(id){
      if(!items.has(id))return;
      generation++;active=id;$('panel').hidden=false;$('gps').disabled=false;
      if(!map){
        map=baseMap.mount({document,environment,idPrefix:'location-'}).map;
        map.on('click',event=>{if(active)setPosition(active,event.latlng.lat,event.latlng.lng);});
      }
      render();
      const item=items.get(id);
      if(valid(item.latitude,item.longitude))map.flyTo([item.latitude,item.longitude],17);
      map.invalidateSize({pan:false});
    }
    $('confirm').onclick=()=>{
      const item=items.get(active);
      if(item&&valid(item.latitude,item.longitude))setPosition(active,item.latitude,item.longitude,true);
    };
    $('gps').onclick=()=>{
      if(!active||$('gps').disabled)return;
      if(!environment.navigator?.geolocation){
        $('status').textContent='Không có GPS. Chạm bản đồ hoặc nhập tọa độ trong phần nâng cao.';return;
      }
      const id=active,version=generation;
      $('gps').disabled=true;$('status').textContent='Đang lấy vị trí của bạn…';
      environment.navigator.geolocation.getCurrentPosition(position=>{
        if(version!==generation||active!==id||!items.has(id))return;
        $('gps').disabled=false;
        if(!setPosition(id,position.coords.latitude,position.coords.longitude)){
          $('status').textContent='GPS trả vị trí không hợp lệ. Chạm bản đồ để chọn.';return;
        }
        map.flyTo([position.coords.latitude,position.coords.longitude],17);
        const accuracy=position.coords.accuracy;
        $('status').textContent='Vị trí của bạn'+(Number.isFinite(accuracy)?' (±'+Math.round(accuracy)+' m)':'')+
          '. Đây có thể là chỗ đứng chụp ảnh; kéo ghim tới biển rồi xác nhận.';
      },()=>{
        if(version!==generation||active!==id)return;
        $('gps').disabled=false;$('status').textContent='Không lấy được GPS. Chạm bản đồ để chọn vị trí biển hoặc nhập tọa độ nâng cao.';
      },{enableHighAccuracy:true,timeout:15000,maximumAge:60000});
    };
    function clear(){
      generation++;items.clear();active=null;removeMarker();
      $('panel').hidden=true;$('gps').disabled=false;$('confirm').disabled=true;$('status').textContent='';
    }
    function setItems(values){
      clear();items=new Map(values.map(item=>[item.id,{...item,confirmed:false}]));
    }
    return {setItems,select,setPosition,clear};
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={mount};
  else root.signSightLocation={mount};
})(typeof window==='undefined'?globalThis:window);
