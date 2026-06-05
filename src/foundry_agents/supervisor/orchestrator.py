"""
Supervisor Agent Orchestrator.

Coordinates the entire tax processing pipeline:
- Receives intake triggers (manual or event-driven)
- Routes to intake agent
- Coordinates extraction, validation, and mapping
- Manages human review and compliance gates
"""

from typing import Any, Dict
from uuid import uuid4

from foundry_agents.time_utils import utc_iso


class SupervisorOrchestrator:
    """Orchestrates the tax pipeline workflow."""

    def __init__(self):
        self.pipeline_id = None
        self.correlation_id = None
        self.state = {}

    def start_pipeline(
        self, intake_payload: Dict[str, Any], runtime_settings: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Initialize pipeline from intake trigger."""
        self.correlation_id = intake_payload.get("correlationId") or str(uuid4())
        self.pipeline_id = f"pipeline-{self.correlation_id}"

        self.state = {
            "pipelineId": self.pipeline_id,
            "correlationId": self.correlation_id,
            "tenantId": intake_payload.get("tenantId"),
            "taxpayerId": intake_payload.get("taxpayerId"),
            "documentName": intake_payload.get("documentName"),
            "blobUri": intake_payload.get("blobUri"),
            "taxYear": intake_payload.get("taxYear"),
            "stage": "intake",
            "status": "in_progress",
            "runtimeSettings": runtime_settings or {},
            "timestamp": utc_iso(),
        }
        if "mockExtractionOverrides" in intake_payload:
            self.state["mockExtractionOverrides"] = intake_payload["mockExtractionOverrides"]

        return {
            "pipelineId": self.pipeline_id,
            "correlationId": self.correlation_id,
            "nextAgent": "intake",
            "payload": self.state,
        }

    def route_to_extraction(self, intake_result: Dict[str, Any]) -> Dict[str, Any]:
        """Route successfully ingested document to extraction."""
        self.state["stage"] = "extraction"
        self.state["intakeResult"] = intake_result

        return {
            "pipelineId": self.pipeline_id,
            "correlationId": self.correlation_id,
            "nextAgent": "extraction",
            "payload": self.state,
        }

    def route_to_validation(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """Route extracted data to validation."""
        self.state["stage"] = "validation"
        self.state["extractionResult"] = extraction_result

        return {
            "pipelineId": self.pipeline_id,
            "correlationId": self.correlation_id,
            "nextAgent": "validation",
            "payload": self.state,
        }

    def route_to_tax_mapping(self, validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """Route validated data to tax mapping."""
        self.state["stage"] = "tax_mapping"
        self.state["validationResult"] = validation_result

        return {
            "pipelineId": self.pipeline_id,
            "correlationId": self.correlation_id,
            "nextAgent": "tax_mapping",
            "payload": self.state,
        }

    def route_to_form_generation(self, mapping_result: Dict[str, Any]) -> Dict[str, Any]:
        """Route mapped data to Form 1040 generation."""
        self.state["stage"] = "form_generation"
        self.state["mappingResult"] = mapping_result

        return {
            "pipelineId": self.pipeline_id,
            "correlationId": self.correlation_id,
            "nextAgent": "form_generation",
            "payload": self.state,
        }

    def route_to_compliance(self, form_generation_result: Dict[str, Any]) -> Dict[str, Any]:
        """Route generated tax artifacts to compliance check."""
        self.state["stage"] = "compliance"
        self.state["formGenerationResult"] = form_generation_result

        return {
            "pipelineId": self.pipeline_id,
            "correlationId": self.correlation_id,
            "nextAgent": "compliance",
            "payload": self.state,
        }

    def route_to_human_review(self, review_source: Dict[str, Any]) -> Dict[str, Any]:
        """Route to human review if flagged."""
        self.state["stage"] = "human_review"
        self.state["humanReviewSource"] = review_source
        if "validationStatus" in review_source:
            self.state["validationResult"] = review_source

        return {
            "pipelineId": self.pipeline_id,
            "correlationId": self.correlation_id,
            "nextAgent": "human_review",
            "payload": self.state,
        }

    def record_human_review(self, review_result: Dict[str, Any]) -> None:
        """Record human review status before continuing the automated pipeline."""
        self.state["humanReviewResult"] = review_result

    def finalize_pipeline(self, final_result: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize the pipeline and record completion."""
        self.state["stage"] = "complete"
        self.state["status"] = "success"
        self.state["finalResult"] = final_result
        self.state["completedAt"] = utc_iso()

        return {
            "pipelineId": self.pipeline_id,
            "correlationId": self.correlation_id,
            "status": "complete",
            "payload": self.state,
        }

    def record_persistence(self, persistence_result: Dict[str, Any]) -> None:
        """Record durable persistence metadata for the completed pipeline."""
        self.state["persistenceResult"] = persistence_result

    def record_persistence_checkpoint(self, checkpoint_result: Dict[str, Any]) -> None:
        """Record durable checkpoint metadata for resume and audit visibility."""
        self.state.setdefault("persistenceCheckpoints", []).append(checkpoint_result)

    def rehydrate_pipeline(self, checkpoint_record: Dict[str, Any]) -> None:
        """Rehydrate pipeline state from a saved checkpoint."""
        self.correlation_id = checkpoint_record.get("correlationId")
        self.pipeline_id = checkpoint_record.get("pipelineId")
        self.state = {
            "pipelineId": self.pipeline_id,
            "correlationId": self.correlation_id,
            "tenantId": checkpoint_record.get("tenantId"),
            "taxpayerId": checkpoint_record.get("taxpayerId"),
            "documentName": checkpoint_record.get("document", {}).get("documentName"),
            "blobUri": checkpoint_record.get("document", {}).get("blobUri"),
            "taxYear": checkpoint_record.get("taxYear"),
            "stage": checkpoint_record.get("checkpointStage"),
            "status": checkpoint_record.get("lifecycleStatus"),
            "createdAt": checkpoint_record.get("createdAt"),
            "updatedAt": checkpoint_record.get("updatedAt"),
            "runtimeSettings": checkpoint_record.get("governance", {}),
        }

        if "persistenceCheckpoints" in checkpoint_record:
            self.state["persistenceCheckpoints"] = checkpoint_record["persistenceCheckpoints"]

        if checkpoint_record.get("document") and checkpoint_record["document"].get("sourceStatus"):
            self.state["intakeResult"] = {
                "correlationId": self.correlation_id,
                "blobUri": checkpoint_record["document"].get("blobUri"),
                "intakeStatus": checkpoint_record["document"].get("sourceStatus"),
                "intakeTimestamp": checkpoint_record.get("createdAt"),
                "nextStep": "extraction",
            }

        if "extraction" in checkpoint_record and checkpoint_record["extraction"].get("status"):
            self.state["extractionResult"] = {
                "extractionStatus": checkpoint_record["extraction"]["status"],
                "source": checkpoint_record["extraction"].get("source"),
                "extractedData": checkpoint_record["extraction"].get("extractedData"),
                "fieldConfidence": checkpoint_record["extraction"].get("fieldConfidence"),
                "overallConfidence": checkpoint_record["extraction"].get("overallConfidence"),
                "extractionTimestamp": checkpoint_record["extraction"].get("extractionTimestamp"),
            }
        if "validation" in checkpoint_record and checkpoint_record["validation"].get("status"):
            self.state["validationResult"] = {
                "validationStatus": checkpoint_record["validation"]["status"],
                "needsReview": checkpoint_record["validation"].get("needsReview"),
                "reviewReason": checkpoint_record["validation"].get("reviewReason"),
                "issues": checkpoint_record["validation"].get("issues"),
                "warnings": checkpoint_record["validation"].get("warnings"),
            }
        if "humanReview" in checkpoint_record and checkpoint_record["humanReview"].get("status") is not None:
            status = checkpoint_record["humanReview"]["status"]
            next_step = "tax_mapping" if status in {"approved", "completed"} else "awaiting_human_decision"
            self.state["humanReviewResult"] = {
                "reviewStatus": status,
                "reviewReason": checkpoint_record["humanReview"].get("reason"),
                "assignedQueue": checkpoint_record["humanReview"].get("assignedQueue"),
                "submittedForReview": checkpoint_record["humanReview"].get("submittedForReview"),
                "nextStep": next_step,
            }
        if "taxPlanning" in checkpoint_record and checkpoint_record["taxPlanning"].get("mappingStatus"):
            self.state["mappingResult"] = {
                "mappingStatus": checkpoint_record["taxPlanning"]["mappingStatus"],
                "mappingProfile": checkpoint_record["taxPlanning"].get("mappingProfile"),
                "normalizedTaxFacts": checkpoint_record["taxPlanning"].get("normalizedTaxFacts"),
                "form1040": checkpoint_record["taxPlanning"].get("form1040"),
            }
        if "form1040Document" in checkpoint_record and checkpoint_record["form1040Document"].get("status"):
            self.state["formGenerationResult"] = {
                "generationStatus": checkpoint_record["form1040Document"]["status"],
                "generationMode": checkpoint_record["form1040Document"].get("generationMode"),
                "artifactMode": checkpoint_record["form1040Document"].get("artifactMode"),
                "templateVersion": checkpoint_record["form1040Document"].get("templateVersion"),
                "documentType": checkpoint_record["form1040Document"].get("documentType"),
                "taxYear": checkpoint_record["form1040Document"].get("taxYear"),
                "fieldValues": checkpoint_record["form1040Document"].get("fieldValues", {}),
                "artifact": checkpoint_record["form1040Document"].get("artifact", {}),
                "generatedAt": checkpoint_record["form1040Document"].get("generatedAt"),
                "nextStep": "compliance",
            }
        if "compliance" in checkpoint_record and checkpoint_record["compliance"].get("status"):
            self.state["finalResult"] = {
                "complianceStatus": checkpoint_record["compliance"]["status"],
                "complianceMode": checkpoint_record["compliance"].get("mode"),
                "checks": checkpoint_record["compliance"].get("checks"),
                "auditEvent": checkpoint_record["compliance"].get("auditEvent"),
            }

    def await_human_review(self, review_result: Dict[str, Any]) -> Dict[str, Any]:
        """Pause the pipeline until a human decision is recorded."""
        self.state["stage"] = "awaiting_human_review"
        self.state["status"] = "waiting"
        self.state["humanReviewResult"] = review_result
        self.state["pausedAt"] = utc_iso()

        return {
            "pipelineId": self.pipeline_id,
            "correlationId": self.correlation_id,
            "status": "waiting",
            "nextStep": "awaiting_human_decision",
            "payload": self.state,
        }

    def handle_error(self, error_message: str, stage: str) -> Dict[str, Any]:
        """Handle pipeline errors and route to exception handling."""
        self.state["stage"] = stage
        self.state["status"] = "error"
        self.state["error"] = error_message
        self.state["failedAt"] = utc_iso()

        return {
            "pipelineId": self.pipeline_id,
            "correlationId": self.correlation_id,
            "status": "error",
            "payload": self.state,
        }


if __name__ == "__main__":
    print("Supervisor Orchestrator loaded. Use ManualTestHarness to trigger pipelines.")
