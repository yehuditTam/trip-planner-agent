# Trip Planner — One Agent, Two Harnesses

A weekend trip-planning agent built twice:

- `API/` — on the raw Claude Messages API; the whole harness is hand-written in `API/harness/`.
- `SDK/` — on the Claude Agent SDK; Claude Code runs the harness, we only configure it.
- `shared/` — domain tools and data used by both (Open-Meteo weather/geocoding, itineraries, packing list, memory).

Authors: Leah & Yehudit

## Setup

```bash
py -3.14 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

## Run

```bash
# Offline tests (no API key needed)
.venv/Scripts/python -m pytest

# API version — needs ANTHROPIC_API_KEY set in the terminal only (never in code/git)
.venv/Scripts/python API/main.py --scenario scenario.json --out results/api.json

# SDK version — uses your Claude Code login; ANTHROPIC_API_KEY must NOT be set
.venv/Scripts/python SDK/main.py --scenario scenario.json --out results/sdk.json
```

See `REPORT.md` for the comparison.
