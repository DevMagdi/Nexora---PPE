# Nexora — Real-Time Multi-Sector PPE Compliance Platform

**Nexora** is a full-stack, real-time Personal Protective Equipment (PPE) compliance monitoring platform built for **Construction Sites / Industrial Facilities** and **Medical / Healthcare Environments**.

Nexora connects to existing cameras (**RTSP / IP cameras, Webcams, or Video Files**), runs real-time AI detection using dedicated **Ultralytics YOLO** models per sector, streams annotated MJPEG feeds and live WebSocket telemetry to an Arabic RTL React dashboard, and dispatches instant alerts via **Database, Email (SMTP), Slack, and Webhooks**.

![Nexora Dashboard](Visuals/ppe-public-view.png)

---

## Key Features

- **Multi-Sector AI Engine (`construction` + `medical`):**
  - **Construction Profile (`Model/ppe.pt`):** Detects `Person`, `Hardhat` / `NO-Hardhat`, `Safety Vest` / `NO-Safety Vest`, `Mask` / `NO-Mask`, `Gloves` / `NO-Gloves`, `Safety Boots` / `NO-Safety Boots`, and `Goggles` / `NO-Goggles` with person-bounding-box IoU association.
  - **Medical Profile (`Model/bestMedicalModel2.pt`):** Detects `mask` / `no mask`, `hand gloves` / `no hand gloves`, `head cap` / `no head cap`, `goggle` / `no goggle`, `lab coat`, `full cover`, and `shoe cover` with grace-period debouncing.
- **Per-Camera Custom Monitoring Rules:** Configure which PPE items are required on each camera independently and update rules on the fly without restarting the stream.
- **Role/Sector Access Control (JWT Auth):** Users can be scoped to `construction`, `medical`, or `both` (general administration), isolating cameras, streams, frames, and violation exports by sector.
- **Live Streaming & Telemetry:**
  - Authenticated **MJPEG** video streaming (`/api/v1/stream/{camera_id}`) with frame-sequence deduplication.
  - Real-time **WebSocket** live detection counters (`/api/v1/ws/{camera_id}`).
- **Multi-Channel Alert Dispatcher:** Parallel, fault-isolated alert delivery to Database (`violations` + `alert_log`), SMTP Email (with violation frame attachment), Slack Webhook, and Generic HTTP Webhook.
- **Modern RTL Arabic Dashboard:** Built with **React 19, TypeScript, Tailwind CSS v4, Radix UI, TanStack Query, and Recharts**, featuring dark/light themes, live compliance rings, time-series analytics, camera management, and CSV export.

---

## Project Structure

```text
Nexora---PPE/
├── app/
│   ├── alerts/            # AlertHandler ABC, AlertDispatcher, Email, Slack & Webhook handlers
│   ├── api/routes/        # FastAPI routers: auth, cameras, violations, stream, meta, health
│   ├── camera/            # CameraManager & sources (RTSP, Webcam, Video File)
│   ├── core/              # Settings, JWT Auth, PPEDetector, ViolationCheckers, FrameAnnotator
│   ├── db/                # SQLAlchemy 2.0 Async models, session, and repository helpers
│   ├── schemas/           # Pydantic v2 request/response schemas
│   └── main.py            # FastAPI application factory, lifespan, and SPA static serving
├── frontend/              # React 19 + TypeScript + Vite + Tailwind CSS v4 dashboard
├── migrations/            # Alembic database migrations (SQLite, PostgreSQL, SQL Server)
├── Model/                 # Bundled YOLO weights (ppe.pt, bestMedicalModel2.pt)
├── docker/                # Multi-stage production Dockerfile & development Dockerfile.dev
├── tests/                 # Unit and integration test suites (pytest + httpx AsyncClient)
├── docker-compose.yml     # Production stack (FastAPI + React SPA + PostgreSQL 16)
└── docker-compose.dev.yml # Development stack with hot-reload (FastAPI + Vite dev server)
```

---

## Quick Start

### 1. Local Development (`dev`)

#### Backend (FastAPI)

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy environment configuration
cp .env.example .env

# 4. Run database migrations (optional — tables are also auto-created on startup)
alembic upgrade head

# 5. Start the API server with hot-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **API Docs (Swagger UI):** `http://localhost:8000/docs`
- **Health Check:** `http://localhost:8000/api/v1/health`

#### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

- Open `http://localhost:5173` (Vite proxies `/api` and `/frames` to `http://127.0.0.1:8000`, including WebSockets).
- Default bootstrap credentials (configurable in `.env`): `admin` / `admin123`.

---

### 2. Production Deployment (`prod`)

#### Option A: Docker Compose (Recommended)

The production `docker/Dockerfile` uses a multi-stage build that compiles the React frontend (`frontend/dist`) and serves both the UI and API from FastAPI alongside PostgreSQL 16:

```bash
cp .env.example .env
# Edit .env and set strong values for JWT_SECRET and BOOTSTRAP_PASSWORD
docker compose up --build -d
```

Then open `http://localhost:8000`.

For development with Docker (hot-reloading Backend on `:8000` + Vite Dev Server on `:5173`):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

#### Option B: Unified Bare-Metal Production Server

If you build the frontend once (`cd frontend && npm run build`), FastAPI automatically detects `frontend/dist` and serves the full React SPA and API on port `8000`:

```bash
cd frontend && npm ci && npm run build && cd ..
APP_ENV=prod uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

*(Note: Use `--workers 1` when running `CameraManager` in-process so camera tasks and WebSocket state are managed by a single coordinator process).*

---

## Environment Variables Reference (`.env`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `APP_ENV` | `dev` | Environment mode (`dev`, `staging`, `prod`) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./ppe_detection.db` | Async SQLAlchemy connection URL (`sqlite+aiosqlite`, `postgresql+asyncpg`, `mssql+aioodbc`) |
| `JWT_SECRET` | `CHANGE_ME_SUPER_SECRET` | Secret key used to sign JWT access tokens |
| `BOOTSTRAP_USERNAME` | `admin` | Initial admin username created when `users` table is empty |
| `BOOTSTRAP_PASSWORD` | `admin123` | Initial admin password |
| `BOOTSTRAP_SECTOR` | `construction` | Initial user sector (`construction`, `medical`, `both`) |
| `CONSTRUCTION_MODEL_PATH` | `Model/ppe.pt` | Path to YOLO weights for construction cameras |
| `MEDICAL_MODEL_PATH` | `Model/bestMedicalModel2.pt` | Path to YOLO weights for medical cameras |
| `ALERT_COOLDOWN_SECONDS` | `60` | Minimum seconds between repeated alerts for the same PPE type per camera |
| `VIOLATION_PERSIST_SECONDS` | `8` | Seconds a construction PPE violation must persist before triggering an alert |
| `MEDICAL_VIOLATION_PERSIST_SECONDS` | `3` | Seconds a medical PPE violation must persist before triggering an alert |
| `ALLOWED_RTSP_PREFIXES` | *(empty)* | Comma-separated allowlist of RTSP prefixes (e.g. `rtsp://192.168.1.`) |
| `ALLOWED_VIDEO_DIR` | *(empty)* | Restrict `file` camera sources to paths inside this directory |
| `SENDER_EMAIL` / `RECEIVER_EMAIL` / `EMAIL_PASSWORD` | *(empty)* | SMTP credentials for email alerts |
| `SLACK_WEBHOOK_URL` / `WEBHOOK_URL` | *(empty)* | Optional Slack or generic HTTP webhook URLs |

---

## Testing & Code Quality

```bash
# Backend Linting (Ruff)
ruff check app tests migrations train.py

# Backend Unit & Integration Tests (Pytest)
pytest

# Frontend Linting (Oxlint) & Production Build Check (TypeScript + Vite)
cd frontend
npm run lint
npm run build
```

---

## License

Released under the [MIT License](LICENSE).
