# syntax=docker/dockerfile:1
# QEM-Bench production image: React viewer + FastAPI API + Qiskit Aer simulator in one container.

FROM node:20-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 600000
COPY frontend/ ./
# Empty backend URL: the browser calls /api on the same origin that served the page.
ENV REACT_APP_BACKEND_URL="" \
    GENERATE_SOURCEMAP=false \
    DISABLE_EMERGENT_OVERLAY=true
RUN yarn build

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    QEM_VIEWER_DATA_DIR=viewer_data \
    QEM_BENCH_DIR=../qem-bench \
    QEM_RUNS_DIR=/tmp/qem_runs \
    FRONTEND_BUILD_DIR=../frontend_build \
    PORT=8000
WORKDIR /srv/backend
COPY backend/requirements.prod.txt ./
RUN pip install --no-cache-dir -r requirements.prod.txt
COPY backend/*.py ./
COPY backend/viewer_data ./viewer_data
COPY qem-bench/pyproject.toml /srv/qem-bench/pyproject.toml
COPY qem-bench/src /srv/qem-bench/src
COPY qem-bench/scripts /srv/qem-bench/scripts
COPY qem-bench/configs /srv/qem-bench/configs
COPY --from=frontend /build/build /srv/frontend_build
RUN useradd --create-home --uid 10001 app && mkdir -p /tmp/qem_runs && chown -R app /tmp/qem_runs
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health')"
# One worker on purpose: the "one run at a time" guard and run tracking live in this process.
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips '*'"]
