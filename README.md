# Teacher Timetable Optimizer

Automated academic timetabling: given teachers, rooms, class groups, courses and
preferences, a **constraint-programming solver (Google OR-Tools CP-SAT)** computes an
optimized weekly schedule that respects all hard constraints and minimizes a weighted
soft-objective. A **FastAPI** backend exposes the solver and a scenario database, and a
**React + Vite + Tailwind** frontend provides full CRUD, live optimization and an
interactive timetable grid.

## Features

- **Hard constraints** enforced by the solver:
  - teachers, rooms and class groups (students) cannot be double-booked
  - a teacher only teaches subjects they know, and only courses they are assigned to
  - lab courses only in lab rooms with capacity ≥ class-group size
  - teacher weekly-hour limits, availability days and blocked slots (`Mon-1`, `Wed-3`, …)
  - per-course cap on sessions per day
- **Soft objective** (weights configurable in the UI):
  - minimize idle gaps inside a class group's day
  - spread a course's sessions across the week (≤ 1 per day preferred)
  - balance weekly load across teachers
- **Infeasibility explanations** — when no schedule exists, the API reports which
  courses conflict (via CP-SAT assumption cores) plus arithmetic pre-checks
  (workload vs. available periods, lab capacity, unknown references).
- **Scenario persistence** — create/save/load/delete scheduling scenarios in SQLite;
  every optimization run is archived as a named schedule with score and solver stats.
- **Async optimization** — long solves run as background jobs with progress polling,
  so the UI stays responsive (default solver limit 30 s, returns best-feasible).
- **Interactive grid** — Mon–Fri × 4 periods, color-coded, viewable by class group,
  teacher, room or course; export to JSON/CSV.

## Architecture

```
┌────────────────────────────┐        ┌──────────────────────────────────┐
│  React + Vite + Tailwind   │  /api  │  FastAPI (uvicorn)               │
│  frontend/                 │ ─────▶ │   ├─ /api/optimize  (stateless)  │
│  scenario CRUD · forms     │ proxy  │   ├─ /api/scenarios CRUD         │
│  timetable grid · jobs     │        │   ├─ /api/scenarios/{id}/optimize│
└────────────────────────────┘        │   ├─ /api/jobs/{id}  (async)     │
                                      │   └─ solver.py  ── CP-SAT model  │
                                      │  SQLAlchemy ORM                  │
                                      │   └─ SQLite (timetable.db)       │
                                      └──────────────────────────────────┘
```

| Layer | Tech |
|---|---|
| Solver | Python, Google OR-Tools CP-SAT (parallel search) |
| API | FastAPI, pydantic v2, background tasks + in-memory job registry |
| Persistence | SQLAlchemy 2.x ORM, SQLite |
| Frontend | React 19, Vite 8, Tailwind CSS 4 |
| Tests | pytest (solver + API + persistence), CI via GitHub Actions |
| Deployment | Docker + docker-compose (nginx serves the frontend, proxies `/api`) |

## Running locally

Backend (Python 3.12, venv recommended):

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cd backend && ../.venv/bin/uvicorn app:app --reload   # API on http://127.0.0.1:8000
```

Frontend (Node 22+):

```bash
cd frontend
npm install
npm run dev            # UI on http://localhost:5173 (proxies /api to :8000)
```

Open http://localhost:5173, click **Load demo data**, then **Optimize schedule**.

## Running with Docker

```bash
docker compose up --build
# frontend: http://localhost:5173   backend: http://localhost:8000/docs
```

## API overview

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness probe |
| POST | `/api/optimize` | stateless one-shot optimization |
| GET/POST | `/api/scenarios` | list / create a scenario |
| GET/PUT/DELETE | `/api/scenarios/{id}` | read / replace / delete a scenario |
| POST | `/api/scenarios/{id}/optimize[?async=true]` | optimize from stored data (auto-saves the result) |
| GET | `/api/jobs/{job_id}` | poll async job status/result |
| GET/DELETE | `/api/scenarios/{id}/schedules[/{sid}]` | list / fetch / delete saved schedules |

Interactive docs: `http://localhost:8000/docs`.

## Testing

```bash
.venv/bin/python -m pytest backend/tests -q     # 16 tests: solver, API, persistence
```

## Benchmarks

`backend/benchmark.py` generates synthetic scenarios at increasing scale
(deterministic, seeded) and times a full solve on one machine (28 cores, default
preference weights, 60 s limit):

| Scale | Teachers | Rooms | Class groups | Courses | Weekly hours | Result | Objective | Solve time |
|---|---|---|---|---|---|---|---|---|
| small | 5 | 4 | 2 | 8 | 19 | optimal | 4.0 | 0.08 s |
| medium | 10 | 8 | 5 | 25 | 64 | optimal | 7.0 | 1.5 s |
| large | 20 | 14 | 10 | 50 | 123 | optimal | 7.0 | 7.6 s |
| xlarge | 35 | 25 | 18 | 90 | 224 | optimal | 7.0 | 33 s |

Numbers vary by machine; run the script yourself for your hardware.

## Project structure

```
├── backend/
│   ├── app.py            # FastAPI app, stateless /api/optimize, lifespan
│   ├── models.py         # pydantic request models + Preferences
│   ├── solver.py         # CP-SAT model: hard constraints, soft objective, explanations
│   ├── database.py       # SQLite engine / session / init
│   ├── db_models.py      # ORM: Scenario, TeacherRow, ..., SavedSchedule
│   ├── api_scenarios.py  # scenarios CRUD + async optimize + jobs + schedules router
│   ├── benchmark.py      # synthetic benchmark harness
│   └── tests/            # pytest suite
├── frontend/
│   └── src/
│       ├── App.jsx               # layout, scenario state, optimize flow
│       ├── api.js                # REST client, job polling, exports
│       └── components/           # EntityEditor, TimetableGrid, SchedulesPanel, ...
├── docker-compose.yml
└── .github/workflows/ci.yml      # pytest + frontend build on push/PR
```

## Roadmap ideas

- PDF/Excel export server-side, iCal feed per teacher
- Multi-section courses (lecture + lab components), lunch breaks, double periods
- User accounts (JWT) with per-user scenarios
- Scenario comparison view (diff two saved schedules)
- Manual drag-and-drop edits with instant constraint validation
