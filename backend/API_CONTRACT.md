# Future Skills Compass API contract

All forecast and ranking responses are estimates. Development mode uses only
the explicitly marked synthetic fixture repository until the verified engine
and course catalogue are available.

## `POST /api/profile/parse`

Request:

```json
{
  "occupation_id": "office_clerk",
  "text": "I use Excel for data analysis",
  "current_skills": ["Basic Excel"]
}
```

Response:

```json
{
  "skills": [
    {
      "skill_id": "skill-data-analysis",
      "skill_name": "Data analysis",
      "extracted_phrase": "data analysis",
      "confidence": 0.95
    }
  ],
  "label": "Estimate",
  "assumption_note": "..."
}
```

Unknown occupations and unverified IDs are rejected or removed. Both `text`
and plain-English `current_skills` are normalized to verified curated
`ESCO-*` skill IDs.

## `GET /api/signals`

Returns the 20 Malaysian demand records as signal badges. Each object includes
`name`, `base_vacancies_2025`, `projected_vacancies_2026`,
`growth_rate_pct`, `status` (`rising`, `declining`, or `stable`), and a
`source` object containing the original `source` and `date_published`.

## `GET /api/sdg`

Returns one record per engine occupation with `occupation`, `sdg_link`,
`reasoning`, `status`, `basis`, `evidence`, `source`, and `date`. The current
engine catalogue contains 42 occupations.
These records are intentionally exposed independently from demand signals:
there is no exact occupation-name join between the two curated files.

## `GET /api/personas`

Returns `individual_users` and `hr_team_cohort` from the synthetic persona
catalogue. Individual users include CV text and skills for one-click demo
profile loading. `USR-002` is a fresh graduate and correctly returns
`"current_role": null`. Each persona also includes `normalized_skill_ids`.

## `POST /api/match`

Request:

```json
{
  "skill_ids": ["skill-data-analysis"],
  "current_occupation_id": null,
  "scenario": "moderate",
  "sdg_preference": 0.5
}
```

The response contains ranked role objects with score breakdown, matched and
missing verified skill IDs, estimate labeling, and source badges. Each role
also includes:

```json
{
  "robustness_estimate": "Estimate: stays in your top 5 in 100% of simulated futures",
  "robustness": {
    "runs": 1000,
    "variation": 0.2,
    "top5_count": 1000,
    "top5_frequency": 1.0,
    "label": "Estimate",
    "assumption_note": "..."
  }
}
```

The simulation applies independent `U(-0.2, 0.2)` momentum variation per
role skill for 1,000 runs. It is an adapter seam for Shishka's future engine;
the development implementation uses the fixture role trend as its momentum
source.

## `POST /api/snapshot/load`

Request: `{"snapshot_id": "baseline_snapshot"}`. The response confirms the
active snapshot, timestamp, and source metadata.

## `POST /api/snapshot/diff`

Request:
`{"skill_ids": [], "baseline_snapshot_id": "baseline_snapshot", "new_snapshot_id": "latest_snapshot"}`.
The response provides per-role movement and a human-readable explanation.

## `POST /api/pathway`

Request:

```json
{
  "skill_ids": [],
  "target_role_id": "role-project-support",
  "sdg_filter": null
}
```

Response fields:

- `missing_skills`: verified skill IDs still needed by the role.
- `pathway`: course recommendations with `course_id`, `title`, `provider`,
  `url`, `cost`, `hrd_corp_claimable`, `sdg_tags`, `hours`, and
  `hours_verified`, and `source_badges`.
- `best_next_hour`: the highest marginal score improvement divided by exact
  verified course hours.

Only courses with `hours_verified: true` participate in `best_next_hour` and
`marginal_score_per_hour`. Courses with `hours_verified: false` or `null`
return `"hours not verified"` and have `marginal_score_per_hour: null`; their
hours are never used in calculations.

The current curated course schema does not provide an HRD Corp eligibility
column, so curated rows return `hrd_corp_claimable: null` (unknown) rather
than an unsupported claim. The field is ready for the real catalogue to
populate. Pathway `sdg_tags` are derived from the target role's curated SDG
mapping.

When present, `data/curated/courses.csv` is loaded through the course adapter.
It provides `course_id`, `course_title`, `provider`, `skill_ids`
(semicolon-separated), `hours`, `hours_verified`, `cost`, and `url`.
The loader validates all fields and splits every `skill_ids` value on `;`.
If the file is absent, the explicitly labeled development catalogue is used.

## Engine mode (`ENGINE_MODE=true`)

Same routes and response models, served from the real engine. Differences:

- **IDs are real.** `skill_id` values are ESCO v1.2 skill URIs, for example
  `http://data.europa.eu/esco/skill/1973c966-...`. `role_id` and `occupation_id`
  are `occ_id` values from `data/curated/target_occupations.csv`, such as
  `accounts_clerk` and `bookkeeper`. Unknown IDs are dropped by the guardrail;
  an unknown `occupation_id` returns `422`.
- **Display names:** show `skill_name`, `matched_skill_names` and
  `missing_skill_names`. Do not prettify the URIs.
- **`POST /api/profile/parse`** skills carry `status`: `suggested` (cosine ≥ 0.60)
  or `needs_confirmation`.
- **`POST /api/profile/parse_file`** (new) takes multipart `file` (PDF or `.txt`,
  max 2 MB) and an optional form field `occupation_id`. It returns the same body
  as `parse`.
- **`GET /api/signals?skill=<uri>&skill=<uri>&scenario=moderate|fast&snapshot_id=`**
  returns the Skills Radar. Each item has `value` = skill momentum (z-units), `status`
  (`rising`, `stable` or `declining`), `is_green`, `is_digital`, `label: "Estimate"`
  and `source`. Without `skill` it returns the strongest rising and declining skills.
- **`POST /api/match`** accepts `current_occupation_id: null` for fresh graduates and
  switchers; otherwise that occupation is left out. Each role adds:
  - `rank`, `essential_skills_total`, `matched_skill_names`, `missing_skill_names`;
  - `score_points`: the points from coverage, outlook and transferability, which sum
    to `total_match_score`;
  - `score_breakdown`: what the user reads. `skills_covered_score` is the raw share of
    essential skills held, `role_trend_score` the outlook index from 0 to 100,
    `transferability_score` the raw similarity of missing skills to held ones;
  - `ai_exposure`: `automation_share_pct` of the role's observed tasks, with source;
  - `robustness`: `top5_frequency`, `median_score`, `p10`, `p90`, `worst_rank`,
    `safest_pick` and `assumption_note`.

  `source_badges` list the AEI snapshot, ESCO and O*NET with dates and URLs.
- **`POST /api/snapshot/load`**: `baseline_snapshot` = AEI Nov 2025 (`aei_2025_11`),
  `latest_snapshot` = AEI May 2026 (`aei_2026_05`).
- **`POST /api/snapshot/diff`** also accepts `current_occupation_id` and `scenario`.
  Each change has `old_rank`, `new_rank`, `movement`, `old_score`, `new_score`,
  `driving_metric` (`outlook` or `skill momentum`), `explanation` and `source`.
- **`GET /api/occupations`** (new): the 42 target occupations for the current-job picker.
- **`GET /api/context?snapshot_id=`** (new): Malaysia vs global AI-usage figures from
  the AEI snapshot, labelled as observed usage. A value is `null` where that release
  does not publish it.
- **`POST /api/pathway`** takes `skill_ids`, `target_role_id` and optionally
  `current_occupation_id` and `scenario`. It returns the role's missing essential
  skills in learning order (broader ESCO concepts first, then by score gain), with
  one course per skill.
  - Each course has `step`, `skill_id`, `skill_name`, `also_covers` (other missing
    skills the same course teaches), `gain_points`, `sdg_tags` (the role's SDGs)
    and `source_badges`, which point to the course page and the date it was checked.
  - `hours` is a number only when `hours_verified` is true; otherwise it is
    `"hours not verified"` and `marginal_score_per_hour` is `null`.
  - `cost` is MYR, or `null` when not checked. `hrd_corp_claimable` is `null` when
    not checked.
  - `best_next_hour` is the verified course with the largest score gain across the
    user's top 10 roles per hour, or `null`.
  - The response also has `totals` (`courses`, `verified_hours`,
    `unverified_courses`, `cost_myr`, `cost_unknown`) and `skills_without_course`.
- **`GET /api/xray?occupation=<occ_id>&snapshot_id=`**: Task X-ray of a job.
  - Each O*NET task has `weight_pct` (importance), `usage_share_pct` (share of all
    Claude.ai chats), `automation_pct`, `augmentation_pct`, a `label`
    (`automating` / `assisting` / `mostly human`) and a `note`.
  - The response also has `summary_weight_pct`, the `thresholds` used (from
    `engine/config.yaml`), `source_badges`, and `label: "Estimate"`.
- **`POST /api/upgrade`** takes `{occupation_id, skill_ids, scenario}`: "upgrade in
  place". It lists skills of the current job, most similar to its `assisting` tasks,
  that the user lacks. Each has `supports_tasks`, `task_weight_pct`, `momentum`,
  `momentum_status` and a `course` (or `null`).
- **`GET /api/team`** (synthetic demo cohort) and **`POST /api/team`** (`{members:
  [{id, name, current_occ_id, skill_ids | skills}], scenario}`, synthetic data only):
  the HR heatmap. For each member, `task_split_pct` is the X-ray split of the current
  job and `top_roles` are their top 3 roles.
- **`GET /health`** and **`GET /api/health`** expose the active mode and
  `compute_provider` (`local-deterministic` or `runpod-serverless`).

Frontend note: `frontend/src/api.js` calls `http://localhost:8000`. For single-port
hosting (FastAPI serves `frontend/dist` when it exists) the base URL should be
relative (`""`).
