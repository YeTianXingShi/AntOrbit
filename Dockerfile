# ---- Stage 1: Build Vue 3 Admin UI ----
FROM node:22-alpine AS web-builder

WORKDIR /web
COPY web/package.json ./
RUN npm install --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---- Stage 2: Python FastAPI Runtime ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ANTORBIT_DATA_DIR=/data \
    ANTORBIT_WEB_DIST_DIR=/app/web_dist

WORKDIR /app

COPY server/pyproject.toml ./
COPY server/app ./app
RUN pip install --no-cache-dir .

COPY --from=web-builder /web/dist /app/web_dist

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
