"""Checkpoint router (#37): the simulated fixtures, or RouteLLM's strong-model win rate.

RouteLLM scores a prompt from 0 to 1 ("how much the strong model is needed"); a score at
or above the threshold recommends the large model. The router name and threshold are
pilot decisions: they must be configured explicitly and held fixed during the study.
There is no fallback recommendation when the router fails.
"""

import json
import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass

from .definitions import RECOMMENDATIONS

# Provisional participant-facing reasons for RouteLLM recommendations, pending approval.
ROUTELLM_REASONS = {
    "small": "Router estimate: the small model is likely enough for this stage.",
    "large": "Router estimate: this stage likely needs the large model.",
}
# RouteLLM routers that call the OpenAI embeddings API (and so need a real key).
OPENAI_ROUTERS = ("mf", "sw_ranking")


class RouterError(Exception):
    """Routing failed. The message is safe to log: no keys or provider bodies."""


@dataclass
class RoutingResult:
    model: str
    reason: str
    router: str
    score: float | None = None
    threshold: float | None = None
    latency_ms: int = 0


class MockRouter:
    """The frontend mock's fixed per-checkpoint recommendations."""

    name = "mock"

    def recommend(self, prompt: str, checkpoint: str) -> RoutingResult:
        fixture = RECOMMENDATIONS[checkpoint]
        return RoutingResult(fixture["model"], fixture["reason"], self.name)


class RouteLLMRouter:
    def __init__(self, name: str, threshold: float, score: Callable[[str], float]):
        self.name, self.threshold, self._score = f"routellm:{name}", threshold, score

    def recommend(self, prompt: str, checkpoint: str) -> RoutingResult:
        started = time.monotonic()
        try:
            score = float(self._score(prompt))
        except Exception as error:  # RouteLLM, torch, network, or embedding failures
            raise RouterError(f"{self.name} failed ({type(error).__name__})") from None
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise RouterError(f"{self.name} returned an invalid score")
        model = "large" if score >= self.threshold else "small"
        return RoutingResult(model, ROUTELLM_REASONS[model], self.name, score, self.threshold,
                             int((time.monotonic() - started) * 1000))


def load_routellm_scorer(name: str, openai_api_key: str | None) -> Callable[[str], float]:
    """Load one RouteLLM router with its published GPT-4-augmented checkpoint."""
    # RouteLLM builds an OpenAI client at import time, so a key must be in the environment
    # even for routers that never call OpenAI (bert, causal_llm, random).
    if openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", openai_api_key)
    elif name not in OPENAI_ROUTERS:
        os.environ.setdefault("OPENAI_API_KEY", "not-used-by-this-router")
    try:
        from routellm.controller import GPT_4_AUGMENTED_CONFIG
        from routellm.routers.routers import ROUTER_CLS
    except ImportError as error:
        raise RuntimeError("ROUTER_MODE=routellm needs `pip install -r requirements-routellm.txt`.") from error
    router = ROUTER_CLS[name](**GPT_4_AUGMENTED_CONFIG.get(name, {}))
    return router.calculate_strong_win_rate


def routing_prompt(scenario: dict, checkpoint: str, plan: dict, messages: list[dict]) -> str:
    """The text the router scores: the stage task, requirements, plan, and recent messages."""
    requirements = scenario["requirements"]
    recent = [m["text"] for m in messages if m["role"] == "user"][-3:]
    lines = [
        f"Help plan the {checkpoint} stage of an event: {scenario['title']}.",
        f"{requirements['attendees']} guests, total budget {requirements['budgetCents'] / 100:.2f} USD, "
        f"dietary needs {', '.join(requirements['dietaryNeeds'])}, wheelchair access "
        f"{'required' if requirements['wheelchairRequired'] else 'not required'}.",
        "Compare catalog options and check budget, capacity, dietary coverage, and accessibility.",
        f"Current plan: {json.dumps(plan)}.",
    ]
    if recent:
        lines.append("Participant's recent questions: " + " | ".join(recent))
    return "\n".join(lines)
