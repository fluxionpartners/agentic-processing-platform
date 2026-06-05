import sys
import tempfile
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from foundry_agents.compliance.agent import ComplianceAgent
from foundry_agents.config import AgentSettings
from foundry_agents.extraction.agent import ExtractionAgent
from foundry_agents.form_generation.agent import Form1040GenerationAgent
from foundry_agents.human_review.agent import HumanReviewAgent
from foundry_agents.intake.agent import IntakeAgent
from foundry_agents.supervisor.orchestrator import SupervisorOrchestrator
from foundry_agents.tax_mapping.agent import TaxMappingAgent
from foundry_agents.validation.agent import ValidationAgent


class LocalAgentEndpoint:
    """Minimal local stand-in for a child agent endpoint."""

    def __init__(self, name, handler):
        self.name = name
        self.handler = handler
        self.messages = []

    def invoke(self, message, settings):
        self.messages.append(message)
        result = self.handler(message["payload"], settings)
        return {
            "fromAgent": self.name,
            "correlationId": message["correlationId"],
            "payload": result,
        }


class AgentToAgentSimulationTests(unittest.TestCase):
    def test_supervisor_delegates_to_child_agent_endpoints(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        settings = AgentSettings(form_1040_artifact_path=temp_dir.name)
        supervisor = SupervisorOrchestrator()
        child_agents = {
            "intake": LocalAgentEndpoint("intake-agent", IntakeAgent.process),
            "extraction": LocalAgentEndpoint("extraction-agent", ExtractionAgent.process),
            "validation": LocalAgentEndpoint("validation-agent", ValidationAgent.process),
            "tax_mapping": LocalAgentEndpoint("tax-mapping-agent", TaxMappingAgent.process),
            "form_generation": LocalAgentEndpoint(
                "form-generation-agent", Form1040GenerationAgent.process
            ),
            "compliance": LocalAgentEndpoint("compliance-agent", ComplianceAgent.process),
        }

        intake_event = {
            "tenantId": "tenant-001",
            "taxpayerId": "taxpayer-12345",
            "documentName": "W2_2024_sample.pdf",
            "blobUri": "https://example.invalid/raw-w2/W2_2024_sample.pdf",
            "taxYear": 2024,
            "correlationId": "a2a-happy-path",
        }
        start = supervisor.start_pipeline(
            intake_event,
            runtime_settings=settings.as_runtime_metadata(),
        )

        intake_reply = child_agents["intake"].invoke(start, settings)
        extraction_route = supervisor.route_to_extraction(intake_reply["payload"])

        extraction_reply = child_agents["extraction"].invoke(extraction_route, settings)
        validation_route = supervisor.route_to_validation(extraction_reply["payload"])

        validation_reply = child_agents["validation"].invoke(validation_route, settings)
        self.assertFalse(validation_reply["payload"]["needsReview"])

        mapping_route = supervisor.route_to_tax_mapping(validation_reply["payload"])
        mapping_reply = child_agents["tax_mapping"].invoke(mapping_route, settings)

        form_generation_route = supervisor.route_to_form_generation(mapping_reply["payload"])
        form_generation_reply = child_agents["form_generation"].invoke(
            form_generation_route, settings
        )

        compliance_route = supervisor.route_to_compliance(form_generation_reply["payload"])
        compliance_reply = child_agents["compliance"].invoke(compliance_route, settings)
        final = supervisor.finalize_pipeline(compliance_reply["payload"])

        self.assertEqual(final["status"], "complete")
        self.assertEqual(final["payload"]["stage"], "complete")
        self.assertEqual(final["payload"]["finalResult"]["complianceStatus"], "passed")
        self.assertEqual(child_agents["extraction"].messages[0]["nextAgent"], "extraction")
        self.assertEqual(child_agents["tax_mapping"].messages[0]["nextAgent"], "tax_mapping")
        self.assertEqual(
            child_agents["form_generation"].messages[0]["nextAgent"], "form_generation"
        )

    def test_agent_to_agent_review_pause(self):
        settings = AgentSettings()
        supervisor = SupervisorOrchestrator()
        review_agent = LocalAgentEndpoint("human-review-agent", HumanReviewAgent.process)

        start = supervisor.start_pipeline(
            {
                "tenantId": "tenant-001",
                "taxpayerId": "taxpayer-12345",
                "documentName": "W2_2024_sample.pdf",
                "blobUri": "https://example.invalid/raw-w2/W2_2024_sample.pdf",
                "taxYear": 2024,
                "correlationId": "a2a-review",
            },
            runtime_settings=settings.as_runtime_metadata(),
        )
        self.assertEqual(start["nextAgent"], "intake")

        validation_result = {
            "correlationId": "a2a-review",
            "validationStatus": "failed",
            "issues": [
                {
                    "code": "missing_required_field",
                    "severity": "error",
                    "field": "employerEIN",
                    "message": "Missing required W-2 field: employerEIN",
                }
            ],
            "warnings": [],
            "needsReview": True,
            "reviewReason": "blocking_validation_issues",
            "nextStep": "human_review",
        }

        review_route = supervisor.route_to_human_review(validation_result)
        review_reply = review_agent.invoke(review_route, settings)

        self.assertEqual(review_reply["fromAgent"], "human-review-agent")
        self.assertEqual(review_reply["payload"]["nextStep"], "tax_mapping")


if __name__ == "__main__":
    unittest.main()
