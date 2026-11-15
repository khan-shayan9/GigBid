"""The central error handler: every error leaves as {"detail": {"code", "message"}}.

Unexpected failures are logged with the trace id and PII masked; users never see stack traces.
"""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agent.mcp_client import ToolFailed, ToolUnavailable
from data.pipeline.pii import mask_pii

log = logging.getLogger("gigbid.api")
MARKETPLACE_DOWN = "The marketplace is unavailable. Your work is kept; try again shortly."


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _reply(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"detail": {"code": code, "message": message}}, status_code=status)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_: Request, error: ApiError) -> JSONResponse:
        return _reply(error.status, error.code, error.message)

    @app.exception_handler(ToolUnavailable)
    async def unavailable(_: Request, error: ToolUnavailable) -> JSONResponse:
        log.warning("dependency unavailable: %s", mask_pii(str(error)))
        return _reply(503, "marketplace_unavailable", MARKETPLACE_DOWN)

    @app.exception_handler(ToolFailed)
    async def refused(_: Request, error: ToolFailed) -> JSONResponse:
        code = str(error).split(":", 1)[0]
        status = 404 if code == "not_found" else 400
        return _reply(status, code, mask_pii(str(error)))

    @app.exception_handler(Exception)
    async def unexpected(_: Request, error: Exception) -> JSONResponse:
        trace_id = uuid.uuid4().hex
        log.error("unexpected error %s: %s", trace_id, mask_pii(repr(error)))
        return _reply(500, "internal_error", f"Something went wrong (trace {trace_id}).")
