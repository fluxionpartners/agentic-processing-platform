"""Extraction Agent."""

from datetime import datetime, timezone
import json
from typing import Any, Optional

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.extraction.adapters import create_extraction_adapter
from foundry_agents.utils.azure_helpers import reconstruct_state_from_thread


class ExtractionAgent:
    """Handles document extraction and parsing."""

    @staticmethod
    def process(
        thread_id: str,
        project_client: AIProjectClient,
        settings: Optional[AgentSettings] = None
    ) -> Any:
        """Extract normalized W-2 data using the configured extraction adapter."""
        settings = settings or load_agent_settings()
        state = reconstruct_state_from_thread(project_client, thread_id)

        adapter = create_extraction_adapter(settings)
        extraction = adapter.extract(state)
        field_confidence = extraction["fieldConfidence"]

        result = {
            "correlationId": state.get("correlationId"),
            "blobUri": state.get("blobUri"),
            "extractionStatus": "success",
            "source": {
                "documentName": state.get("documentName"),
                "blobUri": state.get("blobUri"),
                "extractor": adapter.name,
                "mode": settings.extraction_mode,
                "modelId": settings.document_intelligence_model_id
                if settings.extraction_mode == "document-intelligence"
                else None,
            },
            "extractedData": extraction["extractedData"],
            "fieldConfidence": field_confidence,
            "overallConfidence": round(
                sum(field_confidence.values()) / len(field_confidence), 4
            )
            if field_confidence
            else 0,
            "rawResult": extraction.get("rawResult"),
            "extractionTimestamp": datetime.now(timezone.utc).isoformat(),
            "nextStep": "validation",
        }

        project_client.agents.create_message(
            thread_id=thread_id,
            role="assistant",
            content=json.dumps(result)
        )
        
        assistant_id = getattr(settings, "extraction_assistant_id", "asst_extraction")
        run = project_client.agents.create_run(thread_id=thread_id, assistant_id=assistant_id)
        return run


if __name__ == "__main__":
    print("Extraction Agent loaded.")
