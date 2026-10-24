# Future Skills Compass

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=20232A)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white)](https://vite.dev/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Guardrail verification](https://img.shields.io/badge/guardrail-50%2F50%20passed-2ea44f)](backend/tests/guardrail_50run_report.json)

> Deterministic career-transition analysis for Malaysian workers and SMEs.

Future Skills Compass combines skill-momentum modelling, Monte Carlo career-robustness simulation, and SDG-weighted upskilling recommendations for workers exposed to AI task automation. It returns ranked roles, evidence badges, snapshot deltas, and verified-hour learning pathways without inventing database identifiers or course facts.

**Quick links:** [Architecture](#system-architecture-and-data-pipeline) · [Algorithms](#core-algorithmic-mechanics) · [API](#api-reference) · [Runbook](#local-development-testing-and-replit-deployment) · [Limitations](#known-limitations-and-tooling-declaration)

## System architecture and data pipeline

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ Data ingestion and signal layer: data/curated/ + data/extracts/          │
│ AEI · ESCO v1.2 · O*NET/ISCO · DOSM/PERKESO · SDG maps · course catalog │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ validated CSV/JSON → SQLite
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Core engine: engine/service.py                                           │
│ exposure/outlook → skill momentum → match ranking → snapshot diff       │
│ 1,000-run momentum perturbation and top-5 survival frequency              │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ typed response models
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ FastAPI gateway: backend/app/                                             │
│ deterministic phrase extraction · curated adapters · strict ID allowlist │
│ provenance badges · DEV_MODE fixture path · ENGINE_MODE real-data path   │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ REST /api/*
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ React/Vite client: frontend/ · http://localhost:5173                     │
│ Skills Radar · Role Cards · SDG trade-off slider · pathway ROI           │
└─────────────────────────────────────────────────────────────────────────┘
```

The project keeps two curated generations side by side. The current fixture
adapter reads the v1 files (`courses.csv`, `sdg_mapping.csv`, and related
persona/demand files). The engine build is configured for v2 ESCO-keyed files;
see [data/curated/README.md](data/curated/README.md) before changing the active
curated version.

## Core algorithmic mechanics

### Skill momentum and outlook

For occupation \(o\), the engine derives an outlook from demand and exposure:

```text
O_o = α·D_o + β·z(augmentation_o) − γ·z(automation_o)
```

`moderate` uses `γ = 1`; `fast` uses `γ = 2`. Demand is neutral when source
verification is disabled in `engine/config.yaml`. Skill momentum is the
weighted outlook of occupations requiring the skill:

```text
M_k = Σ_o r_ok·O_o / Σ_o r_ok
```

`r_ok` is `1.0` for essential and `0.5` for optional skill relations.

### Match score

The configured engine decomposition is:

```text
S = 100 × (w_c·C + w_o·Ô + w_t·T) + λ·SDG
```

where `C` is essential-skill coverage, `Ô` is normalized role outlook,
`T` is transferability, and `λ` is the SDG weight.

**SDG term (engine).** The slider value `sdg_preference = p ∈ [0, 1]` sets
`λ = p · sdg_lambda_max` (20 points; the brief's 10 is one line in
`engine/config.yaml`). The SDG part is added on top of the other parts, so
`score_points` always add up to the total, and skills still decide the top of the list.

`SDG_o ∈ [0, 1]` measures how much of the role's ESCO skill profile serves an SDG,
not how many goals it is tagged with:

- a skill in the ESCO Green collection, or mapped to an SDG target, counts 1;
- a skill only in the Digital collection counts 0.25;
- skills are weighted 1 if essential, 0.5 if optional, and the result is scaled so the
  most SDG-aligned role scores 1.

Without a preference `λ = sdg_lambda = 0`. The fixture adapter keeps its own
blended `sdg_preference_score`.

### 1,000 futures robustness estimate

For each run, each role's skill-momentum contribution is perturbed:

```text
M'_k = M_k × (1 + U(-r, r)),   r = 0.2
```

The default fixture configuration executes `1,000` seeded runs, re-ranks roles
on each run, and reports:

```text
top5_frequency(role) = top5_count(role) / 1000
```

Responses carry `label: "Estimate"` and the configured assumption text. This
is sensitivity analysis, not a jobs forecast.

### Pathway and “Best Next Hour”

`Engine.pathway` (engine/service.py) works in five steps:

1. Take the target role's missing essential skills.
2. Order them with broader ESCO concepts first, then by the match-score gain each
   skill would add.
3. Pick one catalogue course per skill: the shortest with page-verified hours,
   otherwise a course marked "hours not verified". A course that teaches several
   missing skills is listed once.
4. Compute "best next hour": the verified course with the largest score gain across
   the user's top 10 roles, divided by its hours.
5. Add up hours and known costs.

Roles whose skills no course teaches return those skills in
`skills_without_course`; unrelated courses are never filled in. An unverified
course is returned with:

```json
{ "hours": "hours not verified", "marginal_score_per_hour": null }
```

Course `skill_ids` are semicolon-delimited in the v1 catalogue and are split by
the typed loader. Course, role, skill, cost, SDG, and source/date fields remain
attached to each response step.

### Task X-ray, upgrade in place and team view

- **`GET /api/xray`** labels every O*NET task of a job from the AEI task data:
  - `mostly human`: no measurable AI use in the sample;
  - `automating`: at least 60% of the AI use is automation;
  - `assisting`: the rest.

  Thresholds are under `xray:` in `engine/config.yaml`.
- **`POST /api/upgrade`** links the `assisting` tasks to the job's most similar ESCO
  skills (MiniLM text similarity) and lists the ones the user lacks, each with momentum
  and a course. This is the "AI-upgraded version of your current role".
- **`/api/team`** applies the X-ray and the role match to every member of a
  (synthetic) team for the HR heatmap.

### Snapshot diffing

The engine compares deterministic state vectors between `baseline_snapshot`
(`aei_2025_11`) and `latest_snapshot` (`aei_2026_05`). Each metric carries
source and publication-date metadata; aliases are resolved through the engine
store rather than through client-side string conventions.

## Zero-hallucination guardrails and security posture

`backend/app/services/guardrails.py` validates response identifiers against
verified repository sets. Unknown skill, role, and course identifiers are
blocked before serialization; engine responses pass through the corresponding
store guardrail. SDG records are loaded from curated tables rather than
created from free text.

The demo personas are synthetic-only: Aina, Danial (fresh graduate), Sarah
(career switcher), and the HR cohort. The repository does not collect or ship
NRIC numbers, phone numbers, email addresses, or production user records.
Uploaded CV parsing is an engine-mode local feature and is bounded to 2 MB and
20,000 characters.

### 50-run adversarial verification

| Check | Result |
|---|---:|
| Test | `backend/tests/test_guardrails_50runs.py` |
| Runs | 50 |
| Unverified IDs passed | 0 |
| Invalid values blocked | 150 |
| Report | [guardrail_50run_report.json](backend/tests/guardrail_50run_report.json) |

## API reference

The canonical request/response contract is
[backend/API_CONTRACT.md](backend/API_CONTRACT.md). Interactive OpenAPI
documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

| Method | Endpoint | Purpose | Key request / response fields |
|---|---|---|---|
| `POST` | `/api/profile/parse` | Extract and normalize skills | `text`, `current_skills` → `skills[]` |
| `GET` | `/api/signals` | Skills Radar or demand signals | `skill`, `scenario`, `snapshot_id` → dated badges |
| `POST` | `/api/match` | Rank target occupations | `skill_ids`, `current_occupation_id`, `scenario`, `sdg_preference` |
| `POST` | `/api/snapshot/load` | Select a market snapshot | `snapshot_id` → active snapshot metadata |
| `POST` | `/api/snapshot/diff` | Compare baseline and latest state | `skill_ids`, snapshot IDs → role changes |
| `POST` | `/api/pathway` | Generate pathway and best next hour | `skill_ids`, `target_role_id`, `sdg_filter` |
| `GET` | `/api/sdg` | Read curated SDG mappings | → occupation, SDG, evidence, status, source/date |

Additional engine-only endpoints are `/api/profile/parse_file`,
`/api/occupations`, `/api/context`, and `/api/personas`. Health is exposed at
`/health`.

## Data sources, provenance, and licensing

The repository stores source snapshots and transformation scripts. Dates below
refer to the committed snapshot or source period, not a claim of live data.
External dataset redistribution remains subject to each upstream provider's
terms.

| Dataset | Repository path | Scope / role | Snapshot or update | License / provenance |
|---|---|---|---|---|
| Anthropic Economic Index | `data/extracts/aei_*` | Task usage, automation, augmentation, country signals | Nov 2025 baseline; May 2026 latest | Anthropic source data; retain upstream terms |
| ESCO v1.2 | `data/extracts/esco_*` | Occupations, skills, broader-skill links | ESCO v1.2 extract | European Commission / ESCO terms |
| O*NET 31.0 | `data/extracts/onet_*` | Task importance and occupation task evidence | O*NET 31.0 | O*NET data notice |
| DOSM/PERKESO demand | `data/curated/malaysian_job_demand_real.csv`, `demand_*` | Malaysian vacancies and occupation mapping | 2025–2026 fields in committed CSVs | Curated public-source records; verify source terms |
| Course catalogue / HRD Corp fields | `data/curated/courses*.csv`, `course_*` | Course IDs, providers, hours, cost, URL, verification | Curated project snapshot | Provider pages and project curation; no HRD claim is inferred when absent |
| UN SDG mapping | `data/curated/sdg_mapping.csv`, `sdg_map_v2.csv` | Occupation/skill evidence mapped to SDG targets | Curated build; v2 covers 42 occupations in this checkout | UN SDG taxonomy plus project mapping rules |

## Local development, testing, and Replit deployment

### Requirements

- Python 3.10+; Python 3.11 is the recommended runtime.
- Node.js 20+ and npm for the Vite client.
- PowerShell on Windows, Bash on macOS/Linux/Replit.

### Backend fixture mode

`DEV_MODE=true` enables the deterministic synthetic adapter for frontend
integration. It is not the real engine.

```powershell
cd D:\Coding_Proj\Hackathon\MetaMind
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
$env:DEV_MODE="true"
$env:ENGINE_MODE="false"
.venv\Scripts\python -m uvicorn backend.app.main:app --reload --port 8000
```

Open [http://localhost:8000/docs](http://localhost:8000/docs). CORS defaults to
`http://localhost:5173`; override it with `CORS_ORIGIN`.

### Engine mode

`ENGINE_MODE=true` routes API work to `engine/`, builds the local SQLite store
from committed extracts/curated data, and may download the configured MiniLM
model. Use lexical matching to avoid the model download:

```powershell
cd D:\Coding_Proj\Hackathon\MetaMind
$env:DEV_MODE="false"
$env:ENGINE_MODE="true"
$env:SIMILARITY_BACKEND="lexical"
.venv\Scripts\python -m uvicorn backend.app.main:app --reload --port 8000
```

The supported environment variables are `DEV_MODE`, `ENGINE_MODE`,
`CORS_ORIGIN`, `SIMULATION_RUNS`, `SIMULATION_VARIATION`, `CURATED_VERSION`,
`SIMILARITY_BACKEND`, and `SKILLSHIFT_DB`. The one-command scripts
[`run.ps1`](run.ps1) and [`run.sh`](run.sh) install dependencies, build the
frontend, and start engine mode by default. On Windows, double-click
[`run.cmd`](run.cmd) or type `run`: it starts `run.ps1` without changing the
PowerShell execution policy. `run.sh` also works in Git Bash on Windows.

### Frontend

```powershell
cd D:\Coding_Proj\Hackathon\MetaMind\frontend
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite proxy forwards
`/api` to port 8000. For a production bundle:

```powershell
npm run build
```

### Tests and report generation

From the repository root:

```powershell
pytest -c backend\pytest.ini -q
$env:PYTHONPATH="."
pytest -q engine\tests data\tests
pytest -c backend\pytest.ini -q backend\tests\test_guardrails_50runs.py
```

The guardrail test regenerates
`backend/tests/guardrail_50run_report.json`. The full current validation baseline
is 53 backend tests and 29 engine/data tests.

### Replit

The root [.replit](.replit) selects Python 3.11 and Node.js 20, sets
`ENGINE_MODE=true`, exposes port 8000 as external port 80, and runs `bash run.sh`.
`run.sh` rebuilds `data/skillshift_v2.db` with `python -m engine.build` before
Uvicorn starts, so curated CSV changes are applied on every deploy.
To reproduce the runtime locally:

```bash
ENGINE_MODE=true PORT=8000 bash run.sh
```

Replit sets `REPL_ID`; `run.sh` responds by binding Uvicorn to `0.0.0.0`.

### RunPod inference hook

Set `RUNPOD_API_KEY` and either `RUNPOD_ENDPOINT_ID` for a Serverless endpoint
or `RUNPOD_BASE_URL` for a vLLM/Ollama-compatible endpoint. When configured,
engine-mode profile parsing tries RunPod first, validates returned IDs against
the ESCO store, and falls back to deterministic local extraction on timeout,
invalid output, or missing configuration.

```powershell
$env:RUNPOD_API_KEY="<key>"
$env:RUNPOD_ENDPOINT_ID="<endpoint-id>"
& .venv\Scripts\python.exe scripts\verify_runpod.py
```

The verification proof is written to
`data/runpod_verification_proof.json` without recording the API key. `/health`
reports `compute_provider` as `runpod-serverless` when the hook is configured;
otherwise it reports `local-deterministic`.

## Known limitations and tooling declaration

- The fixture extractor is deterministic phrase/alias matching. It is not a
  general semantic parser and unknown phrases are not converted into invented
  IDs.
- Curated CSVs are point-in-time snapshots. Demand is neutral in the v2 engine
  until a checked source URL and verified figures are supplied.
- `sdg_map_v2.csv` (built by `data/scripts/build_sdg_map_v2.py`) has one row per
  target occupation:
  - 36 rows come from ESCO rules (Green/Digital collections and skill → SDG target);
  - 6 come from the team's verified rows (`sdg_team_v2.csv`);
  - the team's rows for job titles outside the catalogue are kept without an
    `occ_id`.

  Treat `status`, `basis`, `evidence` and `source` as reviewable provenance.
- Synthetic CV intake is bounded and local. Scanned PDFs are not OCR'd.
- `hours_verified` is a hard gate for pathway ROI; missing HRD Corp data is
  represented as `null`, not as a false eligibility claim.
- SDG strength comes from the ESCO skill profile. The team's SDG rows add goals and
  reasons, but no strength unless the role's skills back them; roles without SDG-linked
  skills get little SDG weight.
- Task X-ray labels use global Claude.ai usage, not Malaysian data. "Mostly human"
  means no measurable AI use in the sample, not that AI cannot do the task.
- "Upgrade in place" links tasks to skills by text similarity, not by an official
  task-skill mapping.

Development tooling and provenance are explicit: Python, FastAPI, Pydantic,
Uvicorn, React, Vite, pytest, Replit, Claude Code, ESCO, O*NET, Anthropic
Economic Index extracts, Malaysian public demand records, and UN SDG mapping
rules are used as documented above. No hardcoded credentials or secrets are
stored in the repository.

## License

This project is licensed under the [Apache License 2.0](LICENSE). Upstream data
and provider content remain subject to their respective licenses and terms.
