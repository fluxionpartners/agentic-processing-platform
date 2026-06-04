"""
Extraction Agent.

Parses W-2 documents and extracts structured tax data.
Integrates with Azure AI Document Intelligence (mocked for now).
"""

from typing import Dict, Any
from foundry_agents.time_utils import utc_iso


class ExtractionAgent:
    """Handles document extraction and parsing."""

    @staticmethod
    def process(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Mock extraction using Document Intelligence."""
        correlation_id = payload.get("correlationId")
        blob_uri = payload.get("blobUri")

        # Mock extracted fields
        extracted_data = {
            "taxYear": 2024,
            "employerEIN": "12-3456789",
            "employerName": "Sample Corporation",
            "employeeSSN": "XXX-XX-1234",
            "boxes": {
                "Box1": 75000.00,
                "Box2": 8500.00,
                "Box3": 60000.00,
                "Box4": 3700.00,
            },
        }
        extracted_data.update(payload.get("mockExtractionOverrides", {}))

        result = {
            "correlationId": correlation_id,
            "blobUri": blob_uri,
            "extractionStatus": "success",
            "extractedData": extracted_data,
            "extractionTimestamp": utc_iso(),
            "nextStep": "validation",
        }

        return result


if __name__ == "__main__":
    print("Extraction Agent loaded.")
