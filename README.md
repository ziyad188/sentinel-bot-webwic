# SentinelBot Webwic

SentinelBot Webwic is a full-stack platform for managing automated QA runs, issues, evidence, and Slack ownership. It consists of three services:
- **Frontend**: React + Vite SPA for dashboards, runs, issues, evidence, and user management.
- **Backend API**: FastAPI service that provides auth, data access, and orchestration.
- **Sentinel Runner**: A separate FastAPI service that executes AI-driven Playwright runs and writes results to Supabase.

**What This Repo Contains**
- `frontend/` – Web UI (React, Vite, Tailwind, shadcn/ui).
- `backend/` – API server with Supabase Auth + Postgres + Storage.
- `sentinelbot/` – Autonomous QA runner (Claude + Playwright).
- `docs/docker-compose.yml` – Example deployment with prebuilt images.

**How The Services Connect**
- The frontend calls the backend API for auth, lists, issues, evidence, and users.
- The backend calls the Sentinel Runner through `TEST_SERVICE_URL` when you start a run.
- The Sentinel Runner reads and writes to Supabase and optionally posts to Slack.

---


## Architecture Overview

```mermaid
graph TB
    subgraph Client["Client"]
        API_REQ["API Request<br/>(POST /api/test)"]
        POLL["Poll Results<br/>(GET /api/runs/:id)"]
    end

    subgraph SentinelBot["SentinelBot Server (FastAPI :8502)"]
        direction TB
        SERVER["FastAPI Server"]
        SCHEDULER["Continuous Scheduler<br/>(24/7 Monitoring)"]
        
        subgraph RunEngine["Run Engine"]
            EXECUTE["_execute_run()"]
            CALLBACKS["Callbacks<br/>(output, tool, API)"]
            REALTIME["Real-Time Issue<br/>Detection"]
        end
    end

    subgraph AI["Claude AI (Anthropic API)"]
        LOOP["Agentic Sampling Loop"]
        PROMPT["System Prompt<br/>+ Persona + Locale"]
    end

    subgraph Browser["Playwright Browser"]
        PW_TOOL["PlaywrightComputerTool"]
        ACTIONS["click, type, scroll,<br/>screenshot, wait"]
        PERF["Performance Metrics<br/>(Core Web Vitals)"]
        A11Y["Accessibility Audit<br/>(axe-core)"]
    end

    subgraph Database["Supabase"]
        direction TB
        DB_TABLES["Tables: runs, issues, evidence,<br/>run_logs, run_steps, perf_metrics,<br/>devices, networks, projects"]
        STORAGE["Storage Buckets<br/>(screenshots, videos)"]
    end

    subgraph Notifications["Slack"]
        SLACK["Slack Notifier"]
    end

    API_REQ --> SERVER
    SERVER -->|run_id| API_REQ
    POLL --> SERVER

    SERVER -->|BackgroundTask| EXECUTE
    SERVER -->|continuous=true| SCHEDULER
    SCHEDULER -->|rotating combos| EXECUTE

    EXECUTE --> LOOP
    PROMPT --> LOOP
    LOOP <-->|tool_use / tool_result| PW_TOOL

    PW_TOOL --> ACTIONS
    PW_TOOL --> PERF
    PW_TOOL --> A11Y

    CALLBACKS --> DB_TABLES
    CALLBACKS --> STORAGE
    EXECUTE --> DB_TABLES
    EXECUTE --> STORAGE
    SERVER --> DB_TABLES

    EXECUTE --> SLACK
    REALTIME --> SLACK
```

---

**Demo Video**
Click on the image to view demo video:
[![Watch the demo](docs/unnamed.png)](https://drive.google.com/file/d/1IQvkQfjvHsuefoAhzOE_3WMrDeNisOeg/view?usp=sharing)


**Configuration**
Each service has its own environment file:
- `backend/.env.example` → `backend/.env`
- `frontend/.env.example` → `frontend/.env`
- Sentinel Runner uses env vars documented in `sentinelbot/README.md`

If you use `docs/docker-compose.yml`, create:
- `docs/.env.backend` (based on `backend/.env.example`)
- `docs/.env.frontend` (based on `frontend/.env.example`)

**Local Development**
Backend:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Frontend:
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Sentinel Runner:
```bash
cd sentinelbot
python -m venv .venv
source .venv/bin/activate
pip install -r sentinel/requirements-sentinel.txt
python -m playwright install chromium
uvicorn sentinel.sentinel_server:app --host 0.0.0.0 --port 8502
```

Dev ports:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:8080` (Vite proxies API requests to the backend)
- Sentinel Runner: `http://localhost:8502`

**Docker**
Backend:
```bash
cd backend
docker build -t sentinel-backend .
docker run --rm -p 8000:8000 --env-file .env sentinel-backend
```

Frontend:
```bash
cd frontend
docker build -t sentinel-frontend .
docker run --rm -p 8080:80 sentinel-frontend
```

Sentinel Runner:
```bash
cd sentinelbot
docker build -f Dockerfile.sentinel -t sentinelbot:local .
docker run --rm -p 8502:8502 --env-file .env sentinelbot:local
```

**API Docs**
- Backend: `GET /docs`, `GET /redoc`
- Sentinel Runner: `GET /docs`

**More Details**
- Backend: `backend/README.md`
- Frontend: `frontend/README.md`
- Sentinel Runner: `sentinelbot/README.md`

---

