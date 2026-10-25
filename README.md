# thai-stock-quote

Weekly prices, analyst consensus and simple analytics for the SET100.

## Scripts

get_tickers.py -> download the SET100 constituents from the SET website, save to tickers.csv

download.py -> download weekly quotes of each ticker from Yahoo Finance (yfinance) into data/, only new weeks; SET index and TDEX (SET50 ETF, the long-run benchmark) into data/index/; files of stocks that left the index move to data/former/

consensus.py -> snapshot the analyst-consensus table from 9hoon.com (aset) for SET100 tickers, save to data/consensus/YYYY-MM-DD.csv

consensus_history.py -> history of the daily consensus snapshots and each stock's change in median target since the previous snapshot and about a month earlier, written to reports/

analytics.py -> risk/return metrics, multi-factor screener (momentum, volatility, dividend yield, consensus upside) and a 12-1 momentum backtest, written to reports/

screener.py -> ad-hoc filters on the weekly quotes (returns, RSI, 10/40-week SMA, 52-week high/low, volatility, volume) and, with --consensus, the newest 9hoon snapshot (upside, analyst count, rating, P/E, P/BV, dividend yield)

```bash
python screener.py --min-rsi 50 --above-sma 40 --golden-cross --near-high 5
python screener.py --consensus --min-upside 15 --min-analysts 5 --rating Buy --sort upside
python screener.py --consensus --max-pe 15 --min-div 4 --sort div_yield --top 10 --csv value.csv
# every SET and mai stock (data/market/), with market, company/fund, sector and traded-value filters
python screener.py --universe all --market mai --kind company --min-value 5 --above-sma 40
python screener.py --universe all --consensus --min-upside 20 --sector BANK --sector FIN
```

market_download.py -> weekly quotes since 2016 for every stock on SET and mai (about 930, from the set.or.th stock list) into data/market/prices/, fetched from Yahoo in batches; the list, with each stock's market, sector and kind (company or property fund/REIT), goes to data/market/symbols.csv

test_sources.py -> check which data sources (Yahoo, 9hoon, Settrade, set.or.th) answer from your network, e.g. when a download starts failing

market_coverage.py -> list every SET and mai stock from set.or.th and test which ones Yahoo and 9hoon cover, written to reports/market/ (run by .github/workflows/market-coverage.yml, results as a run artifact)

recon.py -> map how a web page delivers its data (tables, forms, JS endpoints, HAR captures) before writing a scraper

## Automation

.github/workflows/update-data.yml runs the SET100 scripts on weekdays at 18:40 Bangkok time and commits the results. .github/workflows/market-data.yml then runs market_download.py and `consensus.py --all-symbols --out-dir data/market/consensus` for the whole market at 18:52. It can also be started by hand from the Actions tab. .github/workflows/ci.yml runs the tests on every push.

## Setup

```bash
pip install -r requirements.txt        # scripts
pip install -r requirements-dev.txt    # tests and notebook
pytest -q
```

## Docs

- docs/reverse-engineering-data-sources.md: how to find where a page gets its data, with tools from awesome-reverse-engineering
- docs/literature-review-analyst-forecasts.md: research on the accuracy and value of analyst target prices, with notes for the screener
- notebooks/set100_web_data_and_backtest.ipynb: teaching notebook (Thai) covering data collection, data cleaning, risk metrics, screening and backtesting

## Caveats

The backtest uses today's SET100 list for the whole history, so it has survivorship bias. Yahoo's Thai price history has split and adjustment errors, which analytics.py repairs (see clean_prices and total_return_index). Analyst consensus figures belong to their publishers; use them for personal research. Nothing here is investment advice.
