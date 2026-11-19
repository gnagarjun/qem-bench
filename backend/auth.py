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
MAX_FAILS, GLOBAL_FAILS, LOCK_MIN = 5, 20, 15
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
    # per-client counter plus a global one, since forwarded IPs can be spoofed
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    now = datetime.now(timezone.utc)
    limits = {ip: MAX_FAILS, "__global__": GLOBAL_FAILS}
    recs = {r["identifier"]: r async for r in db.login_attempts.find({"identifier": {"$in": list(limits)}})}
    for rec in recs.values():
        if rec.get("locked_until") and rec["locked_until"].replace(tzinfo=timezone.utc) > now:
            raise HTTPException(429, f"Too many failed attempts. Try again in {LOCK_MIN} minutes.")
    if not bcrypt.checkpw(body.password.encode(), _HASH):
        for ident, limit in limits.items():
            fails = recs.get(ident, {}).get("fails", 0) + 1
            locked = fails >= limit
            await db.login_attempts.update_one({"identifier": ident}, {"$set": {
                "fails": 0 if locked else fails, "locked_until": now + timedelta(minutes=LOCK_MIN) if locked else None}}, upsert=True)
        raise HTTPException(401, "Wrong password")
    await db.login_attempts.update_many({"identifier": {"$in": list(limits)}}, {"$set": {"fails": 0, "locked_until": None}})
    return {"token": make_token()}


@router.get("/me")
def me(owner: str = Depends(require_owner)):
    return {"role": owner}
