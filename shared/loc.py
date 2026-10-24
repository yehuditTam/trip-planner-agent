"""Lines of code per harness component (non-blank, non-comment-only lines)."""
import re
from pathlib import Path

from shared.store import ROOT

COMPONENTS = ["loop", "tools", "history", "memory", "context", "compaction", "caching", "tokens"]


def _code_lines(path: Path) -> list[str]:
    out, in_doc = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith('"""'):
            if not (len(s) > 3 and s.endswith('"""')):
                in_doc = not in_doc
            continue
        if in_doc or not s or s.startswith("#"):
            continue
        out.append(line)
    return out


def api_loc() -> dict:
    h = ROOT / "API" / "harness"
    loc = {c: len(_code_lines(h / f"{c}.py")) for c in COMPONENTS}
    loc["agent.py + main.py"] = sum(len(_code_lines(ROOT / "API" / f)) for f in ("agent.py", "main.py"))
    return loc


def sdk_loc() -> dict:
    """Lines marked '# replaces: <component>' (comment-only markers count: they are config decisions)."""
    loc = {c: 0 for c in COMPONENTS}
    for f in ("agent.py", "tools.py"):
        for line in (ROOT / "SDK" / f).read_text(encoding="utf-8").splitlines():
            if m := re.search(r"# replaces: (\w+)", line):
                loc[m.group(1)] += 1
    loc["agent.py + main.py + tools.py (total)"] = sum(len(_code_lines(ROOT / "SDK" / f)) for f in ("agent.py", "main.py", "tools.py"))
    return loc
