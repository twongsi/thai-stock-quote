import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sector_rotation as sr  # noqa: E402


def _prices(n=120, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-05", periods=n, freq="W-FRI")
    r = rng.normal(0.002, 0.03, size=(n, 4))
    return pd.DataFrame(100 * np.cumprod(1 + r, axis=0), index=idx, columns=["B", "A1", "A2", "C1"])


def test_sector_index_equal_weight_matches_mean_return():
    p = _prices()
    idx = sr.sector_index(p, {"A": ["A1", "A2"]})
    expected = 100 * (1 + p[["A1", "A2"]].pct_change().mean(axis=1).fillna(0)).cumprod()
    pd.testing.assert_series_equal(idx["A"], expected, check_names=False)


def test_sector_index_skips_missing_member():
    p = _prices()
    p.loc[p.index[:30], "A2"] = np.nan  # A2 lists later
    idx = sr.sector_index(p, {"A": ["A1", "A2"]})
    early = 100 * (1 + p["A1"].pct_change().fillna(0)).cumprod()
    assert np.allclose(idx["A"].iloc[:30], early.iloc[:30])


def test_rrg_quadrants_follow_axes():
    p = _prices()
    _, ratio, mom, quad, _ = sr.rrg(p[["A1", "C1"]], p["B"], n=10)
    t = ratio.dropna().index.intersection(mom.dropna().index)
    for col in ["A1", "C1"]:
        for d in t:
            r, m, q = ratio.at[d, col], mom.at[d, col], quad.at[d, col]
            want = "Leading" if r >= 100 and m >= 100 else "Weakening" if r >= 100 else "Lagging" if m < 100 else "Improving"
            assert q == want


def test_rrg_is_100_for_a_copy_of_the_benchmark():
    p = _prices()
    p["A1"] = p["B"] * 2
    _, ratio, _, _, _ = sr.rrg(p[["A1"]], p["B"], n=10)
    assert np.allclose(ratio["A1"].dropna(), 100)


def test_backtest_uses_next_period_return():
    # A score that knows the future would earn far more than a lagged one; the backtest
    # must apply weights decided at t to returns at t+1
    p = _prices(200)
    idx = p[["A1", "A2", "C1"]]
    fwd = idx.pct_change().shift(-1)  # look-ahead score
    res, w, _ = sr.backtest(idx, p["B"], fwd, top=1, rebalance=1, cost_bps=0)
    r = idx.pct_change().fillna(0).loc[w.index]
    assert np.allclose(res["strategy"], (w.shift(1) * r).sum(axis=1))
