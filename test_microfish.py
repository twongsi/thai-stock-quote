#!/usr/bin/env python3
"""Smoke tests for the MiroFish stock simulator (run in mock mode, no network).

Run with:  MICROFISH_MOCK=1 python test_microfish.py
"""

import os
import sys

os.environ["MICROFISH_MOCK"] = "1"  # force offline deterministic backend

from microfish import load_snapshot, render_report
from microfish.agent import VALID_STANCES
from microfish.llm import LLMClient, _extract_json
from microfish.personas import default_cast
from microfish.simulator import Simulation

FAILURES = []


def check(cond, msg):
    if cond:
        print(f"  ok  - {msg}")
    else:
        print(f"  FAIL - {msg}")
        FAILURES.append(msg)


def first_ticker():
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    for name in sorted(os.listdir(data_dir)):
        if name.endswith(".csv"):
            return name[:-4]
    raise RuntimeError("no data files found")


def test_json_extraction():
    print("test_json_extraction")
    check(_extract_json('```json\n{"a": 1}\n```') == {"a": 1}, "fenced json parses")
    check(_extract_json('noise {"stance": "bullish"} tail')["stance"] == "bullish", "embedded json parses")
    check(_extract_json("no json here") == {}, "missing json -> empty dict")


def test_snapshot():
    print("test_snapshot")
    t = first_ticker()
    snap = load_snapshot(t)
    check(snap.ticker == t, f"snapshot ticker is {t}")
    check(snap.last_close > 0, "last close is positive")
    check(-3.0 <= snap.momentum_score <= 3.0, "momentum score in range")
    check(snap.annualised_vol_pct >= 0, "volatility non-negative")
    check(len(snap.to_facts()) > 50, "fact sheet renders")


def test_simulation():
    print("test_simulation")
    t = first_ticker()
    snap = load_snapshot(t)
    sim = Simulation(
        ticker_snapshot=snap,
        llm=LLMClient(),
        personas=default_cast(),
        horizon_weeks=4,
        debate_rounds=1,
    )
    result = sim.run()
    check(len(result.rounds) == 2, "one debate round yields 2 rounds of stances")
    check(len(result.final_round) == len(default_cast()), "every analyst reported")
    check(result.consensus_stance in VALID_STANCES, "consensus stance is valid")
    check(0.0 <= result.consensus_confidence <= 1.0, "consensus confidence in [0,1]")
    check(0.0 <= result.agreement <= 1.0, "agreement in [0,1]")
    for s in result.final_round:
        check(s.stance in VALID_STANCES, f"{s.agent} stance valid")

    report = render_report(result)
    check(t in report, "report mentions ticker")
    check("Consensus" in report, "report has consensus section")


def test_determinism():
    print("test_determinism")
    t = first_ticker()
    snap = load_snapshot(t)
    r1 = Simulation(snap, LLMClient(), debate_rounds=0).run()
    r2 = Simulation(snap, LLMClient(), debate_rounds=0).run()
    check(r1.consensus_stance == r2.consensus_stance, "mock backend is deterministic")


def main():
    for fn in (test_json_extraction, test_snapshot, test_simulation, test_determinism):
        fn()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
