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


def test_dividend_yield_not_inflated_by_price_rally():
    idx = weekly(60)
    close = pd.Series(np.linspace(5, 15, 60), index=idx)   # price triples
    factor = pd.Series(np.where(np.arange(60) < 30, 0.95, 1.0), index=idx)  # one 5.3% dividend
    adj = close * factor
    assert np.isclose(a.trailing_dividend_yield(adj, close), 1 / 0.95 - 1)


def test_summarize_skips_short_or_empty_series():
    idx = weekly(60)
    r = pd.DataFrame({'A': 0.001, 'B': np.nan}, index=idx)
    assert list(a.summarize(r).index) == ['A']


def test_load_benchmarks_skips_short_series(tmp_path):
    long = pd.DataFrame({'Date': weekly(60), 'Close': np.linspace(1, 2, 60), 'Adj Close': np.linspace(1, 2, 60)})
    short = long.head(1)
    long.to_csv(tmp_path / 'TDEX.csv', index=False)
    short.to_csv(tmp_path / 'SET.csv', index=False)
    names = [s.name for s in a.load_benchmarks(str(tmp_path))]
    assert names == ['TDEX']


def test_export_sandbox_data_writes_rebased_series(tmp_path):
    folder = tmp_path / 'index'
    folder.mkdir()
    idx = weekly(60)
    close = 10 * 1.01 ** np.arange(60)
    pd.DataFrame({'Date': idx, 'Close': close, 'Adj Close': close}).to_csv(folder / 'TDEX.csv', index=False)
    pd.DataFrame({'Date': idx[:1], 'Close': [1.0], 'Adj Close': [1.0]}).to_csv(folder / 'SET.csv', index=False)
    out = tmp_path / 'sandbox-data.js'
    data = a.export_sandbox_data(str(out), str(folder))
    assert list(data['series']) == ['TDEX']      # one-row SET file is skipped
    tdex = data['series']['TDEX']
    assert tdex['values'][0] == 100 and np.isclose(tdex['values'][-1], 100 * 1.01 ** 59, rtol=1e-4)
    assert data['asOf'] == tdex['dates'][-1]
    assert out.read_text().splitlines()[1].startswith('window.SANDBOX_DATA = {')
