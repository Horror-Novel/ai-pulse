from datetime import datetime, timedelta, timezone
import hashlib

import jwt
import pytest

from app import models
from app.auth import hash_password, verify_password, SECRET_KEY
from tests.conftest import login

NW = "Northwind Logistics"
BP = "Bluepeak Retail"


def test_employee_and_multi_org_roles(client):
    employee, data = login(client, "priya@northwind.test", NW)
    nw_id = data["organizations"][0]["org_id"]
    assert client.get(f"/dashboard?org_id={nw_id}", headers=employee).status_code == 403
    ravi_nw, data = login(client, "ravi@consult.test", NW)
    ravi_bp, _ = login(client, "ravi@consult.test", BP)
    bp_id = next(o["org_id"] for o in data["organizations"] if o["org_name"] == BP)
    assert client.get(f"/dashboard?org_id={nw_id}", headers=ravi_nw).status_code == 403
    assert client.get(f"/dashboard?org_id={bp_id}", headers=ravi_bp).status_code == 200
    assert client.get(f"/dashboard?org_id={nw_id}", headers=ravi_bp).status_code == 403
    assert client.get(f"/dashboard?org_id={bp_id}", headers=ravi_nw).status_code == 403


def test_org_selection_and_membership_revocation(client, db):
    headers, _ = login(client, "asha@northwind.test", NW)
    assert client.post("/auth/select-org", headers=headers, json={"org_id": 2}).status_code == 403
    m = db.query(models.Membership).join(models.User).filter(models.User.email == "asha@northwind.test").one()
    db.delete(m)
    db.commit()
    assert client.get("/diagnostic/questions", headers=headers).status_code == 403


@pytest.mark.parametrize("path,method", [
    ("/diagnostic/questions", "get"), ("/diagnostic/submit", "post"),
    ("/diagnostic/me", "delete"), ("/diagnostic/me/export", "get"),
    ("/reports/me", "get"), ("/dashboard?org_id=1", "get"),
])
def test_all_private_endpoints_require_auth(client, path, method):
    assert getattr(client, method)(path).status_code == 401


@pytest.mark.parametrize("claims", [
    {"sub": "1"}, {"sub": "not-an-id", "exp": 9_999_999_999},
    {"sub": "1", "org": True, "exp": 9_999_999_999},
    {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
])
def test_invalid_jwt_claims_fail_safely(client, claims):
    token = jwt.encode(claims, SECRET_KEY, algorithm="HS256")
    assert client.get("/reports/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_unscoped_and_forged_tokens(client):
    headers, _ = login(client, "priya@northwind.test")
    assert client.get("/reports/me", headers=headers).status_code == 400
    forged = jwt.encode({"sub": "1", "org": 1, "exp": 9_999_999_999}, "wrong-key-that-is-long-enough-for-hmac-sha256", algorithm="HS256")
    assert client.get("/reports/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_password_hashing_and_legacy_upgrade(client, db):
    a, b = hash_password("secret"), hash_password("secret")
    assert a != b
    assert verify_password("secret", a)
    assert not verify_password("wrong", a)
    user = db.query(models.User).filter_by(email="priya@northwind.test").one()
    user.password_hash = hashlib.sha256(b"pulse123").hexdigest()
    db.commit()
    login(client, user.email, NW)
    db.refresh(user)
    assert user.password_hash.startswith("pbkdf2_sha256$")


def test_wrong_password_and_no_cache(client):
    assert client.post("/auth/login", json={"email": "priya@northwind.test", "password": "bad"}).status_code == 401
    headers, _ = login(client, "priya@northwind.test", NW)
    assert client.get("/reports/me", headers=headers).headers["cache-control"] == "no-store"


def test_seeded_passwords_have_individual_salts(db):
    hashes = [u.password_hash for u in db.query(models.User).all()]
    assert len(set(hashes)) == len(hashes)
