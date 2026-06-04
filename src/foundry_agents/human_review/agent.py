"""
Human Review Agent.

Manages human review workflows for flagged or ambiguous records.
Routes to approval/rejection and escalation as needed.
"""

from typing import Dict, Any, Optional

from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.human_review.adapters import create_human_review_adapter


class HumanReviewAgent:
    """Handles human review workflows."""

    @staticmethod
    def process(payload: Dict[str, Any], settings: Optional[AgentSettings] = None) -> Dict[str, Any]:
        """Submit record for human review."""
        settings = settings or load_agent_settings()
        adapter = create_human_review_adapter(settings)
        result = adapter.submit(payload)
        result["reviewAdapter"] = adapter.name
        return result


if __name__ == "__main__":
    print("Human Review Agent loaded.")
