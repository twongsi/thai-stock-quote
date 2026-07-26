#!/usr/bin/env python3
"""MiroFish for stocks — CLI.

Run a multi-agent analyst simulation on a Thai stock and print a forecast
report. Works offline (mock LLM) if ANTHROPIC_API_KEY is not set.

Examples
--------
    # Real Claude backend (needs ANTHROPIC_API_KEY):
    python run_simulation.py PTT --horizon 4 --debate-rounds 1

    # Offline demo, no API key required:
    MICROFISH_MOCK=1 python run_simulation.py AOT

    # Inject seed news the macro analyst will weigh:
    python run_simulation.py DELTA --news "New AI-server contract announced."

    # Ask a follow-up question to the panel afterwards:
    python run_simulation.py KBANK --ask "What's the biggest downside risk?"
"""

from __future__ import annotations

import argparse
import sys

from microfish import load_snapshot, render_report
from microfish.llm import LLMClient
from microfish.personas import default_cast
from microfish.simulator import Simulation


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_simulation.py",
        description="MiroFish-style multi-agent analyst simulation for a stock.",
    )
    p.add_argument("ticker", help="Ticker symbol, e.g. PTT (must exist in data/).")
    p.add_argument("--horizon", type=int, default=4, help="Forecast horizon in weeks (default 4).")
    p.add_argument("--lookback", type=int, default=52, help="Weeks of history to summarise (default 52).")
    p.add_argument("--debate-rounds", type=int, default=1, help="Number of debate rounds (default 1).")
    p.add_argument("--analysts", type=int, default=None, help="How many personas to use (default: all).")
    p.add_argument("--news", default="", help="Optional seed news/context for the panel.")
    p.add_argument("--ask", default=None, help="Ask the panel a follow-up question after the run.")
    p.add_argument("--data-dir", default=None, help="Directory of <ticker>.csv files.")
    p.add_argument("--out", default=None, help="Write the report to this file as well as stdout.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        snapshot = load_snapshot(
            args.ticker.upper(),
            data_dir=args.data_dir,
            lookback_weeks=args.lookback,
            notes=args.news,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    llm = LLMClient()
    if llm.is_mock:
        print("[note] Running in MOCK mode (no ANTHROPIC_API_KEY). "
              "Forecasts are deterministic stand-ins.\n", file=sys.stderr)

    sim = Simulation(
        ticker_snapshot=snapshot,
        llm=llm,
        personas=default_cast(args.analysts),
        horizon_weeks=args.horizon,
        debate_rounds=args.debate_rounds,
    )
    result = sim.run()
    report = render_report(result)
    print(report)

    if args.out:
        with open(args.out, "w") as f:
            f.write(report + "\n")
        print(f"\n[report written to {args.out}]", file=sys.stderr)

    # Stage 5: optional interactive follow-up with the most confident analyst.
    if args.ask:
        lead = max(result.final_round, key=lambda s: s.confidence)
        agent = next(a for a in result.agents if a.name == lead.agent)
        print(f"\n## Q&A with {agent.name}\n")
        print(f"**Q:** {args.ask}\n")
        print(f"**A:** {agent.answer(snapshot, args.ask)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
