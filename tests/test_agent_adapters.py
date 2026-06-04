import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from foundry_agents.compliance.adapters import LocalComplianceAdapter, create_compliance_adapter
from foundry_agents.config import (
    AgentSettings,
    HUMAN_REVIEW_MODE_MANUAL,
    HUMAN_REVIEW_MODE_QUEUE,
)
from foundry_agents.human_review.adapters import (
    LocalAutoApproveHumanReviewAdapter,
    ManualHumanReviewAdapter,
    QueueHumanReviewAdapter,
    create_human_review_adapter,
)
from foundry_agents.intake.adapters import LocalIntakeAdapter, create_intake_adapter
from foundry_agents.tax_mapping.adapters import (
    USFederal2024W2MappingAdapter,
    create_tax_mapping_adapter,
)
from foundry_agents.validation.adapters import LocalW2ValidationAdapter, create_validation_adapter


class AgentAdapterTests(unittest.TestCase):
    def test_intake_adapter_factory_returns_local_adapter(self):
        adapter = create_intake_adapter(AgentSettings())

        self.assertIsInstance(adapter, LocalIntakeAdapter)
        self.assertEqual(adapter.name, "local-intake-event-v1")

    def test_validation_adapter_factory_returns_local_rules(self):
        adapter = create_validation_adapter(AgentSettings())

        self.assertIsInstance(adapter, LocalW2ValidationAdapter)
        self.assertEqual(adapter.name, "local-w2-validation-rules-v1")

    def test_tax_mapping_adapter_factory_returns_configured_profile(self):
        adapter = create_tax_mapping_adapter(AgentSettings())

        self.assertIsInstance(adapter, USFederal2024W2MappingAdapter)
        self.assertEqual(adapter.name, "us-federal-2024-w2-mapping-v1")

    def test_human_review_adapter_factory_returns_mode_specific_adapter(self):
        self.assertIsInstance(
            create_human_review_adapter(AgentSettings()),
            LocalAutoApproveHumanReviewAdapter,
        )
        self.assertIsInstance(
            create_human_review_adapter(AgentSettings(human_review_mode=HUMAN_REVIEW_MODE_QUEUE)),
            QueueHumanReviewAdapter,
        )
        self.assertIsInstance(
            create_human_review_adapter(AgentSettings(human_review_mode=HUMAN_REVIEW_MODE_MANUAL)),
            ManualHumanReviewAdapter,
        )

    def test_compliance_adapter_factory_returns_local_controls(self):
        adapter = create_compliance_adapter(AgentSettings())

        self.assertIsInstance(adapter, LocalComplianceAdapter)
        self.assertEqual(adapter.name, "local-compliance-controls-v1")


if __name__ == "__main__":
    unittest.main()
