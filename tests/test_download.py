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
