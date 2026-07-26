# thai-stock-quote

Tools for pulling Thai (SET) stock data, plus **MiroFish** — a multi-agent
LLM simulator that forecasts a stock by running a swarm of analyst agents.

## Data tooling

- `get_tickers.py` — download the ticker symbols of each SET100 stock from
  Settrade and save them to `tickers.csv`.
- `download.py` — download weekly price quotes for each ticker from Yahoo into
  `data/<TICKER>.csv`.

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
