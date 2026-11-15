"""Approvals: approve, edit or reject a paused run. Each answer resumes the graph thread."""

from fastapi import APIRouter

from apps.api.deps import AccountDep, RuntimeDep, ThreadId
from apps.api.schemas.runs import ResumeIn, RunRef
from apps.api.services import profiles, runs

router = APIRouter(prefix="/runs", tags=["approvals"])


@router.post("/{thread_id}/resume", response_model=RunRef, status_code=202)
async def resume(body: ResumeIn, account: AccountDep, rt: RuntimeDep,
                 thread_id: str = ThreadId) -> RunRef:
    persona = await profiles.persona_of(rt, account)
    return await runs.resume(rt, account, persona, thread_id, body)
