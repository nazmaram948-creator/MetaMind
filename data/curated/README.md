# data/curated

Hand-curated inputs. Two versions are kept side by side until the team picks one:

- **v1**: the team's original files, unchanged. The backend loads these today.
- **v2**: corrected versions keyed to real ESCO v1.2 IDs and to our 42 target
  occupations (`target_occupations.csv`). They are new files; nothing in v1 was edited.

| Topic | v1 (team, unchanged) | v2 (new) | What v2 fixes |
|---|---|---|---|
| Courses | `courses.csv` | `courses_v2.csv` (built by `data/scripts/build_courses_v2.py` from `course_skill_map_v2.csv` + `course_page_checks.csv`) | v1 `skill_ids` such as `ESCO-DA-01` are not ESCO identifiers, so courses could not be linked to skills. v2 uses real ESCO skill URIs. `hours_verified` is true only when the course page states the hours, and the method is recorded. |
| Demand | `malaysian_job_demand_real.csv` | `demand_occupation_map.csv` (links each v1 row to an `occ_id` / MASCO group) and `demand_masco_v2.csv` (MASCO major groups × quarter, **empty placeholders + TODO**) | v1 rows have no source URL and use free-text job titles. Until the DOSM figures are entered with URLs, the engine treats demand as neutral. |
| SDGs | `sdg_mapping.csv` | `sdg_map_v2.csv` (built by `data/scripts/build_sdg_map_v2.py`) | v1 is keyed by job titles that are not in our catalogue, so no recommended role could get an SDG tag. v2 covers all 42 occupations, with the basis and ESCO evidence for each link. |
| Personas | `synthetic_personas.json` | `personas_v2.json` and `persona_occupation_map.csv` (maps v1 personas to `occ_id`) | v2 follows the brief: accounts clerk (Aina, Selangor), customer-service officer and data-entry clerk with full synthetic CVs, plus v1's fresh graduate. Same JSON shape as v1, so the backend loader accepts either. |

Rules that apply to both versions:

- Synthetic or public data only. No age, gender, NRIC, phone or e-mail in any persona.
- An ID that is not in the database is never shown (guardrail).
- Every v2 row carries a `status` or `note` saying what still needs a human check.

Check the v2 files after any edit:

```bash
pytest data/tests/check_curated_v2.py -q
```

To rebuild the generated v2 files:

```bash
python data/scripts/extract_esco.py        # ESCO extracts used for validation
python data/scripts/check_course_pages.py  # live check of course pages (cached)
python data/scripts/build_courses_v2.py
python data/scripts/build_sdg_map_v2.py
```
