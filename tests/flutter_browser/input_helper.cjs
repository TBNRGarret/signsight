const {expect}=require('@playwright/test');

async function enterText(page,name,value,{autofillId}={}){
 const field=page.getByRole('textbox',{name,exact:true});
 await field.click();
 // Autofill can adopt a focused semantics input after the click has completed.
 // Its configured ID is stable; the earlier placeholder can lose filled text.
 if(autofillId)await expect(field).toHaveAttribute('id',autofillId);
 await expect(field).toBeFocused();
 await field.fill(value);await expect(field).toHaveValue(value);
}

module.exports={enterText};
