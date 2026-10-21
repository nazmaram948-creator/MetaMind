# MetaMind
hackathon project on Aiversecity Future-Ready work force

## Backend

The P1 backend is a FastAPI service under `backend/app/`. It exposes profile parsing,
signals, role matching, snapshot load/diff, and the P2 learning pathway and
robustness fields.

### Quickstart

From the repository root:

```powershell
pip install -r backend/requirements.txt
$env:DEV_MODE="true"
uvicorn backend.app.main:app --reload --port 8000
```

On macOS/Linux:

```bash
pip install -r backend/requirements.txt
export DEV_MODE=true
uvicorn backend.app.main:app --reload --port 8000
```

Open the interactive API at [http://localhost:8000/docs](http://localhost:8000/docs).
The complete request and response schemas are documented in
[backend/API_CONTRACT.md](backend/API_CONTRACT.md).

### Environment

- `DEV_MODE=true` enables the synthetic skills, roles, courses, and signal
  fixtures so the frontend can integrate immediately. Use this only for local
  development and demos.
- `DEV_MODE=false` disables fixture-backed API responses until the verified
  data/engine adapters are configured.
- `CORS_ORIGIN` defaults to `http://localhost:5173` for the Vite frontend.
- `SIMULATION_RUNS` defaults to `1000`.
- `SIMULATION_VARIATION` defaults to `0.2`, representing the `U(-0.2, 0.2)`
  skill-momentum variation used by the development robustness adapter.
- Curated deliverables are loaded from `data/curated/`: `courses.csv`,
  `malaysian_job_demand_real.csv`, `sdg_mapping.csv`, and
  `synthetic_personas.json`.

### Tests and guardrails

Run the full suite:

```bash
pytest -c backend/pytest.ini -q
```

Run the API tests and required 50-run adversarial ID guardrail check:

```bash
pytest -c backend/pytest.ini -q backend/tests/test_api.py backend/tests/test_guardrails_50runs.py
```

The guardrail test writes its verification result to
`backend/tests/guardrail_50run_report.json`. It records 50 runs and confirms that no
unverified skill, role, or course IDs pass through the API.

### Data and engine integration

The development repository is implemented in
`backend/app/services/repository.py`. Replace the fixture adapters there with the
verified data sources once the real tables are ready:

- **Max / data engine:** wire the role matching, dated signals, skill momentum,
  snapshot loading/diff, and 1,000-futures simulation through the existing
  service seams. Keep the route response models and verified-ID guardrails
  unchanged.
- **Walid / course and demand data:** provide
  `data/curated/courses.csv` with `course_id`, `course_title`, `provider`,
  semicolon-separated `skill_ids`, integer `hours`, boolean `hours_verified`,
  integer `cost`, and `url`. Only courses with `hours_verified=true` may be
  used for `best_next_hour` calculations; unverified hours must remain
  `"hours not verified"`.
- **Demand and SDG data:** `/api/signals` reads the 20 demand rows and exposes
  category, growth, source, and publication date. `/api/sdg` reads the 40 SDG
  rows independently; do not inner-join the two files by occupation name.
- **Demo selectors:** `/api/personas` exposes the three individual personas
  and five-person HR cohort, including Danial's nullable `current_role`.

After integrating real sources, run the focused tests and full suite before
switching demos or deployments away from `DEV_MODE=true`.

### Backend layout

```text
backend/
  app/
    main.py                 # FastAPI app and routes
    schemas.py              # Request/response models
    config.py               # Environment-backed settings
    services/               # Data, extraction, guardrail, and simulation adapters
  tests/                    # API, curated-data, and 50-run guardrail tests
  requirements.txt          # Backend dependencies
  pytest.ini                # Backend pytest discovery/import path
  start.sh                 # Replit/Linux startup script
  .env.example              # Backend environment reference
  API_CONTRACT.md           # Frontend integration contract
```

The curated datasets remain shared project inputs under `data/curated/`.
`.replit` stays at the repository root and starts `backend/start.sh`.
