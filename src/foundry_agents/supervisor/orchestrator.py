"""Supervisor Agent Orchestrator.

Coordinates the entire tax processing pipeline using azure-ai-projects:
- Instantiates a cloud-managed thread
- Chains the agent tools sequentially on the thread
- Polls execution runs to verify success at each stage
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.compliance.agent import ComplianceAgent
from foundry_agents.extraction.agent import ExtractionAgent
from foundry_agents.form_generation.agent import Form1040GenerationAgent
from foundry_agents.human_review.agent import HumanReviewAgent
from foundry_agents.intake.agent import IntakeAgent
from foundry_agents.tax_mapping.agent import TaxMappingAgent
from foundry_agents.validation.agent import ValidationAgent
from foundry_agents.utils.azure_helpers import get_project_client, reconstruct_state_from_thread


class SupervisorOrchestrator:
    """Orchestrates the tax pipeline workflow using Azure AI Projects."""

    def __init__(self, project_client: Optional[AIProjectClient] = None, settings: Optional[AgentSettings] = None):
        self.settings = settings or load_agent_settings()
        self.project_client = project_client or get_project_client(self.settings)
        self.execution_log: List[Dict[str, Any]] = []

    def record_step(self, stage: str, agent: str, result: Dict[str, Any]) -> None:
        self.execution_log.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": stage,
                "agent": agent,
                "result": result,
            }
        )

    def run(self, intake_payload: Dict[str, Any], thread_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute the full agent pipeline sequentially on a thread."""
        # Unify via native threads: refactor to instantiate cloud-managed thread if not provided
        if not thread_id:
            thread = self.project_client.agents.create_thread()
            thread_id = thread.id
            # Add initial payload to thread
            payload_to_save = dict(intake_payload)
            payload_to_save.setdefault("runtimeSettings", self.settings.as_runtime_metadata())
            self.project_client.agents.create_message(
                thread_id=thread_id,
                role="user",
                content=json.dumps(payload_to_save)
            )

        state = reconstruct_state_from_thread(self.project_client, thread_id)

        # 1. Intake Stage
        if "intakeResult" not in state:
            run = IntakeAgent.process(thread_id, self.project_client, self.settings)
            run = self._poll_run(thread_id, run.id)
            state = reconstruct_state_from_thread(self.project_client, thread_id)
            self.record_step("intake", "IntakeAgent", state.get("intakeResult", {}))

        # 2. Extraction Stage
        if "extractionResult" not in state:
            run = ExtractionAgent.process(thread_id, self.project_client, self.settings)
            run = self._poll_run(thread_id, run.id)
            state = reconstruct_state_from_thread(self.project_client, thread_id)
            self.record_step("extraction", "ExtractionAgent", state.get("extractionResult", {}))

        # 3. Validation Stage
        if "validationResult" not in state:
            run = ValidationAgent.process(thread_id, self.project_client, self.settings)
            run = self._poll_run(thread_id, run.id)
            state = reconstruct_state_from_thread(self.project_client, thread_id)
            self.record_step("validation", "ValidationAgent", state.get("validationResult", {}))
        validation_result = state.get("validationResult", {})

        # 4. Human Review Gate (if flagged)
        needs_review = validation_result.get("needsReview", False)
        if needs_review:
            if "humanReviewResult" not in state:
                # Human review uses custom logic / external gate
                review_result = HumanReviewAgent.process(state, self.settings)
                self.record_step("human_review", "HumanReviewAgent", review_result)

                # Store the human review result back onto the thread
                self.project_client.agents.create_message(
                    thread_id=thread_id,
                    role="assistant",
                    content=json.dumps({"humanReviewResult": review_result})
                )
                state = reconstruct_state_from_thread(self.project_client, thread_id)
            else:
                self.record_step("human_review", "HumanReviewAgent", state["humanReviewResult"])

            review_result = state["humanReviewResult"]
            if review_result.get("nextStep") != "tax_mapping":
                # Persist pipeline checkpoint on pause
                from foundry_agents.persistence import persist_tax_pipeline_checkpoint
                state["threadId"] = thread_id
                state["checkpointStage"] = "await_human_review"
                state["lifecycleStatus"] = "waiting"
                state["document"] = {"documentName": state.get("documentName"), "blobUri": state.get("blobUri")}
                persist_tax_pipeline_checkpoint(state, self.settings, "await_human_review")
                
                state["status"] = "waiting"
                state["stage"] = "awaiting_human_review"

                return {
                    "pipelineId": f"pipeline-{state.get('correlationId')}",
                    "correlationId": state.get("correlationId"),
                    "status": "waiting",
                    "nextStep": "awaiting_human_decision",
                    "thread_id": thread_id,
                    "payload": state,
                }

        # 5. Tax Mapping Stage
        if "mappingResult" not in state:
            run = TaxMappingAgent.process(thread_id, self.project_client, self.settings)
            run = self._poll_run(thread_id, run.id)
            state = reconstruct_state_from_thread(self.project_client, thread_id)
        self.record_step("tax_mapping", "TaxMappingAgent", state.get("mappingResult", {}))

        # 6. Form 1040 Generation Stage
        if "formGenerationResult" not in state:
            run = Form1040GenerationAgent.process(thread_id, self.project_client, self.settings)
            run = self._poll_run(thread_id, run.id)
            state = reconstruct_state_from_thread(self.project_client, thread_id)
        self.record_step("form_generation", "Form1040GenerationAgent", state.get("formGenerationResult", {}))

        # 7. Compliance Stage
        if "complianceResult" not in state:
            run = ComplianceAgent.process(thread_id, self.project_client, self.settings)
            run = self._poll_run(thread_id, run.id)
            state = reconstruct_state_from_thread(self.project_client, thread_id)
        compliance_result = state.get("complianceResult", {})
        self.record_step("compliance", "ComplianceAgent", compliance_result)

        # 8. Finalize
        state["status"] = "success"
        state["stage"] = "complete"
        state["threadId"] = thread_id

        # Persist tax facts before adding execution_log to state
        # (execution_log contains result refs that would cause circular json.dumps)
        from foundry_agents.persistence import persist_tax_pipeline_state
        try:
            persistence_result = persist_tax_pipeline_state(state, self.settings)
            state["persistenceResult"] = persistence_result
            self.record_step("persistence", "TaxFactPersistence", persistence_result)
        except Exception:
            pass

        # Add execution_log to state AFTER persistence to avoid circular refs
        state["execution_log"] = self.execution_log

        final_result = {
            "pipelineId": f"pipeline-{state.get('correlationId')}",
            "correlationId": state.get("correlationId"),
            "status": "complete",
            "thread_id": thread_id,
            "payload": state,
        }

        # Record a finalize summary (not the full final_result, to avoid circular ref)
        self.record_step("finalize", "Orchestrator", {
            "pipelineId": final_result["pipelineId"],
            "status": "complete",
            "correlationId": final_result["correlationId"],
        })
        return final_result

    def _poll_run(self, thread_id: str, run_id: str) -> Any:
        """Poll the run status sequentially until completion."""
        while True:
            run = self.project_client.agents.get_run(thread_id=thread_id, run_id=run_id)
            if run.status not in ["queued", "in_progress"]:
                break
            time.sleep(0.001)
        if run.status != "completed":
            raise RuntimeError(f"Run {run_id} failed with status {run.status}")
        return run


if __name__ == "__main__":
    print("Supervisor Orchestrator loaded.")
