const test=require('node:test'),assert=require('node:assert/strict');
const {createCard}=require('../frontend/contribution_history.js');
class Node{
 constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.attributes={};}
 append(...nodes){this.children.push(...nodes);}
 set textContent(text){this.text=String(text);this.children=[];}
 get textContent(){return (this.text||'')+this.children.map(n=>n.textContent).join('');}
 setAttribute(name,value){this.attributes[name]=value;}
}
const document={createElement:tag=>new Node(tag)};
const row={id:'o',image_id:'photo',status:'pending',detection:{qcvn_code:'P.102',name_vi:'Cấm đi ngược chiều',predicted_class:5},latitude:10.7,longitude:106.7,created_at:'2026-10-21T00:00:00'};
function all(node){return [node,...node.children.flatMap(all)];}
test('pending and rejected contributions never link to an unpublished map record',()=>{
 for(const status of ['pending','rejected']){
  const {card}=createCard({document,observation:{...row,status,sign_record_id:'record'}});
  assert.equal(all(card).filter(n=>n.tagName==='a').length,0);
  assert.match(card.textContent,status==='pending'?/Chờ duyệt/:/Bị từ chối/);
 }
});
test('accepted history links to its exact record and displays the review comment as text',()=>{
 const {card}=createCard({document,observation:{...row,status:'accepted',sign_record_id:'record&other=1',review_comment:'<img src=x onerror=alert(1)>'}});
 const links=all(card).filter(n=>n.tagName==='a');
 assert.equal(links.length,1);assert.equal(links[0].href,'index.html?sign=record%26other%3D1');
 assert.match(card.textContent,/<img src=x onerror=alert\(1\)>/);
 assert.equal(all(card).filter(n=>n.tagName==='img').length,0);
});
test('history presents a proposed corrected class instead of the original prediction',()=>{
 const {card}=createCard({document,codes:['P.127 (50)'],observation:{...row,proposed_class:0}});
 assert.equal(card.children[0].textContent,'P.127 (50)');
});
test('history includes an accessible private preview and expandable detail',()=>{
 const {card,canvas}=createCard({document,observation:row});
 assert.equal(canvas.hidden,true);assert.equal(canvas.attributes.role,'img');
 assert.ok(all(card).some(n=>n.tagName==='details'));assert.match(card.textContent,/Gửi lúc:.*Vị trí:/);
});
