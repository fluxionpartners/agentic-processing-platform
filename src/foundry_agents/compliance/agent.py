"""Compliance Agent."""

from datetime import datetime, timezone
import json
from typing import Any, Optional

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.compliance.adapters import create_compliance_adapter
from foundry_agents.utils.azure_helpers import reconstruct_state_from_thread


class ComplianceAgent:
    """Handles compliance and governance checks."""

    @staticmethod
    def process(
        thread_id: str,
        project_client: AIProjectClient,
        settings: Optional[AgentSettings] = None
    ) -> Any:
        """Apply compliance checks."""
        settings = settings or load_agent_settings()
        state = reconstruct_state_from_thread(project_client, thread_id)
        
        adapter = create_compliance_adapter(settings)
        evaluation = adapter.evaluate(state)
        compliance_checks = evaluation["checks"]
        all_passed = all(compliance_checks.values())

        result = {
            "correlationId": state.get("correlationId"),
            "complianceStatus": "passed" if all_passed else "flagged",
            "complianceMode": settings.compliance_mode,
            "complianceAdapter": adapter.name,
            "checks": compliance_checks,
            "auditEvent": evaluation["auditEvent"],
            "complianceTimestamp": datetime.now(timezone.utc).isoformat(),
            "nextStep": "complete",
        }

        project_client.agents.create_message(
            thread_id=thread_id,
            role="assistant",
            content=json.dumps(result)
        )
        
        assistant_id = getattr(settings, "compliance_assistant_id", "asst_compliance")
        run = project_client.agents.create_run(thread_id=thread_id, assistant_id=assistant_id)
        return run


if __name__ == "__main__":
    print("Compliance Agent loaded.")
