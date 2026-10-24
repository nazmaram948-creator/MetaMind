# SkillShift MY

> SkillShift MY (Future Skills Compass) is an AI-powered, deterministic career-transition analysis platform that guides Malaysian workers and students from their current skill sets to sustainable, future-ready roles in the AI era.

---

## Team Information

| Field                  | Details                                     |
| ---------------------- | ------------------------------------------- |
| **Team Name**          | MetaMind                                    |
| **Team Domain**        | Domain 1                                    |
| **SDG Track (1–17)**   | SDG 4 - Quality Education &                 |
                         | SDG 8 - Decent Work and Economic Growth     |
| **Team Leader**        | Sallam Maram Niyazi Abdulmawla              |
| **University**         | XMUM / UniKL MIIT                           |
| **Number of Members**  | 5                                           |

## Links

| Resource          | Link                                           |
| ----------------- | ---------------------------------------------- |
| GitHub Repository | https://github.com/nazmaram948-creator/MetaMind/tree/dc22bc7743d20d1c0467a601fd88aa2b7edd5785  |
| Live Demo         | https://meta-mind-1.replit.app                 |
| RunPod Endpoint   | Not used                                       |
| Slide Deck        |                                                |
| Demo Video        |                                                |

---

## Overview

### Problem

In Malaysia, 56% of professionals already utilize AI tools at work, yet only 26% have received formal training, while over 600,000 workers require reskilling within three to five years. This challenge severely impacts displaced working adults, fresh graduates, career switchers, and HR leaders seeking actionable upskilling pathways. Traditional career guidance relies on static lists that become obsolete as AI capabilities evolve, leaving workers unable to identify resilient skills and failing to align career growth with global sustainability goals.

### Solution

SkillShift MY turns public, dated data into a transparent career path. A person uploads a synthetic CV (PDF or text), pastes text, or picks a demo profile. A small pre-trained embedding model matches the CV phrases to ESCO skills, and the person confirms or removes each one. The engine then ranks 42 occupations with an explainable score built from skill coverage, role outlook (from Anthropic Economic Index snapshots) and transferability, and tests how stable each ranking is across 1,000 simulated futures. Every role is linked to the SDGs it supports, and a learning pathway lists catalogue courses for the person's skill gaps. Every forecast is labelled "Estimate" with its source and date, and anything that is not in the database is blocked, so the system cannot invent jobs, courses or statistics.

### Key Features

- **Skills intake & verification** —  Upload a CV (PDF/text), paste text, or use a synthetic profile; skills map to ESCO for user confirmation or removal.
- **Future Skills Radar** — Displays rising, stable, and declining skills via Anthropic Economic Index data, complete with source/date badges and a Moderate/Fast AI-adoption toggle.
- **Explainable role matching** — Simulates 1,000 runs varying skill momentum by ±20% to identify "Safest picks" (frequency in top 5), clearly marked as an estimate with visible assumptions.
- **1,000-futures robustness estimate** — Generates personalized "Best Next Hour" upskilling recommendations linked to verified HRD Corp courses, explicitly mapping every skill and role to UN SDG targets (SDG 4 & SDG 8) with an interactive SDG trade-off slider.
- **Live data refresh** — Load newer data" updates the AEI snapshot from Nov 2025 to May 2026, explaining rank shifts.
- **SDG explorer & slider** — Links each role to justified SDGs, using an interactive slider to re-rank roles by blending skill fit with SDG alignment.
- **Learning pathway** — Suggests curated courses for skill gaps; displays only verified hours, labels cost/HRD Corp status as unverified/unknown, and flags when gaps lack matching courses.
- **Guardrails & privacy** — Blocks unknown skill, role, or course IDs (validated via 50-run testing), omits age and gender collection, and restricts usage to synthetic profiles.

### Tech Stack

| Layer         | Technology                   |
| ------------- | ---------------------------- |
| Frontend      | React 19, Vite, Recharts (plain CSS)    |
| Backend       | Python 3.12, FastAPI, Uvicorn, Pydantic, pdfplumber (PDF text, capped at 20,000 characters)  |
| Database      | SQLite, built from curated CSV files and data extracts with pandas (`python -m engine.build`) |
| AI / Compute  | Pre-trained sentence-transformers model `all-MiniLM-L6-v2` on CPU for skill matching; NumPy for scoring and the 1,000-run Monte Carlo estimate.                                        |
| Hosting / Dev | **Replit** (deployment, secrets), GitHub (version control), Claude Code and the Replit Agent (AI-assisted development, declared in the Technical Declaration)                           |

---

## Project Structure

The tree below shows the real layout of this repository.

```
MetaMind/
├── .replit                    # Replit run workflow and [deployment] build/run commands
├── .gitignore
├── LICENSE                    # Apache License 2.0
├── README.md
├── docs/                      # Project documentation
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app and /api/* routes (also serves the built frontend)
│   │   ├── schemas.py         # Request/response models
│   │   ├── config.py          # Environment-backed settings
│   │   └── services/          # Engine adapter, curated-data loader, CV text extraction
│   ├── tests/                 # API, curated-data and 50-run guardrail tests
│   ├── API_CONTRACT.md        # API contract used by the frontend
│   ├── pytest.ini
│   ├── requirements.txt
│   └── .env.example           # Environment template (no secrets)
├── engine/
│   ├── build.py               # Builds data/skillshift_v2.db from the curated data
│   ├── config.yaml            # Weights, simulation settings
│   ├── service.py             # Ranking, scenarios, snapshot diff, robustness
│   ├── model.py, parse.py, similarity.py, store.py
│   ├── guardrail.py           # Blocks IDs that are not in the database
│   ├── llm.py                 # Optional LLM interface, disabled by default
│   └── tests/
├── data/
│   ├── curated/               # Team-curated courses, SDG map, personas
│   ├── extracts/              # ESCO, O*NET and AEI extracts
│   ├── scripts/               # Scripts that build and check the curated files
│   └── tests/
├── frontend/
│   ├── src/                   # React app (components/, api.js)
│   ├── public/samples/        # Synthetic sample CVs (PDF)
│   └── package.json
└── submission/
    ├── SDC2026_Metamind_Preliminary.pdf
    ├── SDC2026_Metamind_TechDeclaration.pdf
    └── SDC2026_Metamind_Replit_POU.pdf
```

The generated database `data/skillshift_v2.db` is not committed. It is built with `python -m engine.build`.

### Architecture

```
User ──► Replit (React UI + FastAPI API, one app)
                │
                ├──► Engine (Python): skill matching, momentum, scoring, 1,000-run estimate
                │        └──► Embedding model on CPU (all-MiniLM-L6-v2)
                │
                ├──► SQLite database (ESCO, O*NET, AEI snapshots, course and SDG tables)
                │
                └──► Response returned to user
```

## How to Run

### Option 1 — Run on Replit (Recommended)

1. On Replit, choose **Import from GitHub** and select `nazmaram948-creator/MetaMind`.
2. Open the **Secrets** tab and add `ENGINE_MODE` = `true`. No RunPod keys are needed because RunPod is not used.
3. Click **Run**. The workflow builds the database (`python -m engine.build`), builds the frontend, and starts the backend on port 5000 serving the app. The first start takes a few minutes because the embedding model (about 90 MB) is downloaded.

To publish, use the **Publish** tab. The deployment build installs dependencies, builds the frontend, builds the database and downloads the model; the run command only starts the backend.

### Option 2 — Run Locally

Requirements: Python 3.12 or newer, Node.js 20 or newer.

```bash
git clone https://github.com/nazmaram948-creator/MetaMind.git
cd MetaMind

python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1

pip install -r backend/requirements.txt

cp backend/.env.example backend/.env   # optional; leave the API key lines empty

python -m engine.build                 # builds data/skillshift_v2.db

cd frontend && npm install && npm run build && cd ..

ENGINE_MODE=true python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 5000
```

Open http://localhost:5000. The API documentation is at http://localhost:5000/docs.

On Windows PowerShell, set the variable with `$env:ENGINE_MODE="true"` before the last command.

For frontend development, run the backend on port 8000 (`--port 8000`) and, in another terminal, `cd frontend && npm run dev`, then open http://localhost:5173.

### Run Tests

```bash
pytest -c backend/pytest.ini -q
```

This runs the API, curated-data and guardrail tests, including the 50-run guardrail check, which writes `backend/tests/guardrail_50run_report.json`. The curated data files can be checked with:

```bash
pytest data/tests/check_curated_v2.py -q
```

---

## How We Use Replit *(Required)*

- **Development:** the repository lives on GitHub. Replit was used to import the repository, configure the run workflow and the deployment (`.replit`), and test the production build.
- **Hosting (Deployments):** the live prototype is published with Replit Deployments (Autoscale) at https://meta-mind-1.replit.app. One Replit app serves both the FastAPI backend and the built React frontend.
- **Secrets:** configuration is kept in Replit Secrets (`ENGINE_MODE`) and is also set as a deployment secret. No keys or passwords are stored in the repository.
- **Proof of use:** see `submission/SDC2026_Metamind_Replit_POU.pdf`.

## How We Use RunPod *(Required)*

**RunPod is not used.**

- **AI workload:** SkillShift MY needs no model training and no large-model inference. Its only model is the pre-trained `all-MiniLM-L6-v2` sentence-embedding model (about 90 MB), which matches CV phrases to ESCO skills and runs on CPU inside the Replit app. Ranking and the 1,000-run robustness estimate are NumPy calculations.

---

## Challenges & Learnings


- **Keeping AI output grounded.** Our first design let a language model help with skill extraction and explanations, and included a RunPod GPU hook. We found that a generative model adds the risk of invented skills and courses, which breaks the rule that every recommendation must come from a real source. We switched to a small embedding model for matching and a database ID allowlist (guardrail) for everything the API returns, kept the LLM interface optional and disabled, and removed the RunPod hook. We learned that for a grounded recommender, retrieval plus validation beats free-form generation.
- **Data format mismatches hid real gaps.** A mismatch between how the build matched SDG rows (by occupation title) and how a data file keyed them (by ID) silently replaced 36 real SDG mappings with generic "SDG 8" fallback tags. All automated tests still passed. We fixed the matching, wrote a data checker, and learned to test data coverage as well as code.
- **Stale builds.** The database is generated from the CSV files, so changing a file does nothing until it is rebuilt. We moved the build into the deployment build step and documented `python -m engine.build`.
- **Deploying on Replit.** A published app starts from a fresh machine with no installed packages and a reset file system, so the deployment build must install dependencies, build the frontend and database, and pre-download the model.

## Future Improvements

- [ ] Replace the SDG count with a score that measures how well a role fits each SDG target, and have every SDG link reviewed by a human.
- [ ] Verify course costs and HRD Corp claimability, and expand the course-to-skill mapping so more roles get a real pathway and a trustworthy "best next hour".
- [ ] Use DOSM/PERKESO demand data in the role outlook once it is entered with sources.
- [ ] Add a task-level "Task X-ray" and "Upgrade in place" view based on AEI task data.
- [ ] Add an HR team view with a workforce skills-gap heatmap.
- [ ] Add English, Bahasa Malaysia and Chinese language support and fairness checks.
- [ ] Offer optional LLM-written explanations behind the same ID allowlist, with a GPU endpoint (for example RunPod) only if a larger model is needed.

## Team

| Name                   | Role                                                          | GitHub                                   |
| ---------------------- | ------------------------------------------------------------- | ---------------------------------------- |
| Sallam Maram Niyazi    | Team leader, Frontend and deployment; React frontend          | nazmaram948-creator                      |  
                         |(CV intake, Skills Radar, role cards,                          |                                          |
                         |SDG explorer and slider, learning pathway), Replit             |                                          |
                         |deployment and publishing, repository and data-file checks.    |                                          |
| Maxim Morozov          | Data and engine; Linking ESCO, O*NET and Anthropic Economic   | vindigomakster2-hub                      |
                         |Index data, skill momentum and role outlook, match score,      |                                          |          
                         |snapshot comparison, 1,000-run robustness estimate.            |                                          |
| Mohammad Azri          | Backend and API; FastAPI endpoints, database ID guardrail     | mohammadazri                             |
                         |and the 50-run guardrail test, pathway and SDG data fixes,     |                                          |
                         |pathway fallback flag.                                         |                                          |
| Al-Asbahi Fatima Khaled| Documentation and submission; Project proposal, technical     | fatima-khaled                            |
                         |declaration, README, slide deck, demo video and the final      |                                          |
                         |submission.                                                    |                                          |
| Walid Abdalla Awadh    | Data and content; Course catalogue, SDG mapping, synthetic    | wirleed                                  |
                         |personas and testing.                                          |                                          |

---

## Submission Checklist

- [x] Team name, domain (Domain 1 / Domain 2) and SDG track filled in
- [ ] Slide deck link added
- [ ] Demo video link added
- [ ] Replit used, with proof of use in `submission/`
- [ ] RunPod used, with proof of use in `submission/`
- [ ] Preliminary submission completed (`SDC2026_TeamName_Preliminary.pdf`)
- [ ] Technology declaration completed (`SDC2026_TeamName_TechDeclaration.pdf`)
- [ ] Submission files renamed with your team name (replace `TeamName`)
- [x] "How to Run" steps verified
- [x] No API keys or secrets committed to the repository
---
## Known limitations and tooling declaration

- The fixture extractor is deterministic phrase/alias matching. It is not a
  general semantic parser and unknown phrases are not converted into invented
  IDs.
- Curated CSVs are point-in-time snapshots. Demand is neutral in the v2 engine
  until a checked source URL and verified figures are supplied.
- `sdg_map_v2.csv` is generated from project mapping rules and contains 42
  occupation rows in this checkout; treat its `status`, `basis`, and `evidence`
  fields as reviewable provenance.
- Synthetic CV intake is bounded and local. Scanned PDFs are not OCR'd.
- `hours_verified` is a hard gate for pathway ROI; missing HRD Corp data is
  represented as `null`, not as a false eligibility claim.
- The engine's `sdg_lambda` is currently `0.0`; the fixture API supports the
  `sdg_preference` contract while real-engine SDG weighting remains a configured
  follow-up.

Development tooling and provenance are explicit: Python, FastAPI, Pydantic,
Uvicorn, React, Vite, pytest, Replit, Claude Code, ESCO, O*NET, Anthropic
Economic Index extracts, Malaysian public demand records, and UN SDG mapping
rules are used as documented above. No hardcoded credentials or secrets are
stored in the repository.


## License

This project is licensed under the Apache License 2.0.

