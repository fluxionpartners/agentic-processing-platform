import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from foundry_agents.manual_test_harness import ManualTestHarness
from foundry_agents.pipeline import process_w2_ingestion_event


class AgentOrchestrationTests(unittest.TestCase):
    def test_full_pipeline_completes_successfully(self):
        harness = ManualTestHarness()

        result = harness.run_full_pipeline()

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["payload"]["status"], "success")
        self.assertEqual(
            [entry["stage"] for entry in harness.execution_log],
            ["intake", "extraction", "validation", "tax_mapping", "compliance", "finalize"],
        )

    def test_human_review_scenario_routes_to_review(self):
        harness = ManualTestHarness()

        result = harness.run_pipeline_with_human_review()

        stages = [entry["stage"] for entry in harness.execution_log]
        self.assertEqual(result["status"], "complete")
        self.assertIn("human_review", stages)
        self.assertEqual(result["payload"]["validationResult"]["validationStatus"], "failed")
        self.assertEqual(result["payload"]["humanReviewResult"]["reviewStatus"], "pending")

    def test_process_w2_ingestion_event_runs_pipeline(self):
        result = process_w2_ingestion_event(
            {
                "correlationId": "unit-test-001",
                "tenantId": "tenant-001",
                "taxpayerId": "taxpayer-123",
                "documentName": "W2.pdf",
                "blobUri": "https://example.blob.core.windows.net/raw-w2/W2.pdf",
                "taxYear": 2024,
            }
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["correlationId"], "unit-test-001")


if __name__ == "__main__":
    unittest.main()
