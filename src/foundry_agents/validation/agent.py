"""
Validation Agent.

Applies business rules and compliance checks to extracted data.
Flags anomalies and routes invalid records appropriately.
"""

from typing import Dict, Any, Optional

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.time_utils import utc_iso
from foundry_agents.validation.adapters import create_validation_adapter


class ValidationAgent:
    """Handles data validation and rule application."""

    @staticmethod
    def process(payload: Dict[str, Any], settings: Optional[AgentSettings] = None) -> Dict[str, Any]:
        """Validate extracted data."""
        settings = settings or load_agent_settings()
        correlation_id = payload.get("correlationId")
        adapter = create_validation_adapter(settings)
        validation = adapter.validate(payload)
        issues = validation["issues"]
        warnings = validation["warnings"]
        low_confidence = validation["lowConfidenceFields"]

        validation_status = "passed" if not issues else "failed"
        needs_review = bool(issues or low_confidence)

        result = {
            "correlationId": correlation_id,
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
            "validationTimestamp": utc_iso(),
            "nextStep": "human_review" if needs_review else "tax_mapping",
        }

        return result


if __name__ == "__main__":
    print("Validation Agent loaded.")
