"""MiroFish for stocks.

A MiroFish-inspired multi-agent simulator for equities. A swarm of LLM
"analyst" agents, each with a distinct persona and its own memory, studies a
stock, debates with the others, and converges on a directional forecast.

The pipeline mirrors MiroFish's five stages:

  1. Snapshot   -- build a factual market snapshot from raw OHLCV data
                   (analogous to MiroFish's graph construction from seed data).
  2. Personas   -- instantiate a cast of analyst agents.
  3. Simulate   -- run parallel analysis + multi-round debate among the agents.
  4. Report     -- aggregate the swarm into a single interactive report.
  5. Dialogue   -- ask follow-up questions to any surviving agent.
"""

from .data_loader import MarketSnapshot, load_snapshot
from .personas import ANALYST_PERSONAS, Persona
from .agent import AnalystAgent, Stance
from .simulator import Simulation, SimulationResult
from .report import render_report

__all__ = [
    "MarketSnapshot",
    "load_snapshot",
    "ANALYST_PERSONAS",
    "Persona",
    "AnalystAgent",
    "Stance",
    "Simulation",
    "SimulationResult",
    "render_report",
]
