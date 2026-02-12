import os

BASE = os.path.join("memory", "recall_runtime_bridge")
TESTS = os.path.join(BASE, "tests")

FILES = {}

FILES[os.path.join(BASE, "__init__.py")] = ""
FILES[os.path.join(TESTS, "__init__.py")] = ""

# ---------------------------------------
# recall_runtime_result.py
# ---------------------------------------

FILES[os.path.join(BASE, "recall_runtime_result.py")] = """from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class RecallRuntimeResult:
    applied_targets: Dict[str, float]
"""

# ---------------------------------------
# recall_runtime_policy.py
# ---------------------------------------

FILES[os.path.join(BASE, "recall_runtime_policy.py")] = """class RecallRuntimePolicy:
    ENABLE_RECALL_EXECUTION = True
"""

# ---------------------------------------
# recall_runtime_adapter.py
# ---------------------------------------

FILES[os.path.join(BASE, "recall_runtime_adapter.py")] = """from typing import Dict

from engine.execution.execution_target import ExecutionTarget
from engine.execution.execution_gate import ExecutionGate

from memory.influence_arbitration.influence_packet import InfluencePacket
from .recall_runtime_result import RecallRuntimeResult
from .recall_runtime_policy import RecallRuntimePolicy


class RecallRuntimeAdapter:

    def apply_packet(
        self,
        packet: InfluencePacket,
        gate: ExecutionGate,
        identity_map: Dict[str, float],
    ) -> RecallRuntimeResult:

        if not RecallRuntimePolicy.ENABLE_RECALL_EXECUTION:
            return RecallRuntimeResult(applied_targets={})

        applied = {}

        for target_name, magnitude in packet.targets.items():
            enum_target = ExecutionTarget[target_name]

            identity = identity_map.get(target_name, 0.0)

            result = gate.apply(
                target=enum_target,
                value=magnitude,
                identity=identity,
            )

            applied[target_name] = result

        return RecallRuntimeResult(applied_targets=applied)
"""

# ---------------------------------------
# TESTS
# ---------------------------------------

FILES[os.path.join(TESTS, "test_bridge_execution_off.py")] = """from memory.recall_runtime_bridge.recall_runtime_adapter import RecallRuntimeAdapter
from memory.influence_arbitration.influence_packet import InfluencePacket

class DummyGate:
    def apply(self, target, value, identity):
        return identity  # always identity

def test_execution_off():
    adapter = RecallRuntimeAdapter()
    packet = InfluencePacket(targets={"VALUE_BIAS": 5.0})

    result = adapter.apply_packet(packet, DummyGate(), {"VALUE_BIAS": 0.0})

    assert result.applied_targets["VALUE_BIAS"] == 0.0
"""

FILES[os.path.join(TESTS, "test_bridge_execution_on.py")] = """from memory.recall_runtime_bridge.recall_runtime_adapter import RecallRuntimeAdapter
from memory.influence_arbitration.influence_packet import InfluencePacket

class DummyGate:
    def apply(self, target, value, identity):
        return value

def test_execution_on():
    adapter = RecallRuntimeAdapter()
    packet = InfluencePacket(targets={"VALUE_BIAS": 5.0})

    result = adapter.apply_packet(packet, DummyGate(), {"VALUE_BIAS": 0.0})

    assert result.applied_targets["VALUE_BIAS"] == 5.0
"""

FILES[os.path.join(TESTS, "test_bridge_identity_preserved.py")] = """from memory.recall_runtime_bridge.recall_runtime_adapter import RecallRuntimeAdapter
from memory.influence_arbitration.influence_packet import InfluencePacket

class DummyGate:
    def apply(self, target, value, identity):
        return identity

def test_identity_preserved():
    adapter = RecallRuntimeAdapter()
    packet = InfluencePacket(targets={"VALUE_BIAS": 3.0})

    result = adapter.apply_packet(packet, DummyGate(), {"VALUE_BIAS": 2.0})

    assert result.applied_targets["VALUE_BIAS"] == 2.0
"""

FILES[os.path.join(TESTS, "test_bridge_deterministic.py")] = """from memory.recall_runtime_bridge.recall_runtime_adapter import RecallRuntimeAdapter
from memory.influence_arbitration.influence_packet import InfluencePacket

class DummyGate:
    def apply(self, target, value, identity):
        return value

def test_deterministic():
    adapter = RecallRuntimeAdapter()
    packet = InfluencePacket(targets={"VALUE_BIAS": 4.0})

    r1 = adapter.apply_packet(packet, DummyGate(), {"VALUE_BIAS": 0.0})
    r2 = adapter.apply_packet(packet, DummyGate(), {"VALUE_BIAS": 0.0})

    assert r1 == r2
"""

for path, content in FILES.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

print("Recall Runtime Bridge module created successfully.")