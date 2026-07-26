"""Stage 3 -- run the swarm.

Agents first analyse the snapshot in parallel, then debate over one or more
rounds (each seeing the others' latest stances), and finally the panel is
aggregated into a confidence-weighted consensus.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from statistics import mean

from .agent import AnalystAgent, Stance
from .data_loader import MarketSnapshot
from .llm import LLMClient
from .personas import Persona, default_cast


@dataclass
class SimulationResult:
    snapshot: MarketSnapshot
    horizon_weeks: int
    rounds: list[list[Stance]]        # stances per debate round
    consensus_stance: str
    consensus_confidence: float
    consensus_target_pct: float
    agreement: float                  # 0..1, how aligned the panel is
    agents: list[AnalystAgent] = field(default_factory=list)

    @property
    def final_round(self) -> list[Stance]:
        return self.rounds[-1] if self.rounds else []


@dataclass
class Simulation:
    ticker_snapshot: MarketSnapshot
    llm: LLMClient
    personas: list[Persona] | None = None
    horizon_weeks: int = 4
    debate_rounds: int = 1
    max_workers: int = 6

    def _build_agents(self) -> list[AnalystAgent]:
        cast = self.personas if self.personas is not None else default_cast()
        return [
            AnalystAgent(persona=p, llm=self.llm, horizon_weeks=self.horizon_weeks)
            for p in cast
        ]

    def _map(self, fn, agents: list[AnalystAgent]) -> list[Stance]:
        # Parallelise the (I/O-bound) LLM calls. Preserve agent order.
        if self.llm.is_mock or self.max_workers <= 1:
            return [fn(a) for a in agents]
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(agents))) as ex:
            return list(ex.map(fn, agents))

    def run(self) -> SimulationResult:
        snap = self.ticker_snapshot
        agents = self._build_agents()
        rounds: list[list[Stance]] = []

        # Round 0: independent analysis.
        first = self._map(lambda a: a.analyse(snap, round_no=0), agents)
        rounds.append(first)

        # Cross-pollinate memory so each agent sees the whole panel.
        board = list(first)
        for a in agents:
            for s in board:
                if s.agent != a.name:
                    a.remember(
                        f"[panel r0] {s.agent}: {s.stance} "
                        f"(conf {s.confidence:.2f})"
                    )

        # Debate rounds: each agent rebuts the current board.
        for r in range(1, self.debate_rounds + 1):
            current = list(rounds[-1])
            revised = self._map(
                lambda a, cur=current, rn=r: a.rebut(snap, cur, round_no=rn),
                agents,
            )
            rounds.append(revised)

        consensus = _aggregate(rounds[-1])
        return SimulationResult(
            snapshot=snap,
            horizon_weeks=self.horizon_weeks,
            rounds=rounds,
            agents=agents,
            **consensus,
        )


def _aggregate(final: list[Stance]) -> dict:
    """Confidence-weighted aggregation of the final round into a consensus."""
    if not final:
        return {
            "consensus_stance": "neutral",
            "consensus_confidence": 0.0,
            "consensus_target_pct": 0.0,
            "agreement": 0.0,
        }

    # Net signed confidence decides direction and strength.
    net = mean(s.signed_confidence for s in final)
    if net > 0.1:
        stance = "bullish"
    elif net < -0.1:
        stance = "bearish"
    else:
        stance = "neutral"

    consensus_conf = round(min(abs(net) * 1.5, 0.99), 2)
    consensus_target = round(mean(s.target_change_pct for s in final), 2)

    # Agreement: fraction of the panel sharing the majority direction.
    majority = max(("bullish", "bearish", "neutral"), key=lambda k: sum(s.stance == k for s in final))
    agreement = round(sum(s.stance == majority for s in final) / len(final), 2)

    return {
        "consensus_stance": stance,
        "consensus_confidence": consensus_conf,
        "consensus_target_pct": consensus_target,
        "agreement": agreement,
    }
