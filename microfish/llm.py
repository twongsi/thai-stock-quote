"""LLM backend for the analyst swarm.

Targets the Anthropic Claude API. If the ``anthropic`` package or an API key
is unavailable, the client transparently falls back to a deterministic mock so
the whole pipeline still runs offline (useful for tests and demos).

Environment variables
---------------------
ANTHROPIC_API_KEY   Anthropic API key. If unset, mock mode is used.
MICROFISH_MODEL     Model id to use (default: ``claude-sonnet-5``).
MICROFISH_MOCK      Set to ``1`` to force mock mode even if a key is present.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

DEFAULT_MODEL = os.environ.get("MICROFISH_MODEL", "claude-sonnet-5")


@dataclass
class LLMClient:
    """Thin wrapper over the Anthropic Messages API with a mock fallback."""

    model: str = DEFAULT_MODEL
    max_tokens: int = 1024
    temperature: float = 0.7
    _client: Any = field(default=None, init=False, repr=False)
    _mock: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        force_mock = os.environ.get("MICROFISH_MOCK") == "1"
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if force_mock or not api_key:
            self._mock = True
            return
        try:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=api_key)
        except Exception:
            # SDK missing or failed to initialise -- degrade gracefully.
            self._mock = True

    @property
    def is_mock(self) -> bool:
        return self._mock

    def complete(self, system: str, prompt: str) -> str:
        """Return the model's text response to ``prompt`` under ``system``."""
        if self._mock:
            return _mock_response(system, prompt)
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        ).strip()

    def complete_json(self, system: str, prompt: str) -> dict:
        """Complete and parse the first JSON object found in the response."""
        raw = self.complete(system + "\n\nRespond with a single JSON object only.", prompt)
        return _extract_json(raw)


def _extract_json(text: str) -> dict:
    """Pull the first balanced JSON object out of a text blob."""
    # Strip markdown fences if present.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    if start == -1:
        return {}
    depth = 0
    for i in range(start, len(candidate)):
        ch = candidate[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(candidate[start : i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


# --------------------------------------------------------------------------- #
# Mock backend
# --------------------------------------------------------------------------- #
def _seed(*parts: str) -> int:
    h = hashlib.sha256("||".join(parts).encode()).hexdigest()
    return int(h[:8], 16)


def _mock_response(system: str, prompt: str) -> str:
    """Deterministic pseudo-analysis so the pipeline runs without an API key.

    The mock reads the numeric ``momentum`` hint embedded in the prompt (if
    any) so that mock forecasts loosely track the real trend, which keeps demo
    output believable.
    """
    seed = _seed(system[:64], prompt[-256:])
    m = re.search(r"momentum[_\s]*(?:score)?[:=]?\s*([+-]?\d+(?:\.\d+)?)", prompt, re.IGNORECASE)
    momentum = float(m.group(1)) if m else 0.0

    bias = momentum + ((seed % 21) - 10) / 10.0  # persona-specific jitter
    if bias > 0.6:
        stance, conf = "bullish", 0.55 + (seed % 30) / 100.0
    elif bias < -0.6:
        stance, conf = "bearish", 0.55 + (seed % 30) / 100.0
    else:
        stance, conf = "neutral", 0.40 + (seed % 20) / 100.0
    conf = round(min(conf, 0.95), 2)

    if "JSON" in system or "json" in prompt.lower():
        return json.dumps(
            {
                "stance": stance,
                "confidence": conf,
                "target_change_pct": round(bias * 4.0, 2),
                "rationale": (
                    f"[mock] Momentum reading {momentum:+.2f} with persona bias "
                    f"pushes toward a {stance} view over the horizon."
                ),
            }
        )
    return (
        f"[mock] Reading the snapshot, I lean {stance} (confidence {conf:.2f}). "
        f"Momentum of {momentum:+.2f} is the dominant signal; the rest is noise "
        f"until proven otherwise."
    )
