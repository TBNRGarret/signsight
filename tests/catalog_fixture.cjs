// Synthetic extension verifies IDs are independent of option positions.
module.exports={items:['P.127 (50)','P.127 (60)','P.127 (80)','P.125','P.122','P.102','W.245a','W.227','R.301a','R.301e']
  .map((qcvn_code,new_id)=>({new_id,qcvn_code,name_vi:'Fixture sign'}))
  .concat({new_id:42,qcvn_code:'FIXTURE.42',name_vi:'Synthetic extension'})};
