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
COPY static/ ./static/
COPY generate_config.py ./generate_config.py

ENV PORT=8080
ENV DATABASE_PATH=/data/data.db
ENV DASHBOARD_USERNAME=admin
ENV DASHBOARD_PASSWORD=change-me-in-production
ENV DASHBOARD_MONITOR_LEVEL=3
ENV DASHBOARD_DB_PATH=sqlite:///monitoring/monitoring.db

EXPOSE 8080
VOLUME /data

# Create monitoring directory, generate config, then start gunicorn
CMD mkdir -p /app/monitoring && python generate_config.py && gunicorn -k gthread --workers 1 --threads 8 --timeout 120 --keep-alive 75 --access-logfile - --error-logfile - --capture-output -b 0.0.0.0:8080 src.main:app