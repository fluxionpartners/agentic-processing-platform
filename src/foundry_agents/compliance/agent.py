"""
Compliance Agent.

Applies compliance and governance checks to ensure all data meets regulatory requirements.
"""

from typing import Dict, Any, Optional

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.compliance.adapters import create_compliance_adapter
from foundry_agents.time_utils import utc_iso


class ComplianceAgent:
    """Handles compliance and governance checks."""

    @staticmethod
    def process(payload: Dict[str, Any], settings: Optional[AgentSettings] = None) -> Dict[str, Any]:
        """Apply compliance checks."""
        settings = settings or load_agent_settings()
        correlation_id = payload.get("correlationId")
        adapter = create_compliance_adapter(settings)
        evaluation = adapter.evaluate(payload)
        compliance_checks = evaluation["checks"]
        all_passed = all(compliance_checks.values())

        result = {
            "correlationId": correlation_id,
            "complianceStatus": "passed" if all_passed else "flagged",
            "complianceMode": settings.compliance_mode,
            "complianceAdapter": adapter.name,
            "checks": compliance_checks,
            "auditEvent": evaluation["auditEvent"],
            "complianceTimestamp": utc_iso(),
            "nextStep": "complete",
        }

        return result


if __name__ == "__main__":
    print("Compliance Agent loaded.")
