"""
Intake Agent.

Receives W-2 documents via manual trigger or event-driven ingestion.
Validates the document and passes it to extraction.
"""

from typing import Dict, Any, Optional

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.intake.adapters import create_intake_adapter


class IntakeAgent:
    """Handles document intake and initial validation."""

    @staticmethod
    def process(payload: Dict[str, Any], settings: Optional[AgentSettings] = None) -> Dict[str, Any]:
        """Process intake request."""
        settings = settings or load_agent_settings()
        adapter = create_intake_adapter(settings)
        return adapter.accept(payload)


if __name__ == "__main__":
    print("Intake Agent loaded.")
