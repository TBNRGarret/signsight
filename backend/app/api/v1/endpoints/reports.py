from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from sqlalchemy.orm import Session
from backend.app.core.security import get_current_user,require_roles
from backend.app.db.database import get_db
from backend.app.db.models import SignRecord,SignReport,AppPolicy,PolicyAudit
from backend.app.schemas.reports import ReportCreate,ReportResponse,PolicyUpdate
from backend.app.schemas.images import ObservationReview
from backend.app.services.observation_service import authorized_image
from backend.app.services.report_service import review_report
from datetime import datetime
from backend.app.core.catalog import require_catalog_id

router=APIRouter()


@router.post('/signs/{record_id}/reports',response_model=ReportResponse,status_code=201)
def submit_report(record_id:str,payload:ReportCreate,request:Request,user=Depends(get_current_user),db:Session=Depends(get_db)):
    request.app.state.auth_limiter.check(request,'report',20)
    if payload.proposed_class is not None: require_catalog_id(request.app.state.catalog,payload.proposed_class)
    record=db.get(SignRecord,record_id)
    if record is None: raise HTTPException(404,'Sign not found')
    if record.merged_into_id: raise HTTPException(409,'Sign merged; submit evidence to the linked current record')
    image=authorized_image(db,payload.image_id,user,owner_only=True)
    request.app.state.image_store.read(image.storage_key,image.sha256)
    row=SignReport(record_id=record_id,created_by=user.id,base_revision=record.revision,**payload.model_dump())
    db.rollback(); db.add(row); db.commit(); db.refresh(row); return row


def report_page(query,offset,limit):
    return {'items':[ReportResponse.model_validate(row) for row in query.order_by(SignReport.created_at.desc(),SignReport.id).offset(offset).limit(limit)],
            'total':query.count(),'offset':offset,'limit':limit}


@router.get('/me/reports')
def own_reports(offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100),user=Depends(get_current_user),db:Session=Depends(get_db)):
    return report_page(db.query(SignReport).filter(SignReport.created_by==user.id),offset,limit)


@router.get('/manager/reports')
def reports(status:Literal['pending','accepted','rejected']='pending',offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100),
            user=Depends(require_roles('manager','admin')),db:Session=Depends(get_db)):
    return report_page(db.query(SignReport).filter(SignReport.status==status),offset,limit)


@router.get('/reports/{report_id}',response_model=ReportResponse)
def report_detail(report_id:str,user=Depends(get_current_user),db:Session=Depends(get_db)):
    row=db.get(SignReport,report_id)
    if row is None or (row.created_by!=user.id and user.role not in ('manager','admin')): raise HTTPException(404,'Report not found')
    return row


@router.post('/manager/reports/{report_id}/review',response_model=ReportResponse)
def review(report_id:str,payload:ObservationReview,request:Request,user=Depends(require_roles('manager','admin')),db:Session=Depends(get_db)):
    return review_report(db,report_id,payload,user,request.app.state.image_store,request.app.state.catalog)


@router.get('/policy')
def policy(user=Depends(get_current_user),db:Session=Depends(get_db)):
    row=db.get(AppPolicy,1)
    return {'confirmation_days':row.confirmation_days,'revision':row.revision,'application':'New accepted records; existing records retain their stored period'}


@router.patch('/admin/policy')
def set_policy(payload:PolicyUpdate,user=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    actor=user.id; db.rollback()
    # The no-op UPDATE obtains the write lock before reading for a consistent audit.
    db.query(AppPolicy).filter(AppPolicy.id==1).update({AppPolicy.revision:AppPolicy.revision},synchronize_session=False)
    row=db.get(AppPolicy,1); before=row.confirmation_days
    row.confirmation_days=payload.confirmation_days; row.revision+=1; row.updated_by=actor; row.updated_at=datetime.utcnow()
    db.add(PolicyAudit(actor_id=actor,before_days=before,after_days=row.confirmation_days,revision=row.revision))
    db.commit(); db.refresh(row)
    return {'confirmation_days':row.confirmation_days,'revision':row.revision}


@router.get('/admin/policy/history')
def policy_history(offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100),user=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    query=db.query(PolicyAudit)
    return {'items':[{'id':row.id,'actor_id':row.actor_id,'before_days':row.before_days,'after_days':row.after_days,'revision':row.revision,'created_at':row.created_at}
                     for row in query.order_by(PolicyAudit.created_at.desc(),PolicyAudit.id).offset(offset).limit(limit)],'total':query.count(),'offset':offset,'limit':limit}
