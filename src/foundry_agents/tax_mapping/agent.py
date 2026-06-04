"""
Tax Mapping Agent.

Maps validated W-2 data into 1040 payloads and tax intelligence artifacts.
Supports multiple tax scenarios and state/local mapping.
"""

from typing import Dict, Any, List, Optional

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.domain import sum_amounts
from foundry_agents.time_utils import utc_iso


class TaxMappingAgent:
    """Handles tax payload generation and mapping."""

    @staticmethod
    def process(payload: Dict[str, Any], settings: Optional[AgentSettings] = None) -> Dict[str, Any]:
        """Map extracted data to 1040 format."""
        settings = settings or load_agent_settings()
        correlation_id = payload.get("correlationId")
        extracted_data = payload.get("extractionResult", {}).get("extractedData", {})
        boxes = extracted_data.get("boxes", {})
        state_local = extracted_data.get("stateLocal", [])
        box12_items: List[Dict[str, Any]] = boxes.get("Box12", [])

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

        form_1040 = {
            "federal": federal_w2_input,
            "stateLocal": state_local,
            "taxIntelligence": tax_intelligence,
        }

        result = {
            "correlationId": correlation_id,
            "mappingStatus": "success",
            "mappingProfile": settings.tax_mapping_profile,
            "form1040": form_1040,
            "normalizedTaxFacts": tax_intelligence,
            "mappingTimestamp": utc_iso(),
            "nextStep": "compliance",
        }

        return result


if __name__ == "__main__":
    print("Tax Mapping Agent loaded.")
