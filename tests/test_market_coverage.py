import numpy as np
import pandas as pd

import market_coverage as mc


def test_stock_list_keeps_common_stocks_of_one_market():
    payload = {'securitySymbols': [
        {'symbol': 'PTT', 'market': 'SET', 'securityType': 'S'},
        {'symbol': 'PTT-W1', 'market': 'SET', 'securityType': 'W'},
        {'symbol': 'AU', 'market': 'mai', 'securityType': 'S'},
        {'symbol': 'aoT ', 'market': 'SET', 'securityType': 'S'},
    ]}
    assert mc.stock_list_symbols(payload, 'set') == ['AOT', 'PTT']
    assert mc.stock_list_symbols(payload, 'mai') == ['AU']


def fake_download(tickers, **kw):
    idx = pd.date_range('2026-10-01', periods=5, freq='B')
    cols = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
    frames = {t: pd.DataFrame({c: 1e6 if c == 'Volume' else 10.0 for c in cols}, index=idx)
              for t in tickers if t != 'GONE.BK'}
    if len(tickers) == 1:
        return next(iter(frames.values()))      # yfinance can return flat columns here
    return pd.concat(frames, axis=1)


def test_yahoo_coverage_handles_missing_and_single_batches(monkeypatch):
    monkeypatch.setattr(mc.yf, 'download', fake_download)
    monkeypatch.setattr(mc, 'BATCH', 2)
    out = mc.yahoo_coverage(['PTT', 'GONE', 'AU']).set_index('symbol')
    assert out.loc['PTT', 'yahoo_days'] == 5 and out.loc['AU', 'yahoo_days'] == 5
    assert out.loc['GONE', 'yahoo_days'] == 0
    assert out.loc['PTT', 'yahoo_avg_value_mb'] == 10


def test_hoon_coverage_reads_cover_and_upside(monkeypatch):
    html = ('<table><tr><th>Symbol</th><th>Cover ↕</th><th>Upside(จาก Median %)</th></tr>'
            '<tr><td>PTT</td><td>19</td><td>12.5</td></tr><tr><td>AU</td><td>-</td><td>-</td></tr></table>')
    monkeypatch.setattr(mc.consensus, 'read_source', lambda src: html)
    out = mc.hoon_coverage(['PTT', 'AU', 'AOT']).set_index('symbol')
    assert out.loc['PTT', 'hoon_analysts'] == 19 and out.loc['PTT', 'hoon_upside'] == 12.5
    assert np.isnan(out.loc['AU', 'hoon_analysts']) and 'AOT' not in out.index


def test_summary_counts_per_market():
    cov = pd.DataFrame({'symbol': ['PTT', 'AOT', 'AU'], 'market': ['SET', 'SET', 'mai'],
                        'yahoo_days': [20, 0, 18], 'in_9hoon': [True, False, True],
                        'hoon_analysts': [19, np.nan, np.nan]})
    text = mc.summarize(cov)
    assert 'SET: 2 stocks | Yahoo 1 (50%) | 9hoon 1 (50%), with analysts 1' in text
    assert 'no Yahoo data (1): AOT' in text and 'mai: 1 stocks' in text
