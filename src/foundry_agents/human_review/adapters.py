from abc import ABC, abstractmethod
from typing import Any, Dict

from foundry_agents.config import (
    AgentSettings,
    HUMAN_REVIEW_MODE_LOCAL_AUTO_APPROVE,
    HUMAN_REVIEW_MODE_MANUAL,
    HUMAN_REVIEW_MODE_QUEUE,
)
from foundry_agents.time_utils import utc_iso


class HumanReviewAdapter(ABC):
    """Adapter contract for submitting records to human review workflows."""

    name: str

    @abstractmethod
    def submit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit review packet and return review routing metadata."""


class BaseHumanReviewAdapter(HumanReviewAdapter):
    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings

    def _review_packet(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        validation_result = payload.get("validationResult", {})
        return {
            "correlationId": payload.get("correlationId"),
            "reviewReason": validation_result.get("reviewReason"),
            "issues": validation_result.get("issues", []),
            "warnings": validation_result.get("warnings", []),
            "submittedForReview": utc_iso(),
        }


class LocalAutoApproveHumanReviewAdapter(BaseHumanReviewAdapter):
    name = "local-auto-approve-human-review-v1"

    def submit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        packet = self._review_packet(payload)
        local_decision = payload.get("mockHumanDecision", "approved")
        packet.update(
            {
                "reviewStatus": "pending",
                "assignedQueue": "local-auto-approve",
                "nextStep": "tax_mapping" if local_decision == "approved" else "awaiting_human_decision",
                "mockDecision": local_decision,
                "decisionMode": "local_development",
            }
        )
        return packet


class QueueHumanReviewAdapter(BaseHumanReviewAdapter):
    name = "queue-human-review-v1"

    def submit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        packet = self._review_packet(payload)
        packet.update(
            {
                "reviewStatus": "queued",
                "assignedQueue": "tax-document-review",
                "nextStep": "awaiting_human_decision",
                "mockDecision": None,
                "decisionMode": "review_queue",
            }
        )
        return packet


class ManualHumanReviewAdapter(BaseHumanReviewAdapter):
    name = "manual-human-review-v1"

    def submit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        packet = self._review_packet(payload)
        packet.update(
            {
                "reviewStatus": "pending",
                "assignedQueue": "manual-review",
                "nextStep": "awaiting_human_decision",
                "mockDecision": None,
                "decisionMode": "manual",
            }
        )
        return packet


def create_human_review_adapter(settings: AgentSettings) -> HumanReviewAdapter:
    if settings.human_review_mode == HUMAN_REVIEW_MODE_LOCAL_AUTO_APPROVE:
        return LocalAutoApproveHumanReviewAdapter(settings)
    if settings.human_review_mode == HUMAN_REVIEW_MODE_QUEUE:
        return QueueHumanReviewAdapter(settings)
    if settings.human_review_mode == HUMAN_REVIEW_MODE_MANUAL:
        return ManualHumanReviewAdapter(settings)
    raise ValueError(f"Unsupported human review mode: {settings.human_review_mode}")
