# Build React
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Python API + serve static
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY src/ ./src/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

ENV PORT=8080
ENV DATABASE_PATH=/data/data.db
EXPOSE 8080
VOLUME /data

CMD ["gunicorn", "-k", "gthread", "--workers", "1", "--threads", "8", "--timeout", "120", "--keep-alive", "75", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "-b", "0.0.0.0:8080", "src.main:app"]
#claude --resume 3bbdaa93-3843-45ad-ba5a-4fcf5264c775