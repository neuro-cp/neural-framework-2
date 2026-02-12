from typing import Dict

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
