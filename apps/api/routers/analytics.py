"""Pipeline board, analytics and the memory viewer."""

from fastapi import APIRouter, Path

from apps.api.deps import AccountDep, RuntimeDep
from apps.api.schemas.app import Analytics, MemoryList, Pipeline
from apps.api.services import insights

router = APIRouter(tags=["analytics"])


@router.get("/pipeline", response_model=Pipeline)
async def pipeline(account: AccountDep, rt: RuntimeDep) -> Pipeline:
    return await insights.pipeline(rt, account)


@router.get("/analytics", response_model=Analytics)
async def analytics(account: AccountDep, rt: RuntimeDep) -> Analytics:
    return await insights.analytics(rt, account)


@router.get("/memory", response_model=MemoryList)
async def memories(account: AccountDep, rt: RuntimeDep) -> MemoryList:
    return await insights.memories(rt, account)


@router.delete("/memory/{kind}/{item_id}", status_code=204)
async def forget(account: AccountDep, rt: RuntimeDep, kind: str = Path(max_length=20),
                 item_id: str = Path(min_length=1, max_length=200)) -> None:
    await insights.forget(rt, account, kind, item_id)
