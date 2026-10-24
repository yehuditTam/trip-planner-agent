"""Run the API version: interactive chat, or a scenario (python API/main.py --scenario scenario.json --out results/api.json)."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import anthropic  # noqa: E402

from API.agent import TripAgent  # noqa: E402
from shared import store  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario")
    ap.add_argument("--out")
    ap.add_argument("--compaction-threshold", type=int, default=20_000)
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Set it in this terminal only (never in code or git).")
    os.environ.setdefault("TRIP_STATE_DIR", str(store.ROOT / "state" / "api"))
    client = anthropic.Anthropic()

    if args.scenario:
        from shared.scenario_runner import run_scenario
        run_scenario(args.scenario, args.out, lambda threshold: TripAgent(client, threshold), "api")
        return

    agent = TripAgent(client, args.compaction_threshold)
    print("Trip planner (API). Empty line to quit.")
    while (text := input("you> ").strip()):
        out = agent.chat(text)
        print(f"\nagent> {out['reply']}\n")


if __name__ == "__main__":
    main()
