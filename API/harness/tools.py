"""Tool JSON schemas + dispatch. Errors go back to the model as is_error tool_results."""
import json

from API.harness import logger
from shared import tools_impl

log = logger(__file__)

TOOLS = [
    {
        "name": "geocode",
        "description": "Find a city's coordinates (Open-Meteo). Returns name, country, lat, lon.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name in English"}},
            "required": ["city"],
        },
    },
    {
        "name": "get_forecast",
        "description": "Daily weather forecast (Open-Meteo) for up to 7 days: date, tmin, tmax, rain_mm, WMO code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lat": {"type": "number"},
                "lon": {"type": "number"},
                "days": {"type": "integer", "minimum": 1, "maximum": 7},
            },
            "required": ["lat", "lon"],
        },
    },
    {
        "name": "save_itinerary",
        "description": "Save a trip itinerary to disk.",
        "input_schema": {
            "type": "object",
            "properties": {
                "destination": {"type": "string"},
                "days": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"day": {"type": "integer"}, "plan": {"type": "string"}},
                        "required": ["day", "plan"],
                    },
                },
                "budget": {"type": "number", "description": "Total budget in NIS"},
            },
            "required": ["destination", "days"],
        },
    },
    {
        "name": "packing_list",
        "description": "Rule-based packing list from weather and activities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "style": {"type": "string", "description": "casual | luxury | budget"},
                "min_temp": {"type": "number"},
                "max_temp": {"type": "number"},
                "rain": {"type": "boolean"},
                "activities": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "remember",
        "description": "Save a lasting user preference. A new value for an existing key supersedes the old one.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "budget | hiking | travel_style | food | pace"},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "recall",
        "description": "Look up saved preferences (filtered by query words) and the last saved trip.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Words to filter by; empty for all"}},
        },
    },
]

_IMPL = {t["name"]: getattr(tools_impl, t["name"]) for t in TOOLS}


def compact(obj) -> str:
    """Minimal JSON: no spaces, real Unicode. Fewer tokens per tool result."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def dispatch(block) -> dict:
    """Run one tool_use block and return its tool_result block."""
    fn = _IMPL.get(block.name)
    try:
        if fn is None:
            raise KeyError(f"unknown tool: {block.name}")
        content = compact(fn(**block.input))
        log(f"{block.name}({compact(block.input)}) -> {len(content)} chars")
        return {"type": "tool_result", "tool_use_id": block.id, "content": content}
    except Exception as e:
        log(f"{block.name} FAILED: {type(e).__name__}: {e}")
        return {"type": "tool_result", "tool_use_id": block.id, "content": f"{type(e).__name__}: {e}", "is_error": True}
