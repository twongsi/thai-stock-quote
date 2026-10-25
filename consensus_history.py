"""Track how the analyst consensus changes between daily snapshots.

Reads every data/consensus/YYYY-MM-DD.csv and writes:

    reports/consensus_history.csv   one row per stock per snapshot
    reports/consensus_changes.csv   latest snapshot vs. the previous one and
                                    vs. about a month (20 snapshots) earlier

    python consensus_history.py
"""
import argparse
import glob
import os

import pandas as pd

# Substrings that identify 9hoon's columns, so a renamed header still matches
FIELDS = {
    'Price': ['price'],
    'MedianTarget': ['median'],
    'AverageTarget': ['average'],
    'Upside': ['upside'],
    'Analysts': ['cover'],
    'Rating': ['คำแนะนำ', 'recommend'],
    'BuyHoldSell': ['buy / hold / sell', 'buy/hold/sell'],
}


def pick_columns(df):
    out = {}
    for name, keys in FIELDS.items():
        col = next((c for c in df.columns if any(k in c.lower() for k in keys)), None)
        if col is not None:
            out[name] = df[col]
    return pd.DataFrame(out)


def load_history(folder='data/consensus'):
    frames = []
    for path in sorted(glob.glob(os.path.join(folder, '*.csv'))):
        df = pd.read_csv(path)
        snap = pick_columns(df)
        snap.insert(0, 'Symbol', df['Symbol'])
        snap.insert(0, 'SnapshotDate', os.path.splitext(os.path.basename(path))[0])
        frames.append(snap)
    if not frames:
        return pd.DataFrame(columns=['SnapshotDate', 'Symbol', *FIELDS])
    return pd.concat(frames, ignore_index=True)


def changes(history, month=20):
    """Per stock: latest values and their change since earlier snapshots."""
    dates = sorted(history['SnapshotDate'].unique())
    latest = history[history['SnapshotDate'] == dates[-1]].set_index('Symbol')
    out = latest[[c for c in ['Price', 'MedianTarget', 'Upside', 'Analysts', 'Rating'] if c in latest]].copy()
    out.insert(0, 'SnapshotDate', dates[-1])
    for label, back in (('1D', 1), ('1M', month)):
        if len(dates) <= back:
            out[f'PrevDate{label}'] = None
            out[f'TargetChange{label}'] = float('nan')
            continue
        prev = history[history['SnapshotDate'] == dates[-1 - back]].set_index('Symbol')
        out[f'PrevDate{label}'] = dates[-1 - back]
        out[f'TargetChange{label}'] = latest['MedianTarget'] / prev['MedianTarget'].reindex(latest.index) - 1
        if label == '1D' and 'Rating' in prev:
            out['PrevRating'] = prev['Rating'].reindex(latest.index)
    return out.reset_index()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--folder', default='data/consensus')
    ap.add_argument('--out', default='reports')
    args = ap.parse_args()

    history = load_history(args.folder)
    if history.empty:
        raise SystemExit('no consensus snapshots yet; run consensus.py first')
    os.makedirs(args.out, exist_ok=True)
    history.to_csv(f'{args.out}/consensus_history.csv', index=False)
    ch = changes(history)
    ch.to_csv(f'{args.out}/consensus_changes.csv', index=False, float_format='%.4f')

    n = history['SnapshotDate'].nunique()
    print(f'{n} snapshot(s), latest {ch["SnapshotDate"].iloc[0]}, {len(ch)} stocks')
    moved = ch.dropna(subset=['TargetChange1D'])
    moved = moved[moved['TargetChange1D'] != 0]
    if n > 1:
        print(f'{len(moved)} median targets changed since the previous snapshot')
        if not moved.empty:
            print(moved.sort_values('TargetChange1D')[['Symbol', 'MedianTarget', 'TargetChange1D']].to_string(index=False))


if __name__ == '__main__':
    main()
