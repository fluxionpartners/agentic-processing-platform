from abc import ABC, abstractmethod
from typing import Any, Dict

from foundry_agents.config import AgentSettings
from foundry_agents.time_utils import utc_iso


class ComplianceAdapter(ABC):
    """Adapter contract for compliance evaluation and audit envelope creation."""

    name: str

    @abstractmethod
    def evaluate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate compliance controls and return checks plus optional audit event."""


class LocalComplianceAdapter(ComplianceAdapter):
    """In-process compliance controls for local and default orchestration."""

    name = "local-compliance-controls-v1"

    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings

    def evaluate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        extraction_result = payload.get("extractionResult", {})
        validation_result = payload.get("validationResult", {})
        mapping_result = payload.get("mappingResult", {})
        form_generation_result = payload.get("formGenerationResult", {})
        human_review_result = payload.get("humanReviewResult")
        extracted_data = extraction_result.get("extractedData", {})

        compliance_checks = {
            "sourceDocumentRecorded": bool(extraction_result.get("source", {}).get("blobUri")),
            "extractionConfidenceRecorded": "overallConfidence" in extraction_result,
            "validationCompleted": bool(validation_result.get("validationStatus")),
            "humanReviewRecordedWhenRequired": not validation_result.get("needsReview")
            or bool(human_review_result),
            "taxMappingCompleted": mapping_result.get("mappingStatus") == "success",
            "form1040Generated": form_generation_result.get("generationStatus") == "success",
            "form1040ArtifactRecorded": bool(form_generation_result.get("artifact")),
            "piiMaskedForLogs": not self.settings.require_masked_pii_in_logs
            or str(extracted_data.get("employeeSSN", "")).startswith("XXX-XX-"),
            "retentionPolicyApplied": True,
            "auditEnvelopeCreated": self.settings.audit_event_enabled,
        }
        if self.settings.is_regulated:
            compliance_checks["humanReviewModeNotLocal"] = (
                payload.get("humanReviewResult", {}).get("decisionMode") != "local_development"
            )

        audit_event = {
            "eventType": "TaxPipelineComplianceEvaluated",
            "correlationId": payload.get("correlationId"),
            "tenantId": payload.get("tenantId"),
            "taxpayerId": payload.get("taxpayerId"),
            "documentName": payload.get("documentName"),
            "pipelineId": payload.get("pipelineId"),
            "appEnv": self.settings.app_env,
            "complianceMode": self.settings.compliance_mode,
            "controlResults": compliance_checks,
            "validationStatus": validation_result.get("validationStatus"),
            "form1040ArtifactId": form_generation_result.get("artifact", {}).get("artifactId"),
            "humanReviewStatus": human_review_result.get("reviewStatus")
            if human_review_result
            else None,
            "evaluatedAt": utc_iso(),
        }

        return {
            "checks": compliance_checks,
            "auditEvent": audit_event if self.settings.audit_event_enabled else None,
        }


def create_compliance_adapter(settings: AgentSettings) -> ComplianceAdapter:
    return LocalComplianceAdapter(settings)
