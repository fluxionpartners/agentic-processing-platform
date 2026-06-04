"""
Human Review Agent.

Manages human review workflows for flagged or ambiguous records.
Routes to approval/rejection and escalation as needed.
"""

from typing import Dict, Any, Optional

from foundry_agents.config import (
    AgentSettings,
    HUMAN_REVIEW_MODE_LOCAL_AUTO_APPROVE,
    HUMAN_REVIEW_MODE_MANUAL,
    HUMAN_REVIEW_MODE_QUEUE,
    load_agent_settings,
)
from foundry_agents.time_utils import utc_iso


class HumanReviewAgent:
    """Handles human review workflows."""

    @staticmethod
    def process(payload: Dict[str, Any], settings: Optional[AgentSettings] = None) -> Dict[str, Any]:
        """Submit record for human review."""
        settings = settings or load_agent_settings()
        correlation_id = payload.get("correlationId")
        issues = payload.get("validationResult", {}).get("issues", [])
        warnings = payload.get("validationResult", {}).get("warnings", [])
        review_reason = payload.get("validationResult", {}).get("reviewReason")
        local_decision = payload.get("mockHumanDecision", "approved")
        if settings.human_review_mode == HUMAN_REVIEW_MODE_LOCAL_AUTO_APPROVE:
            review_status = "pending"
            next_step = "tax_mapping" if local_decision == "approved" else "awaiting_human_decision"
            decision_mode = "local_development"
            assigned_queue = "local-auto-approve"
        elif settings.human_review_mode == HUMAN_REVIEW_MODE_QUEUE:
            review_status = "queued"
            next_step = "awaiting_human_decision"
            decision_mode = "review_queue"
            assigned_queue = "tax-document-review"
        elif settings.human_review_mode == HUMAN_REVIEW_MODE_MANUAL:
            review_status = "pending"
            next_step = "awaiting_human_decision"
            decision_mode = "manual"
            assigned_queue = "manual-review"
        else:
            raise ValueError(f"Unsupported human review mode: {settings.human_review_mode}")

        result = {
            "correlationId": correlation_id,
            "reviewStatus": review_status,
            "reviewReason": review_reason,
            "issues": issues,
            "warnings": warnings,
            "submittedForReview": utc_iso(),
            "assignedQueue": assigned_queue,
            "nextStep": next_step,
            "mockDecision": local_decision
            if settings.human_review_mode == HUMAN_REVIEW_MODE_LOCAL_AUTO_APPROVE
            else None,
            "decisionMode": decision_mode,
        }

        return result


if __name__ == "__main__":
    print("Human Review Agent loaded.")
