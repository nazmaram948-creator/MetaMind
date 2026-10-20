# MetaMind
hackathon project on Aiversecity Future-Ready work force

## Backend

The P1 backend is a FastAPI service under `app/`. It exposes profile parsing,
signals, role matching, snapshot load/diff, and the P2 learning pathway and
robustness fields.

### Quickstart

From the repository root:

```powershell
pip install -r requirements.txt
$env:DEV_MODE="true"
uvicorn app.main:app --reload --port 8000
```

On macOS/Linux:

```bash
pip install -r requirements.txt
export DEV_MODE=true
uvicorn app.main:app --reload --port 8000
```

Open the interactive API at [http://localhost:8000/docs](http://localhost:8000/docs).
The complete request and response schemas are documented in
[docs/API_CONTRACT.md](docs/API_CONTRACT.md).

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

### Tests and guardrails

Run the full suite:

```bash
pytest -q
```

Run the API tests and required 50-run adversarial ID guardrail check:

```bash
pytest -q tests/test_api.py tests/test_guardrails_50runs.py
```

The guardrail test writes its verification result to
`tests/guardrail_50run_report.json`. It records 50 runs and confirms that no
unverified skill, role, or course IDs pass through the API.

### Data and engine integration

The development repository is implemented in
`app/services/repository.py`. Replace the fixture adapters there with the
verified data sources once the real tables are ready:

- **Max / data engine:** wire the role matching, dated signals, skill momentum,
  snapshot loading/diff, and 1,000-futures simulation through the existing
  service seams. Keep the route response models and verified-ID guardrails
  unchanged.
- **Walid / course and demand data:** provide
  `data/curated/courses.csv` with the documented course fields, including
  `course_id`, `skill_ids`, `hours`, and `hours_verified`. Only courses with
  `hours_verified=true` may be used for `best_next_hour` calculations;
  unverified hours must remain `"hours not verified"`.

After integrating real sources, run the focused tests and full suite before
switching demos or deployments away from `DEV_MODE=true`.
