import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from foundry_agents.manual_test_harness import ManualTestHarness
from foundry_agents.config import AgentSettings, HUMAN_REVIEW_MODE_QUEUE
from foundry_agents.pipeline import AgentPipeline, process_w2_ingestion_event


class AgentOrchestrationTests(unittest.TestCase):
    def test_full_pipeline_completes_successfully(self):
        harness = ManualTestHarness()

        result = harness.run_full_pipeline()

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["payload"]["status"], "success")
        self.assertEqual(result["payload"]["runtimeSettings"]["appEnv"], "local")
        self.assertEqual(
            result["payload"]["intakeResult"]["runtime"]["extractionMode"], "local"
        )
        self.assertEqual(
            [entry["stage"] for entry in harness.execution_log],
            [
                "intake",
                "intake_checkpoint",
                "extraction",
                "extraction_checkpoint",
                "validation",
                "validation_checkpoint",
                "tax_mapping",
                "tax_mapping_checkpoint",
                "form_generation",
                "form_generation_checkpoint",
                "compliance",
                "compliance_checkpoint",
                "persistence",
                "finalize",
            ],
        )
        self.assertIn("persistenceResult", result["payload"])

    def test_human_review_scenario_routes_to_review(self):
        harness = ManualTestHarness()

        result = harness.run_pipeline_with_human_review()

        stages = [entry["stage"] for entry in harness.execution_log]
        self.assertEqual(result["status"], "complete")
        self.assertIn("human_review", stages)
        self.assertIn("extraction_checkpoint", stages)
        self.assertIn("human_review_checkpoint", stages)
        self.assertIn("persistence", stages)
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

    def test_queue_human_review_mode_pauses_pipeline(self):
        pipeline = AgentPipeline(
            settings=AgentSettings(human_review_mode=HUMAN_REVIEW_MODE_QUEUE)
        )

        result = pipeline.run(
            {
                "correlationId": "unit-test-review-001",
                "tenantId": "tenant-001",
                "taxpayerId": "taxpayer-123",
                "documentName": "W2.pdf",
                "blobUri": "https://example.blob.core.windows.net/raw-w2/W2.pdf",
                "taxYear": 2024,
                "mockExtractionOverrides": {"employerEIN": None},
            }
        )

        self.assertEqual(result["status"], "waiting")
        self.assertEqual(result["nextStep"], "awaiting_human_decision")
        self.assertEqual(
            [entry["stage"] for entry in pipeline.execution_log],
            [
                "intake",
                "intake_checkpoint",
                "extraction",
                "extraction_checkpoint",
                "validation",
                "validation_checkpoint",
                "human_review",
                "human_review_checkpoint",
                "await_human_review_checkpoint",
                "await_human_review",
            ],
        )


if __name__ == "__main__":
    unittest.main()
