"""cache_control breakpoints. Applied to a copy of each request, never saved into history.

Render order is tools -> system -> messages, so:
  1. last tool        -> caches the tool definitions
  2. system block     -> caches tools + system
  3. last message     -> caches the whole conversation so far (read back on the next call)
"""
import copy

from API.harness import logger

log = logger(__file__)
EPHEMERAL = {"type": "ephemeral"}


def apply(system: str, tools: list[dict], messages: list[dict]) -> tuple[list, list, list]:
    tools = copy.deepcopy(tools)
    tools[-1]["cache_control"] = EPHEMERAL
    system_blocks = [{"type": "text", "text": system, "cache_control": EPHEMERAL}]
    messages = copy.deepcopy(messages)
    last = messages[-1]
    if isinstance(last["content"], str):
        last["content"] = [{"type": "text", "text": last["content"]}]
    last["content"][-1]["cache_control"] = EPHEMERAL
    log(f"3 breakpoints: tools[{len(tools) - 1}], system, messages[{len(messages) - 1}]")
    return system_blocks, tools, messages
