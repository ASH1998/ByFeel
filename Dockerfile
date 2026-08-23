FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    BYFEEL_ALLOW_LOCAL_RAW_VIDEO=0 \
    BYFEEL_RUN_ROOT=/tmp/byfeel

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend
RUN uv sync --frozen --no-dev --no-editable

USER 65532:65532

EXPOSE 8080

CMD ["sh", "-c", "exec .venv/bin/uvicorn byfeel.api:app --host 0.0.0.0 --port \"${PORT:-8080}\" --workers 1"]
