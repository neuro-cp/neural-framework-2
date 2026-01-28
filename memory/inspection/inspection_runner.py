from __future__ import annotations

from typing import List, Dict
from collections import defaultdict

from memory.inspection.audit.integrity_audit_base import IntegrityAudit
from memory.inspection.audit.integrity_finding import IntegrityFinding
from memory.inspection.inspection_report import (
    InspectionReport,
    InspectionAuditSummary,
    InspectionReportWithAudits,
)


class InspectionRunner:
    """
    Offline inspection orchestrator.

    Responsibilities:
    - run integrity audits
    - aggregate findings
    - attach results to InspectionReport
    - NO runtime authority
    - NO mutation
    """

    def __init__(
        self,
        *,
        base_report: InspectionReport,
        audits: List[IntegrityAudit],
    ) -> None:
        self._base_report = base_report
        self._audits = audits

    # --------------------------------------------------
    # Execution
    # --------------------------------------------------

    def run(self) -> InspectionReportWithAudits:
        findings: List[IntegrityFinding] = []

        for audit in self._audits:
            findings.extend(audit.run())

        audit_summary = self._summarize(findings)

        return InspectionReportWithAudits(
            **self._base_report.__dict__,
            audits=audit_summary,
        )

    # --------------------------------------------------
    # Aggregation (pure)
    # --------------------------------------------------

    def _summarize(
        self,
        findings: List[IntegrityFinding],
    ) -> InspectionAuditSummary:
        by_audit: Dict[str, List[IntegrityFinding]] = defaultdict(list)
        by_layer: Dict[str, List[IntegrityFinding]] = defaultdict(list)
        by_severity: Dict[str, List[IntegrityFinding]] = defaultdict(list)

        for f in findings:
            by_audit[f.audit_id].append(f)
            by_layer[f.layer].append(f)
            by_severity[f.severity].append(f)

        return InspectionAuditSummary(
            total_findings=len(findings),
            error_count=len(by_severity.get("ERROR", [])),
            warning_count=len(by_severity.get("WARNING", [])),
            by_audit=dict(by_audit),
            by_layer=dict(by_layer),
            by_severity=dict(by_severity),
        )
