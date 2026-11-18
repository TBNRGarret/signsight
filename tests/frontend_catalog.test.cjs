const test=require('node:test'),assert=require('node:assert/strict');
const catalog=require('../frontend/shared/catalog.js');
const items=[{new_id:5,qcvn_code:'P.102',name_vi:'Existing sign'},
  {new_id:42,qcvn_code:'FIXTURE.42',name_vi:'Synthetic extension'}];

test('catalog options retain stable IDs rather than array positions',async()=>{
  const loaded=await catalog.load({request:async route=>{assert.equal(route,'/taxonomy');return {items};}});
  const document={createElement:()=>({})},select={value:'',replaceChildren(...children){this.children=children;}};
  catalog.fill(select,loaded,document,42);
  assert.deepEqual(select.children.map(item=>item.value),['5','42']);
  assert.equal(select.value,'42');
  assert.match(select.children[1].textContent,/Synthetic extension/);
  assert.equal(catalog.codes(loaded)[42],'FIXTURE.42');
});

test('invalid or duplicate IDs cannot silently become selectable classes',async()=>{
  for(const bad of [[],[...items,items[0]],[{...items[0],new_id:'5'}]])
    await assert.rejects(catalog.load({request:async()=>({items:bad})}),/danh mục/);
});

test('a full 1000-entry model catalog still has room for the manual Others option',async()=>{
 const full=Array.from({length:1000},(_,id)=>({new_id:id,qcvn_code:'FIXTURE.'+id,name_vi:'Sign '+id}));
 full.push({new_id:1000000,qcvn_code:'OTHER',name_vi:'Khác / Others'});
 const loaded=await catalog.load({request:async()=>({items:full})});
 assert.equal(loaded.length,1001);
 assert.equal(loaded.at(-1).new_id,1000000);
});
