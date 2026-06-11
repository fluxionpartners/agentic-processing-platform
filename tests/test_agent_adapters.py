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
from foundry_agents.form_generation.adapters import (
    HtmlForm1040GenerationAdapter,
    create_form_1040_generation_adapter,
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

    def test_form_generation_adapter_factory_returns_html_renderer(self):
        adapter = create_form_1040_generation_adapter(AgentSettings())

        self.assertIsInstance(adapter, HtmlForm1040GenerationAdapter)
        self.assertEqual(adapter.name, "irs-1040-html-renderer-v1")

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

    def test_adapters_are_robust_to_explicit_none_payload_fields(self):
        settings = AgentSettings()

        # 1. Validation adapter
        val_adapter = create_validation_adapter(settings)
        val_res = val_adapter.validate({
            "correlationId": "none-test",
            "extractionResult": None
        })
        self.assertEqual(val_res["issues"][0]["code"], "missing_required_field")

        # 2. Tax mapping adapter
        map_adapter = create_tax_mapping_adapter(settings)
        map_res = map_adapter.map({
            "correlationId": "none-test",
            "extractionResult": None
        })
        self.assertEqual(map_res["form1040"]["federal"]["wagesLine1a"], 0)

        # 3. Form generation adapter
        gen_adapter = create_form_1040_generation_adapter(settings)
        gen_res = gen_adapter.generate({
            "correlationId": "none-test",
            "mappingResult": None
        })
        self.assertEqual(gen_res["fieldValues"]["wagesLine1a"], "0.00")

        # 4. Compliance adapter
        comp_adapter = create_compliance_adapter(settings)
        comp_res = comp_adapter.evaluate({
            "correlationId": "none-test",
            "extractionResult": None,
            "validationResult": None,
            "mappingResult": None,
            "formGenerationResult": None,
            "humanReviewResult": None
        })
        self.assertIn("validationCompleted", comp_res["checks"])
        self.assertFalse(comp_res["checks"]["validationCompleted"])

        # 5. Human review adapter
        rev_adapter = create_human_review_adapter(settings)
        rev_res = rev_adapter.submit({
            "correlationId": "none-test",
            "validationResult": None
        })
        self.assertEqual(rev_res["issues"], [])

        # 6. Checkpoint persistence
        from foundry_agents.persistence.store import build_tax_fact_record
        rec = build_tax_fact_record({
            "correlationId": "none-test",
            "extractionResult": None,
            "validationResult": None,
            "mappingResult": None,
            "formGenerationResult": None,
            "finalResult": None,
            "intakeResult": None
        }, settings)
        self.assertEqual(rec["extraction"]["extractedData"], {})

        # 7. Thread rehydration
        from foundry_agents.utils.azure_helpers import reconstruct_state_from_thread
        from foundry_agents.utils.azure_mock import MockAIProjectClient
        
        client = MockAIProjectClient()
        thread = client.agents.create_thread()
        client.agents.create_message(
            thread_id=thread.id,
            role="user",
            content=__import__("json").dumps({"correlationId": "none-test"})
        )
        state = reconstruct_state_from_thread(client, thread.id)
        self.assertEqual(state["correlationId"], "none-test")


if __name__ == "__main__":
    unittest.main()
