import pandas as pd

from download import merge, week_start


def test_week_start_maps_sunday_and_midweek_to_monday():
    dates = pd.Series(pd.to_datetime(['2021-05-23', '2021-05-24', '2021-06-01']))
    assert list(week_start(dates).dt.strftime('%Y-%m-%d')) == ['2021-05-24', '2021-05-24', '2021-05-31']


def test_week_start_drops_timezone():
    dates = pd.Series(pd.to_datetime(['2024-01-08 00:00']).tz_localize('Asia/Bangkok'))
    assert week_start(dates).iloc[0] == pd.Timestamp('2024-01-08')


def test_merge_prefers_new_rows_on_overlap():
    old = pd.DataFrame({'Date': pd.to_datetime(['2021-05-24', '2021-05-31']), 'Close': [1.0, 2.0]})
    new = pd.DataFrame({'Date': pd.to_datetime(['2021-05-31', '2021-06-07']), 'Close': [2.5, 3.0]})
    out = merge(old, new)
    assert list(out['Close']) == [1.0, 2.5, 3.0]


def test_to_weekly_aggregates_days_into_monday_weeks():
    from download import to_weekly
    days = pd.date_range('2024-01-08', periods=10, freq='B')   # two full weeks
    daily = pd.DataFrame({'Open': range(10), 'High': range(10), 'Low': range(10),
                          'Close': range(10), 'Adj Close': range(10), 'Volume': [1] * 10}, index=days)
    w = to_weekly(daily)
    assert list(w.index.strftime('%Y-%m-%d')) == ['2024-01-08', '2024-01-15']
    assert list(w['Open']) == [0, 5] and list(w['Close']) == [4, 9] and list(w['Volume']) == [5, 5]


def test_fetch_drops_weeks_without_a_close(monkeypatch):
    import numpy as np
    import download
    idx = pd.date_range('2026-10-05', periods=4, freq='W-MON', name='Date', tz='Asia/Bangkok')
    hist = pd.DataFrame({c: [10.0, 11.0, 12.0, np.nan] if c in ('Close', 'Adj Close') else 10.0
                         for c in download.COLUMNS}, index=idx)

    class FakeTicker:
        def __init__(self, symbol):
            pass

        def history(self, **kw):
            return hist

    monkeypatch.setattr(download.yf, 'Ticker', FakeTicker)
    out = download.fetch('PTT.BK', '2026-10-01')
    assert list(out['Close']) == [10.0, 11.0, 12.0]
