from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend.app.core.security import (BROWSER_SESSION_COOKIE, credentials_error, get_current_session,
                                       get_current_user, hash_password, verify_password, require_web_request)
from backend.app.db.database import get_db
from backend.app.db.models import AuthSession, User
from backend.app.schemas.auth import LoginRequest, PasswordChange, TokenResponse, UserRegister, UserResponse
from backend.app.services.auth_service import create_user, login, revoke_user_sessions

router = APIRouter()


def token_headers(response: Response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


@router.post("/register", response_model=UserResponse, status_code=201)
def register(payload: UserRegister, request: Request, db: Session = Depends(get_db)):
    request.app.state.auth_limiter.check(request, "register", 10)
    return create_user(db, payload)


@router.post("/login", response_model=TokenResponse)
def login_json(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    browser = request.headers.get("x-signsight-web") == "1"
    if browser:
        require_web_request(request)
    request.app.state.auth_limiter.check(request, "login", 20)
    token_headers(response)
    minutes = request.app.state.settings.session_minutes
    if browser and payload.remember_me:
        minutes = request.app.state.settings.remember_days * 1440
    result = login(db, payload, minutes)
    if browser:
        # Remove the older API-scoped cookie before creating one also available
        # to server-side page authorization. Do not leave duplicate credentials.
        response.delete_cookie(BROWSER_SESSION_COOKIE, path='/api/v1')
        response.set_cookie(BROWSER_SESSION_COOKIE, result.access_token, httponly=True,
                            secure=request.url.scheme == "https", samesite="lax", path="/",
                            max_age=minutes * 60, expires=result.expires_at)
    return result


@router.post("/token", response_model=TokenResponse)
def login_form(request: Request, response: Response,
               form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    request.app.state.auth_limiter.check(request, "login", 20)
    if not 1 <= len(form.username) <= 100 or not 1 <= len(form.password) <= 128:
        raise credentials_error()
    token_headers(response)
    return login(db, LoginRequest(username=form.username, password=form.password), request.app.state.settings.session_minutes)


@router.get("/me", response_model=UserResponse)
def me(response: Response, user: User = Depends(get_current_user)):
    token_headers(response)
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, session: AuthSession = Depends(get_current_session),
           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session.revoked_at = datetime.utcnow()
    db.commit()
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    if "authorization" not in request.headers:
        for path in ('/', '/api/v1'):
            response.delete_cookie(BROWSER_SESSION_COOKIE, path=path, httponly=True,
                                   secure=request.url.scheme == "https", samesite="lax")
    return response


@router.post("/change-password", status_code=204)
def change_password(payload: PasswordChange, request: Request,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    request.app.state.auth_limiter.check(request, "password", 10)
    if not verify_password(payload.current_password, user.password_hash):
        raise credentials_error()
    updated = db.query(User).filter(User.id == user.id, User.password_hash == user.password_hash).update(
        {User.password_hash: hash_password(payload.new_password), User.credential_version: User.credential_version + 1},
        synchronize_session=False,
    )
    if updated != 1:
        db.rollback()
        raise credentials_error()
    revoke_user_sessions(db, user.id)
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
