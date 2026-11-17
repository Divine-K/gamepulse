# syntax=docker/dockerfile:1
# --- build stage: install dependencies into a virtualenv ---------------------------------
FROM python:3.13-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.txt

# --- runtime stage: small image, non-root user -------------------------------------------
FROM python:3.13-slim
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN useradd --system --uid 10001 --create-home gamepulse
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=gamepulse:gamepulse alembic.ini ./
COPY --chown=gamepulse:gamepulse alembic ./alembic
COPY --chown=gamepulse:gamepulse app ./app
COPY --chown=gamepulse:gamepulse docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh
USER gamepulse
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8000'), timeout=3)"
ENTRYPOINT ["./docker-entrypoint.sh"]
