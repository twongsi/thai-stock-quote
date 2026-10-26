"""Risk/return metrics, a stock screener and a momentum backtest on data/*.csv.

All series are weekly (one row per trading week). Returns use Adj Close, so
they include dividends.

    python analytics.py                     # writes reports/*.csv and reports/dashboard.json
    python analytics.py --top 20 --cost-bps 25
"""
import argparse
import glob
import json
import os

import numpy as np
import pandas as pd

WEEKS_PER_YEAR = 52


# ---------- loading ----------

def current_tickers(path='tickers.csv'):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return {t.strip() for t in f.read().split(',') if t.strip()}


def load_prices(data_dir='data', column='Adj Close', tickers=None):
    """Wide DataFrame: index = week, columns = ticker.

    'Adj Close' is rebuilt from Close plus a capped dividend adjustment
    (see total_return_index); 'Close' is the raw close, spike-filtered.
    """
    series = {}
    for path in sorted(glob.glob(os.path.join(data_dir, '*.csv'))):
        ticker = os.path.splitext(os.path.basename(path))[0]
        if tickers is not None and ticker not in tickers:
            continue
        df = pd.read_csv(path, parse_dates=['Date']).drop_duplicates('Date', keep='last').set_index('Date')
        df = df.where(df > 0)
        close = clean_prices(df['Close'])
        series[ticker] = total_return_index(close, df['Adj Close']) if column == 'Adj Close' else close
    return pd.DataFrame(series).sort_index()


def clean_prices(prices, window=9, max_ratio=1.8):
    """Blank out prices far from their local median.

    Yahoo's Thai history has weeks where a split is applied inconsistently
    (e.g. PTT and KTC jumping 10x for a week and back). A price more than
    max_ratio away from the centred rolling median is treated as bad data.
    """
    median = prices.rolling(window, center=True, min_periods=3).median()
    ratio = prices / median
    return prices.where((ratio < max_ratio) & (ratio > 1 / max_ratio))


def total_return_index(close, adj, max_weekly_adj=0.15):
    """Close compounded with the dividend part of Yahoo's adjustment.

    Yahoo's Adj Close for Thai stocks sometimes steps by 3x in a week (KTC,
    March 2014) while Close barely moves. The weekly change in Adj/Close is
    the dividend effect; changes above max_weekly_adj are treated as data
    errors and ignored.
    """
    factor = (adj / close).reindex(close.index)
    step = (factor / factor.ffill().shift(1)).fillna(1.0)
    step = step.where((step - 1).abs() <= max_weekly_adj, 1.0)
    price_ret = close / close.ffill().shift(1)
    growth = (price_ret * step).where(close.notna())
    tri = growth.fillna(1.0).cumprod() * close.dropna().iloc[0] if close.notna().any() else close
    return tri.where(close.notna())


def clean_prices(prices, window=9, max_ratio=1.8):
    """Blank out prices far from their local median.

    Yahoo's Thai history has weeks where a split is applied inconsistently
    (e.g. PTT and KTC jumping 10x for a week and back). A price more than
    max_ratio away from the centred rolling median is treated as bad data.
    """
    median = prices.rolling(window, center=True, min_periods=3).median()
    ratio = prices / median
    return prices.where((ratio < max_ratio) & (ratio > 1 / max_ratio))


def load_index(path='data/index/SET.csv'):
    if not os.path.exists(path):
        return None
    name = os.path.splitext(os.path.basename(path))[0]
    df = pd.read_csv(path, parse_dates=['Date']).drop_duplicates('Date', keep='last').set_index('Date')
    s = df['Adj Close'] if df['Adj Close'].notna().any() else df['Close']
    s = clean_prices(s.where(s > 0)).rename(name)
    print(f'{name}: {s.notna().sum()} weeks, {s.first_valid_index()} to {s.last_valid_index()}')
    return s if s.notna().sum() > WEEKS_PER_YEAR else None


def load_benchmarks(folder='data/index'):
    """Every usable series in data/index/ (SET index, TDEX SET50 ETF)."""
    found = [load_index(p) for p in sorted(glob.glob(os.path.join(folder, '*.csv')))]
    return [s for s in found if s is not None]


def export_sandbox_data(path='docs/sandbox-data.js', folder='data/index'):
    """Weekly total-return index of each benchmark for docs/strategy-sandbox.html.

    Written as a script that sets window.SANDBOX_DATA, so the page can load it
    with a <script> tag when opened straight from disk (fetch() can't read
    local files). Each series is rebased to 100 at its first week.
    """
    series = {}
    for csv in sorted(glob.glob(os.path.join(folder, '*.csv'))):
        name = os.path.splitext(os.path.basename(csv))[0]
        df = pd.read_csv(csv, parse_dates=['Date']).drop_duplicates('Date', keep='last').set_index('Date').sort_index()
        df = df.where(df > 0)
        tri = total_return_index(clean_prices(df['Close']), df['Adj Close']).dropna()
        if len(tri) <= WEEKS_PER_YEAR:
            continue
        tri = tri / tri.iloc[0] * 100
        series[name] = {'dates': [d.date().isoformat() for d in tri.index], 'values': tri.round(4).tolist()}
    if not series:
        return None
    data = {'asOf': max(s['dates'][-1] for s in series.values()), 'series': series}
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w') as f:
        f.write('// Generated by analytics.py (export_sandbox_data); do not edit by hand.\n')
        f.write(f'window.SANDBOX_DATA = {json.dumps(data, allow_nan=False, separators=(",", ":"))};\n')
    return data


# ---------- metrics ----------

def max_drawdown(prices):
    peak = prices.cummax()
    return (prices / peak - 1).min()


def trailing_dividend_yield(adj, close, weeks=WEEKS_PER_YEAR):
    """Dividends paid over 12 months as a share of the price on each ex-date.

    Read from the growth of the Adj Close / Close factor. Total return minus
    price return would overstate it for stocks whose price rose sharply.
    """
    factor = (adj / close).dropna()
    if len(factor) <= weeks:
        return np.nan
    return factor.iloc[-1] / factor.iloc[-1 - weeks] - 1


def momentum(prices, lookback=WEEKS_PER_YEAR, skip=4):
    """12-1 style momentum: return from t-lookback to t-skip."""
    return prices.shift(skip) / prices.shift(lookback) - 1


def metrics(prices, close=None, rf=0.02):
    rets = prices.pct_change(fill_method=None)
    rows = []
    for t in prices.columns:
        p = prices[t].dropna()
        r = rets[t].dropna()
        if len(p) < WEEKS_PER_YEAR:
            continue
        years = (p.index[-1] - p.index[0]).days / 365.25
        cagr = (p.iloc[-1] / p.iloc[0]) ** (1 / years) - 1
        vol = r.std() * np.sqrt(WEEKS_PER_YEAR)
        row = {
            'Symbol': t,
            'Start': p.index[0].date().isoformat(),
            'End': p.index[-1].date().isoformat(),
            'CAGR': cagr,
            'Volatility': vol,
            'Sharpe': (cagr - rf) / vol if vol else np.nan,
            'MaxDrawdown': max_drawdown(p),
            'Return1Y': p.iloc[-1] / p.iloc[-1 - WEEKS_PER_YEAR] - 1,
            'Momentum12_1': momentum(p).iloc[-1],
        }
        if close is not None and t in close:
            c = close[t].reindex(p.index)
            row['DividendYield1Y'] = trailing_dividend_yield(p, c)
        rows.append(row)
    return pd.DataFrame(rows).set_index('Symbol')


# ---------- screener ----------

def zscore(s):
    return (s - s.mean()) / s.std()


def screen(m, consensus=None, weights=None):
    """Composite score: momentum, low volatility, dividend yield, consensus upside.

    consensus: optional DataFrame indexed by Symbol with an 'Upside' column
    (fraction, e.g. 0.15 = 15%). Missing factors are skipped, not zero-filled.
    """
    weights = weights or {'Momentum12_1': 0.35, 'Volatility': -0.25, 'DividendYield1Y': 0.2, 'Upside': 0.2}
    df = m.copy()
    if consensus is not None:
        df = df.join(consensus, how='left')
    parts = []
    for col, w in weights.items():
        if col in df and df[col].notna().sum() > 2:
            parts.append(w * zscore(df[col]).fillna(0))
    df['Score'] = sum(parts) if parts else np.nan
    return df.sort_values('Score', ascending=False)


def load_latest_consensus(folder='data/consensus', upside_col=None, min_cover=3):
    """Upside to the consensus target from the newest snapshot.

    Upside is blanked for stocks covered by fewer than min_cover analysts,
    whose consensus is one or two opinions.
    """
    files = sorted(glob.glob(os.path.join(folder, '*.csv')))
    if not files:
        return None
    df = pd.read_csv(files[-1]).set_index('Symbol')
    col = upside_col or next((c for c in df.columns if 'upside' in c.lower()), None)
    if col is None:
        return None
    up = df[col]
    out = pd.DataFrame({'Upside': up / 100 if up.abs().median() > 1 else up})
    if 'Cover' in df:
        out['Analysts'] = df['Cover']
        out.loc[out['Analysts'] < min_cover, 'Upside'] = np.nan
    return out


# ---------- backtest ----------

def backtest(prices, top=20, rebalance_weeks=4, lookback=WEEKS_PER_YEAR, skip=4, cost_bps=20):
    """Equal-weight top-N momentum portfolio vs. equal-weight universe.

    Survivorship bias: the universe is today's SET100 list, so stocks that were
    dropped or delisted are missing, which flatters both strategies.
    """
    rets = prices.pct_change(fill_method=None)
    mom = momentum(prices, lookback, skip)
    dates = prices.index
    weights = pd.DataFrame(0.0, index=dates, columns=prices.columns)
    current = pd.Series(0.0, index=prices.columns)
    turnover = pd.Series(0.0, index=dates)
    for i, d in enumerate(dates):
        if i >= lookback and (i - lookback) % rebalance_weeks == 0:
            ranks = mom.loc[d].dropna()
            # Only stocks with a price this week can be bought
            ranks = ranks[prices.loc[d].reindex(ranks.index).notna()]
            if len(ranks) >= top:
                chosen = ranks.nlargest(top).index
                target = pd.Series(0.0, index=prices.columns)
                target[chosen] = 1.0 / top
                turnover[d] = (target - current).abs().sum()
                current = target
        weights.loc[d] = current

    # Weights set at the end of week d earn week d+1's return
    held = weights.shift(1).fillna(0)
    gross = (held * rets.fillna(0)).sum(axis=1)
    net = gross - turnover.shift(1).fillna(0) * cost_bps / 1e4
    invested = held.sum(axis=1) > 0
    ew = rets.mean(axis=1)

    out = pd.DataFrame({'Momentum': net, 'EqualWeight': ew})[invested]
    return out


def summarize(returns, rf=0.02):
    rows = {}
    for col in returns:
        r = returns[col].dropna()
        if len(r) < WEEKS_PER_YEAR:
            continue
        nav = (1 + r).cumprod()
        years = len(r) / WEEKS_PER_YEAR
        cagr = nav.iloc[-1] ** (1 / years) - 1
        vol = r.std() * np.sqrt(WEEKS_PER_YEAR)
        rows[col] = {'CAGR': cagr, 'Volatility': vol, 'Sharpe': (cagr - rf) / vol,
                     'MaxDrawdown': max_drawdown(nav), 'Weeks': len(r)}
    return pd.DataFrame(rows).T


# ---------- report ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--top', type=int, default=20)
    ap.add_argument('--cost-bps', type=float, default=20, help='one-way trading cost per unit turnover')
    ap.add_argument('--rf', type=float, default=0.02, help='annual risk-free rate for Sharpe')
    ap.add_argument('--out', default='reports')
    args = ap.parse_args()

    tickers = current_tickers()
    adj = load_prices(tickers=tickers)
    close = load_prices(column='Close', tickers=tickers)
    m = metrics(adj, close, args.rf)
    scr = screen(m, load_latest_consensus())

    bt = backtest(adj, top=args.top, cost_bps=args.cost_bps)
    for bench in load_benchmarks():
        bt = bt.join(bench.pct_change(fill_method=None), how='left')
    summary = summarize(bt, args.rf)

    os.makedirs(args.out, exist_ok=True)
    m.to_csv(f'{args.out}/metrics.csv', float_format='%.4f')
    scr.to_csv(f'{args.out}/screener.csv', float_format='%.4f')
    bt.to_csv(f'{args.out}/backtest_returns.csv', float_format='%.6f')
    summary.to_csv(f'{args.out}/backtest_summary.csv', float_format='%.4f', index_label='Strategy')

    nav_out = (1 + bt.fillna(0)).cumprod()
    nav_out.index.name = 'Date'
    nav_out.to_csv(f'{args.out}/backtest_nav.csv', float_format='%.4f', date_format='%Y-%m-%d')

    rets = adj.pct_change(fill_method=None)
    recent = rets.iloc[-3 * WEEKS_PER_YEAR:]
    corr = recent.loc[:, recent.notna().sum() > WEEKS_PER_YEAR].corr()
    nav = (1 + bt.fillna(0)).cumprod()
    dashboard = {
        'asOf': adj.index[-1].date().isoformat(),
        'metrics': m.reset_index().round(4).replace({np.nan: None}).to_dict('records'),
        'screener': scr.head(30).reset_index().round(4).replace({np.nan: None}).to_dict('records'),
        'backtest': {'dates': [d.date().isoformat() for d in nav.index],
                     **{c: nav[c].round(4).tolist() for c in nav}},
        'summary': summary.round(4).reset_index(names='Strategy').to_dict('records'),
        'corr': {'symbols': list(corr.columns), 'values': corr.round(2).values.tolist()},
        'params': vars(args),
    }
    with open(f'{args.out}/dashboard.json', 'w') as f:
        json.dump(dashboard, f, allow_nan=False)
    export_sandbox_data()

    pd.set_option('display.width', 120)
    print(f'data through {dashboard["asOf"]}, {len(m)} stocks\n')
    print('Top 10 by screener score:')
    print(scr.head(10)[['Momentum12_1', 'Volatility', 'DividendYield1Y', 'Score']].round(3), '\n')
    print('Backtest summary:')
    print(summary.round(3))


if __name__ == '__main__':
    main()
