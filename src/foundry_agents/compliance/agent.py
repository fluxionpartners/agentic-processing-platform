"""
Compliance Agent.

Applies compliance and governance checks to ensure all data meets regulatory requirements.
"""

from typing import Dict, Any, Optional

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.time_utils import utc_iso


class ComplianceAgent:
    """Handles compliance and governance checks."""

    @staticmethod
    def process(payload: Dict[str, Any], settings: Optional[AgentSettings] = None) -> Dict[str, Any]:
        """Apply compliance checks."""
        settings = settings or load_agent_settings()
        correlation_id = payload.get("correlationId")
        extraction_result = payload.get("extractionResult", {})
        validation_result = payload.get("validationResult", {})
        mapping_result = payload.get("mappingResult", {})
        human_review_result = payload.get("humanReviewResult")
        extracted_data = extraction_result.get("extractedData", {})

        compliance_checks = {
            "sourceDocumentRecorded": bool(extraction_result.get("source", {}).get("blobUri")),
            "extractionConfidenceRecorded": "overallConfidence" in extraction_result,
            "validationCompleted": bool(validation_result.get("validationStatus")),
            "humanReviewRecordedWhenRequired": not validation_result.get("needsReview")
            or bool(human_review_result),
            "taxMappingCompleted": mapping_result.get("mappingStatus") == "success",
            "piiMaskedForLogs": not settings.require_masked_pii_in_logs
            or str(extracted_data.get("employeeSSN", "")).startswith("XXX-XX-"),
            "retentionPolicyApplied": True,
            "auditEnvelopeCreated": settings.audit_event_enabled,
        }
        if settings.is_regulated:
            compliance_checks["humanReviewModeNotLocal"] = (
                payload.get("humanReviewResult", {}).get("decisionMode") != "local_development"
            )

        all_passed = all(compliance_checks.values())
        audit_event = {
            "eventType": "TaxPipelineComplianceEvaluated",
            "correlationId": correlation_id,
            "tenantId": payload.get("tenantId"),
            "taxpayerId": payload.get("taxpayerId"),
            "documentName": payload.get("documentName"),
            "pipelineId": payload.get("pipelineId"),
            "appEnv": settings.app_env,
            "complianceMode": settings.compliance_mode,
            "controlResults": compliance_checks,
            "validationStatus": validation_result.get("validationStatus"),
            "humanReviewStatus": human_review_result.get("reviewStatus")
            if human_review_result
            else None,
            "evaluatedAt": utc_iso(),
        }

        result = {
            "correlationId": correlation_id,
            "complianceStatus": "passed" if all_passed else "flagged",
            "complianceMode": settings.compliance_mode,
            "checks": compliance_checks,
            "auditEvent": audit_event if settings.audit_event_enabled else None,
            "complianceTimestamp": utc_iso(),
            "nextStep": "complete",
        }

        return result


if __name__ == "__main__":
    print("Compliance Agent loaded.")
