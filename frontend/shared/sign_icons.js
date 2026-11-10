(function(root){
 'use strict';
 const catalog=typeof module!=='undefined'&&module.exports?require('./sign_registry.js'):root.signSightSignRegistry;
 const normalize=value=>String(value||'').replace(/[.\s]/g,'').toUpperCase();
 const aliases=new Map(catalog.entries.flatMap(row=>row.aliases.map(alias=>[normalize(alias),row.key])));
 function resolve(code,name=''){
  const normalized=normalize(code),label=String(name).trim().replace(/\s+/g,' ').toLowerCase();
  let key=aliases.get(normalized)||'unknown';
  if(normalized==='R301E')key=['đi vòng sang bên phải','hướng đi phải theo: đi vòng sang bên phải','keep right'].includes(label)?'keep_right':'unknown';
  if(normalized==='W245A')key=['đi chậm','slow down','slow_down'].includes(label)?'slow_down':'unknown';
  return {key,url:'shared/signs/'+key+'.svg'};
 }
 function decorate(element,sign,document){
  const icon=resolve(sign.qcvn_code,sign.name_vi);
  element.className+=' sign-map-icon-marker';
  const image=document.createElement('img');image.src=icon.url;image.alt='';image.setAttribute('aria-hidden','true');
  image.className='sign-marker-image';image.onerror=()=>{image.onerror=null;image.src='shared/signs/unknown.svg';};
  element.append(image);
  if(sign.verification_status==='needs_confirmation'||sign.status==='expired'){
   const badge=document.createElement('span');badge.className='sign-marker-revalidation';badge.textContent='!';
   badge.setAttribute('role','img');badge.setAttribute('aria-label','Cần xác nhận lại');element.append(badge);
  }
 }
 const api={resolve,decorate};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.signSightSignIcons=api;
})(typeof window==='undefined'?globalThis:window);
