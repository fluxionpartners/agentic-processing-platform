import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from foundry_agents.config import AgentSettings
from foundry_agents.supervisor.orchestrator import SupervisorOrchestrator
from foundry_agents.utils.azure_mock import MockAIProjectClient


class AgentToAgentSimulationTests(unittest.TestCase):
    def setUp(self):
        from foundry_agents.utils.azure_mock import MockAgentsOperations
        MockAgentsOperations.reset()

    def test_supervisor_delegates_to_child_agent_endpoints(self):
        settings = AgentSettings()
        client = MockAIProjectClient()
        supervisor = SupervisorOrchestrator(project_client=client, settings=settings)

        intake_event = {
            "tenantId": "tenant-001",
            "taxpayerId": "taxpayer-12345",
            "documentName": "W2_2024_sample.pdf",
            "blobUri": "https://example.invalid/raw-w2/W2_2024_sample.pdf",
            "taxYear": 2024,
            "correlationId": "a2a-happy-path",
        }
        
        # Run orchestrator
        final = supervisor.run(intake_event)

        # Verify that all 6 agent runs were created on the thread
        runs = list(client.agents._runs.values())
        self.assertEqual(len(runs), 6) # Intake, Extraction, Validation, TaxMapping, FormGen, Compliance
        
        # Verify stages were logged
        stages = [entry["stage"] for entry in supervisor.execution_log]
        self.assertEqual(final["status"], "complete")
        self.assertIn("intake", stages)
        self.assertIn("extraction", stages)
        self.assertIn("validation", stages)
        self.assertIn("tax_mapping", stages)
        self.assertIn("form_generation", stages)
        self.assertIn("compliance", stages)
        self.assertIn("finalize", stages)

    def test_agent_to_agent_review_pause(self):
        settings = AgentSettings(human_review_mode="manual")
        client = MockAIProjectClient()
        supervisor = SupervisorOrchestrator(project_client=client, settings=settings)

        intake_event = {
            "tenantId": "tenant-001",
            "taxpayerId": "taxpayer-12345",
            "documentName": "W2_2024_sample.pdf",
            "blobUri": "https://example.invalid/raw-w2/W2_2024_sample.pdf",
            "taxYear": 2024,
            "correlationId": "a2a-review",
            "mockExtractionOverrides": {"employerEIN": None},
        }
        
        result = supervisor.run(intake_event)
        self.assertEqual(result["status"], "waiting")
        self.assertEqual(result["nextStep"], "awaiting_human_decision")


if __name__ == "__main__":
    unittest.main()
