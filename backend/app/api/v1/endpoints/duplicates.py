from typing import Literal
from pydantic import BaseModel,ConfigDict
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from backend.app.core.security import require_roles
from backend.app.db.database import get_db
from backend.app.db.models import DuplicateCandidate,SignRecord
from backend.app.schemas.sign import SignRecordResponse
from backend.app.services.geo_service import haversine_distance_meters
from backend.app.services.report_service import snapshot,audit
from backend.app.services import write_receipts

router=APIRouter()


class Review(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['merge','dismiss']


@router.get('/manager/duplicates')
def duplicates(offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100),user=Depends(require_roles('manager','admin')),db:Session=Depends(get_db)):
    query=db.query(DuplicateCandidate).filter(DuplicateCandidate.status=='pending_review')
    return {'items':[{'id':row.id,'distance_meters':row.distance_meters,'class_match':row.class_match,
                     'new_record':SignRecordResponse.model_validate(db.get(SignRecord,row.new_record_id)),
                     'existing_record':SignRecordResponse.model_validate(db.get(SignRecord,row.existing_record_id))}
                    for row in query.order_by(DuplicateCandidate.id).offset(offset).limit(limit)],'total':query.count(),'offset':offset,'limit':limit}


@router.post('/manager/duplicates/{candidate_id}/review')
def review(candidate_id:str,payload:Review,user=Depends(require_roles('manager','admin')),db:Session=Depends(get_db),request_key:str|None=write_receipts.request_key_header):
    actor=user.id; db.rollback()
    prior=write_receipts.begin_review(db,actor,'review_duplicate',request_key,{'id':candidate_id,**payload.model_dump()},candidate_id)
    if prior is not None:
        pair=db.get(DuplicateCandidate,prior[0])
        if pair is None: raise HTTPException(409,'Original review is no longer available')
        return {'id':pair.id,'status':pair.status}
    claimed=db.query(DuplicateCandidate).filter(DuplicateCandidate.id==candidate_id,DuplicateCandidate.status=='pending_review').update(
        {DuplicateCandidate.status:'confirmed_duplicate' if payload.action=='merge' else 'dismissed'},synchronize_session=False)
    if claimed!=1:
        exists=db.get(DuplicateCandidate,candidate_id) is not None; db.rollback()
        raise HTTPException(409 if exists else 404,'Candidate has already been reviewed' if exists else 'Candidate not found')
    pair=db.get(DuplicateCandidate,candidate_id)
    if payload.action=='merge':
        source,target=db.get(SignRecord,pair.new_record_id),db.get(SignRecord,pair.existing_record_id)
        if source.id==target.id or source.status=='removed' or target.status=='removed' or source.merged_into_id or target.merged_into_id:
            db.rollback(); raise HTTPException(409,'Review current records before merging')
        if source.predicted_class!=target.predicted_class or haversine_distance_meters(source.latitude,source.longitude,target.latitude,target.longitude)>30:
            db.rollback(); raise HTTPException(409,'Only nearby signs of the same class can be merged')
        before_source,before_target=snapshot(source),snapshot(target)
        source.merged_into_id=target.id; source.status='removed'; source.revision+=1; target.revision+=1
        audit(db,source,actor,'merge_duplicate',before_source)
        audit(db,target,actor,'merge_duplicate',before_target)
    db.commit()
    return {'id':candidate_id,'status':pair.status}


@router.get('/manager/duplicates/{candidate_id}')
def duplicate_detail(candidate_id:str,user=Depends(require_roles('manager','admin')),db:Session=Depends(get_db)):
    pair=db.get(DuplicateCandidate,candidate_id)
    if pair is None: raise HTTPException(404,'Candidate not found')
    return {'id':pair.id,'status':pair.status}
