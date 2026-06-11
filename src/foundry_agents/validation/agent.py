"""Validation Agent."""

from datetime import datetime, timezone
import json
from typing import Any, Optional

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.validation.adapters import create_validation_adapter
from foundry_agents.utils.azure_helpers import reconstruct_state_from_thread


class ValidationAgent:
    """Handles data validation and rule application."""

    @staticmethod
    def process(
        thread_id: str,
        project_client: AIProjectClient,
        settings: Optional[AgentSettings] = None
    ) -> Any:
        """Validate extracted data."""
        settings = settings or load_agent_settings()
        state = reconstruct_state_from_thread(project_client, thread_id)
        
        adapter = create_validation_adapter(settings)
        validation = adapter.validate(state)
        issues = validation["issues"]
        warnings = validation["warnings"]
        low_confidence = validation["lowConfidenceFields"]

        validation_status = "passed" if not issues else "failed"
        needs_review = bool(issues or low_confidence)

        result = {
            "correlationId": state.get("correlationId"),
            "validationStatus": validation_status,
            "issues": issues,
            "warnings": warnings,
            "needsReview": needs_review,
            "strictness": settings.validation_strictness,
            "validator": adapter.name,
            "lowConfidenceThreshold": settings.low_confidence_threshold,
            "reviewReason": "blocking_validation_issues"
            if issues
            else "low_confidence_extraction"
            if low_confidence
            else None,
            "validationTimestamp": datetime.now(timezone.utc).isoformat(),
            "nextStep": "human_review" if needs_review else "tax_mapping",
        }

        project_client.agents.create_message(
            thread_id=thread_id,
            role="assistant",
            content=json.dumps(result)
        )
        
        assistant_id = getattr(settings, "validation_assistant_id", "asst_validation")
        run = project_client.agents.create_run(thread_id=thread_id, assistant_id=assistant_id)
        return run


if __name__ == "__main__":
    print("Validation Agent loaded.")
