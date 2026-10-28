from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..auth import verify_password, hash_password, make_token, current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    email: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=1024)


class SelectOrgIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    org_id: int = Field(gt=0)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    if not user.password_hash.startswith("pbkdf2_sha256$"):
        user.password_hash = hash_password(body.password)
        db.commit()
    orgs = [
        {"org_id": m.org_id, "org_name": m.org.name, "role": m.role}
        for m in user.memberships
    ]
    return {"token": make_token(user.id), "name": user.name, "organizations": orgs}


@router.post("/select-org")
def select_org(body: SelectOrgIn, user: models.User = Depends(current_user)):
    # Issue a token scoped to the chosen organization
    if not any(m.org_id == body.org_id for m in user.memberships):
        raise HTTPException(403, "Not a member of this organization")
    return {"token": make_token(user.id, body.org_id), "org_id": body.org_id}
