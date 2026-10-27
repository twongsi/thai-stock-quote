"""The analyst agent -- a persona plus memory plus an LLM.

Each agent produces a :class:`Stance` (direction + confidence + rationale),
remembers what it and others have said, and can revise its view after a round
of debate. This is the equities analogue of MiroFish's memory-bearing agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .data_loader import MarketSnapshot
from .llm import LLMClient
from .personas import Persona

VALID_STANCES = ("bullish", "bearish", "neutral")


@dataclass
class Stance:
    agent: str
    stance: str                 # one of VALID_STANCES
    confidence: float           # 0..1
    target_change_pct: float    # expected % move over the horizon
    rationale: str
    round: int = 0

    @property
    def signed_confidence(self) -> float:
        """Confidence signed by direction: + bullish, - bearish, 0 neutral."""
        if self.stance == "bullish":
            return self.confidence
        if self.stance == "bearish":
            return -self.confidence
        return 0.0


def _coerce_stance(agent: str, data: dict, round_no: int) -> Stance:
    stance = str(data.get("stance", "neutral")).strip().lower()
    if stance not in VALID_STANCES:
        stance = "neutral"
    try:
        conf = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    conf = max(0.0, min(1.0, conf))
    try:
        tgt = float(data.get("target_change_pct", 0.0))
    except (TypeError, ValueError):
        tgt = 0.0
    rationale = str(data.get("rationale", "")).strip() or "(no rationale given)"
    return Stance(
        agent=agent,
        stance=stance,
        confidence=conf,
        target_change_pct=tgt,
        rationale=rationale,
        round=round_no,
    )


@dataclass
class AnalystAgent:
    persona: Persona
    llm: LLMClient
    horizon_weeks: int = 4
    memory: list[str] = field(default_factory=list)
    history: list[Stance] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.persona.name

    def remember(self, text: str) -> None:
        self.memory.append(text)

    def _base_system(self) -> str:
        return (
            f"{self.persona.system_prompt}\n\n"
            f"You are '{self.persona.name}', a {self.persona.style}, taking part in "
            f"a multi-analyst forecasting panel for a single stock. Your forecast "
            f"horizon is {self.horizon_weeks} weeks. Stay in character. Be concise "
            f"and specific; reference the concrete numbers in the fact sheet."
        )

    def _memory_block(self) -> str:
        if not self.memory:
            return ""
        recent = self.memory[-6:]
        return "\n\nWhat you and the panel have said so far:\n- " + "\n- ".join(recent)

    def analyse(self, snapshot: MarketSnapshot, round_no: int = 0) -> Stance:
        """Produce (or revise) this agent's stance on the snapshot."""
        system = self._base_system()
        prompt = (
            "Here is the market fact sheet.\n\n"
            f"{snapshot.to_facts()}\n"
            f"{self._memory_block()}\n\n"
            "Give your forecast as JSON with keys: "
            '"stance" (bullish|bearish|neutral), '
            '"confidence" (0-1), '
            '"target_change_pct" (expected % price move over the horizon), '
            '"rationale" (one or two sentences, in character).'
        )
        data = self.llm.complete_json(system, prompt)
        stance = _coerce_stance(self.name, data, round_no)
        self.history.append(stance)
        self.remember(
            f"[{self.name} r{round_no}] {stance.stance} "
            f"(conf {stance.confidence:.2f}): {stance.rationale}"
        )
        return stance

    def rebut(self, snapshot: MarketSnapshot, others: list[Stance], round_no: int) -> Stance:
        """Revise this agent's view after seeing the rest of the panel."""
        board = "\n".join(
            f"- {s.agent}: {s.stance} (conf {s.confidence:.2f}, "
            f"target {s.target_change_pct:+.1f}%) -- {s.rationale}"
            for s in others
            if s.agent != self.name
        )
        system = self._base_system()
        prompt = (
            "Here is the market fact sheet again.\n\n"
            f"{snapshot.to_facts()}\n\n"
            "The rest of the panel just argued:\n"
            f"{board}\n\n"
            "Consider their arguments. You may hold or update your view -- change "
            "your mind only if genuinely persuaded, and stay in character. "
            "Respond as JSON with keys: stance, confidence, target_change_pct, "
            "rationale (say briefly what, if anything, moved you)."
        )
        data = self.llm.complete_json(system, prompt)
        stance = _coerce_stance(self.name, data, round_no)
        self.history.append(stance)
        self.remember(
            f"[{self.name} r{round_no}] revised -> {stance.stance} "
            f"(conf {stance.confidence:.2f}): {stance.rationale}"
        )
        return stance

    def answer(self, snapshot: MarketSnapshot, question: str) -> str:
        """Stage 5 -- free-form follow-up Q&A with this agent."""
        system = self._base_system()
        prompt = (
            f"Market fact sheet:\n{snapshot.to_facts()}\n"
            f"{self._memory_block()}\n\n"
            f"A user asks you: {question}\n\n"
            "Answer in character, concisely."
        )
        return self.llm.complete(system, prompt)
