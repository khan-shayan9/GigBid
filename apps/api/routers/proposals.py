"""Proposal studio: rewrite one paragraph of a draft, grounded in the draft's evidence."""

from fastapi import APIRouter

from apps.api.deps import AccountDep, RuntimeDep, ThreadId
from apps.api.schemas.runs import RegenerateIn, RegenerateOut
from apps.api.services import runs

router = APIRouter(prefix="/runs", tags=["proposals"])


@router.post("/{thread_id}/regenerate", response_model=RegenerateOut)
async def regenerate(body: RegenerateIn, account: AccountDep, rt: RuntimeDep,
                     thread_id: str = ThreadId) -> RegenerateOut:
    return RegenerateOut(paragraph=await runs.regenerate(rt, account, thread_id, body.paragraph))
