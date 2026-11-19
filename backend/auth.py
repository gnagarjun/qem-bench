"""Single-owner password login: JWT bearer tokens guard the endpoints that start simulations."""

import hmac
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

ALG = "HS256"
MAX_FAILS, LOCK_MIN = 5, 15
router = APIRouter(prefix="/api/auth")
bearer = HTTPBearer(auto_error=False)
_HASH = bcrypt.hashpw(os.environ["ADMIN_PASSWORD"].encode(), bcrypt.gensalt())
db = None


class Login(BaseModel):
    password: str


def make_token() -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=12)
    return jwt.encode({"sub": "owner", "type": "access", "exp": exp}, os.environ["JWT_SECRET"], algorithm=ALG)


def require_owner(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    if not cred:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(cred.credentials, os.environ["JWT_SECRET"], algorithms=[ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired, please sign in again")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    if payload.get("type") != "access" or not hmac.compare_digest(payload.get("sub", ""), "owner"):
        raise HTTPException(401, "Invalid token")
    return "owner"


@router.post("/login")
async def login(body: Login, request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    now = datetime.now(timezone.utc)
    rec = await db.login_attempts.find_one({"identifier": ip})
    if rec and rec.get("locked_until") and rec["locked_until"].replace(tzinfo=timezone.utc) > now:
        raise HTTPException(429, f"Too many failed attempts. Try again in {LOCK_MIN} minutes.")
    if not bcrypt.checkpw(body.password.encode(), _HASH):
        fails = (rec or {}).get("fails", 0) + 1
        upd = {"fails": fails, "locked_until": now + timedelta(minutes=LOCK_MIN) if fails >= MAX_FAILS else None}
        if fails >= MAX_FAILS:
            upd["fails"] = 0
        await db.login_attempts.update_one({"identifier": ip}, {"$set": upd}, upsert=True)
        raise HTTPException(401, "Wrong password")
    await db.login_attempts.delete_one({"identifier": ip})
    return {"token": make_token()}


@router.get("/me")
def me(owner: str = Depends(require_owner)):
    return {"role": owner}
