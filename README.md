# thai-stock-quote

Weekly prices, analyst consensus and simple analytics for the SET100.

## Scripts

get_tickers.py -> download the SET100 constituents from the SET website, save to tickers.csv

download.py -> download weekly quotes of each ticker from Yahoo Finance (yfinance) into data/, only new weeks; SET index and TDEX (SET50 ETF, the long-run benchmark) into data/index/; QQQ, SPY, ABFTH (Thai government bond ETF) and the USD/THB rate into data/assets/ for the sandbox; files of stocks that left the index move to data/former/

consensus.py -> snapshot the analyst-consensus table from 9hoon.com (aset) for SET100 tickers, save to data/consensus/YYYY-MM-DD.csv

consensus_history.py -> history of the daily consensus snapshots and each stock's change in median target since the previous snapshot and about a month earlier, written to reports/

analytics.py -> risk/return metrics, multi-factor screener (momentum, volatility, dividend yield, consensus upside) and a 12-1 momentum backtest, written to reports/; also writes weekly total-return series of TDEX, ABFTH, QQQ and SPY (the US ETFs also in baht) to docs/sandbox-data.js for the sandbox page

recon.py -> map how a web page delivers its data (tables, forms, JS endpoints, HAR captures) before writing a scraper

## Automation

.github/workflows/update-data.yml runs all of the above on weekdays at 18:40 Bangkok time and commits the results. It can also be started by hand from the Actions tab. .github/workflows/ci.yml runs the tests on every push.

## Setup

```bash
pip install -r requirements.txt        # scripts
pip install -r requirements-dev.txt    # tests and notebook
pytest -q
```

## Docs

- docs/reverse-engineering-data-sources.md: how to find where a page gets its data, with tools from awesome-reverse-engineering
- docs/literature-review-analyst-forecasts.md: research on the accuracy and value of analyst target prices, with notes for the screener
- docs/strategy-sandbox.html: browser sandbox (Thai) for stress-testing a Core-Satellite allocation under four hypothetical scenarios, a backtest of the same allocation either on real weekly ETF data since 2010 (TDEX for the Thai sleeve, ABFTH for bonds, QQQ or SPY in baht or USD for US equities; cash, and any sleeve before its data starts, grows at its assumed rate) against a 100% TDEX benchmark, or as a Monte Carlo simulation (correlated monthly returns, P5/median/P95 fan chart, drawdown and loss probability), both with monthly rebalancing and optional DCA, and cash-secured put / covered call payoffs at expiry; open the file in a browser (keep sandbox-data.js next to it)
- notebooks/set100_web_data_and_backtest.ipynb: teaching notebook (Thai) covering data collection, data cleaning, risk metrics, screening and backtesting

## Caveats

The backtest uses today's SET100 list for the whole history, so it has survivorship bias. Yahoo's Thai price history has split and adjustment errors, which analytics.py repairs (see clean_prices and total_return_index). Analyst consensus figures belong to their publishers; use them for personal research. Nothing here is investment advice.
