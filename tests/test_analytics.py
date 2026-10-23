import numpy as np
import pandas as pd

import analytics as a


def weekly(n, start='2015-01-05'):
    return pd.date_range(start, periods=n, freq='W-MON')


def test_clean_prices_removes_isolated_spike():
    s = pd.Series([10.0] * 10, index=weekly(10))
    s.iloc[5] = 100.0
    out = a.clean_prices(s)
    assert np.isnan(out.iloc[5]) and out.drop(out.index[5]).notna().all()


def test_total_return_index_ignores_bad_adjustment_step():
    idx = weekly(4)
    close = pd.Series([10.0, 10.0, 11.0, 11.0], index=idx)
    adj = pd.Series([3.0, 3.0, 11.0, 11.0], index=idx)   # factor jumps 0.3 -> 1.0
    tri = a.total_return_index(close, adj)
    assert np.allclose(tri.values, [10, 10, 11, 11])


def test_total_return_index_keeps_dividend():
    idx = weekly(3)
    close = pd.Series([100.0, 95.0, 95.0], index=idx)     # 5 baht dividend goes ex
    adj = pd.Series([95.0, 95.0, 95.0], index=idx)
    tri = a.total_return_index(close, adj)
    assert np.isclose(tri.iloc[-1] / tri.iloc[0], 1.0)


def test_backtest_picks_the_trending_stocks():
    idx = weekly(120)
    up = pd.Series(1.01 ** np.arange(120), index=idx)
    flat = pd.Series(np.ones(120), index=idx)
    prices = pd.DataFrame({'UP': up, 'FLAT': flat, 'DOWN': 0.995 ** np.arange(120)}, index=idx)
    out = a.backtest(prices, top=1, cost_bps=0)
    assert np.allclose(out['Momentum'].iloc[1:], 0.01)


def test_screen_skips_missing_factors():
    m = pd.DataFrame({'Momentum12_1': [0.5, 0.1, -0.2], 'Volatility': [0.2, 0.3, 0.4]},
                     index=['A', 'B', 'C'])
    out = a.screen(m)
    assert list(out.index) == ['A', 'B', 'C']
