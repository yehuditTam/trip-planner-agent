"""The same shared tools, exposed through an in-process MCP server."""
import json

from claude_agent_sdk import create_sdk_mcp_server, tool

from shared import tools_impl


def _wrap(fn):
    async def handler(args):
        try:
            text = json.dumps(fn(**args), separators=(",", ":"), ensure_ascii=False)
            return {"content": [{"type": "text", "text": text}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "is_error": True}  # replaces: tools (is_error)
    return handler


TOOLS = [  # replaces: tools (schemas + dispatch)
    tool("geocode", "Find a city's coordinates (Open-Meteo). Returns name, country, lat, lon.",
         {"city": str})(_wrap(tools_impl.geocode)),
    tool("get_forecast", "Daily forecast (Open-Meteo), up to 7 days: date, tmin, tmax, rain_mm, WMO code.",
         {"lat": float, "lon": float, "days": int})(_wrap(tools_impl.get_forecast)),
    tool("save_itinerary", 'Save a trip itinerary. days = [{"day": 1, "plan": "..."}], budget in NIS.',
         {"destination": str, "days": list, "budget": float})(_wrap(tools_impl.save_itinerary)),
    tool("packing_list", "Rule-based packing list. style: casual|luxury|budget.",
         {"style": str, "min_temp": float, "max_temp": float, "rain": bool, "activities": list})(_wrap(tools_impl.packing_list)),
    tool("remember", "Save a lasting preference (key: budget|hiking|travel_style|food|pace). New value supersedes old.",
         {"key": str, "value": str})(_wrap(tools_impl.remember)),
    tool("recall", "Look up saved preferences (filtered by query words) and the last trip.",
         {"query": str})(_wrap(tools_impl.recall)),
]

SERVER = create_sdk_mcp_server("trip", tools=TOOLS)  # replaces: tools (dispatch)
TOOL_NAMES = [f"mcp__trip__{t.name}" for t in TOOLS]
