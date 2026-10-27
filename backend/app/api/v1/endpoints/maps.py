from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from sqlalchemy.orm import Session
from backend.app.core.security import get_current_user
from backend.app.db.database import get_db
from backend.app.db.models import SignRecord,SignAudit
from backend.app.schemas.sign import SignRecordResponse
from backend.app.services.lifecycle_service import check_and_update_lifecycle_status
from backend.app.services.map_service import VISIBLE,nearby_signs
import json
from backend.app.services.evidence_service import sign_evidence

router=APIRouter()


@router.get('/taxonomy')
def taxonomy(user=Depends(get_current_user)):
    from ai_engine.config import TAXONOMY
    return {'items': [{key: item[key] for key in ('new_id', 'qcvn_code', 'name_vi')}
                      for item in TAXONOMY]}


def page(query,offset,limit):
    return {'items':[SignRecordResponse.model_validate(row) for row in query.order_by(SignRecord.id).offset(offset).limit(limit)],
            'total':query.count(),'offset':offset,'limit':limit}


@router.get('/map/signs')
def map_signs(min_lat:float|None=Query(None,ge=-90,le=90,allow_inf_nan=False),max_lat:float|None=Query(None,ge=-90,le=90,allow_inf_nan=False),
              min_lon:float|None=Query(None,ge=-180,le=180,allow_inf_nan=False),max_lon:float|None=Query(None,ge=-180,le=180,allow_inf_nan=False),
              class_id:int|None=Query(None,ge=0,le=9),status:Literal['active','expired','pending_revalidation','removed']|None=None,
              offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),user=Depends(get_current_user),db:Session=Depends(get_db)):
    check_and_update_lifecycle_status(db)
    query=db.query(SignRecord).filter(SignRecord.status==status) if status else db.query(SignRecord).filter(SignRecord.status.in_(VISIBLE))
    bounds=(min_lat,max_lat,min_lon,max_lon)
    if any(value is not None for value in bounds):
        if any(value is None for value in bounds) or min_lat>=max_lat or min_lon>=max_lon: raise HTTPException(422,'Provide four ordered map bounds')
        query=query.filter(SignRecord.latitude.between(min_lat,max_lat),SignRecord.longitude.between(min_lon,max_lon))
    if class_id is not None: query=query.filter(SignRecord.predicted_class==class_id)
    return page(query,offset,limit)


@router.get('/signs/nearby')
def nearby(latitude:float=Query(ge=-90,le=90,allow_inf_nan=False),longitude:float=Query(ge=-180,le=180,allow_inf_nan=False),
           radius_meters:float=Query(300,ge=100,le=1000,allow_inf_nan=False),offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),
           user=Depends(get_current_user),db:Session=Depends(get_db)):
    check_and_update_lifecycle_status(db)
    items=nearby_signs(db,latitude,longitude,radius_meters)
    return {'items':items[offset:offset+limit],'total':len(items),'offset':offset,'limit':limit,'radius_meters':radius_meters}


@router.get('/signs/{record_id}')
def detail(record_id:str,user=Depends(get_current_user),db:Session=Depends(get_db)):
    check_and_update_lifecycle_status(db); record=db.get(SignRecord,record_id)
    if record is None: raise HTTPException(404,'Sign not found')
    return {'sign':SignRecordResponse.model_validate(record),'evidence':[{'id':row.id,'content_url':row.image_url,
            'sha256':row.image_hash,'size_bytes':row.file_size_bytes,'created_at':row.created_at} for row in sign_evidence(db,record_id)]}


@router.get('/signs/{record_id}/history')
def history(record_id:str,offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100),user=Depends(get_current_user),db:Session=Depends(get_db)):
    if db.get(SignRecord,record_id) is None: raise HTTPException(404,'Sign not found')
    query=db.query(SignAudit).filter(SignAudit.record_id==record_id)
    return {'items':[{'id':row.id,'action':row.action,'before':json.loads(row.before_json),'after':json.loads(row.after_json),'created_at':row.created_at}
                     for row in query.order_by(SignAudit.created_at.desc(),SignAudit.id).offset(offset).limit(limit)],'total':query.count(),'offset':offset,'limit':limit}


@router.get('/me/confirmation-requests')
def confirmations(offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100),user=Depends(get_current_user),db:Session=Depends(get_db)):
    check_and_update_lifecycle_status(db)
    query=db.query(SignRecord).filter(SignRecord.status.in_(VISIBLE),SignRecord.verification_status=='needs_confirmation')
    return page(query,offset,limit)


@router.get('/places/search')
def places(request:Request,q:str=Query(min_length=3,max_length=200),user=Depends(get_current_user),db:Session=Depends(get_db)):
    query=' '.join(q.split())
    if len(query)<3: raise HTTPException(422,'Enter at least 3 characters')
    request.app.state.auth_limiter.check(request,'places',10); db.rollback()
    provider = request.app.state.place_provider
    return {'items':provider.search(query), 'provider':provider.name}
