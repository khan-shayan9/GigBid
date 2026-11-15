from fastapi import APIRouter, UploadFile

from agent.config import load_config
from apps.api.deps import AccountDep, RuntimeDep
from apps.api.errors import ApiError
from apps.api.schemas.app import Connections, Profile, ProfileIn, UploadOut
from apps.api.services import profiles

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=Profile)
async def get_profile(account: AccountDep, rt: RuntimeDep) -> Profile:
    return await profiles.get_profile(rt, account)


@router.put("", response_model=Profile)
async def save_profile(body: ProfileIn, account: AccountDep, rt: RuntimeDep) -> Profile:
    return await profiles.save_profile(rt, account, body)


@router.get("/connections", response_model=Connections)
async def connections(account: AccountDep, rt: RuntimeDep) -> Connections:
    return await profiles.connections(rt, account)


@router.post("/portfolio", response_model=UploadOut, status_code=201)
async def upload_portfolio(file: UploadFile, account: AccountDep, rt: RuntimeDep) -> UploadOut:
    limit = load_config()["api"]["upload_max_bytes"]
    content = await file.read(limit + 1)  # one byte over is enough to know it is too large
    if len(content) > limit:
        raise ApiError(413, "file_too_large", f"Files may be at most {limit} bytes.")
    return await profiles.upload(rt, account, file.filename or "upload", content)
