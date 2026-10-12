# ── Stage 1: Build React Frontend ─────────────────────────────
FROM node:22-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python FastAPI + YOLO Runtime ────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache)
COPY requirements/prod.txt requirements/base.txt requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

# Copy backend code, migrations, and models
COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini ./
COPY Model/ppe.pt Model/bestMedicalModel_FINAL.pt Model/

# Copy built React SPA from Stage 1
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

# Runtime storage owned by the non-root app user; production mounts named volumes here.
RUN mkdir -p /app/violation_frames /var/nexora/backups /var/nexora/videos \
    && useradd -u 1000 -m appuser \
    && chown -R appuser:appuser /app /var/nexora
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
