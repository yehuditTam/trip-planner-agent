"""Long-term memory: stored in memory.json / trips.json (shared/store), retrieved by topic relevance."""
from API.harness import logger
from shared import tools_impl

log = logger(__file__)

# A preference is relevant when the user message touches its topic.
TOPICS = {
    "budget": ["budget", "cost", "price", "cheap", "expensive", "luxury", "nis", "money", "afford"],
    "hiking": ["hike", "hiking", "trail", "walk", "trek", "desert", "climb"],
    "food": ["food", "eat", "restaurant", "kosher", "vegan", "vegetarian"],
    "travel_style": ["luxury", "hotel", "style", "comfort", "camping"],
    "pace": ["pace", "relax", "busy", "slow"],
}
# Planning needs every constraint; "what do you remember" needs history too.
PLANNING = ["plan", "itinerary", "trip", "weekend", "packing", "pack"]
RECALL = ["remember", "preference", "about me", "last trip", "previous"]


def retrieve(user_msg: str) -> str | None:
    """Return a compact memory block for this turn, or None when nothing is relevant."""
    text = user_msg.lower()
    prefs = tools_impl.active_preferences()
    wants_all = any(w in text for w in RECALL)
    planning = any(w in text for w in PLANNING)

    def relevant(p):
        words = TOPICS.get(p["key"], [p["key"]])
        return wants_all or planning or any(w in text for w in words)

    chosen = [p for p in prefs if relevant(p)]
    last_trip = tools_impl.last_trip_summary() if (wants_all or planning) else None
    log(f"retrieve: {len(chosen)}/{len(prefs)} preferences, last_trip={'yes' if last_trip else 'no'}")
    if not chosen and not last_trip:
        return None
    lines = [f"- {p['key']}: {p['value']}" for p in chosen]
    if last_trip:
        lines.append(f"- last trip: {last_trip}")
    return "Saved memory (relevant to this message):\n" + "\n".join(lines)
