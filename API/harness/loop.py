"""The agent loop: call the model while it asks for tools; return all tool_results in one message."""
from API.harness import history, logger
from API.harness.tools import dispatch

log = logger(__file__)
MAX_ITERATIONS = 10


def to_param(block) -> dict:
    """Response block -> request block, unchanged (thinking blocks must be replayed as-is)."""
    return block.to_dict()


def run(call_model, messages: list[dict]) -> tuple[str, list[str]]:
    """Mutates `messages` (and history on disk). Returns (final text, names of tools called)."""
    tools_called: list[str] = []
    resp = call_model(messages)
    iterations = 1
    log(f"model call #{iterations} stop_reason={resp.stop_reason}")
    _append(messages, {"role": "assistant", "content": [to_param(b) for b in resp.content]})

    while resp.stop_reason == "tool_use":
        uses = [b for b in resp.content if b.type == "tool_use"]
        tools_called += [b.name for b in uses]
        log(f"running {len(uses)} tool(s): {', '.join(b.name for b in uses)}")
        # All results in ONE user message - splitting them discourages parallel tool calls.
        _append(messages, {"role": "user", "content": [dispatch(b) for b in uses]})
        if iterations >= MAX_ITERATIONS:
            log(f"stopping: reached {MAX_ITERATIONS} iterations")
            break
        resp = call_model(messages)
        iterations += 1
        log(f"model call #{iterations} stop_reason={resp.stop_reason}")
        _append(messages, {"role": "assistant", "content": [to_param(b) for b in resp.content]})

    if resp.stop_reason == "refusal":
        log(f"refusal: {getattr(resp.stop_details, 'category', None)}")
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text, tools_called


def _append(messages: list[dict], message: dict) -> None:
    messages.append(message)
    history.append_message(message)
