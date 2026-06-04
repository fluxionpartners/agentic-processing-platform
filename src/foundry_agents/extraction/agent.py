"""Extraction Agent."""

from typing import Dict, Any, Optional

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.extraction.adapters import create_extraction_adapter
from foundry_agents.time_utils import utc_iso


class ExtractionAgent:
    """Handles document extraction and parsing."""

    @staticmethod
    def process(payload: Dict[str, Any], settings: Optional[AgentSettings] = None) -> Dict[str, Any]:
        """Extract normalized W-2 data using the configured extraction adapter."""
        correlation_id = payload.get("correlationId")
        blob_uri = payload.get("blobUri")

        settings = settings or load_agent_settings()
        adapter = create_extraction_adapter(settings)
        extraction = adapter.extract(payload)
        field_confidence = extraction["fieldConfidence"]

        result = {
            "correlationId": correlation_id,
            "blobUri": blob_uri,
            "extractionStatus": "success",
            "source": {
                "documentName": payload.get("documentName"),
                "blobUri": blob_uri,
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
            "extractionTimestamp": utc_iso(),
            "nextStep": "validation",
        }

        return result


if __name__ == "__main__":
    print("Extraction Agent loaded.")
