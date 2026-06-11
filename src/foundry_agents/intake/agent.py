"""Intake Agent."""

import json
from typing import Any, Optional

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.intake.adapters import create_intake_adapter
from foundry_agents.utils.azure_helpers import reconstruct_state_from_thread


class IntakeAgent:
    """Handles document intake and initial validation."""

    @staticmethod
    def process(
        thread_id: str,
        project_client: AIProjectClient,
        settings: Optional[AgentSettings] = None
    ) -> Any:
        """Process intake request."""
        settings = settings or load_agent_settings()
        state = reconstruct_state_from_thread(project_client, thread_id)
        
        adapter = create_intake_adapter(settings)
        result = adapter.accept(state)
        
        project_client.agents.create_message(
            thread_id=thread_id,
            role="assistant",
            content=json.dumps(result)
        )
        
        assistant_id = getattr(settings, "intake_assistant_id", "asst_intake")
        run = project_client.agents.create_run(thread_id=thread_id, assistant_id=assistant_id)
        return run


if __name__ == "__main__":
    print("Intake Agent loaded.")
