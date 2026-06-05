"""
Form 1040 Generation Agent.

Renders 1040 document artifacts from validated tax mapping output.
"""

from typing import Any, Dict, Optional

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.form_generation.adapters import create_form_1040_generation_adapter
from foundry_agents.time_utils import utc_iso


class Form1040GenerationAgent:
    """Handles Form 1040 document artifact generation."""

    @staticmethod
    def process(payload: Dict[str, Any], settings: Optional[AgentSettings] = None) -> Dict[str, Any]:
        """Generate a Form 1040 artifact from mapped tax facts."""
        settings = settings or load_agent_settings()
        adapter = create_form_1040_generation_adapter(settings)
        generation = adapter.generate(payload)

        return {
            "correlationId": payload.get("correlationId"),
            "generationStatus": "success",
            "generationMode": settings.form_1040_generation_mode,
            "artifactMode": settings.form_1040_artifact_mode,
            "generator": adapter.name,
            "templateVersion": generation["templateVersion"],
            "documentType": generation["documentType"],
            "taxYear": generation["taxYear"],
            "fieldValues": generation["fieldValues"],
            "artifact": generation["artifact"],
            "generatedAt": utc_iso(),
            "nextStep": "compliance",
        }


if __name__ == "__main__":
    print("Form 1040 Generation Agent loaded.")
