/* Catalog IDs belong to stored signs; their array positions belong to no model. */
(function(root){
  'use strict';
  async function load(api){
    const result=await api.request('/taxonomy'),items=result?.items,ids=new Set();
    if(!Array.isArray(items)||!items.length||items.length>1000)throw new Error('Chưa tải được danh mục biển. Thử lại.');
    for(const item of items){
      if(!Number.isSafeInteger(item.new_id)||item.new_id<0||ids.has(item.new_id)||
         typeof item.qcvn_code!=='string'||!item.qcvn_code.trim()||typeof item.name_vi!=='string'||!item.name_vi.trim())
        throw new Error('Dữ liệu danh mục biển không hợp lệ. Thử tải lại.');
      ids.add(item.new_id);
    }
    return items;
  }
  function fill(select,items,document,value='',allLabel=null){
    const option=(value,text)=>{const node=document.createElement('option');node.value=String(value);node.textContent=text;return node;};
    const options=items.map(item=>option(item.new_id,item.qcvn_code+' · '+item.name_vi));
    if(allLabel!==null)options.unshift(option('',allLabel));
    select.replaceChildren(...options);
    select.value=String(value);
  }
  function codes(items){return Object.fromEntries(items.map(item=>[item.new_id,item.qcvn_code]));}
  const exported={load,fill,codes};
  if(typeof module!=='undefined'&&module.exports)module.exports=exported;
  else root.signSightCatalog=exported;
})(typeof window==='undefined'?globalThis:window);
