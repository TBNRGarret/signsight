"""Argon2 passwords and opaque, hashed, revocable bearer sessions."""

import hashlib
import re
import secrets
from collections import OrderedDict
from datetime import datetime
from threading import Lock
from time import monotonic

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import AuthSession, User

password_hasher = PasswordHasher()
_dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)
BROWSER_SESSION_COOKIE = "signsight_session"


def require_web_request(request: Request):
    """Cookie writes require a custom header and may only come from this origin.

    The header cannot be submitted by an HTML form. Cross-origin JavaScript needs
    a CORS preflight, which this app does not allow for cookie authentication.
    """
    origin = request.headers.get("origin")
    expected = str(request.base_url).rstrip("/")
    if (request.headers.get("x-signsight-web") != "1"
            or (origin is not None and origin != expected)
            or request.headers.get("sec-fetch-site") == "cross-site"):
        raise HTTPException(403, "Browser session requires a same-origin request")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        valid = password_hasher.verify(encoded or _dummy_hash, password)
        return bool(encoded) and valid
    except (VerificationError, InvalidHashError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def credentials_error():
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired credentials", headers={"WWW-Authenticate": "Bearer"})


def get_current_session(request: Request, token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> AuthSession:
    # Never silently fall back to a more privileged cookie after a bad bearer.
    if "authorization" not in request.headers:
        token = request.cookies.get(BROWSER_SESSION_COOKIE)
        if token and request.method not in {"GET", "HEAD", "OPTIONS"}:
            require_web_request(request)
    if not token or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise credentials_error()
    session = db.get(AuthSession, hash_token(token))
    if session is None or session.revoked_at is not None or session.expires_at <= datetime.utcnow():
        raise credentials_error()
    return session


def get_current_user(session: AuthSession = Depends(get_current_session), db: Session = Depends(get_db)) -> User:
    user = db.get(User, session.user_id)
    if (user is None or not user.is_active or not user.password_hash
            or user.role not in {"user", "manager", "admin"}
            or session.credential_version != user.credential_version):
        raise credentials_error()
    return user


def require_roles(*roles: str):
    def check_role(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user
    return check_role


class AuthRateLimiter:
    """Bounded, thread-safe per-IP limiter for the single-process Alpha server.

    Shared rate limiting at the ingress is required for multiple workers. Ignore
    client-supplied forwarding headers; use the peer address configured by ASGI.
    """

    def __init__(self):
        self._buckets = OrderedDict()
        self._lock = Lock()

    def check(self, request: Request, action: str, limit: int):
        peer = request.client.host if request.client else "unknown"
        key = (action, peer)
        now = monotonic()
        with self._lock:
            while self._buckets:
                first_key, (_, deadline) = next(iter(self._buckets.items()))
                if deadline > now:
                    break
                self._buckets.pop(first_key)
            count, deadline = self._buckets.get(key, (0, now + 60))
            if count >= limit or (key not in self._buckets and len(self._buckets) >= 10000):
                raise HTTPException(429, "Too many authentication attempts", headers={"Retry-After": str(max(1, int(deadline - now) + 1))})
            self._buckets[key] = (count + 1, deadline)
