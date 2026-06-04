from abc import ABC, abstractmethod
from typing import Any, Dict

from foundry_agents.config import (
    AgentSettings,
    EXTRACTION_MODE_DOCUMENT_INTELLIGENCE,
    EXTRACTION_MODE_LOCAL,
)
from foundry_agents.domain import default_field_confidence, default_w2_record, deep_merge


class W2ExtractionAdapter(ABC):
    """Adapter contract for turning a source document into normalized W-2 data."""

    name: str

    @abstractmethod
    def extract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return extractedData and fieldConfidence for the given pipeline payload."""


class LocalW2ExtractionAdapter(W2ExtractionAdapter):
    """Deterministic local extraction adapter for tests and offline development."""

    name = "local-deterministic-w2-v1"

    def extract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        extracted_data = default_w2_record(payload.get("taxYear"))
        extracted_data = deep_merge(extracted_data, payload.get("mockExtractionOverrides", {}))

        field_confidence = default_field_confidence(extracted_data)
        field_confidence.update(payload.get("mockConfidenceOverrides", {}))

        return {
            "extractedData": extracted_data,
            "fieldConfidence": field_confidence,
            "rawResult": None,
        }


class DocumentIntelligenceW2ExtractionAdapter(W2ExtractionAdapter):
    """Azure AI Document Intelligence extraction adapter placeholder."""

    name = "azure-document-intelligence-w2"

    def __init__(self, settings: AgentSettings):
        self.settings = settings

    def extract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.settings.document_intelligence_endpoint:
            raise RuntimeError(
                "W2_EXTRACTION_MODE=document-intelligence requires "
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT. The real extraction adapter "
                "is intentionally explicit so sample data is never used by accident."
            )
        raise NotImplementedError(
            "Azure AI Document Intelligence extraction mapping is not implemented yet. "
            "Next step: call the Document Intelligence analyze API for the blobUri and "
            "map its fields into extractedData and fieldConfidence."
        )


def create_extraction_adapter(settings: AgentSettings) -> W2ExtractionAdapter:
    if settings.extraction_mode == EXTRACTION_MODE_LOCAL:
        return LocalW2ExtractionAdapter()
    if settings.extraction_mode == EXTRACTION_MODE_DOCUMENT_INTELLIGENCE:
        return DocumentIntelligenceW2ExtractionAdapter(settings)
    raise ValueError(f"Unsupported extraction mode: {settings.extraction_mode}")
