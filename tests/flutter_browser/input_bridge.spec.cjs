const {test,expect}=require('@playwright/test');
const {enterText}=require('./input_helper.cjs');

test('text entry survives delayed adoption of a focused Flutter semantics input',async({page})=>{
 await page.setContent('<input aria-label="Mật khẩu" type="password" data-semantics-role="text-field">');
 await page.evaluate(()=>{
  const semantic=document.querySelector('input');
  semantic.addEventListener('focus',()=>setTimeout(()=>{
   // Flutter configures/replaces its focused editing element after a frame.
   const editing=semantic.cloneNode();editing.value='';
   editing.id='current-password';editing.setAttribute('autocomplete','current-password');
   semantic.replaceWith(editing);editing.focus();
  },500),{once:true});
 });
 await enterText(page,'Mật khẩu','Synthetic-password-123',{autofillId:'current-password'});
 const input=page.getByRole('textbox',{name:'Mật khẩu',exact:true});
 await expect(input).toHaveAttribute('autocomplete','current-password');
 await expect(input).toHaveValue('Synthetic-password-123');
});
