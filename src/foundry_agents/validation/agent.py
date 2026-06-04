"""
Validation Agent.

Applies business rules and compliance checks to extracted data.
Flags anomalies and routes invalid records appropriately.
"""

from typing import Dict, Any
from foundry_agents.time_utils import utc_iso


class ValidationAgent:
    """Handles data validation and rule application."""

    @staticmethod
    def process(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate extracted data."""
        correlation_id = payload.get("correlationId")
        extracted_data = payload.get("extractionResult", {}).get("extractedData", {})

        # Mock validation rules
        issues = []
        if not extracted_data.get("employerEIN"):
            issues.append("Missing employer EIN")
        if not extracted_data.get("employeeSSN"):
            issues.append("Missing employee SSN")

        validation_status = "passed" if not issues else "failed"
        needs_review = len(issues) > 0

        result = {
            "correlationId": correlation_id,
            "validationStatus": validation_status,
            "issues": issues,
            "needsReview": needs_review,
            "validationTimestamp": utc_iso(),
            "nextStep": "compliance" if not needs_review else "human_review",
        }

        return result


if __name__ == "__main__":
    print("Validation Agent loaded.")
