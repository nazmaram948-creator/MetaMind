// Official UN titles of the 17 Sustainable Development Goals (sdgs.un.org/goals).
// Names only: which goals a role links to always comes from /api/sdg.
export const SDG_NAMES = {
  1: "No Poverty",
  2: "Zero Hunger",
  3: "Good Health and Well-being",
  4: "Quality Education",
  5: "Gender Equality",
  6: "Clean Water and Sanitation",
  7: "Affordable and Clean Energy",
  8: "Decent Work and Economic Growth",
  9: "Industry, Innovation and Infrastructure",
  10: "Reduced Inequalities",
  11: "Sustainable Cities and Communities",
  12: "Responsible Consumption and Production",
  13: "Climate Action",
  14: "Life Below Water",
  15: "Life on Land",
  16: "Peace, Justice and Strong Institutions",
  17: "Partnerships for the Goals",
};

export const SDG_NOTE = "SDG links as returned by the API, no source date provided";

/** "SDG 4; SDG 9" -> [4, 9]. Only numbers present in the API string, nothing inferred. */
export const goalsOf = (link = "") => [...link.matchAll(/SDG\s*(\d{1,2})/g)].map((m) => Number(m[1]));

/** The reasoning chains several "skill -> target" clauses; the first one is the one-line reason. */
export const firstClause = (text = "") => text.split(/;\s*/)[0];

/** /api/sdg rows keyed by lower-case occupation title, which equals the role title. */
export const indexSdg = (rows) =>
  Object.fromEntries(rows.map((r) => [r.occupation.toLowerCase(), { ...r, goals: goalsOf(r.sdg_link) }]));
