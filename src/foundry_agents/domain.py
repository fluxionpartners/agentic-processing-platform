from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional


REQUIRED_W2_FIELDS = ["taxYear", "employerEIN", "employerName", "employeeSSN"]
LOW_CONFIDENCE_THRESHOLD = 0.85


def default_w2_record(tax_year: Optional[int] = None) -> Dict[str, Any]:
    """Return a deterministic normalized W-2 record for local development."""
    return {
        "taxYear": tax_year or 2024,
        "employerEIN": "12-3456789",
        "employerName": "Sample Corporation",
        "employeeSSN": "XXX-XX-1234",
        "employeeName": "Alex Taxpayer",
        "controlNumber": "CTRL-001",
        "boxes": {
            "Box1": 75000.00,
            "Box2": 8500.00,
            "Box3": 60000.00,
            "Box4": 3720.00,
            "Box5": 75000.00,
            "Box6": 1087.50,
            "Box12": [
                {"code": "D", "amount": 6500.00, "description": "401(k) elective deferrals"}
            ],
        },
        "stateLocal": [
            {
                "state": "NY",
                "stateWages": 75000.00,
                "stateTaxWithheld": 4200.00,
                "localityName": "NYC",
                "localWages": 75000.00,
                "localTaxWithheld": 3100.00,
            }
        ],
    }


def default_field_confidence(record: Dict[str, Any]) -> Dict[str, float]:
    """Create confidence scores for extracted fields."""
    confidence = {field: 0.97 for field in REQUIRED_W2_FIELDS if field in record}
    for box_name in record.get("boxes", {}):
        confidence[f"boxes.{box_name}"] = 0.96
    for index, state_record in enumerate(record.get("stateLocal", [])):
        for field in state_record:
            confidence[f"stateLocal.{index}.{field}"] = 0.94
    return confidence


def deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Merge nested dictionaries while allowing explicit None overrides."""
    result = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def low_confidence_fields(confidence: Dict[str, float], threshold: float) -> List[str]:
    return sorted(field for field, score in confidence.items() if score < threshold)


def sum_amounts(records: Iterable[Dict[str, Any]], field: str) -> float:
    return round(sum(float(record.get(field) or 0) for record in records), 2)
