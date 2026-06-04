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

    def start_pipeline(self, intake_payload: Dict[str, Any]) -> Dict[str, Any]:
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

    def route_to_compliance(self, mapping_result: Dict[str, Any]) -> Dict[str, Any]:
        """Route mapped data to compliance check."""
        self.state["stage"] = "compliance"
        self.state["mappingResult"] = mapping_result

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
