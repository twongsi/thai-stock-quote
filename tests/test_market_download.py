import numpy as np
import pandas as pd

import market_download as md


def weekly(start, n, close=10.0):
    idx = pd.date_range(start, periods=n, freq='W-MON', name='Date')
    return pd.DataFrame({c: (1e6 if c == 'Volume' else close) for c in md.COLUMNS}, index=idx)


def test_frames_by_symbol_handles_flat_and_missing():
    multi = pd.concat({'PTT.BK': weekly('2026-01-05', 3), 'AU.BK': weekly('2026-01-05', 3) * np.nan}, axis=1)
    out = md.frames_by_symbol(multi, ['PTT.BK', 'AU.BK', 'GONE.BK'])
    assert list(out) == ['PTT.BK'] and list(out['PTT.BK'].columns) == ['Date'] + md.COLUMNS
    flat = md.frames_by_symbol(weekly('2026-01-05', 2), ['PTT.BK'])
    assert len(flat['PTT.BK']) == 2


def test_update_all_fetches_new_symbols_in_full_and_extends_existing(tmp_path, monkeypatch):
    old = weekly('2024-01-01', 60, close=5.0).reset_index()
    old.to_csv(tmp_path / 'PTT.csv', index=False, date_format='%Y-%m-%d')
    calls = []

    def fake_fetch(symbols, start):
        calls.append((tuple(symbols), start))
        if start == md.START_DATE:
            return {s: weekly('2025-06-02', 70, close=7.0).reset_index() for s in symbols if s != 'GONE'}
        return {s: weekly('2025-02-03', 4, close=9.0).reset_index() for s in symbols}

    monkeypatch.setattr(md, 'fetch_batch', fake_fetch)
    failed = md.update_all(['PTT', 'AU', 'GONE'], str(tmp_path))
    assert failed == ['GONE']
    # one call for the stocks without history, one incremental call for PTT
    assert (('AU', 'GONE'), md.START_DATE) in calls
    assert any(syms == ('PTT',) and start != md.START_DATE for syms, start in calls)
    ptt = pd.read_csv(tmp_path / 'PTT.csv')
    assert len(ptt) == 60 + 4 - 3      # old file ends 2025-02-17: three weeks overlap and are replaced
    assert ptt['Close'].iloc[0] == 5.0 and ptt['Close'].iloc[-1] == 9.0
    assert len(pd.read_csv(tmp_path / 'AU.csv')) == 70
