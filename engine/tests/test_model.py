"""Unit tests for the scoring functions on tiny hand-made inputs."""
import numpy as np
import pandas as pd
import pytest

from engine import model


def test_exposure_weights_usage_and_split():
    occ_task = pd.DataFrame({"occ_id": ["a", "a", "b"], "task_id": [1, 2, 3], "weight": [0.75, 0.25, 1.0]})
    sig = pd.DataFrame({"usage_share": [0.02, np.nan, 0.01], "automation_share": [0.6, np.nan, np.nan],
                        "augmentation_share": [0.4, np.nan, np.nan]}, index=[1, 2, 3])
    e = model.exposure(occ_task, sig, default_auto=0.5)
    assert e.E["a"] == pytest.approx(0.015)          # 0.75 * 0.02, task 2 not observed
    assert e.A["a"] == pytest.approx(0.009)
    assert e.G["a"] == pytest.approx(0.006)
    assert e.n_observed["a"] == 1 and e.observed_weight["a"] == pytest.approx(0.75)
    assert e.n_imputed_split["b"] == 1                # used task without a split -> default share
    assert e.automation_share["b"] == pytest.approx(0.5)


def test_outlook_penalises_automation_more_in_fast_scenario():
    exp = pd.DataFrame({"G": [1.0, 2.0, 3.0], "A": [3.0, 2.0, 1.0]}, index=["x", "y", "z"])
    moderate = model.outlook(exp, pd.Series(dtype=float), 1, 1, 1)
    fast = model.outlook(exp, pd.Series(dtype=float), 1, 1, 2)
    assert moderate.O["z"] > moderate.O["x"]
    assert fast.O["x"] < moderate.O["x"] and fast.O["z"] > moderate.O["z"]
    assert moderate.O_hat.min() == 0 and moderate.O_hat.max() == 1
    assert (moderate.D == 0).all()                    # no demand data -> neutral


def test_outlook_uses_demand():
    exp = pd.DataFrame({"G": [1.0, 1.0], "A": [1.0, 1.0]}, index=["x", "y"])
    o = model.outlook(exp, pd.Series({"x": 1.0, "y": -1.0}), 1, 1, 1)
    assert o.O["x"] > o.O["y"]


def test_momentum_is_weighted_mean_of_outlooks():
    occ_skill = pd.DataFrame({"occ_id": ["a", "b", "a"], "skill_uri": ["k1", "k1", "k2"], "r": [1.0, 0.5, 1.0]})
    m = model.momentum(occ_skill, pd.Series({"a": 2.0, "b": -1.0}))
    assert m["k1"] == pytest.approx((2.0 - 0.5) / 1.5)
    assert m["k2"] == pytest.approx(2.0)


def test_radar_status():
    assert model.radar_status(0.5, 0.25) == "rising"
    assert model.radar_status(-0.5, 0.25) == "declining"
    assert model.radar_status(0.1, 0.25) == "stable"


def sim_identity(a, b):
    return np.array([[1.0 if x == y else 0.2 for y in b] for x in a])


ESS = {"r1": ["k1", "k2"], "r2": ["k3", "k4"], "cur": ["k1"]}
W = {"coverage": 0.5, "outlook": 0.3, "transferability": 0.2}


def test_match_components_and_ranking():
    o_hat = pd.Series({"r1": 0.0, "r2": 1.0, "cur": 0.5})
    m = pd.Series({"k1": 0.0, "k2": 0.0, "k3": 0.0, "k4": 0.0})
    df = model.match(["k1"], ESS, o_hat, m, sim_identity, weights=W, kappa=0.5, exclude=["cur"], normalise=False)
    assert set(df.occ_id) == {"r1", "r2"}             # current occupation excluded
    r1 = df.set_index("occ_id").loc["r1"]
    assert r1.C_raw == pytest.approx(0.5) and r1.T_raw == pytest.approx(0.2)
    assert r1.S == pytest.approx(100 * (0.5 * 0.5 + 0.3 * 0.0 + 0.2 * 0.2))
    assert list(df["rank"]) == [1, 2]
    assert (df.pts_coverage + df.pts_outlook + df.pts_transferability).round(6).tolist() == df.S.round(6).tolist()


def test_match_coverage_weights_rising_skills_more():
    o_hat = pd.Series({"r1": 0.5, "r2": 0.5, "cur": 0.5})
    m = pd.Series({"k1": 2.0, "k2": -2.0})
    have_rising = model.match(["k1"], {"r1": ["k1", "k2"]}, o_hat, m, sim_identity, weights=W, kappa=0.5, normalise=False)
    have_falling = model.match(["k2"], {"r1": ["k1", "k2"]}, o_hat, m, sim_identity, weights=W, kappa=0.5, normalise=False)
    assert have_rising.C_raw[0] > 0.5 > have_falling.C_raw[0]


def test_match_edge_cases():
    o_hat = pd.Series({"r1": 0.5, "r2": 0.5, "cur": 0.5})
    m = pd.Series(dtype=float)
    none = model.match([], ESS, o_hat, m, sim_identity, weights=W, kappa=0.5, normalise=False)
    assert (none.T_raw == 0).all() and (none.C_raw == 0).all()
    full = model.match(["k1", "k2"], {"r1": ["k1", "k2"]}, o_hat, m, sim_identity, weights=W, kappa=0.5, normalise=False)
    assert full.T_raw[0] == 1.0 and full.C_raw[0] == 1.0


def test_minmax():
    assert model.minmax([1, 2, 3]).tolist() == [0.0, 0.5, 1.0]
    assert model.minmax([2, 2]).tolist() == [0.0, 0.0]


def test_futures_reproducible_and_bounded():
    ess = {f"r{i}": [f"k{i}", f"k{i + 1}"] for i in range(8)}
    o_hat = pd.Series({k: i / 7 for i, k in enumerate(ess)})
    m = pd.Series({f"k{i}": (i - 4) / 4 for i in range(9)})
    ranked = model.match(["k3", "k4"], ess, o_hat, m, sim_identity, weights=W, kappa=0.5)
    kw = dict(weights=W, kappa=0.5, runs=300, r=0.2, seed=7, top_n=5)
    a = model.futures(ranked, ess, m, ["k3", "k4"], **kw)
    b = model.futures(ranked, ess, m, ["k3", "k4"], **kw)
    pd.testing.assert_frame_equal(a, b)
    assert a.p_top.between(0, 1).all() and (a.p10 <= a["median"]).all() and (a["median"] <= a.p90).all()
    still = model.futures(ranked, ess, m, ["k3", "k4"], **{**kw, "r": 0.0})
    top5 = set(ranked.occ_id[:5])
    assert set(still.occ_id[still.p_top == 1.0]) == top5   # no noise -> deterministic top 5
