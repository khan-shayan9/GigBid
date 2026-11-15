from fastapi import APIRouter, Path

from apps.api.deps import AccountDep, RuntimeDep
from apps.api.schemas.app import MessageThreads
from apps.api.schemas.runs import RunRef
from apps.api.services import messages

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=MessageThreads)
async def threads(account: AccountDep, rt: RuntimeDep) -> MessageThreads:
    return await messages.threads(rt, account)


@router.post("/{message_id}/reply", response_model=RunRef, status_code=202)
async def draft_reply(account: AccountDep, rt: RuntimeDep,
                      message_id: str = Path(min_length=1, max_length=100,
                                             pattern=r"^[A-Za-z0-9_:~-]+$")) -> RunRef:
    return await messages.draft_reply(rt, account, message_id)
