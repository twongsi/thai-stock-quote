# thai-stock-quote

Weekly prices, analyst consensus and simple analytics for the SET100.

## Scripts

get_tickers.py -> download the SET100 constituents from the SET website, save to tickers.csv

download.py -> download weekly quotes of each ticker from Yahoo Finance (yfinance) into data/, only new weeks; SET index and TDEX (SET50 ETF, the long-run benchmark) into data/index/; QQQ, SPY, ABFTH (Thai government bond ETF) and the USD/THB rate into data/assets/ for the sandbox; files of stocks that left the index move to data/former/

consensus.py -> snapshot the analyst-consensus table from 9hoon.com (aset) for SET100 tickers, save to data/consensus/YYYY-MM-DD.csv

consensus_history.py -> history of the daily consensus snapshots and each stock's change in median target since the previous snapshot and about a month earlier, written to reports/

analytics.py -> risk/return metrics, multi-factor screener (momentum, volatility, dividend yield, consensus upside) and a 12-1 momentum backtest, written to reports/; also writes weekly total-return series of TDEX, ABFTH, QQQ and SPY (the US ETFs also in baht) to docs/sandbox-data.js for the sandbox page

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

rrg/ -> RRG Studio (relative rotation graph page for SET industry/sector baskets, world indices in USD, US ETFs and stocks, with CSV upload) and sector_rotation.py (sector index, RS-Ratio/RS-Momentum, scoring and backtest). See rrg/README.md and rrg/WORKFLOW.md (Thai)

recon.py -> map how a web page delivers its data (tables, forms, JS endpoints, HAR captures) before writing a scraper

## Automation

.github/workflows/update-data.yml runs the SET100 scripts on weekdays at 18:40 Bangkok time and commits the results. .github/workflows/market-data.yml then runs market_download.py and `consensus.py --all-symbols --out-dir data/market/consensus` for the whole market at 18:52. It can also be started by hand from the Actions tab. .github/workflows/ci.yml runs the tests on every push. .github/workflows/rrg-weekly.yml rebuilds the RRG Studio page and sector rotation report on Saturdays and can deploy rrg/docs to GitHub Pages.

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

## MiroFish — multi-agent stock simulator

A [MiroFish](https://github.com/666ghj/MiroFish)-inspired prediction engine,
applied to equities. Instead of one model giving one answer, a **swarm of LLM
analyst agents** — each with a distinct persona (momentum trader, value
investor, contrarian, risk manager, quant, macro strategist) and its own
memory — studies the stock, **debates** with the rest of the panel, and
converges on a confidence-weighted directional forecast.

The pipeline mirrors MiroFish's five stages:

1. **Snapshot** — distil raw OHLCV history into a compact fact sheet
   (`microfish/data_loader.py`).
2. **Personas** — instantiate the analyst cast (`microfish/personas.py`).
3. **Simulate** — parallel analysis + multi-round debate
   (`microfish/simulator.py`, `microfish/agent.py`).
4. **Report** — aggregate the swarm into a Markdown report
   (`microfish/report.py`).
5. **Dialogue** — ask a follow-up question to the lead analyst (`--ask`).

### Backend

The agents run on the **Anthropic Claude API**. Set your key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pip install -r microfish/requirements.txt
```

If no key is set, the simulator automatically falls back to a **deterministic
mock** so the full pipeline runs offline (great for demos and CI). Force it
with `MICROFISH_MOCK=1`. Override the model with `MICROFISH_MODEL`.

### Usage

```bash
# Real Claude backend
python run_simulation.py PTT --horizon 4 --debate-rounds 1

# Offline demo, no API key needed
MICROFISH_MOCK=1 python run_simulation.py AOT

# Inject seed news the macro analyst will weigh
python run_simulation.py DELTA --news "New AI-server contract announced."

# Ask the panel a follow-up question after the run
python run_simulation.py KBANK --ask "What's the biggest downside risk?"

# Save the report to a file too
python run_simulation.py SCB --out report.md
```

Key options: `--analysts N` (use N personas), `--lookback W` (weeks of history
to summarise), `--data-dir DIR`.

### Tests

```bash
MICROFISH_MOCK=1 python test_microfish.py
```

> ⚠️ MiroFish output is a research/creative simulation, **not investment
> advice**.
