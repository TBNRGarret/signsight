import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from backend.app.core.security import get_current_user, require_roles
from backend.app.db.database import get_db
from backend.app.db.models import AccountAudit, SignRecord, User
from backend.app.schemas.auth import AccountUpdate, UserPage, UserResponse
from backend.app.schemas.sign import SignRecordResponse
from backend.app.services.auth_service import revoke_user_sessions

router = APIRouter()


@router.get("/me/contributions", response_model=list[SignRecordResponse])
def my_contributions(response: Response, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return db.query(SignRecord).filter(SignRecord.created_by == user.id).order_by(
        SignRecord.created_at.desc(), SignRecord.id,
    ).offset(offset).limit(limit).all()


@router.get("/admin/users", response_model=UserPage)
def list_users(response: Response, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
               admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    query = db.query(User)
    return UserPage(items=query.order_by(User.created_at, User.id).offset(offset).limit(limit).all(),
                    total=query.count(), offset=offset, limit=limit)


@router.patch("/admin/users/{user_id}", response_model=UserResponse)
def update_user(user_id: str, payload: AccountUpdate, response: Response,
                admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).with_for_update().first()
    if target is None:
        raise HTTPException(404, "User not found")
    # The bootstrap administrator remains protected. Creating/changing additional
    # administrators needs an explicit recovery/governance flow in a later step.
    if target.role == "admin":
        raise HTTPException(403, "Administrator accounts cannot be changed through this endpoint")
    if payload.is_active is True and target.password_hash is None:
        raise HTTPException(409, "Legacy account requires an explicit password recovery process")
    changes = payload.model_dump(exclude_none=True)
    before = {field: getattr(target, field) for field in changes}
    for field, value in changes.items():
        setattr(target, field, value)
    if changes.get("is_active") is False:
        target.credential_version += 1
        revoke_user_sessions(db, target.id)
    db.add(AccountAudit(actor_id=admin.id, target_user_id=target.id, action="account_updated",
                        details=json.dumps({"before": before, "after": changes}, sort_keys=True)))
    db.commit()
    db.refresh(target)
    response.headers["Cache-Control"] = "no-store"
    return target
