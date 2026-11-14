FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

EXPOSE 8081
# One worker only: the rate limiter and fault attempt counts live in process memory.
CMD ["sh", "-c", "uvicorn --factory gigsim.app:create_app --host 0.0.0.0 --port ${PORT:-8081} --workers 1"]
