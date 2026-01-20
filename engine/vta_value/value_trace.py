from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class ValueTrace:
    """
    Diagnostic trace for tonic VTA value signal.

    This is observational only.
    It must never influence runtime behavior.
    """

    records: List[Dict[str, Any]] = field(default_factory=list)

    # ============================================================
    # Trace API
    # ============================================================

    def record(
        self,
        *,
        time: float,
        step: int,
        value: float,
        source: str = "vta",
        note: str = "",
    ) -> None:
        """
        Record a snapshot of the value signal.

        Parameters:
        - time: runtime time (seconds)
        - step: runtime step index
        - value: current tonic value
        - source: logical source label (default: 'vta')
        - note: optional diagnostic annotation
        """
        self.records.append(
            {
                "time": time,
                "step": step,
                "value": float(value),
                "source": source,
                "note": note,
            }
        )

    def clear(self) -> None:
        """Clear all trace records."""
        self.records.clear()

    def as_list(self) -> List[Dict[str, Any]]:
        """Return raw trace records (for CSV / pandas use)."""
        return list(self.records)

    def summary(self) -> Dict[str, Any]:
        """
        Lightweight summary for quick inspection.
        """
        if not self.records:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "mean": None,
            }

        values = [r["value"] for r in self.records]
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
        }
