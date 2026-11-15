"""Runs: list, detail, the live stream, and retrying a run that stopped on an error."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from apps.api.deps import AccountDep, RuntimeDep, ThreadId
from apps.api.schemas.runs import RunDetail, RunKind, RunList, RunRef
from apps.api.services import profiles, runs
from apps.api.streaming import open_run_stream

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=RunList)
async def list_runs(account: AccountDep, rt: RuntimeDep, kind: RunKind = "bid") -> RunList:
    return RunList(runs=await runs.summaries(rt, account, kind))


@router.get("/{thread_id}", response_model=RunDetail)
async def get_run(account: AccountDep, rt: RuntimeDep, thread_id: str = ThreadId) -> RunDetail:
    return await runs.detail(rt, account, thread_id)


@router.get("/{thread_id}/stream", response_class=StreamingResponse,
            responses={200: {"content": {"text/event-stream": {}}}})
async def stream_run(account: AccountDep, rt: RuntimeDep,
                     thread_id: str = ThreadId) -> StreamingResponse:
    events = await open_run_stream(rt, account, thread_id)
    # no-transform: a compressing proxy (Next.js gzip) would otherwise buffer the whole stream.
    return StreamingResponse(events, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform",
                                      "X-Accel-Buffering": "no"})


@router.post("/{thread_id}/retry", response_model=RunRef, status_code=202)
async def retry(account: AccountDep, rt: RuntimeDep, thread_id: str = ThreadId) -> RunRef:
    persona = await profiles.persona_of(rt, account)
    return await runs.retry(rt, account, persona, thread_id)
