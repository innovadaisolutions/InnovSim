FROM node:22-alpine AS web
WORKDIR /build/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AW_DATABASE_PATH=/data/workbench.db AW_WEB_DIST=/app/web/dist
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps . && useradd --create-home --uid 10001 workbench && mkdir -p /data && chown workbench:workbench /data
COPY --from=web /build/web/dist ./web/dist
USER workbench
EXPOSE 8787
CMD ["python", "-m", "agent_workbench", "serve", "--host", "0.0.0.0", "--port", "8787"]
