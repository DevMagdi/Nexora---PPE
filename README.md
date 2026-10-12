# Nexora — Real-Time Multi-Sector PPE Compliance Platform

**Nexora** is a full-stack, real-time Personal Protective Equipment (PPE) compliance monitoring platform built for **Construction Sites / Industrial Facilities** and **Medical / Healthcare Environments**.

Nexora connects to existing cameras (**RTSP / IP cameras, Webcams, or Video Files**), runs real-time AI detection using dedicated **Ultralytics YOLO** models per sector, streams annotated MJPEG feeds and live WebSocket telemetry to an Arabic RTL React dashboard, and dispatches instant alerts via **Database, Email (SMTP), Slack, and Webhooks**.

![Nexora Dashboard](Visuals/ppe-public-view.png)

---

## Key Features

- **Smart Hybrid AI Engine (`construction` + `medical` fused):**
  - **Construction Model (`Model/ppe.pt`):** Detects `Person`, `Hardhat` / `NO-Hardhat`, `Safety Vest` / `NO-Safety Vest`, `Mask` / `NO-Mask`, `Gloves` / `NO-Gloves`, `Safety Boots` / `NO-Safety Boots`, and `Goggles` / `NO-Goggles` with person-bounding-box IoU association.
  - **Medical Model (`Model/bestMedicalModel.pt`):** Detects `mask` / `no mask`, `hand gloves` / `no hand gloves`, `head cap` / `no head cap`, `goggle` / `no goggle`, `lab coat`, `full cover`, and `shoe cover` with grace-period debouncing.
  - **`HybridPPEDetector` (`app/core/hybrid_detector.py`):** Runs **both** YOLO models on the same frame, normalises every class name to one canonical vocabulary (`no goggle` ≡ `NO-Goggles`), merges duplicate boxes with **cross-model confidence fusion**, resolves positive/negative conflicts, and feeds a single detection list to the existing checkers. Medical cameras finally get a `Person` class (the medical model has none), so PPE items can be associated with staff and "staff present but lab coat missing" works out of the box.
- **Smart Skin Layer (`app/core/skin_analysis.py`):** Adds deterministic OpenCV evidence on top of the models:
  - **`calc_skin_ratio`** — dual-threshold (HSV + YCrCb) skin pixel ratio per region.
  - **Bare-hand detection with `distanceTransform`** — a real bare hand is a *thick* skin blob; gloved hands and stray skin (wrists/arms/background) are not. Confirms `NO-Gloves`, downgrades fake `Gloves`, and scans for bare hands when the models report no glove box at all.
  - **Eye-bridge `NO-Goggles`** — if the strip between the eye centres (the nose bridge) is skin/eye coloured, goggles are not worn → emits `NO-Goggles`. If instead a glass/opaque band covers the eye line, `Goggles` is confirmed. Works with `haarcascade_eye` when available and with the built-in contrast eye detector on OpenCV 5 (where `cv2.CascadeClassifier` was removed).
  - Every produced/fused detection is tagged (`model:medical+skin:eye_bridge`, …) and drawn with a `[skin]` marker in the live stream, and `skin_hits` is published in the WebSocket counts.
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
│   ├── core/              # Settings, JWT Auth, PPEDetector, HybridPPEDetector, SkinAnalysis, Checkers
│   ├── db/                # SQLAlchemy 2.0 Async models, session, and repository helpers
│   ├── schemas/           # Pydantic v2 request/response schemas
│   └── main.py            # FastAPI application factory, lifespan, and SPA static serving
├── frontend/              # React 19 + TypeScript + Vite + Tailwind CSS v4 dashboard
├── migrations/            # Alembic database migrations (SQLite, PostgreSQL, SQL Server)
├── Model/                 # Bundled YOLO weights (ppe.pt, bestMedicalModel.pt)
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
| `MEDICAL_MODEL_PATH` | `Model/bestMedicalModel.pt` | Path to YOLO weights for medical cameras |
| `HYBRID_DETECTION_ENABLED` | `true` | Fuse the construction + medical models in one `HybridPPEDetector` per camera profile |
| `HYBRID_CONSTRUCTION_ON_MEDICAL` | `true` | Run the construction model alongside medical cameras (adds `Person` + association) |
| `HYBRID_MEDICAL_ON_CONSTRUCTION` | `false` | Run the medical model alongside construction cameras (mask/goggle verification, heavier) |
| `HYBRID_MERGE_IOU` / `HYBRID_CONFLICT_IOU` | `0.55` / `0.30` | Duplicate-merge and positive/negative conflict thresholds |
| `HYBRID_OVERRIDE_MIN_CONTAINMENT` | `0.45` | Minimum smaller-box coverage before the skin layer may override a model box |
| `HYBRID_HEAD_REGION_RATIO` | `0.32` | Top fraction of a person box treated as the head/face region |
| `SKIN_FILTER_ENABLED` | `true` | Master switch for the skin layer (`calc_skin_ratio`) |
| `SKIN_BARE_HAND_ENABLED` | `true` | Bare-hand detection via `distanceTransform` |
| `SKIN_EYE_BRIDGE_ENABLED` | `true` | Eye-bridge `NO-Goggles` test |
| `SKIN_MIN_RATIO` / `SKIN_STRONG_RATIO` | `0.18` / `0.32` | Skin ratio that counts as "exposed" / "strong enough to override a positive class" |
| `SKIN_BARE_HAND_MIN_THICKNESS` / `SKIN_BARE_HAND_MIN_AREA` | `0.12` / `0.10` | Minimum distanceTransform thickness and blob area for a bare hand |
| `SKIN_EYE_BRIDGE_MIN_SKIN_RATIO` | `0.22` | Minimum skin ratio in the nose-bridge strip for `NO-Goggles` |
| `SKIN_GLASS_CONFIRM_MIN_RATIO` | `0.05` | Glass-band height ratio that confirms `Goggles` |
| `SKIN_SYNTHETIC_MIN_CONF` | `0.45` | Floor confidence for skin-generated detections |
| `ALERT_COOLDOWN_SECONDS` | `60` | Minimum seconds between repeated alerts for the same PPE type per camera |
| `VIOLATION_PERSIST_SECONDS` | `8` | Seconds a construction PPE violation must persist before triggering an alert |
| `MEDICAL_VIOLATION_PERSIST_SECONDS` | `3` | Seconds a medical PPE violation must persist before triggering an alert |
| `ALLOWED_RTSP_PREFIXES` | *(empty)* | Comma-separated allowlist of RTSP prefixes (e.g. `rtsp://192.168.1.`) |
| `ALLOWED_VIDEO_DIR` | *(empty)* | Restrict `file` camera sources to paths inside this directory |
| `SENDER_EMAIL` / `RECEIVER_EMAIL` / `EMAIL_PASSWORD` | *(empty)* | SMTP credentials for email alerts |
| `SLACK_WEBHOOK_URL` / `WEBHOOK_URL` | *(empty)* | Optional Slack or generic HTTP webhook URLs |

---

## Hybrid Detection & Skin Filter (Deep Dive)

```text
frame ─┬─► construction YOLO (ppe.pt)          ─┐
       └─► medical YOLO (bestMedicalModel.pt)  ─┤
                                                ▼
                            canonicalise names + merge (IoU) + confidence fusion
                                                ▼
                       resolve positive/negative conflicts (Mask vs NO-Mask …)
                                                ▼
   smart skin layer:  calc_skin_ratio  |  distanceTransform (bare hand)  |  eye bridge (NO-Goggles)
                                                ▼
                       list[Detection] ──► ViolationCheckers ──► DB / Email / Slack / Webhook
```

**Why it matters**

| Problem with a single model | Hybrid + skin answer |
| :--- | :--- |
| Medical model has **no `Person`** class | Construction model supplies `Person`; PPE items are associated to the nearest person by IoU |
| `no goggle` vs `NO-Goggles` naming clash | One canonical vocabulary (`app/core/ppe.py::canonical_class_name`) used by merging, checkers and counters |
| Small PPE items missed at low confidence | Second model + skin evidence (`NO-Mask`, `NO-Gloves`, `NO-Goggles`) generated *after* the confidence filter |
| "Gloves" predicted on a bare hand | `distanceTransform` thickness test downgrades fake `Gloves` to `NO-Gloves` |
| False `NO-Goggles` on someone wearing goggles | The glass-band check on the eye line confirms `Goggles` instead |

**Tuning tips**

* Too many `NO-Goggles` alerts → raise `SKIN_EYE_BRIDGE_MIN_SKIN_RATIO` (e.g. `0.30`) or set `SKIN_EYE_BRIDGE_ENABLED=false`.
* Bare-hand scan too eager → raise `SKIN_BARE_HAND_MIN_THICKNESS` / `SKIN_STRONG_RATIO`.
* CPU-only hosts → keep `HYBRID_MEDICAL_ON_CONSTRUCTION=false` (default) so construction cameras still run one model.
* Need the old behaviour? `HYBRID_DETECTION_ENABLED=false` restores one-model-per-profile exactly as before.

**Verification**

```bash
# unit tests for the skin layer + hybrid detector (no GPU / torch weights needed)
pytest tests/unit/test_skin_analysis.py tests/unit/test_hybrid_detector.py -v
```

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
