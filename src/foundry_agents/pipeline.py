from typing import Any, Dict, List, Optional

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.compliance.agent import ComplianceAgent
from foundry_agents.extraction.agent import ExtractionAgent
from foundry_agents.human_review.agent import HumanReviewAgent
from foundry_agents.intake.agent import IntakeAgent
from foundry_agents.persistence import (
    persist_tax_pipeline_checkpoint,
    persist_tax_pipeline_state,
)
from foundry_agents.supervisor.orchestrator import SupervisorOrchestrator
from foundry_agents.tax_mapping.agent import TaxMappingAgent
from foundry_agents.time_utils import utc_iso
from foundry_agents.validation.agent import ValidationAgent


class AgentPipeline:
    """Programmatic pipeline runner for manual tests and event-driven triggers."""

    def __init__(self, settings: Optional[AgentSettings] = None) -> None:
        self.settings = settings or load_agent_settings()
        self.orchestrator = SupervisorOrchestrator()
        self.execution_log: List[Dict[str, Any]] = []

    def record_step(self, stage: str, agent: str, result: Dict[str, Any]) -> None:
        self.execution_log.append(
            {
                "timestamp": utc_iso(),
                "stage": stage,
                "agent": agent,
                "result": result,
            }
        )

    def persist_checkpoint(self, stage: str) -> Dict[str, Any]:
        checkpoint_result = persist_tax_pipeline_checkpoint(
            self.orchestrator.state, self.settings, stage
        )
        self.orchestrator.record_persistence_checkpoint(checkpoint_result)
        self.record_step(f"{stage}_checkpoint", "TaxFactPersistence", checkpoint_result)
        return checkpoint_result

    def run(self, intake_trigger: Dict[str, Any]) -> Dict[str, Any]:
        from foundry_agents.persistence.store import create_tax_fact_store

        correlation_id = intake_trigger.get("correlationId")
        tenant_id = intake_trigger.get("tenantId")
        record_id = f"tax-facts-{correlation_id}" if correlation_id else None
        existing_record = None

        if record_id:
            store = create_tax_fact_store(self.settings)
            existing_record = store.load(record_id, partition_key=tenant_id)

        if existing_record:
            self.orchestrator.rehydrate_pipeline(existing_record)
            if "mockExtractionOverrides" in intake_trigger:
                self.orchestrator.state["mockExtractionOverrides"] = intake_trigger["mockExtractionOverrides"]
        else:
            self.orchestrator.start_pipeline(
                intake_trigger, runtime_settings=self.settings.as_runtime_metadata()
            )

        # 1. Intake Stage
        if "intakeResult" in self.orchestrator.state:
            intake_result = self.orchestrator.state["intakeResult"]
        else:
            intake_result = IntakeAgent.process(self.orchestrator.state, self.settings)
            self.record_step("intake", "IntakeAgent", intake_result)

        # 2. Extraction Stage
        extraction_route = self.orchestrator.route_to_extraction(intake_result)
        if "extractionResult" in self.orchestrator.state:
            extraction_result = self.orchestrator.state["extractionResult"]
        else:
            self.persist_checkpoint("intake")
            extraction_result = ExtractionAgent.process(extraction_route["payload"], self.settings)
            self.record_step("extraction", "ExtractionAgent", extraction_result)

        # 3. Validation Stage
        validation_route = self.orchestrator.route_to_validation(extraction_result)
        if "validationResult" in self.orchestrator.state:
            validation_result = self.orchestrator.state["validationResult"]
        else:
            self.persist_checkpoint("extraction")
            validation_result = ValidationAgent.process(validation_route["payload"], self.settings)
            self.record_step("validation", "ValidationAgent", validation_result)

        # 4. Human Review Gate (if needed)
        needs_review = validation_result.get("needsReview")
        if needs_review:
            review_route = self.orchestrator.route_to_human_review(validation_result)
            if "humanReviewResult" in self.orchestrator.state:
                review_result = self.orchestrator.state["humanReviewResult"]
            else:
                self.persist_checkpoint("validation")
                review_result = HumanReviewAgent.process(review_route["payload"], self.settings)
                self.record_step("human_review", "HumanReviewAgent", review_result)
                self.orchestrator.record_human_review(review_result)
                self.persist_checkpoint("human_review")
            
            if review_result.get("nextStep") != "tax_mapping":
                paused_result = self.orchestrator.await_human_review(review_result)
                self.persist_checkpoint("await_human_review")
                self.record_step("await_human_review", "Orchestrator", paused_result)
                return paused_result

        # 5. Tax Mapping Stage
        mapping_route = self.orchestrator.route_to_tax_mapping(validation_result)
        if "mappingResult" in self.orchestrator.state:
            mapping_result = self.orchestrator.state["mappingResult"]
        else:
            if not needs_review:
                self.persist_checkpoint("validation")
            mapping_result = TaxMappingAgent.process(mapping_route["payload"], self.settings)
            self.record_step("tax_mapping", "TaxMappingAgent", mapping_result)

        # 6. Compliance Stage
        compliance_route = self.orchestrator.route_to_compliance(mapping_result)
        if "finalResult" in self.orchestrator.state:
            compliance_result = self.orchestrator.state["finalResult"]
        else:
            self.persist_checkpoint("tax_mapping")
            compliance_result = ComplianceAgent.process(compliance_route["payload"], self.settings)
            self.record_step("compliance", "ComplianceAgent", compliance_result)

        # 7. Finalize
        if self.orchestrator.state.get("status") == "success" and self.orchestrator.state.get("stage") == "complete":
            final_result = {
                "pipelineId": self.orchestrator.pipeline_id,
                "correlationId": self.orchestrator.correlation_id,
                "status": "complete",
                "payload": self.orchestrator.state,
            }
        else:
            final_result = self.orchestrator.finalize_pipeline(compliance_result)
            self.persist_checkpoint("compliance")
            persistence_result = persist_tax_pipeline_state(final_result["payload"], self.settings)
            self.orchestrator.record_persistence(persistence_result)
            self.record_step("persistence", "TaxFactPersistence", persistence_result)
            self.record_step("finalize", "Orchestrator", final_result)

        return final_result


def process_w2_ingestion_event(
    event: Dict[str, Any],
    *,
    mock_extraction_overrides: Optional[Dict[str, Any]] = None,
    settings: Optional[AgentSettings] = None,
) -> Dict[str, Any]:
    """Process a W-2 ingestion event emitted by the intake service."""
    intake_trigger = dict(event)
    if mock_extraction_overrides:
        intake_trigger["mockExtractionOverrides"] = mock_extraction_overrides
    return AgentPipeline(settings=settings).run(intake_trigger)
