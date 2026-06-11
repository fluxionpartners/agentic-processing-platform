"""Form 1040 Generation Agent."""

from datetime import datetime, timezone
import json
from typing import Any, Optional

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.form_generation.adapters import create_form_1040_generation_adapter
from foundry_agents.utils.azure_helpers import reconstruct_state_from_thread


class Form1040GenerationAgent:
    """Handles Form 1040 document artifact generation."""

    @staticmethod
    def process(
        thread_id: str,
        project_client: AIProjectClient,
        settings: Optional[AgentSettings] = None
    ) -> Any:
        """Generate a Form 1040 artifact from mapped tax facts."""
        settings = settings or load_agent_settings()
        state = reconstruct_state_from_thread(project_client, thread_id)
        
        adapter = create_form_1040_generation_adapter(settings)
        generation = adapter.generate(state)

        result = {
            "correlationId": state.get("correlationId"),
            "generationStatus": "success",
            "generationMode": settings.form_1040_generation_mode,
            "artifactMode": settings.form_1040_artifact_mode,
            "generator": adapter.name,
            "templateVersion": generation["templateVersion"],
            "documentType": generation["documentType"],
            "taxYear": generation["taxYear"],
            "fieldValues": generation["fieldValues"],
            "artifact": generation["artifact"],
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "nextStep": "compliance",
        }

        project_client.agents.create_message(
            thread_id=thread_id,
            role="assistant",
            content=json.dumps(result)
        )
        
        assistant_id = getattr(settings, "form_generation_assistant_id", "asst_form_generation")
        run = project_client.agents.create_run(thread_id=thread_id, assistant_id=assistant_id)
        return run


if __name__ == "__main__":
    print("Form 1040 Generation Agent loaded.")
