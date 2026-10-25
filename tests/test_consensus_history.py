import pandas as pd

import consensus_history as ch


def write_snapshot(folder, date, rows):
    pd.DataFrame(rows).to_csv(folder / f'{date}.csv', index=False)


def test_changes_between_snapshots(tmp_path):
    cols = lambda sym, price, target, rating: {
        'SnapshotDate': 'x', 'Symbol': sym, 'Price': price, 'Cover': 10,
        'คำแนะนำ': rating, 'เป้าหมาย Median(บาท)': target, 'Upside(จาก Median %)': 0}
    write_snapshot(tmp_path, '2026-10-22', [cols('PTT', 30, 40, 'Buy'), cols('AOT', 60, 70, 'Hold')])
    write_snapshot(tmp_path, '2026-10-23', [cols('PTT', 31, 44, 'Buy'), cols('AOT', 61, 70, 'Buy')])
    hist = ch.load_history(tmp_path)
    assert set(hist.columns) >= {'SnapshotDate', 'Symbol', 'MedianTarget', 'Rating', 'Analysts'}
    out = ch.changes(hist).set_index('Symbol')
    assert abs(out.loc['PTT', 'TargetChange1D'] - 0.10) < 1e-9
    assert out.loc['AOT', 'TargetChange1D'] == 0
    assert out.loc['AOT', 'PrevRating'] == 'Hold' and out.loc['AOT', 'Rating'] == 'Buy'
    assert out['TargetChange1M'].isna().all()


def test_single_snapshot_has_no_changes(tmp_path):
    write_snapshot(tmp_path, '2026-10-23', [{'Symbol': 'PTT', 'Price': 30, 'เป้าหมาย Median(บาท)': 40}])
    out = ch.changes(ch.load_history(tmp_path))
    assert out['TargetChange1D'].isna().all()
