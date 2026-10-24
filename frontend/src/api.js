// Same-origin by default: Vite proxies /api in dev, FastAPI serves the build in prod.
const BASE = import.meta.env.VITE_API_BASE ?? "";

async function request(path, options = {}) {
  const res = await fetch(BASE + path, options);
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* empty or non-JSON body */
  }
  if (!res.ok) {
    const detail = body?.detail;
    const msg = typeof detail === "string" ? detail : Array.isArray(detail) ? detail[0]?.msg : null;
    const error = new Error(msg || `${path} failed (${res.status})`);
    error.status = res.status; // lets callers tell "not built yet" (501) from a real failure
    throw error;
  }
  return body;
}

const json = (path, payload) =>
  request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const getHealth = () => request("/health");
export const getPersonas = () => request("/api/personas");
export const getOccupations = () => request("/api/occupations");
export const getContext = () => request("/api/context");
export const getSdg = () => request("/api/sdg");

export const getPathway = (skill_ids, target_role_id, sdg_filter = null) =>
  json("/api/pathway", { skill_ids, target_role_id, sdg_filter });

export const parseProfile = (text, occupation_id) =>
  json("/api/profile/parse", { text, occupation_id: occupation_id || null });

export function parseFile(file, occupation_id) {
  const form = new FormData();
  form.append("file", file);
  if (occupation_id) form.append("occupation_id", occupation_id);
  return request("/api/profile/parse_file", { method: "POST", body: form });
}

// sdg_preference is sent only when given, so existing callers send the same body as before
export const matchRoles = (skill_ids, current_occupation_id, scenario, sdg_preference) =>
  json("/api/match", {
    skill_ids,
    current_occupation_id: current_occupation_id || null,
    scenario,
    ...(sdg_preference !== undefined && { sdg_preference }),
  });

export function getSignals(skill_ids, scenario) {
  const q = new URLSearchParams({ scenario });
  skill_ids.forEach((id) => q.append("skill", id));
  return request(`/api/signals?${q}`);
}

export const loadSnapshot = (snapshot_id) => json("/api/snapshot/load", { snapshot_id });

export const diffSnapshots = (skill_ids, current_occupation_id, scenario) =>
  json("/api/snapshot/diff", {
    skill_ids,
    current_occupation_id: current_occupation_id || null,
    scenario,
    baseline_snapshot_id: "baseline_snapshot",
    new_snapshot_id: "latest_snapshot",
  });
