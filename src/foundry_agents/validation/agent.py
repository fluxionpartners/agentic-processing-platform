"""
Validation Agent.

Applies business rules and compliance checks to extracted data.
Flags anomalies and routes invalid records appropriately.
"""

import re
from typing import Dict, Any, List, Optional

from foundry_agents.config import (
    AgentSettings,
    VALIDATION_STRICTNESS_STRICT,
    load_agent_settings,
)
from foundry_agents.domain import (
    REQUIRED_W2_FIELDS,
    is_number,
    low_confidence_fields,
)
from foundry_agents.time_utils import utc_iso


class ValidationAgent:
    """Handles data validation and rule application."""

    @staticmethod
    def process(payload: Dict[str, Any], settings: Optional[AgentSettings] = None) -> Dict[str, Any]:
        """Validate extracted data."""
        settings = settings or load_agent_settings()
        correlation_id = payload.get("correlationId")
        extraction_result = payload.get("extractionResult", {})
        extracted_data = extraction_result.get("extractedData", {})
        field_confidence = extraction_result.get("fieldConfidence", {})

        issues: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        for field in REQUIRED_W2_FIELDS:
            if not extracted_data.get(field):
                issues.append(
                    {
                        "code": "missing_required_field",
                        "severity": "error",
                        "field": field,
                        "message": f"Missing required W-2 field: {field}",
                    }
                )

        employer_ein = extracted_data.get("employerEIN")
        if employer_ein and not re.fullmatch(r"\d{2}-\d{7}", str(employer_ein)):
            issues.append(
                {
                    "code": "invalid_ein_format",
                    "severity": "error",
                    "field": "employerEIN",
                    "message": "Employer EIN must match NN-NNNNNNN.",
                }
            )

        employee_ssn = extracted_data.get("employeeSSN")
        if employee_ssn and not re.fullmatch(r"(XXX-XX-\d{4}|\d{3}-\d{2}-\d{4})", str(employee_ssn)):
            issues.append(
                {
                    "code": "invalid_ssn_format",
                    "severity": "error",
                    "field": "employeeSSN",
                    "message": "Employee SSN must be masked or formatted as NNN-NN-NNNN.",
                }
            )

        boxes = extracted_data.get("boxes", {})
        for box_name, amount in boxes.items():
            if isinstance(amount, list):
                for index, item in enumerate(amount):
                    if not is_number(item.get("amount")):
                        issues.append(
                            {
                                "code": "invalid_amount",
                                "severity": "error",
                                "field": f"boxes.{box_name}.{index}.amount",
                                "message": f"{box_name} item amount must be numeric.",
                            }
                        )
                continue
            if not is_number(amount):
                issues.append(
                    {
                        "code": "invalid_amount",
                        "severity": "error",
                        "field": f"boxes.{box_name}",
                        "message": f"{box_name} must be numeric.",
                    }
                )

        box1 = boxes.get("Box1", 0)
        box3 = boxes.get("Box3", 0)
        box4 = boxes.get("Box4", 0)
        box5 = boxes.get("Box5", 0)
        box6 = boxes.get("Box6", 0)
        if is_number(box1) and is_number(box3) and box3 > box1:
            warnings.append(
                {
                    "code": "ss_wages_exceed_wages",
                    "severity": "warning",
                    "field": "boxes.Box3",
                    "message": "Social Security wages exceed Box 1 wages; review pretax adjustments.",
                }
            )
        if is_number(box3) and is_number(box4) and abs(round(box3 * 0.062, 2) - box4) > 2:
            warnings.append(
                {
                    "code": "ss_withholding_mismatch",
                    "severity": "warning",
                    "field": "boxes.Box4",
                    "message": "Social Security withholding does not align with 6.2% of Box 3.",
                }
            )
        if is_number(box5) and is_number(box6) and abs(round(box5 * 0.0145, 2) - box6) > 2:
            warnings.append(
                {
                    "code": "medicare_withholding_mismatch",
                    "severity": "warning",
                    "field": "boxes.Box6",
                    "message": "Medicare withholding does not align with 1.45% of Box 5.",
                }
            )

        if settings.validation_strictness == VALIDATION_STRICTNESS_STRICT:
            box2 = boxes.get("Box2", 0)
            if is_number(box1) and is_number(box2) and box1 > 0 and box2 <= 0:
                warnings.append(
                    {
                        "code": "no_federal_withholding",
                        "severity": "warning",
                        "field": "boxes.Box2",
                        "message": "Strict validation flagged W-2 wages with no federal withholding.",
                    }
                )

        low_confidence = low_confidence_fields(
            field_confidence, settings.low_confidence_threshold
        )
        for field in low_confidence:
            warnings.append(
                {
                    "code": "low_confidence_extraction",
                    "severity": "warning",
                    "field": field,
                    "message": f"Extraction confidence for {field} is below threshold.",
                }
            )

        validation_status = "passed" if not issues else "failed"
        needs_review = bool(issues or low_confidence)

        result = {
            "correlationId": correlation_id,
            "validationStatus": validation_status,
            "issues": issues,
            "warnings": warnings,
            "needsReview": needs_review,
            "strictness": settings.validation_strictness,
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
