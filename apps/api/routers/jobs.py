from fastapi import APIRouter, Path

from apps.api.deps import AccountDep, RuntimeDep
from apps.api.schemas.app import Inbox
from apps.api.schemas.runs import RunRef
from apps.api.services import jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])
JobId = Path(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_:~-]+$")


@router.get("", response_model=Inbox)
async def inbox(account: AccountDep, rt: RuntimeDep) -> Inbox:
    return await jobs.inbox(rt, account)


@router.post("/{job_id}/skip", status_code=204)
async def skip(account: AccountDep, rt: RuntimeDep, job_id: str = JobId) -> None:
    await jobs.skip(rt, account, job_id)


@router.post("/{job_id}/analyse", response_model=RunRef, status_code=202)
async def analyse(account: AccountDep, rt: RuntimeDep, job_id: str = JobId) -> RunRef:
    return await jobs.analyse(rt, account, job_id)
