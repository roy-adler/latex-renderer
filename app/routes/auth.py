"""Authentication endpoints: register, login, me."""

import re
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from database import create_user, get_user_by_email
from auth import hash_password, verify_password, create_token, require_user
from ratelimit import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthBody(BaseModel):
    email: str
    password: str


@router.post("/register")
@limiter.limit("5/minute")
async def register(request: Request, body: AuthBody):
    if not EMAIL_RE.match(body.email):
        raise HTTPException(400, "Invalid email format")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    pw_hash = hash_password(body.password)
    user = create_user(body.email.lower().strip(), pw_hash)
    if user is None:
        raise HTTPException(409, "Email already registered")
    token = create_token(user["id"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"]}}


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: AuthBody):
    user = get_user_by_email(body.email.lower().strip())
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user["id"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"]}}


@router.get("/me")
async def me(request: Request):
    user = require_user(request)
    return {"id": user["id"], "email": user["email"]}
