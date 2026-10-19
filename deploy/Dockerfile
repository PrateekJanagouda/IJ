# One container for the hosted demo: Next.js on $PORT (public), Django on 127.0.0.1:8000
# (private). The browser and the Android app only ever talk to Next, which proxies /api to
# Django, so session and CSRF cookies stay same-origin. Build from the repo root:
#   docker build -f deploy/Dockerfile .

FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Rewrites are baked in at build time; Django runs next to Next inside the container.
ENV BACKEND_URL=http://127.0.0.1:8000 NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 NEXT_TELEMETRY_DISABLED=1
COPY --from=web /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY backend/ backend/
COPY --from=web /web/.next/standalone/ web/
COPY --from=web /web/.next/static/ web/.next/static/
COPY deploy/start.sh start.sh
RUN useradd --create-home --uid 1000 equra && chmod +x start.sh
USER equra
ENV PORT=10000
EXPOSE 10000
CMD ["./start.sh"]
