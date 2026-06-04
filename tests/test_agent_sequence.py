import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from foundry_agents.compliance.agent import ComplianceAgent
from foundry_agents.extraction.agent import ExtractionAgent
from foundry_agents.tax_mapping.agent import TaxMappingAgent
from foundry_agents.validation.agent import ValidationAgent


class AgentSequenceTests(unittest.TestCase):
    def test_extraction_outputs_normalized_w2_with_confidence(self):
        result = ExtractionAgent.process(
            {
                "correlationId": "corr-001",
                "documentName": "W2.pdf",
                "blobUri": "https://example/w2.pdf",
                "taxYear": 2025,
            }
        )

        self.assertEqual(result["extractionStatus"], "success")
        self.assertEqual(result["source"]["mode"], "local")
        self.assertEqual(result["extractedData"]["taxYear"], 2025)
        self.assertIn("fieldConfidence", result)
        self.assertGreater(result["overallConfidence"], 0.9)

    def test_validation_flags_low_confidence_for_human_review(self):
        extraction_result = ExtractionAgent.process(
            {
                "correlationId": "corr-002",
                "mockConfidenceOverrides": {"employerEIN": 0.5},
            }
        )

        result = ValidationAgent.process(
            {"correlationId": "corr-002", "extractionResult": extraction_result}
        )

        self.assertEqual(result["validationStatus"], "passed")
        self.assertTrue(result["needsReview"])
        self.assertEqual(result["reviewReason"], "low_confidence_extraction")
        self.assertEqual(result["warnings"][0]["code"], "low_confidence_extraction")

    def test_validation_flags_missing_required_field(self):
        extraction_result = ExtractionAgent.process(
            {
                "correlationId": "corr-003",
                "mockExtractionOverrides": {"employerEIN": None},
            }
        )

        result = ValidationAgent.process(
            {"correlationId": "corr-003", "extractionResult": extraction_result}
        )

        self.assertEqual(result["validationStatus"], "failed")
        self.assertTrue(result["needsReview"])
        self.assertEqual(result["issues"][0]["code"], "missing_required_field")

    def test_tax_mapping_outputs_1040_and_tax_intelligence_payloads(self):
        extraction_result = ExtractionAgent.process({"correlationId": "corr-004"})
        result = TaxMappingAgent.process(
            {"correlationId": "corr-004", "extractionResult": extraction_result}
        )

        self.assertEqual(result["mappingStatus"], "success")
        self.assertEqual(result["form1040"]["federal"]["wagesLine1a"], 75000.00)
        self.assertEqual(
            result["normalizedTaxFacts"]["retirementPlanning"][
                "preTaxRetirementContributions"
            ],
            6500.00,
        )

    def test_compliance_outputs_audit_event(self):
        extraction_result = ExtractionAgent.process(
            {"correlationId": "corr-005", "blobUri": "https://example/w2.pdf"}
        )
        validation_result = ValidationAgent.process(
            {"correlationId": "corr-005", "extractionResult": extraction_result}
        )
        mapping_result = TaxMappingAgent.process(
            {"correlationId": "corr-005", "extractionResult": extraction_result}
        )

        result = ComplianceAgent.process(
            {
                "correlationId": "corr-005",
                "pipelineId": "pipeline-corr-005",
                "tenantId": "tenant-001",
                "taxpayerId": "taxpayer-123",
                "documentName": "W2.pdf",
                "extractionResult": extraction_result,
                "validationResult": validation_result,
                "mappingResult": mapping_result,
            }
        )

        self.assertEqual(result["complianceStatus"], "passed")
        self.assertEqual(
            result["auditEvent"]["eventType"], "TaxPipelineComplianceEvaluated"
        )
        self.assertTrue(result["checks"]["piiMaskedForLogs"])


if __name__ == "__main__":
    unittest.main()
