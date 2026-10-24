"""Offline stand-ins: a scripted Anthropic client that returns real anthropic.types.Message objects."""
import itertools

from anthropic.types import Message

_ids = itertools.count(1)


def usage(inp=100, out=20, read=0, write=0):
    return {"input_tokens": inp, "output_tokens": out,
            "cache_read_input_tokens": read, "cache_creation_input_tokens": write}


def tool_use(name, **inp):
    return {"type": "tool_use", "id": f"toolu_{next(_ids)}", "name": name, "input": inp}


def text(t):
    return {"type": "text", "text": t}


def reply(*blocks, stop=None, **u):
    stop = stop or ("tool_use" if any(b["type"] == "tool_use" for b in blocks) else "end_turn")
    content = [{"type": "thinking", "thinking": "", "signature": "sig"}, *blocks]
    return Message.model_validate({
        "id": f"msg_{next(_ids)}", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": content, "stop_reason": stop, "stop_sequence": None, "usage": usage(**u)})


class FakeMessages:
    def __init__(self, script):
        self.script = list(script)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("FakeClient ran out of scripted responses")
        return self.script.pop(0)


class FakeClient:
    def __init__(self, script):
        self.messages = FakeMessages(script)
