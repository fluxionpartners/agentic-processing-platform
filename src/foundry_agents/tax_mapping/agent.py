"""
Tax Mapping Agent.

Maps validated W-2 data into 1040 payloads and tax intelligence artifacts.
Supports multiple tax scenarios and state/local mapping.
"""

from typing import Dict, Any, Optional

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.tax_mapping.adapters import create_tax_mapping_adapter
from foundry_agents.time_utils import utc_iso


class TaxMappingAgent:
    """Handles tax payload generation and mapping."""

    @staticmethod
    def process(payload: Dict[str, Any], settings: Optional[AgentSettings] = None) -> Dict[str, Any]:
        """Map extracted data to 1040 format."""
        settings = settings or load_agent_settings()
        correlation_id = payload.get("correlationId")
        adapter = create_tax_mapping_adapter(settings)
        mapping = adapter.map(payload)

        result = {
            "correlationId": correlation_id,
            "mappingStatus": "success",
            "mappingProfile": settings.tax_mapping_profile,
            "mapper": adapter.name,
            "form1040": mapping["form1040"],
            "normalizedTaxFacts": mapping["normalizedTaxFacts"],
            "mappingTimestamp": utc_iso(),
            "nextStep": "compliance",
        }

        return result


if __name__ == "__main__":
    print("Tax Mapping Agent loaded.")
