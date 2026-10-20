# Future Skills Compass API contract

All forecast and ranking responses are estimates. Development mode uses only
the explicitly marked synthetic fixture repository until the verified engine
and course catalogue are available.

## `POST /api/profile/parse`

Request:

```json
{"occupation_id": "office_clerk", "text": "I use Excel for data analysis"}
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

Unknown occupations and unverified IDs are rejected or removed.

## `GET /api/signals`

Returns a list of `{id, name, value, status, label, source}` objects. Every
metric has `label: "Estimate"` and a `source` object containing `source` and
`date`.

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
  `hours_verified`.
- `best_next_hour`: the highest marginal score improvement divided by exact
  verified course hours.

Only courses with `hours_verified: true` participate in `best_next_hour` and
`marginal_score_per_hour`. Courses with `hours_verified: false` or `null`
return `"hours not verified"` and have `marginal_score_per_hour: null`; their
hours are never used in calculations.

When present, `data/curated/courses.csv` is loaded through the course adapter.
It should provide `course_id`, `title`, `provider`, `url`, `cost`,
`hrd_corp_claimable`, `sdg_tags` (semicolon-separated), `skill_ids
(semicolon-separated)`, `hours`, and `hours_verified`. If the file is absent,
the explicitly labeled development catalogue is used.
