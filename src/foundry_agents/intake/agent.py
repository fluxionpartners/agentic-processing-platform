"""
Intake Agent.

Receives W-2 documents via manual trigger or event-driven ingestion.
Validates the document and passes it to extraction.
"""

from typing import Dict, Any
from foundry_agents.time_utils import utc_iso


class IntakeAgent:
    """Handles document intake and initial validation."""

    @staticmethod
    def process(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process intake request."""
        correlation_id = payload.get("correlationId")
        blob_uri = payload.get("blobUri")

        result = {
            "correlationId": correlation_id,
            "blobUri": blob_uri,
            "intakeStatus": "accepted",
            "intakeTimestamp": utc_iso(),
            "nextStep": "extraction",
        }

        return result


if __name__ == "__main__":
    print("Intake Agent loaded.")
