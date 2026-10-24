import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    """Every test gets its own empty state directory."""
    monkeypatch.setenv("TRIP_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return tmp_path / "state"
