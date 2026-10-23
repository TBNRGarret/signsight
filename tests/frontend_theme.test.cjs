const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const key='signsight.theme';
function setup({store=new Map(),dark=false,blocked=false,deferred=false}={}){
  const events=new Map(),root={dataset:{}};
  const buttons=['system','light','dark'].map(value=>({dataset:{themeChoice:value},attributes:{},handlers:{},
    setAttribute(name,value){this.attributes[name]=value;},addEventListener(name,fn){this.handlers[name]=fn;}}));
  let mediaChanged;
  const media={matches:dark,addEventListener:(name,fn)=>mediaChanged=fn};
  let ready;const nodes=deferred?[]:buttons.slice();
  const document={documentElement:root,readyState:deferred?'loading':'complete',querySelectorAll:selector=>selector==='[data-theme-choice]'?nodes:[],
    addEventListener:(name,fn)=>ready=fn};
  const window={matchMedia:()=>media,addEventListener:(name,fn)=>events.set(name,fn),localStorage:{
    getItem(name){if(blocked)throw Error('blocked');return store.get(name)??null;},
    setItem(name,value){if(blocked)throw Error('blocked');store.set(name,value);}}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../frontend/theme.js'),'utf8'),{window,document});
  return{root,buttons,store,events,selected(){return buttons.filter(b=>b.attributes['aria-pressed']==='true').map(b=>b.dataset.themeChoice);},
    choose(value){buttons.find(b=>b.dataset.themeChoice===value).handlers.click();},
    finish(){nodes.push(...buttons);document.readyState='complete';ready();},
    system(dark){media.matches=dark;mediaChanged();}};
}
test('system mode follows device preference and reacts to device changes',()=>{
  const a=setup({dark:true});assert.equal(a.root.dataset.theme,'dark');assert.deepEqual(a.selected(),['system']);
  a.system(false);assert.equal(a.root.dataset.theme,'light');
});
test('head script applies the saved theme before controls exist and binds after DOM ready',()=>{
  const a=setup({store:new Map([[key,'dark']]),deferred:true});assert.equal(a.root.dataset.theme,'dark');
  a.finish();assert.deepEqual(a.selected(),['dark']);a.choose('light');assert.equal(a.root.dataset.theme,'light');
});
test('explicit light/dark choice persists across pages and overrides device changes',()=>{
  const store=new Map(),a=setup({store,dark:true});a.choose('light');
  assert.equal(a.root.dataset.theme,'light');assert.equal(store.get(key),'light');
  a.system(true);assert.equal(a.root.dataset.theme,'light');
  const next=setup({store,dark:true});assert.equal(next.root.dataset.theme,'light');
  next.choose('dark');assert.equal(next.root.dataset.theme,'dark');
  next.choose('system');next.system(false);assert.equal(next.root.dataset.theme,'light');
});
test('another tab theme change syncs without trusting an older event value',()=>{
  const a=setup();a.store.set(key,'dark');a.events.get('storage')({key,newValue:'light'});
  assert.equal(a.root.dataset.theme,'dark');assert.deepEqual(a.selected(),['dark']);
  a.store.clear();a.events.get('storage')({key:null});assert.deepEqual(a.selected(),['system']);
});
test('theme works with blocked storage and rejects unknown saved values',()=>{
  const a=setup({blocked:true});a.choose('dark');assert.equal(a.root.dataset.theme,'dark');
  const b=setup({store:new Map([[key,'unexpected']]),dark:true});assert.deepEqual(b.selected(),['system']);
  assert.equal(b.root.dataset.theme,'dark');
});
test('all pages initialize theme in the head and provide a labelled chooser',()=>{
  for(const name of ['index','observations','management']){
    const html=fs.readFileSync(path.join(__dirname,`../frontend/${name}.html`),'utf8');
    const head=html.split('</head>')[0];assert.match(head,/src="theme\.js/);assert.match(head,/href="theme\.css/);
    assert.match(html,/role="group" aria-label="Giao diện"/);
    for(const [value,label] of [['system','Theo thiết bị'],['light','Sáng'],['dark','Tối']]){
      assert.match(html,new RegExp('<button[^>]*data-theme-choice="'+value+'"[^>]*aria-label="'+label+'"'));
    }
    assert.doesNotMatch(html,/data-theme-select/);
  }
});

test('icon buttons keep exactly one selected preference when device or another tab changes',()=>{
  const a=setup({dark:true});assert.deepEqual(a.selected(),['system']);
  a.choose('light');assert.deepEqual(a.selected(),['light']);a.system(true);assert.deepEqual(a.selected(),['light']);
  a.store.set(key,'dark');a.events.get('storage')({key});assert.deepEqual(a.selected(),['dark']);
  a.choose('system');assert.equal(a.root.dataset.theme,'dark');assert.deepEqual(a.selected(),['system']);
});
