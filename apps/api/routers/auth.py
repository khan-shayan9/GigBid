import os

from fastapi import APIRouter, Response

from agent.config import load_config
from apps.api.auth.users import check_password, new_session
from apps.api.deps import SESSION_COOKIE, AccountDep, RuntimeDep
from apps.api.errors import ApiError
from apps.api.schemas.app import LoginIn, Session
from apps.api.services import profiles

router = APIRouter(prefix="/auth", tags=["auth"])


async def _session(rt: RuntimeDep, account: str) -> Session:
    return Session(account=account, profile=await profiles.get_profile(rt, account),
                   personas=load_config()["api"]["personas"],
                   marketplace_mode=profiles.marketplace_mode(),
                   policy_version=load_config()["policy"]["version"])


@router.post("/login", response_model=Session)
async def login(body: LoginIn, response: Response, rt: RuntimeDep) -> Session:
    if not check_password(body.username, body.password):
        raise ApiError(401, "bad_credentials", "Wrong username or password.")
    hours = load_config()["api"]["session_hours"]
    response.set_cookie(SESSION_COOKIE, new_session(body.username, hours),
                        max_age=int(hours * 3600), httponly=True, samesite="lax",
                        secure=os.environ.get("APP_ENV") == "production")
    return await _session(rt, body.username)


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE)


@router.get("/session", response_model=Session)
async def session(account: AccountDep, rt: RuntimeDep) -> Session:
    return await _session(rt, account)
