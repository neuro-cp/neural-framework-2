from __future__ import annotations

import json
from memory.inspection.inspection_report import InspectionReport


class JSONInspectionExporter:
    """
    Explicit JSON view over an InspectionReport.

    Read-only.
    Descriptive only.
    No authority leakage.
    """

    def export(self, report: InspectionReport) -> str:
        payload = {
            # --- Provenance ---
            "report_id": report.report_id,
            "generated_step": report.generated_step,
            "generated_time": report.generated_time,
            "inspected_components": list(report.inspected_components),

            # --- Core counts ---
            "episode_count": report.episode_count,
            "semantic_record_count": report.semantic_record_count,
            "drift_record_count": report.drift_record_count,
            "promotion_candidate_count": report.promotion_candidate_count,

            # --- Descriptive summaries ---
            "summaries": dict(report.summaries),

            # --- Warnings only (human-facing) ---
            "warnings": list(report.warnings),
        }

        return json.dumps(payload, indent=2, sort_keys=True)
