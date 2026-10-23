# MetaMind: SkillShift MY
hackathon project on Aiversecity Future-Ready work force

## Run the app

One process serves the app and the API on **http://localhost:8000**, with real data
(`ENGINE_MODE=true`). You need **Python 3.10+** (3.11 recommended) and **Node.js 20+**.

Windows (PowerShell), from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File run.ps1
```

To run manually in demo mode, use:

```powershell
cd D:\Coding_Proj\Hackathon\MetaMind
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
$env:DEV_MODE="true"
$env:ENGINE_MODE="false"
.venv\Scripts\python -m uvicorn backend.app.main:app --reload --port 8000
```

For the real engine, replace the two environment-variable lines with:

```powershell
$env:DEV_MODE="false"
$env:ENGINE_MODE="true"
```

For frontend hot reload, open a second PowerShell terminal:

```powershell
cd D:\Coding_Proj\Hackathon\MetaMind\frontend
npm ci
npm run dev
```

macOS / Linux:

```bash
bash run.sh
```

The script creates `.venv`, installs the Python packages, builds the frontend and
starts the server. The first run takes a few minutes: about 300 MB of packages, then
the database builds itself and the language model (about 90 MB) downloads on the
first start. Later runs start in seconds. On Replit, press **Run** (`.replit` calls `run.sh`).

<details>
<summary>The same steps by hand</summary>

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt    # macOS/Linux: .venv/bin/python
cd frontend && npm ci && npm run build && cd ..
ENGINE_MODE=true .venv/Scripts/python -m uvicorn backend.app.main:app --port 8000
```

On PowerShell, replace the last line with `$env:ENGINE_MODE="true"` and then
`.venv\Scripts\python -m uvicorn backend.app.main:app --port 8000`.
</details>

**Frontend with hot reload (development):** keep the server above running and, in
a second terminal, run `cd frontend` followed by `npm run dev`. Open http://localhost:5173;
`/api` is forwarded to port 8000.

| Symptom | Fix |
|---|---|
| Banner "This API was started without the engine" | The server was started without `ENGINE_MODE=true`. Use `run.ps1` / `run.sh` |
| Banner "Starting the engine…" | First start: DB build + model download. Wait; it disappears when ready |
| "Can't reach the API" | The server is not running, or runs on another port |
| `run.ps1` cannot be loaded | Run it as shown above (`-ExecutionPolicy Bypass`) |
| Port 8000 busy | `run.ps1 -Port 8010`, or `PORT=8010 bash run.sh` |
| Windows: pip fails with a "Long Path" / `No such file or directory` error | Clone into a short folder (e.g. `C:\dev\MetaMind`), delete `.venv`, run again |


## Backend

The P1 backend is a FastAPI service under `backend/app/`. It exposes profile parsing,
signals, role matching, snapshot load/diff, and the P2 learning pathway and
robustness fields.

### Backend only, with development fixtures

For API work without the engine (`DEV_MODE=true` serves synthetic fixtures). From the repository root:

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

Run the backend suite from the repository root:

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

Run the engine and data tests separately:

```powershell
$env:PYTHONPATH="."
pytest -q engine\tests data\tests
```

Build the frontend:

```powershell
Set-Location frontend
npm ci
npm run build
```

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

### Engine mode (real data)

`ENGINE_MODE=true` serves the same routes from the real engine in `engine/` instead
of the fixtures. Response models are unchanged; they only gain optional fields (see
[backend/API_CONTRACT.md](backend/API_CONTRACT.md#engine-mode-engine_modetrue)).
Without it, nothing changes: fixtures with `DEV_MODE=true`, `503` otherwise.

```bash
export ENGINE_MODE=true
uvicorn backend.app.main:app --reload --port 8000
```

On Windows PowerShell use `$env:ENGINE_MODE="true"` instead of `export`.

On first start the SQLite database is built from `data/extracts/` and `data/curated/`
in a few seconds (no network). The embedding model (all-MiniLM-L6-v2, about 90 MB)
downloads once and the skill embeddings are cached in `data/cache/`.

| Setting | Default | Meaning |
|---|---|---|
| `ENGINE_MODE` | `false` | `true` = real engine |
| `CURATED_VERSION` | `v2` | `v1` = team curated files, `v2` = ESCO-keyed files ([data/curated/README.md](data/curated/README.md)) |
| `SIMILARITY_BACKEND` | `minilm` | `lexical` = word overlap, no model download |
| `SKILLSHIFT_DB` | `data/skillshift_<version>.db` | database path |

All weights and thresholds are in [engine/config.yaml](engine/config.yaml). The model:

- **Exposure** per occupation from O*NET task importance and the Anthropic Economic
  Index task-level usage and automation/augmentation split.
- **Outlook** `O = alpha·D + beta·z(augmentation) − gamma·z(automation)`, with
  `gamma` = 1 (moderate) or 2 (fast). Demand `D` stays neutral until DOSM figures
  with source URLs are entered.
- **Skill momentum** = outlook of the occupations that need the skill (Skills Radar).
- **Match** = coverage of essential skills, outlook and transferability, plus 1,000
  simulated futures for robustness.
- **Snapshots**: `baseline_snapshot` = AEI Nov 2025, `latest_snapshot` = AEI May 2026.

Rebuild the database after changing curated files with `python -m engine.build`.

Replit / Linux: plain `pip install sentence-transformers` pulls the CUDA build of
PyTorch (several GB). Install the CPU build first:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Or run with `SIMILARITY_BACKEND=lexical`. The engine also falls back to lexical
matching on its own when sentence-transformers is not installed.

The backend pytest configuration covers `backend/tests/`. Run the engine and data
tests with the separate command above; they use lexical matching, so no model
download is needed.

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
