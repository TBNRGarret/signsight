import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.core.security import hash_token, verify_password
from backend.app.db.models import AccountAudit, AuthSession, ConfirmationEvent, SignRecord, User
from backend.manage import bootstrap_admin

PASSWORD = "Test-password-123"
SIGN = {"predicted_class": 0, "confidence": 0.94, "latitude": 10.78,
        "longitude": 106.70, "location_source": "device"}


def register(client, username="alice"):
    response = client.post("/api/v1/auth/register", json={
        "username": username, "email": f"{username}@example.com", "password": PASSWORD,
    })
    assert response.status_code == 201, response.text
    return response.json()


def login(client, username="alice", password=PASSWORD):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def headers(token):
    return {"Authorization": f"Bearer {token}".encode("utf-8")}


def administrator(client, application):
    bootstrap_admin("owner", "owner@example.com", PASSWORD, application.state.session_factory)
    return login(client, "owner")


def manager(client, application):
    admin = administrator(client, application)
    account = register(client, "manager")
    response = client.patch(f"/api/v1/admin/users/{account['id']}", headers=headers(admin["access_token"]), json={"role": "manager"})
    assert response.status_code == 200, response.text
    return login(client, "manager")


def test_registration_hashes_password_and_cannot_choose_role(client, application):
    response = client.post("/api/v1/auth/register", json={
        "username": " ALICE ", "email": "Alice@EXAMPLE.COM", "password": PASSWORD,
    })
    assert response.status_code == 201
    account = response.json()
    assert account["username"] == "alice" and account["email"] == "alice@example.com"
    assert account["role"] == "user" and account["is_active"] is True
    assert "password" not in response.text and "credential_version" not in response.text
    with application.state.session_factory() as db:
        user = db.get(User, account["id"])
        assert user.password_hash.startswith("$argon2id$")
        assert verify_password(PASSWORD, user.password_hash)
        assert user.password_hash != PASSWORD
    for field, value in [("role", "admin"), ("is_active", True), ("reputation_score", 99999)]:
        response = client.post("/api/v1/auth/register", json={
            "username": "bob", "email": "bob@example.com", "password": PASSWORD, field: value,
        })
        assert response.status_code == 422


def test_duplicate_identities_are_case_insensitive(client):
    register(client)
    for username, email in [("ALICE", "other@example.com"), ("other", "ALICE@example.com")]:
        response = client.post("/api/v1/auth/register", json={"username": username, "email": email, "password": PASSWORD})
        assert response.status_code == 409


@pytest.mark.parametrize("change", [
    {"password": "S3!x"}, {"password": "x" * 129}, {"username": "a"},
    {"username": "bad name"}, {"email": "not-email"},
])
def test_invalid_registration_never_echoes_password(client, change):
    payload = {"username": "alice", "email": "alice@example.com", "password": PASSWORD, **change}
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    assert payload["password"] not in response.text


def test_login_sessions_are_hashed_and_logout_revokes_only_current_session(client, application):
    register(client)
    first = login(client)
    second = login(client, " ALICE ")
    assert first["access_token"] != second["access_token"]
    assert first["expires_at"].endswith("Z")
    with application.state.session_factory() as db:
        rows = db.query(AuthSession).all()
        assert len(rows) == 2
        assert all(row.token_hash not in {first["access_token"], second["access_token"]} for row in rows)
        assert db.get(AuthSession, hash_token(first["access_token"])) is not None
    first_headers = headers(first["access_token"])
    assert client.get("/api/v1/auth/me", headers=first_headers).json()["username"] == "alice"
    assert client.post("/api/v1/auth/logout", headers=first_headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=first_headers).status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers(second["access_token"])).status_code == 200


def test_login_unknown_bad_password_and_disabled_account_use_same_error(client, application):
    account = register(client)
    failures = [client.post("/api/v1/auth/login", json={"username": username, "password": password})
                for username, password in [("missing", PASSWORD), ("alice", "incorrect-password")]]
    with application.state.session_factory() as db:
        db.get(User, account["id"]).is_active = False
        db.commit()
    failures.append(client.post("/api/v1/auth/login", json={"username": "alice", "password": PASSWORD}))
    assert all(response.status_code == 401 for response in failures)
    assert len({response.text for response in failures}) == 1
    with application.state.session_factory() as db:
        assert db.query(AuthSession).count() == 0


@pytest.mark.parametrize("token", [None, "wrong", "é" * 43, "a" * 43])
def test_missing_malformed_and_unknown_token_rejected(client, token):
    response = client.get("/api/v1/auth/me", headers=headers(token) if token is not None else {})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_expired_session_and_stale_credential_version_rejected(client, application):
    register(client)
    expired = login(client)
    stale = login(client)
    with application.state.session_factory() as db:
        db.get(AuthSession, hash_token(expired["access_token"])).expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.get(AuthSession, hash_token(stale["access_token"])).credential_version = -1
        db.commit()
    for result in [expired, stale]:
        assert client.get("/api/v1/auth/me", headers=headers(result["access_token"])).status_code == 401


def test_password_change_requires_old_password_and_revokes_all_sessions(client):
    register(client)
    first, second = login(client), login(client)
    auth = headers(first["access_token"])
    assert client.post("/api/v1/auth/change-password", headers=auth, json={
        "current_password": "wrong-password", "new_password": "Changed-password-123",
    }).status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 200
    assert client.post("/api/v1/auth/change-password", headers=auth, json={
        "current_password": PASSWORD, "new_password": "Changed-password-123",
    }).status_code == 204
    for session in [first, second]:
        assert client.get("/api/v1/auth/me", headers=headers(session["access_token"])).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "alice", "password": PASSWORD}).status_code == 401
    assert login(client, password="Changed-password-123")["user"]["username"] == "alice"


@pytest.mark.parametrize("method,path,payload", [
    ("post", "/api/v1/signs/register", SIGN),
    ("post", "/api/v1/revalidation/missing-id", {"action": "report_removed"}),
    ("get", "/api/v1/revalidation/duplicates", None),
    ("get", "/api/v1/revalidation/pending", None),
    ("get", "/api/v1/admin/users", None),
])
def test_user_cannot_call_management_endpoints(client, method, path, payload):
    register(client)
    response = client.request(method, path, headers=headers(login(client)["access_token"]), json=payload)
    assert response.status_code == 403
    assert client.request(method, path, json=payload).status_code == 401


def test_admin_role_changes_apply_to_existing_session_and_are_audited(client, application):
    admin = administrator(client, application)
    account = register(client)
    auth = headers(login(client)["access_token"])
    assert client.get("/api/v1/revalidation/duplicates", headers=auth).status_code == 403
    url = f"/api/v1/admin/users/{account['id']}"
    assert client.patch(url, headers=headers(admin["access_token"]), json={"role": "manager"}).status_code == 200
    assert client.get("/api/v1/revalidation/duplicates", headers=auth).status_code == 200
    assert client.get("/api/v1/admin/users", headers=auth).status_code == 403
    assert client.patch(url, headers=headers(admin["access_token"]), json={"role": "user"}).status_code == 200
    assert client.get("/api/v1/revalidation/duplicates", headers=auth).status_code == 403
    with application.state.session_factory() as db:
        audits = db.query(AccountAudit).all()
        assert len(audits) == 2
        assert all(audit.actor_id == admin["user"]["id"] for audit in audits)
        assert json.loads(audits[0].details)["after"]["role"] == "manager"


def test_disabled_account_sessions_do_not_return_after_reactivation(client, application):
    admin = administrator(client, application)
    account = register(client)
    old = login(client)
    url = f"/api/v1/admin/users/{account['id']}"
    admin_headers = headers(admin["access_token"])
    assert client.patch(url, headers=admin_headers, json={"is_active": False}).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers(old["access_token"])).status_code == 401
    assert client.patch(url, headers=admin_headers, json={"is_active": True}).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers(old["access_token"])).status_code == 401
    assert login(client)["user"]["is_active"] is True


def test_admin_list_is_paginated_does_not_expose_secrets_and_owner_is_protected(client, application):
    admin = administrator(client, application)
    register(client)
    auth = headers(admin["access_token"])
    response = client.get("/api/v1/admin/users?limit=1&offset=1", headers=auth)
    assert response.status_code == 200 and response.json()["total"] == 2
    assert len(response.json()["items"]) == 1
    assert all(secret not in response.text for secret in ["password_hash", "token_hash", "credential_version", PASSWORD])
    assert client.patch(f"/api/v1/admin/users/{admin['user']['id']}", headers=auth, json={"is_active": False}).status_code == 403
    assert client.patch(f"/api/v1/admin/users/{admin['user']['id']}", headers=auth, json={"role": "user"}).status_code == 403


def test_admin_cannot_grant_admin_or_activate_passwordless_legacy_account(client, application):
    admin = administrator(client, application)
    account = register(client)
    auth = headers(admin["access_token"])
    url = f"/api/v1/admin/users/{account['id']}"
    assert client.patch(url, headers=auth, json={"role": "admin"}).status_code == 422
    assert client.patch(url, headers=auth, json={}).status_code == 422
    with application.state.session_factory() as db:
        old = User(username="legacy", email="legacy@example.com", role="user", password_hash=None, is_active=False)
        db.add(old); db.commit(); db.refresh(old)
        legacy_id = old.id
    assert client.patch(f"/api/v1/admin/users/{legacy_id}", headers=auth, json={"is_active": True}).status_code == 409


def test_management_writes_use_server_identity_and_history_is_scoped(client, application):
    result = manager(client, application)
    auth = headers(result["access_token"])
    forged = client.post("/api/v1/signs/register", headers=auth, json={**SIGN, "created_by": "someone-else"})
    assert forged.status_code == 422
    response = client.post("/api/v1/signs/register", headers=auth, json=SIGN)
    assert response.status_code == 200, response.text
    record = response.json()
    assert record["created_by"] == result["user"]["id"]
    assert client.post(f"/api/v1/revalidation/{record['id']}", headers=auth, json={
        "action": "confirm_existing", "confirmed_by": "someone-else",
    }).status_code == 422
    assert client.post(f"/api/v1/revalidation/{record['id']}", headers=auth, json={"action": "confirm_existing"}).status_code == 200
    with application.state.session_factory() as db:
        event = db.query(ConfirmationEvent).one()
        assert event.confirmed_by == result["user"]["id"]
    assert len(client.get("/api/v1/me/contributions", headers=auth).json()) == 1
    register(client)
    assert client.get("/api/v1/me/contributions", headers=headers(login(client)["access_token"])).json() == []


@pytest.mark.parametrize("change", [{"predicted_class": 10}, {"confidence": 1.5}, {"latitude": 91}, {"status": "active"}])
def test_invalid_manual_record_is_not_written(client, application, change):
    auth = headers(manager(client, application)["access_token"])
    assert client.post("/api/v1/signs/register", headers=auth, json={**SIGN, **change}).status_code == 422
    with application.state.session_factory() as db:
        assert db.query(SignRecord).count() == 0


def test_registration_transaction_rolls_back_when_duplicate_check_fails(client, application, monkeypatch):
    auth = headers(manager(client, application)["access_token"])
    def fail(*args, **kwargs):
        raise RuntimeError("duplicate lookup unavailable")
    monkeypatch.setattr("backend.app.api.v1.endpoints.signs.check_and_create_duplicate_candidates", fail)
    with pytest.raises(RuntimeError, match="duplicate lookup"):
        client.post("/api/v1/signs/register", headers=auth, json=SIGN)
    with application.state.session_factory() as db:
        assert db.query(SignRecord).count() == 0


def test_form_login_swagger_security_and_non_caching_headers(client):
    register(client)
    response = client.post("/api/v1/auth/token", data={"username": "alice", "password": PASSWORD})
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    auth = headers(response.json()["access_token"])
    assert client.get("/api/v1/auth/me", headers=auth).headers["Cache-Control"] == "no-store"
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/api/v1/signs/register"]["post"]["security"]
    assert schema["paths"]["/api/v1/signs/register"]["post"]["deprecated"]


def test_login_and_token_share_rate_limit(client):
    for _ in range(20):
        assert client.post("/api/v1/auth/login", json={"username": "missing", "password": PASSWORD}).status_code == 401
    response = client.post("/api/v1/auth/token", data={"username": "missing", "password": PASSWORD})
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0


def test_foreign_keys_enabled(application, client):
    with application.state.session_factory() as db:
        db.add(AuthSession(token_hash="0" * 64, user_id="missing", credential_version=0, expires_at=datetime.utcnow()))
        with pytest.raises(IntegrityError):
            db.commit()


def test_bootstrap_is_explicit_and_cannot_be_repeated(client, application):
    admin = bootstrap_admin("owner", "owner@example.com", PASSWORD, application.state.session_factory)
    assert admin.role == "admin"
    with pytest.raises(ValueError, match="already exists"):
        bootstrap_admin("other", "other@example.com", PASSWORD, application.state.session_factory)


def test_web_served_from_backend_and_cors_is_explicit(client):
    html = client.get("/web/index.html")
    assert html.status_code == 200 and 'id="login-form"' in html.text
    assert client.get("/web/auth.js").status_code == 200
    allowed = client.options("/api/v1/auth/login", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    })
    assert allowed.status_code == 200
    assert allowed.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    denied = client.options("/api/v1/auth/login", headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"})
    assert denied.status_code == 400 and "Access-Control-Allow-Origin" not in denied.headers
