import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.security import credentials_error, hash_password, hash_token, password_hasher, verify_password
from backend.app.db.models import AuthSession, User
from backend.app.schemas.auth import LoginRequest, TokenResponse, UserRegister, UserResponse


def create_user(db: Session, payload: UserRegister, role: str = "user") -> User:
    existing = db.query(User.id).filter(or_(
        func.lower(User.username) == payload.username,
        func.lower(User.email) == str(payload.email).lower(),
    )).first()
    if existing:
        raise HTTPException(409, "Username or email is unavailable")
    user = User(username=payload.username, email=str(payload.email).lower(),
                password_hash=hash_password(payload.password), role=role, is_active=True)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username or email is unavailable") from None
    db.refresh(user)
    return user


def login(db: Session, payload: LoginRequest, session_minutes: int) -> TokenResponse:
    username = payload.username.strip().lower()
    user = db.query(User).filter(func.lower(User.username) == username).first()
    valid = verify_password(payload.password, user.password_hash if user else None)
    if not valid or user is None or not user.is_active or user.role not in {"user", "manager", "admin"}:
        raise credentials_error()
    if password_hasher.check_needs_rehash(user.password_hash):
        # Do not overwrite a password changed by another request during hashing.
        db.query(User).filter(User.id == user.id, User.password_hash == user.password_hash).update(
            {User.password_hash: hash_password(payload.password)}, synchronize_session=False,
        )
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=session_minutes)
    db.add(AuthSession(token_hash=hash_token(raw_token), user_id=user.id,
                       credential_version=user.credential_version, expires_at=expires_at))
    db.commit()
    return TokenResponse(access_token=raw_token, expires_at=expires_at.replace(tzinfo=timezone.utc), user=UserResponse.model_validate(user))


def revoke_user_sessions(db: Session, user_id: str):
    db.query(AuthSession).filter(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)).update(
        {AuthSession.revoked_at: datetime.utcnow()}, synchronize_session=False,
    )
