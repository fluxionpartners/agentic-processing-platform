"""Tax Mapping Agent."""

from datetime import datetime, timezone
import json
from typing import Any, Optional

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.tax_mapping.adapters import create_tax_mapping_adapter
from foundry_agents.utils.azure_helpers import reconstruct_state_from_thread


class TaxMappingAgent:
    """Handles tax payload generation and mapping."""

    @staticmethod
    def process(
        thread_id: str,
        project_client: AIProjectClient,
        settings: Optional[AgentSettings] = None
    ) -> Any:
        """Map extracted data to 1040 format."""
        settings = settings or load_agent_settings()
        state = reconstruct_state_from_thread(project_client, thread_id)
        
        adapter = create_tax_mapping_adapter(settings)
        mapping = adapter.map(state)

        result = {
            "correlationId": state.get("correlationId"),
            "mappingStatus": "success",
            "mappingProfile": settings.tax_mapping_profile,
            "mapper": adapter.name,
            "form1040": mapping["form1040"],
            "normalizedTaxFacts": mapping["normalizedTaxFacts"],
            "mappingTimestamp": datetime.now(timezone.utc).isoformat(),
            "nextStep": "compliance",
        }

        project_client.agents.create_message(
            thread_id=thread_id,
            role="assistant",
            content=json.dumps(result)
        )
        
        assistant_id = getattr(settings, "tax_mapping_assistant_id", "asst_tax_mapping")
        run = project_client.agents.create_run(thread_id=thread_id, assistant_id=assistant_id)
        return run


if __name__ == "__main__":
    print("Tax Mapping Agent loaded.")
