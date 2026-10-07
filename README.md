# Nexora

**Nexora** is a real-time PPE (Personal Protective Equipment) compliance monitoring
platform built for factories, construction sites, and industrial facilities.

Nexora connects to your existing cameras (RTSP / IP / webcam / recorded video),
runs real-time AI detection on each feed, and alerts you instantly when workers
are missing required safety equipment — **customized per camera**.

## Key Feature: Per-Camera Monitoring Rules

Not every camera needs to check the same thing. With Nexora, each camera can be
configured independently:

- 🏗️ Factory entrance → Helmet + Vest
- 🧪 Lab area → Lab Coat + Gloves + Goggles
- 🔥 Welding zone → Helmet + Gloves + Vest
- 📦 Warehouse → Vest only

## Tech Stack

- **Backend:** FastAPI (async), SQLAlchemy (async ORM), SQLite (default)
- **AI:** YOLO (Ultralytics) for real-time PPE detection
- **Frontend:** Vanilla JS + Bootstrap 5 dashboard
- **Alerts:** Database logging, Email, Webhook (Slack/Teams/custom)
- **Streaming:** MJPEG + WebSocket live counts

## Running Locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000