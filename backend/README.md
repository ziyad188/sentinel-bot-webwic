# Sentinel Backend

FastAPI backend for the Sentinel web-bot. It authenticates users via Supabase, queries data from a Supabase Postgres database, and exposes endpoints for runs, issues, evidence, categories, and Slack user ownership. It also integrates with an external "test service" to trigger new runs.

**Tech Stack**
- Python 3.12
- FastAPI + Pydantic v2
- asyncpg (Postgres)
- Supabase (Auth + Storage)
- httpx (external HTTP calls)

**Architecture**
- `app.py` wires the FastAPI app, CORS, routers, and lifecycle hooks.
- Auth is Supabase JWT-based using the JWKS endpoint, enforced by `core/auth/deps.py`.
- Database access uses an asyncpg pool created at startup and reused via `db/deps.py`.
- Service pattern: `routes -> services -> repositories -> db/http`.
- Evidence URLs are signed using Supabase Storage with the service role key.

**Project Structure**
- `app.py` – FastAPI app entrypoint.
- `core/routes/` – API routes grouped by domain.
- `core/services/` – business logic and orchestration.
- `core/repositories/` – database queries and external integrations.
- `core/schemas/` – request/response models.
- `db/` – database connection and dependency.
- `settings/` – configuration + logging setup.
- `utils/` – shared helpers (e.g., storage URL signing).
- `conf/application.conf` – optional config file with env expansion.
- `tests/` – utility tests (Slack webhook/bot verification).

**Configuration**
Configuration loads from, in order:
1. Explicit init values.
2. `conf/application.conf` (env expansion is applied).
3. Environment variables.
4. `backend/.env` (loaded via python-dotenv).

Use `backend/.env.example` as a template for required keys.

Environment variables:
| Key | Description |
| --- | --- |
| `APP_NAME` | App name shown in OpenAPI docs |
| `APP_ENV` | Environment label (development/staging/production) |
| `DEBUG` | Enable debug mode and open CORS |
| `HOST` | Server bind host |
| `PORT` | Server bind port |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon key (public) |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (used to sign storage URLs) |
| `SUPABASE_JWT_SECRET` | JWT secret (not used directly; JWKS is used) |
| `SUPABASE_SCHEMA` | Postgres schema (default `public`) |
| `SUPABASE_DB_HOST` | Postgres host |
| `SUPABASE_DB_PORT` | Postgres port |
| `SUPABASE_DB_NAME` | Postgres DB name |
| `SUPABASE_DB_USER` | Postgres user |
| `SUPABASE_DB_PASSWORD` | Postgres password |
| `SUPABASE_DB_SSLMODE` | Postgres SSL mode (default `require`) |
| `SLACK_BOT_TOKEN` | Slack bot token (used in test script) |
| `SLACK_SIGNING_SECRET` | Slack signing secret |
| `SLACK_APP_TOKEN` | Slack app token |
| `SLACK_DEFAULT_CHANNEL` | Slack default channel |
| `STORAGE_BUCKET_SCREENSHOTS` | Supabase Storage bucket for screenshots |
| `STORAGE_BUCKET_VIDEOS` | Supabase Storage bucket for videos |
| `LOG_LEVEL` | Logging level (default `INFO`) |
| `TEST_SERVICE_URL` | External test-service base URL |

**Running Locally**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

OpenAPI docs are available at:
- `GET /docs`
- `GET /redoc`

**Docker**
```bash
cd backend
docker build -t sentinel-backend .
docker run --rm -p 8000:8000 --env-file .env sentinel-backend
```

**API Overview**
Health:
- `GET /health` – basic service status.

Auth:
- `POST /auth/signup` – create Supabase user.
- `POST /auth/login` – email/password login.
- `POST /auth/refresh` – refresh session.
- `POST /auth/logout` – revoke session (requires bearer token).

Lists:
- `GET /list/devices`
- `GET /list/networks`
- `GET /list/projects`

Projects:
- `POST /projects` – create a project.

Runs:
- `POST /runs` – triggers the external test service and creates a run.
- `GET /runs` – list runs by `project_id`, with optional `status`/`severity`.
- `GET /runs/{run_id}/issues` – issues + media for a run.
- `GET /runs/running` – active runs.

Issues:
- `GET /issues` – list issues with filters.
- `GET /issues/{issue_id}` – issue detail + signed media URLs.
- `GET /issues/last/issuedata` – most recent issue (optional project filter).
- `PATCH /issues/{issue_id}/status` – update status (`investigating` or `resolved`).

Evidence:
- `GET /evidence` – list evidence by project and type.

Users:
- `GET /users` – list Slack users.
- `GET /users/with-categories` – list Slack users + categories.
- `POST /users` – create Slack user and assign categories to a project.

Categories:
- `GET /categories` – list project category owners.
- `GET /categories/options` – list categories.
- `POST /categories/owner` – assign a Slack user to a category.

Widgets:
- `POST /widgets/summary` – daily summary metrics for a project.

**Auth Notes**
All non-auth endpoints require a `Bearer` token from Supabase. Tokens are validated against Supabase JWKS and require the `authenticated` audience.

**Sentinal AI Service Integration**
`POST /runs` calls `{TEST_SERVICE_URL}/api/test` with:
- `project_id`, `device_id`, `network_id`, `locale`, `persona`, `input_data`
- `continous_monitoring` is always set to `False`

**Logging**
Logs are written to console and `backend/logs/app.log`.

**Tests**
`tests/slack_test.py` can send Slack webhooks and upload files. Required env vars:
- `SLACK_WEBHOOK_P0`, `SLACK_WEBHOOK_P1`, `SLACK_WEBHOOK_P2`
- Optional: `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`, `TEST_PNG_PATH`, `TEST_MP4_PATH`
