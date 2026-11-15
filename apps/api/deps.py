"""Request dependencies: the shared runtime and the signed-in account (the tenant)."""

from typing import Annotated

from fastapi import Depends, Path, Request

from apps.api.auth.users import session_account
from apps.api.errors import ApiError
from apps.api.runtime import Runtime

SESSION_COOKIE = "gigbid_session"
# A graph thread id: <account>:<kind>:<subject> (apps/api/services/runs.py).
ThreadId = Path(min_length=1, max_length=200, pattern=r"^[a-z0-9_]+:[a-z]+:[A-Za-z0-9_:~-]+$")


def get_runtime(request: Request) -> Runtime:
    return request.app.state.runtime


def current_account(request: Request) -> str:
    account = session_account(request.cookies.get(SESSION_COOKIE, ""))
    if account is None:
        raise ApiError(401, "unauthenticated", "Sign in first.")
    return account


RuntimeDep = Annotated[Runtime, Depends(get_runtime)]
AccountDep = Annotated[str, Depends(current_account)]
