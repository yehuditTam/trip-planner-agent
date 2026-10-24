"""Usage and cost per model call and per turn."""
from API.harness import logger

log = logger(__file__)

# USD per million tokens. Cache write = 5-minute TTL (1.25x input).
PRICES = {
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_write": 5.00, "cache_read": 0.20},
}


def cost(model: str, u: dict) -> float:
    p = PRICES[model]
    return (u["input"] * p["input"] + u["output"] * p["output"]
            + u["cache_write"] * p["cache_write"] + u["cache_read"] * p["cache_read"]) / 1_000_000


class TurnMeter:
    def __init__(self, model: str):
        self.model = model
        self.reset()

    def reset(self) -> None:
        self.usage = {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0}
        self.model_calls = 0
        self.last_context_tokens = 0

    def record(self, usage) -> None:
        u = {
            "input": usage.input_tokens,
            "cache_read": usage.cache_read_input_tokens or 0,
            "cache_write": usage.cache_creation_input_tokens or 0,
            "output": usage.output_tokens,
        }
        for k in u:
            self.usage[k] += u[k]
        self.model_calls += 1
        # Size of the prompt the model just saw - what compaction compares to its threshold.
        self.last_context_tokens = u["input"] + u["cache_read"] + u["cache_write"]
        log(f"call #{self.model_calls}: in={u['input']} cache_read={u['cache_read']} "
            f"cache_write={u['cache_write']} out={u['output']} ${cost(self.model, u):.5f}")

    def summary(self) -> dict:
        total_in = self.usage["input"] + self.usage["cache_read"] + self.usage["cache_write"]
        out = {
            "tokens": dict(self.usage),
            "model_calls": self.model_calls,
            "cost_usd": round(cost(self.model, self.usage), 6),
            "cache_hit_pct": round(100 * self.usage["cache_read"] / total_in, 1) if total_in else 0.0,
        }
        log(f"turn total: {out['tokens']} calls={out['model_calls']} cache_hit={out['cache_hit_pct']}% ${out['cost_usd']:.5f}")
        return out
