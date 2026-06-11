from abc import ABC, abstractmethod
from typing import Any, Dict, List

from foundry_agents.config import AgentSettings, TAX_MAPPING_PROFILE_US_FEDERAL_2024
from foundry_agents.domain import sum_amounts


class TaxMappingAdapter(ABC):
    """Adapter contract for mapping extracted facts into tax payloads."""

    name: str

    @abstractmethod
    def map(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return form and planning facts for extracted tax document data."""


class USFederal2024W2MappingAdapter(TaxMappingAdapter):
    """W-2 to US federal 2024 planning fact mapping profile."""

    name = "us-federal-2024-w2-mapping-v1"

    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings

    def map(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        extraction_result = payload.get("extractionResult") or {}
        extracted_data = extraction_result.get("extractedData") or {}
        boxes = extracted_data.get("boxes") or {}
        state_local = extracted_data.get("stateLocal") or []
        box12_items: List[Dict[str, Any]] = boxes.get("Box12") or []

        federal_w2_input = {
            "taxYear": extracted_data.get("taxYear"),
            "filingStatus": "single",
            "wagesLine1a": boxes.get("Box1", 0),
            "federalIncomeTaxWithheld": boxes.get("Box2", 0),
            "socialSecurityWages": boxes.get("Box3", 0),
            "socialSecurityTaxWithheld": boxes.get("Box4", 0),
            "medicareWages": boxes.get("Box5", 0),
            "medicareTaxWithheld": boxes.get("Box6", 0),
        }

        retirement_contributions = [
            item for item in box12_items if str(item.get("code", "")).upper() in {"D", "E", "F", "G", "S"}
        ]
        tax_intelligence = {
            "incomeSummary": {
                "w2Wages": federal_w2_input["wagesLine1a"],
                "federalWithheld": federal_w2_input["federalIncomeTaxWithheld"],
                "stateWithheld": sum_amounts(state_local, "stateTaxWithheld"),
                "localWithheld": sum_amounts(state_local, "localTaxWithheld"),
            },
            "retirementPlanning": {
                "preTaxRetirementContributions": round(
                    sum(float(item.get("amount") or 0) for item in retirement_contributions), 2
                ),
                "contributionCodes": [item.get("code") for item in retirement_contributions],
            },
            "stateLocalTax": state_local,
        }

        return {
            "form1040": {
                "federal": federal_w2_input,
                "stateLocal": state_local,
                "taxIntelligence": tax_intelligence,
            },
            "normalizedTaxFacts": tax_intelligence,
        }


def create_tax_mapping_adapter(settings: AgentSettings) -> TaxMappingAdapter:
    if settings.tax_mapping_profile == TAX_MAPPING_PROFILE_US_FEDERAL_2024:
        return USFederal2024W2MappingAdapter(settings)
    raise ValueError(f"Unsupported tax mapping profile: {settings.tax_mapping_profile}")
