# syntax=docker/dockerfile:1@sha256:87999aa3d42bdc6bea60565083ee17e86d1f3339802f543c0d03998580f9cb89
FROM python:3.14.6-slim-bookworm@sha256:86f975aca15cf04a40b399eebede9aea7c82eae084d1f1a0a6ef6bcaae871a30

LABEL org.opencontainers.image.title="Intelligent Predictive Maintenance and Technical Knowledge Assistant" \
      org.opencontainers.image.description="Bounded local demonstration image for reproducible execution; not a public production deployment"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin appuser \
    && mkdir -p \
        /app/outputs \
        /app/data/interim/knowledge/retrieval \
        /app/data/interim/application \
    && chown -R appuser:appuser /app

COPY --chown=appuser:appuser requirements.txt /app/requirements.txt
COPY --chown=appuser:appuser requirements-container.txt /app/requirements-container.txt
RUN python -m pip install --no-cache-dir --root-user-action=ignore --requirement /app/requirements-container.txt

COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser config/ /app/config/

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=4s --start-period=20s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3).read()"]

# Uvicorn binds all interfaces only inside the isolated container namespace.
# compose.yaml publishes the port exclusively on host loopback 127.0.0.1.
CMD ["python", "-m", "uvicorn", "predictive_maintenance.application.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
