from abc import ABC, abstractmethod
from typing import Any, Dict

from foundry_agents.config import AgentSettings
from foundry_agents.time_utils import utc_iso


class IntakeAdapter(ABC):
    """Adapter contract for initial document intake handling."""

    name: str

    @abstractmethod
    def accept(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Accept an intake payload and return the normalized intake result."""


class LocalIntakeAdapter(IntakeAdapter):
    """Local/event-payload intake adapter for already-uploaded W-2 documents."""

    name = "local-intake-event-v1"

    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings

    def accept(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "correlationId": payload.get("correlationId"),
            "blobUri": payload.get("blobUri"),
            "intakeStatus": "accepted",
            "runtime": {
                "appEnv": self.settings.app_env,
                "extractionMode": self.settings.extraction_mode,
            },
            "adapter": self.name,
            "intakeTimestamp": utc_iso(),
            "nextStep": "extraction",
        }


def create_intake_adapter(settings: AgentSettings) -> IntakeAdapter:
    return LocalIntakeAdapter(settings)
