const BASE = "http://localhost:8000";

async function request(path, options) {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

const post = (path, body) =>
  request(path, { method: "POST", body: JSON.stringify(body) });

export const parseProfile = (occupation_id, text) =>
  post("/api/profile/parse", { occupation_id, text });
export const getSignals = () => request("/api/signals");
export const getPersonas = () => request("/api/personas");
export const matchRoles = (skill_ids, scenario = "moderate", sdg_preference = 0.5) =>
  post("/api/match", { skill_ids, current_occupation_id: null, scenario, sdg_preference });
export const loadSnapshot = (snapshot_id) =>
  post("/api/snapshot/load", { snapshot_id });
export const diffSnapshots = (skill_ids, baseline, latest) =>
  post("/api/snapshot/diff", {
    skill_ids,
    baseline_snapshot_id: baseline,
    new_snapshot_id: latest,
  });
export const getPathway = (skill_ids, target_role_id, sdg_filter = null) =>
  post("/api/pathway", { skill_ids, target_role_id, sdg_filter });