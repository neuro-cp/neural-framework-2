from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from memory.inspection.audit.integrity_finding import IntegrityFinding


# ==================================================
# Core inspection report
# ==================================================

@dataclass(frozen=True)
class InspectionReport:
    """
    Immutable, offline inspection snapshot.

    An InspectionReport:
    - summarizes system state across memory layers
    - is produced offline only
    - carries NO authority
    - is safe to discard and recompute
    - MUST NOT influence runtime behavior

    This object exists solely for human inspection
    or external audit tooling.
    """

    # Report identity
    report_id: str
    generated_step: Optional[int]
    generated_time: Optional[float]

    # Scope metadata
    inspected_components: List[str]

    # High-level counts
    episode_count: int
    semantic_record_count: int
    drift_record_count: int
    promotion_candidate_count: int

    # Diagnostic summaries (descriptive only)
    summaries: Dict[str, Any] = field(default_factory=dict)

    # Integrity observations (human-readable)
    anomalies: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Versioning
    policy_versions: Dict[str, str] = field(default_factory=dict)
    schema_versions: Dict[str, str] = field(default_factory=dict)

    # Freeform notes (non-executive)
    notes: Optional[str] = None


# ==================================================
# Audit aggregation (pure extension)
# ==================================================

@dataclass(frozen=True)
class InspectionAuditSummary:
    """
    Aggregated view of integrity audit results.

    This object:
    - groups audit findings
    - computes counts only
    - carries NO authority
    - MUST NOT mutate or filter findings
    """

    total_findings: int
    error_count: int
    warning_count: int

    # Grouped views (read-only)
    by_audit: Dict[str, List[IntegrityFinding]]
    by_layer: Dict[str, List[IntegrityFinding]]
    by_severity: Dict[str, List[IntegrityFinding]]


@dataclass(frozen=True)
class InspectionReportWithAudits(InspectionReport):
    """
    InspectionReport with integrity audit results attached.

    This is a pure extension:
    - no new authority
    - no behavioral implication
    - safe for export, diffing, or UI
    """

    audits: InspectionAuditSummary
