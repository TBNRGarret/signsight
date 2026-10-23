/* MapLibre renderer adapter. Application points are always [latitude, longitude]. */
(function(root){
 'use strict';
 const HOME=[106.7009,10.7769], STYLES=['liberty','bright','dark'];
 const url=id=>'https://tiles.openfreemap.org/styles/'+id;
 function mount({maplibregl=root.maplibregl,document,environment=root,idPrefix=''}){
  const $=id=>document.getElementById(idPrefix+id);
  const notice=$('map-notice'),message=$('map-message'),retry=$('map-retry'),home=$('map-home'),select=$('map-source');
  const key='signsight.map-style';
  let style='liberty';
  try{const saved=environment.localStorage?.getItem(key);if(STYLES.includes(saved))style=saved;}catch(_){}
  select.value=style;
  let native=null,disposed=false,failed=false,timer=null,frame=null,observer=null,popup=null,popupOwner=null,serial=0,styleReady=false;
  const routes=new Map();
  function show(text){message.textContent=text;notice.hidden=false;}
  function clearTimer(){if(timer!==null)environment.clearTimeout(timer);timer=null;}
  function loading(){
   clearTimer();show('Đang tải bản đồ OpenFreeMap…');
   timer=environment.setTimeout(()=>{timer=null;if(!disposed)show('Bản đồ tải chậm. Kiểm tra kết nối rồi thử tải lại.');},12000);
  }
  function unavailable(){show('Không khởi tạo được bản đồ WebGL. Thử cập nhật Safari/Chrome hoặc bật tăng tốc đồ họa. Bạn vẫn có thể đăng nhập và nhập tọa độ trong phần nâng cao.');}
  try{
   native=new maplibregl.Map({container:idPrefix+'map',style:url(style),center:HOME,zoom:15,
    maxZoom:20,renderWorldCopies:false,attributionControl:{compact:true}});
   native.addControl(new maplibregl.NavigationControl({visualizePitch:true}),'top-left');
  }catch(_){unavailable();retry.onclick=()=>environment.location?.reload();}

  const position=point=>[point[1],point[0]];
  const map={
   native,enabled:!!native,
   on(name,fn){native?.on(name,name==='click'?event=>fn({...event,latlng:{lat:event.lngLat.lat,lng:event.lngLat.lng}}):fn);return map;},
   flyTo(point,zoom){native?.flyTo({center:position(point),zoom});return map;},
   getZoom:()=>native?.getZoom()??15,
   getBounds:()=>native?.getBounds()??{getSouth:()=>10.7769,getNorth:()=>10.7769,getWest:()=>106.7009,getEast:()=>106.7009},
   invalidateSize(){native?.resize();},
   fitBounds(bounds,{padding=[40,40]}={}){native?.fitBounds(bounds,{padding:Math.max(...padding),maxZoom:18});},
   removeLayer(layer){layer?.remove();},
   closePopup(){popup?.remove();popup=null;popupOwner=null;},
   addMarker(point,options={}){
    if(!native||disposed)return null;
    const element=document.createElement('button');element.type='button';element.className='sign-map-marker';
    element.style.setProperty?.('--marker-color',options.fillColor||options.color||'#2563eb');
    element.style.width=element.style.height=((options.radius||9)*2)+'px';
    element.setAttribute('aria-label',options.label||'Vị trí biển báo');
    if(options.highlight){element.className+=' sign-map-highlight';element.tabIndex=-1;element.setAttribute('aria-hidden','true');}
    const marker=new maplibregl.Marker({element,draggable:!!options.draggable}).setLngLat(position(point)).addTo(native);
    if(options.popup)element.addEventListener('click',event=>{
     event.stopPropagation();map.closePopup();popupOwner=marker;
     popup=new maplibregl.Popup({offset:14,maxWidth:'300px'}).setLngLat(marker.getLngLat()).setDOMContent(options.popup()).addTo(native);
    });
    return {on(name,fn){marker.on(name,fn);return this;},getLatLng(){const p=marker.getLngLat();return {lat:p.lat,lng:p.lng};},
     remove(){if(popupOwner===marker)map.closePopup();marker.remove();},native:marker};
   },
   addRoute(points){
    const id='signsight-route-'+(++serial),coordinates=points.map(p=>[p.longitude,p.latitude]);
    const bounds=[[Math.min(...coordinates.map(p=>p[0])),Math.min(...coordinates.map(p=>p[1]))],
     [Math.max(...coordinates.map(p=>p[0])),Math.max(...coordinates.map(p=>p[1]))]];
    const entry={id,coordinates};
    routes.set(id,entry);drawRoute(entry);
    return {getBounds:()=>bounds,remove(){
     routes.delete(id);if(native?.getLayer(id))native.removeLayer(id);if(native?.getSource(id))native.removeSource(id);
    }};
   },
   remove(){native?.remove();}
  };
  function drawRoute(entry){
   if(!native||disposed||!styleReady||native.getSource(entry.id))return;
   native.addSource(entry.id,{type:'geojson',data:{type:'Feature',properties:{},geometry:{type:'LineString',coordinates:entry.coordinates}}});
   native.addLayer({id:entry.id,type:'line',source:entry.id,layout:{'line-join':'round','line-cap':'round'},
    paint:{'line-color':'#3b82f6','line-width':6,'line-opacity':.85}});
  }
  if(!native){select.disabled=true;home.disabled=true;return {map};}
  native.on('style.load',()=>{styleReady=true;for(const route of routes.values())drawRoute(route);});
  native.on('dataloading',()=>{if(!failed&&timer===null)loading();});
  native.on('idle',()=>{
   if(disposed)return;
   if(native.isStyleLoaded()&&native.areTilesLoaded()){
    clearTimer();if(!failed)notice.hidden=true;
   }
  });
  native.on('error',()=>{
   if(disposed)return;failed=true;clearTimer();
   show('Không tải được bản đồ OpenFreeMap. Kiểm tra kết nối rồi bấm Thử tải lại.');
  });
  native.on('webglcontextlost',()=>{failed=true;clearTimer();show('Bản đồ tạm mất kết nối đồ họa. Thử tải lại nếu chưa tự phục hồi.');});
  native.on('webglcontextrestored',()=>{failed=false;loading();});
  function reload(){if(disposed)return;failed=false;styleReady=false;loading();native.setStyle(url(style),{diff:false});}
  retry.onclick=reload;
  select.onchange=()=>{
   if(!STYLES.includes(select.value)||select.value===style)return;
   style=select.value;try{environment.localStorage?.setItem(key,style);}catch(_){}
   reload();
  };
  home.onclick=()=>native.flyTo({center:HOME,zoom:15,bearing:0,pitch:0});
  const container=native.getContainer();
  function resize(){
   if(disposed||frame!==null)return;
   frame=environment.requestAnimationFrame(()=>{
    frame=null;if(!disposed&&container.clientWidth>0&&container.clientHeight>0)native.resize();
   });
  }
  observer=environment.ResizeObserver?new environment.ResizeObserver(resize):null;
  observer?.observe(container);
  native.on('remove',()=>{
   disposed=true;observer?.disconnect();clearTimer();if(frame!==null)environment.cancelAnimationFrame(frame);
   frame=null;routes.clear();map.closePopup();retry.onclick=home.onclick=select.onchange=null;
  });
  loading();resize();return {map};
 }
 if(typeof module!=='undefined'&&module.exports)module.exports={mount};
 else root.signSightMap={mount};
})(typeof window==='undefined'?globalThis:window);
