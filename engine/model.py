"""The scoring model (F1-F4, skill momentum, 1,000 futures). Pure functions on frames.

F1 exposure   E_o = sum_t w_ot u_t;  A_o = sum_t w_ot u_t auto_t;  G_o = sum_t w_ot u_t aug_t
F2 outlook    O_o = alpha D_o + beta z(G_o) - gamma z(A_o)
F3 momentum   M_k = sum_o r_ok O_o / sum_o r_ok
F4 match      S = 100 (wc C + wo O_hat + wt T) + lambda SDG_o
"""
from __future__ import annotations

from collections.abc import Callable, Iterable

import numpy as np
import pandas as pd


def zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd > 0 else s * 0.0


def exposure(occ_task: pd.DataFrame, task_signals: pd.DataFrame, default_auto: float) -> pd.DataFrame:
    """F1. occ_task: occ_id, task_id, weight. task_signals indexed by task_id.

    Tasks with no observed usage count as u = 0 ("not observed in the sample").
    A used task without a published split gets the snapshot-wide automation share.
    """
    t = occ_task.merge(task_signals, left_on="task_id", right_index=True, how="left")
    t["u"] = t.usage_share.fillna(0.0)
    t["imputed_split"] = t.automation_share.isna() & (t.u > 0)
    t["auto"] = t.automation_share.fillna(default_auto)
    t["aug"] = t.augmentation_share.fillna(1.0 - default_auto)
    t["wu"] = t.weight * t.u
    g = t.groupby("occ_id")
    out = pd.DataFrame({
        "E": g.wu.sum(),
        "A": (t.wu * t.auto).groupby(t.occ_id).sum(),
        "G": (t.wu * t.aug).groupby(t.occ_id).sum(),
        "n_tasks": g.task_id.count(),
        "n_observed": (t.u > 0).groupby(t.occ_id).sum(),
        "observed_weight": (t.weight * (t.u > 0)).groupby(t.occ_id).sum(),
        "n_imputed_split": t.imputed_split.groupby(t.occ_id).sum(),
    })
    out["automation_share"] = np.where(out.E > 0, out.A / out.E.where(out.E > 0, 1), np.nan)
    return out


def outlook(exp: pd.DataFrame, demand_z: pd.Series, alpha: float, beta: float, gamma: float) -> pd.DataFrame:
    """F2. Returns O, O_hat (min-max to 0..1) and the z-scored parts."""
    d = demand_z.reindex(exp.index).fillna(0.0)
    zg, za = zscore(exp.G), zscore(exp.A)
    o = alpha * d + beta * zg - gamma * za
    rng = o.max() - o.min()
    o_hat = (o - o.min()) / rng if rng > 0 else o * 0 + 0.5
    return pd.DataFrame({"D": d, "zG": zg, "zA": za, "O": o, "O_hat": o_hat})


def momentum(occ_skill: pd.DataFrame, o: pd.Series) -> pd.Series:
    """F3. occ_skill: occ_id, skill_uri, r. Returns M_k for every linked skill."""
    t = occ_skill.assign(O=occ_skill.occ_id.map(o))
    t = t.dropna(subset=["O"])
    num = (t.r * t.O).groupby(t.skill_uri).sum()
    den = t.r.groupby(t.skill_uri).sum()
    return num / den


def minmax(x):
    """Scale to 0..1 (a constant input maps to 0)."""
    x = np.asarray(x, dtype=float)
    lo, hi = np.min(x, axis=-1, keepdims=True), np.max(x, axis=-1, keepdims=True)
    rng = hi - lo
    return np.where(rng > 0, (x - lo) / np.where(rng > 0, rng, 1), 0.0)


def radar_status(m: float, threshold: float) -> str:
    return "rising" if m > threshold else "declining" if m < -threshold else "stable"


def match(
    user_skills: Iterable[str],
    essentials: dict[str, list[str]],
    o_hat: pd.Series,
    m: pd.Series,
    similarity: Callable[[list[str], list[str]], np.ndarray],
    *,
    weights: dict[str, float],
    kappa: float,
    sdg: pd.Series | None = None,
    sdg_lambda: float = 0.0,
    exclude: Iterable[str] = (),
    normalise: bool = True,
) -> pd.DataFrame:
    """F4 for every occupation in `essentials` (occ_id -> essential skill URIs).

    C = momentum-weighted share of essential skills the user has (weight exp(kappa M_k));
    T = mean over missing essential skills of the best similarity to any user skill.
    With normalise=True, C and T are min-max scaled across roles (like O_hat)
    before weighting; the raw values are kept in C_raw / T_raw.
    """
    user = list(dict.fromkeys(user_skills))
    owned = set(user)
    excluded = set(exclude)
    rows = []
    for occ, ess in essentials.items():
        if occ in excluded or not ess:
            continue
        w = np.exp(kappa * m.reindex(ess).fillna(0.0).to_numpy())
        have = np.array([k in owned for k in ess])
        c = float(w[have].sum() / w.sum())
        missing = [k for k, h in zip(ess, have) if not h]
        if not missing:
            t = 1.0
        elif not user:
            t = 0.0
        else:
            t = float(similarity(missing, user).max(axis=1).mean())
        sdg_o = float(sdg.get(occ, 0.0)) if sdg is not None else 0.0
        rows.append({"occ_id": occ, "C_raw": c, "T_raw": t, "O_hat": float(o_hat[occ]), "SDG": sdg_o,
                     "n_essential": len(ess), "matched": [k for k, h in zip(ess, have) if h], "missing": missing})
    df = pd.DataFrame(rows)
    df["C"] = minmax(df.C_raw) if normalise else df.C_raw
    df["T"] = minmax(df.T_raw) if normalise else df.T_raw
    df["pts_coverage"] = 100 * weights["coverage"] * df.C
    df["pts_outlook"] = 100 * weights["outlook"] * df.O_hat
    df["pts_transferability"] = 100 * weights["transferability"] * df["T"]
    df["pts_sdg"] = sdg_lambda * df.SDG
    df["S"] = df.pts_coverage + df.pts_outlook + df.pts_transferability + df.pts_sdg
    df = df.sort_values(["S", "occ_id"], ascending=[False, True]).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df) + 1)
    return df


def futures(
    ranked: pd.DataFrame,
    essentials: dict[str, list[str]],
    m: pd.Series,
    user_skills: Iterable[str],
    *,
    weights: dict[str, float],
    kappa: float,
    runs: int,
    r: float,
    seed: int,
    top_n: int,
    sdg_lambda: float = 0.0,
    normalise: bool = True,
) -> pd.DataFrame:
    """1,000 futures: perturb each M_k by (1 + U(-r, r)), recompute C, re-rank.

    O_hat and T do not depend on M_k, so only coverage moves. Returns per role
    P(in top n), median score and P10/P90.
    """
    occs = list(ranked.occ_id)
    skills = sorted({k for o in occs for k in essentials[o]})
    idx = {k: i for i, k in enumerate(skills)}
    ess = np.zeros((len(occs), len(skills)))
    for i, o in enumerate(occs):
        ess[i, [idx[k] for k in essentials[o]]] = 1.0
    owned = np.array([k in set(user_skills) for k in skills], dtype=float)
    base_m = m.reindex(skills).fillna(0.0).to_numpy()

    rng = np.random.default_rng(seed)
    noise = rng.uniform(-r, r, size=(runs, len(skills)))
    wts = np.exp(kappa * base_m * (1.0 + noise))            # runs x skills
    c = (wts * owned) @ ess.T / (wts @ ess.T)               # runs x occs
    if normalise:
        c = minmax(c)                                        # per run, across roles
    fixed = (weights["outlook"] * ranked.O_hat.to_numpy() + weights["transferability"] * ranked["T"].to_numpy()
             ) * 100 + sdg_lambda * ranked.SDG.to_numpy()
    scores = 100 * weights["coverage"] * c + fixed
    order = np.argsort(-scores, axis=1, kind="stable")
    ranks = np.empty_like(order)
    np.put_along_axis(ranks, order, np.arange(1, len(occs) + 1)[None, :].repeat(runs, 0), axis=1)
    return pd.DataFrame({
        "occ_id": occs,
        "p_top": (ranks <= top_n).mean(axis=0),
        "worst_rank": ranks.max(axis=0),
        "median": np.median(scores, axis=0),
        "p10": np.percentile(scores, 10, axis=0),
        "p90": np.percentile(scores, 90, axis=0),
    })
