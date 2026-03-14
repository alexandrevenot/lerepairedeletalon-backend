# Builder
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /srv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

COPY app/ ./app/

RUN uv sync --frozen --no-dev

# Runtime
FROM python:3.11-slim AS runtime

WORKDIR /srv

COPY --from=builder /srv/.venv /srv/.venv
COPY --from=builder /srv/app /srv/app

ENV PATH="/srv/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p /srv/logs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]