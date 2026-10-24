"""TripAgent on the raw Messages API: wires the hand-written harness together."""
import json
import time

from API.harness import caching, compaction, context, history, logger, loop, memory
from API.harness.tokens import TurnMeter
from API.harness.tools import TOOLS
from shared.prompts import SYSTEM_PROMPT

log = logger(__file__)

MODEL = "claude-opus-5-5"
EFFORT = "medium"
MAX_TOKENS = 16000


class TripAgent:
    def __init__(self, client, compaction_threshold: int = 20_000, model: str = MODEL, effort: str = EFFORT):
        self.client = client
        self.model = model
        self.effort = effort
        self.threshold = compaction_threshold
        self.meter = TurnMeter(model)
        # A new instance always starts from disk: history (append-only) + memory files.
        self.messages, self.summary = history.load_active()
        self.loaded_from_disk = len(self.messages)
        self.context_tokens = len(json.dumps(self.messages)) // 4  # estimate until the first real call

    def _call(self, messages: list[dict]):
        system, tools, msgs = caching.apply(SYSTEM_PROMPT, TOOLS, messages)
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=tools,
            messages=msgs,
            output_config={"effort": self.effort},
        )
        self.meter.record(resp.usage)
        return resp

    def chat(self, user_text: str) -> dict:
        t0 = time.perf_counter()
        self.meter.reset()
        compacted = False
        if self.messages and compaction.should_compact(self.context_tokens, self.threshold):
            self.summary = compaction.compact(self._call, self.messages)
            self.messages = []
            compacted = True

        user_msg = context.build_user_turn(
            user_text, memory.retrieve(user_text), self.summary if not self.messages else None)
        self.messages.append(user_msg)
        history.append_message(user_msg)

        reply, tools_called = loop.run(self._call, self.messages)
        self.context_tokens = self.meter.last_context_tokens
        stats = self.meter.summary()
        return {"reply": reply, "tools": tools_called, "compacted": compacted,
                "time_s": round(time.perf_counter() - t0, 2), **stats}
