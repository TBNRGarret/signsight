const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const registry=path.join(__dirname,'../frontend/shared/sign_icons.js');
const icons=fs.existsSync(registry)?require(registry):null;
test('approved visual registry and all CAR35 images are bundled locally',()=>{
 assert.ok(icons,'The approved visual registry is missing');
 const resolved=Array.from({length:35},(_,i)=>icons.resolve('DS.SS.'+String(i).padStart(2,'0')));
 assert.equal(new Set(resolved.map(r=>r.key)).size,35);
 for(const row of resolved){assert.notEqual(row.key,'unknown');assert.ok(fs.existsSync(path.join(__dirname,'../frontend',row.url)));}
 assert.equal(icons.resolve('P.122').key,'legacy_stop');
});
test('known legacy ambiguity never silently turns a left arrow or generic danger into a different sign',()=>{
 assert.ok(icons,'The approved visual registry is missing');
 assert.equal(icons.resolve('R.301e','Các xe chỉ được rẽ trái').key,'unknown');
 assert.equal(icons.resolve('R.301e').key,'unknown');
 assert.equal(icons.resolve('R.301e','Left or right').key,'unknown');
 assert.equal(icons.resolve('R.301e','Không phải biển đi vòng sang bên phải').key,'unknown');
 assert.equal(icons.resolve('R.301e','Đi vòng sang bên phải').key,'keep_right');
 assert.equal(icons.resolve('R.302a').key,'keep_right');
 assert.equal(icons.resolve('W.245a','Đi chậm / Nguy hiểm khác').key,'unknown');
 assert.equal(icons.resolve('W.245a','Unknown').key,'unknown');
 assert.equal(icons.resolve('W.245a').key,'unknown');
 assert.equal(icons.resolve('W.245a','Đi chậm').key,'slow_down');
 assert.equal(icons.resolve('DS.SS.28','Đi chậm').key,'slow_down');
 assert.equal(icons.resolve('../../secret').key,'unknown');
});
test('approved originals retain checksums and each derived Flutter PNG has provenance',()=>{
 const file=path.join(__dirname,'../frontend/shared/signs/catalog.json');
 assert.ok(fs.existsSync(file),'The approved asset catalogue is missing');
 const catalog=JSON.parse(fs.readFileSync(file));assert.equal(catalog.entries.length,36);
 for(const row of catalog.entries){
  const svg=fs.readFileSync(path.join(path.dirname(file),row.svg));
  assert.equal(crypto.createHash('sha256').update(svg).digest('hex'),row.source.sha256);
  assert.match(row.source.page,/^https:\/\/commons.wikimedia.org\/wiki\/File/);
  assert.ok(row.source.license);assert.ok(row.source.artist_html);
  const png=fs.readFileSync(path.join(__dirname,'../mobile/assets/signs',row.key+'.png'));
  assert.deepEqual([...png.subarray(0,8)],[137,80,78,71,13,10,26,10]);
 }
});
test('marker separates the physical sign icon from its confirmation badge and has a neutral image fallback',()=>{
 assert.ok(icons,'The approved visual registry is missing');
 const document={createElement:tag=>({tag,children:[],attrs:{},setAttribute(k,v){this.attrs[k]=v;},append(...nodes){this.children.push(...nodes);}})};
 const element={className:'sign-map-marker',children:[],append(...nodes){this.children.push(...nodes);}};
 icons.decorate(element,{qcvn_code:'P.127 (50)',name_vi:'Speed',verification_status:'needs_confirmation'},document);
 assert.match(element.className,/sign-map-icon-marker/);
 assert.equal(element.children[0].src,'shared/signs/speed_limit_50.svg');
 assert.equal(element.children[1].className,'sign-marker-revalidation');
 element.children[0].onerror();assert.equal(element.children[0].src,'shared/signs/unknown.svg');
 const expired={className:'sign-map-marker',children:[],append(...nodes){this.children.push(...nodes);}};
 icons.decorate(expired,{qcvn_code:'P.102',status:'expired',verification_status:'current'},document);
 assert.equal(expired.children[1]?.className,'sign-marker-revalidation');
});
