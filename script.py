from pathlib import Path

BASE = Path("learning/governance_gate")

FILES = {
    "__init__.py": "",

    "gate_policy.py": """
class GovernanceGatePolicy:
    '''
    Pure governance gate policy.

    Approves only structurally clean governance records.

    Contract:
    - Pure
    - Deterministic
    - No mutation
    - No runtime access
    '''

    def compute(self, record=None):
        record = record or {}

        fragility = record.get("fragility_index", 0)
        was_clamped = record.get("was_clamped", False)

        if fragility > 0:
            return {
                "approved": False,
                "reason": "fragility_detected",
            }

        if was_clamped:
            return {
                "approved": False,
                "reason": "adjustment_clamped",
            }

        return {
            "approved": True,
            "reason": "structurally_clean",
        }
""",

    "gate_engine.py": """
from typing import Dict
from .gate_policy import GovernanceGatePolicy


class GovernanceGateEngine:
    '''
    Offline governance gate engine.

    Contract:
    - Pure
    - Deterministic
    - No mutation
    - No registry access
    '''

    def __init__(self):
        self._policy = GovernanceGatePolicy()

    def evaluate(self, *, record: Dict = None) -> Dict[str, object]:
        return self._policy.compute(record)
""",

    "gate_trace.py": """
from dataclasses import dataclass


@dataclass(frozen=True)
class GovernanceGateTrace:
    approved: bool
    reason: str
""",

    "gate_report.py": """
from dataclasses import dataclass


@dataclass(frozen=True)
class GovernanceGateReport:
    approved: bool
    reason: str
"""
}

TEST_FILES = {
    "__init__.py": "",

    "test_gate_is_deterministic.py": """
from learning.governance_gate.gate_engine import GovernanceGateEngine

def test_gate_is_deterministic():
    engine = GovernanceGateEngine()

    record = {
        "fragility_index": 0,
        "was_clamped": False,
    }

    a = engine.evaluate(record=record)
    b = engine.evaluate(record=record)

    assert a == b
""",

    "test_gate_rejects_when_clamped.py": """
from learning.governance_gate.gate_engine import GovernanceGateEngine

def test_gate_rejects_when_clamped():
    engine = GovernanceGateEngine()

    record = {
        "fragility_index": 0,
        "was_clamped": True,
    }

    result = engine.evaluate(record=record)

    assert result["approved"] is False
    assert result["reason"] == "adjustment_clamped"
""",

    "test_gate_rejects_when_fragile.py": """
from learning.governance_gate.gate_engine import GovernanceGateEngine

def test_gate_rejects_when_fragile():
    engine = GovernanceGateEngine()

    record = {
        "fragility_index": 5,
        "was_clamped": False,
    }

    result = engine.evaluate(record=record)

    assert result["approved"] is False
    assert result["reason"] == "fragility_detected"
""",

    "test_gate_accepts_clean_record.py": """
from learning.governance_gate.gate_engine import GovernanceGateEngine

def test_gate_accepts_clean_record():
    engine = GovernanceGateEngine()

    record = {
        "fragility_index": 0,
        "was_clamped": False,
    }

    result = engine.evaluate(record=record)

    assert result["approved"] is True
    assert result["reason"] == "structurally_clean"
""",

    "test_gate_no_authority_edges.py": """
import inspect
import learning.governance_gate.gate_engine as mod

def test_gate_no_authority_edges():
    src = inspect.getsource(mod)
    assert "engine.runtime" not in src
"""
}

def write_files(base_path, files_dict):
    base_path.mkdir(parents=True, exist_ok=True)
    for name, content in files_dict.items():
        path = base_path / name
        path.write_text(content.strip() + "\n", encoding="utf-8")

write_files(BASE, FILES)
write_files(BASE / "tests", TEST_FILES)

print("Governance Gate bundle generated successfully.")