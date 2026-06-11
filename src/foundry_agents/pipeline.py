from typing import Any, Dict, List, Optional

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.supervisor.orchestrator import SupervisorOrchestrator


class AgentPipeline:
    """Programmatic pipeline runner that delegates to SupervisorOrchestrator."""

    def __init__(self, settings: Optional[AgentSettings] = None) -> None:
        self.settings = settings or load_agent_settings()
        self.orchestrator = SupervisorOrchestrator(settings=self.settings)

    @property
    def execution_log(self) -> List[Dict[str, Any]]:
        return self.orchestrator.execution_log

    def run(self, intake_trigger: Dict[str, Any]) -> Dict[str, Any]:
        """Run the pipeline using the supervisor orchestrator.

        On resumption (same correlationId), recovers the thread_id from the
        persisted checkpoint and injects any human review decisions that were
        recorded while the pipeline was paused.
        """
        from foundry_agents.persistence.store import create_tax_fact_store
        import json

        correlation_id = intake_trigger.get("correlationId")
        tenant_id = intake_trigger.get("tenantId")
        record_id = f"tax-facts-{correlation_id}" if correlation_id else None

        thread_id = intake_trigger.get("thread_id") or intake_trigger.get("threadId")

        # Attempt to load existing checkpoint for resumption
        existing_record = None
        if not thread_id and record_id:
            try:
                store = create_tax_fact_store(self.settings)
                existing_record = store.load(record_id, partition_key=tenant_id)
                if existing_record:
                    thread_id = existing_record.get("threadId")
            except Exception:
                pass

        # If resuming with a checkpoint that has human review approval,
        # inject the review decision onto the thread so the orchestrator sees it.
        if thread_id and existing_record:
            human_review = existing_record.get("humanReview") or {}
            if human_review.get("status") == "approved":
                review_msg = {
                    "humanReviewResult": {
                        "reviewStatus": "pending",
                        "reviewReason": human_review.get("reason", ""),
                        "submittedForReview": human_review.get("submittedForReview", ""),
                        "assignedQueue": human_review.get("assignedQueue", ""),
                        "nextStep": "tax_mapping",
                        "mockDecision": "approved",
                        "decisionMode": "resumed_from_checkpoint",
                    }
                }
                # Write the approval message onto the thread if not already present
                project_client = self.orchestrator.project_client
                try:
                    msgs = project_client.agents.list_messages(thread_id=thread_id)
                    has_review = False
                    for msg in getattr(msgs, "data", []):
                        content_text = ""
                        if isinstance(msg.content, list):
                            content_text = msg.content[0].text.value if hasattr(msg.content[0], "text") else ""
                        else:
                            content_text = msg.content
                        try:
                            parsed = json.loads(content_text)
                            if "humanReviewResult" in parsed:
                                if parsed["humanReviewResult"].get("nextStep") == "tax_mapping":
                                    has_review = True
                                    break
                        except Exception:
                            pass
                    if not has_review:
                        project_client.agents.create_message(
                            thread_id=thread_id,
                            role="assistant",
                            content=json.dumps(review_msg),
                        )
                except Exception:
                    pass

        return self.orchestrator.run(intake_payload=intake_trigger, thread_id=thread_id)


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
