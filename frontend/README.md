# Sentinel Frontend

React + Vite frontend for the Sentinel web-bot. It provides authentication flows, dashboards, runs, issues, evidence views, and user management for the backend API.

**Tech Stack**
- React 18 + TypeScript
- Vite 5
- Tailwind CSS + shadcn/ui + Radix UI
- TanStack Query
- React Router

**Architecture**
- `src/App.tsx` sets up routing, auth guard, and app shell layout.
- API calls are made via `fetch` to relative paths (`/auth`, `/runs`, etc.).
- In development, Vite proxies these paths to the backend.
- In production, Nginx proxies the same paths to the backend container.
- Auth sessions are stored in localStorage/sessionStorage with refresh support.

**Project Structure**
- `src/pages/` – route-level pages (Dashboard, Runs, Issues, Evidence, Users, Auth).
- `src/components/` – shared UI and layout components.
- `src/hooks/` – UI helpers like toasts.
- `src/lib/` – auth/session, project selection, run configuration.
- `public/` – static assets.
- `vite.config.ts` – dev server + API proxy configuration.

**Configuration**
Copy `frontend/.env.example` to `frontend/.env`.

Environment variables:
| Key | Description |
| --- | --- |
| `VITE_DEMO_MODE` | Enables the “Run now” workflow when `true`. When `false`, the dashboard shows a demo-only message. |

**Running Locally**
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Vite dev server runs on `http://localhost:8080` and proxies API requests to `http://localhost:8000`.

**Build + Preview**
```bash
cd frontend
npm run build
npm run preview
```

**Docker**
```bash
cd frontend
docker build -t sentinel-frontend .
docker run --rm -p 8080:80 sentinel-frontend
```

The production container expects the backend to be reachable as `backend:8000` (see `frontend/nginx.conf`). Use `docs/docker-compose.yml` or update the Nginx config for a different backend host.

**App Routes**
- `/login` – email/password login.
- `/signup` – account creation.
- `/dashboard` – KPI overview, live runs panel, alerts.
- `/runs` – run list + details.
- `/issues` – issue list + detail view, status updates.
- `/evidence` – screenshots and video evidence.
- `/users` – Slack user list and category assignment.

**API Expectations**
The frontend expects these backend routes to exist:
- `/auth/*`
- `/list/*`
- `/projects`
- `/runs/*`
- `/issues/*`
- `/evidence`
- `/users/*`
- `/widgets/*`

**Tests**
```bash
cd frontend
npm test
```
