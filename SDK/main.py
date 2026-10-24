"""Run the SDK version: interactive chat, or a scenario (python SDK/main.py --scenario scenario.json --out results/sdk.json)."""
import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from SDK.agent import SDKTripAgent  # noqa: E402
from shared import store  # noqa: E402


async def chat_repl() -> None:
    async with SDKTripAgent() as agent:
        print("Trip planner (SDK). Empty line to quit.")
        while (text := input("you> ").strip()):
            out = await agent.chat(text)
            print(f"\nagent> {out['reply']}\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario")
    ap.add_argument("--out")
    args = ap.parse_args()

    if os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is set - billing would move to the key. Unset it to use your Claude Code login.")
    os.environ.setdefault("TRIP_STATE_DIR", str(store.ROOT / "state" / "sdk"))

    if args.scenario:
        from shared.scenario_runner import run_scenario
        run_scenario(args.scenario, args.out, lambda threshold: SDKTripAgent(), "sdk")
        return
    asyncio.run(chat_repl())


if __name__ == "__main__":
    main()
