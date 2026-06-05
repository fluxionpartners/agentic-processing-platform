import sys
import tempfile
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from foundry_agents.config import AgentSettings, EXTRACTION_MODE_DOCUMENT_INTELLIGENCE
from foundry_agents.compliance.agent import ComplianceAgent
from foundry_agents.extraction.adapters import DocumentIntelligenceW2ExtractionAdapter
from foundry_agents.extraction.agent import ExtractionAgent
from foundry_agents.form_generation.agent import Form1040GenerationAgent
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

    def test_document_intelligence_adapter_maps_prebuilt_w2_response(self):
        settings = AgentSettings(
            extraction_mode=EXTRACTION_MODE_DOCUMENT_INTELLIGENCE,
            document_intelligence_endpoint="https://example.cognitiveservices.azure.com/",
        )
        adapter = DocumentIntelligenceW2ExtractionAdapter(settings)
        adapter._analyze_document = lambda _: {
            "apiVersion": "2024-11-30",
            "documents": [
                {
                    "fields": {
                        "TaxYear": {"valueInteger": 2024, "confidence": 0.99},
                        "Employer": {
                            "valueObject": {
                                "Name": {"valueString": "Contoso Ltd", "confidence": 0.98},
                                "IdNumber": {"valueString": "98-7654321", "confidence": 0.97},
                            }
                        },
                        "Employee": {
                            "valueObject": {
                                "Name": {"valueString": "Jane Taxpayer", "confidence": 0.98},
                                "SocialSecurityNumber": {
                                    "valueString": "123-45-6789",
                                    "confidence": 0.96,
                                },
                            }
                        },
                        "WagesTipsAndOtherCompensation": {
                            "valueNumber": 88000,
                            "confidence": 0.95,
                        },
                        "FederalIncomeTaxWithheld": {
                            "valueNumber": 12000,
                            "confidence": 0.94,
                        },
                        "SocialSecurityWages": {"valueNumber": 88000, "confidence": 0.95},
                        "SocialSecurityTaxWithheld": {
                            "valueNumber": 5456,
                            "confidence": 0.95,
                        },
                        "MedicareWagesAndTips": {"valueNumber": 88000, "confidence": 0.95},
                        "MedicareTaxWithheld": {"valueNumber": 1276, "confidence": 0.95},
                        "AdditionalInfo": {
                            "valueArray": [
                                {
                                    "valueObject": {
                                        "LetterCode": {"valueString": "D", "confidence": 0.9},
                                        "Amount": {"valueNumber": 7000, "confidence": 0.9},
                                    }
                                }
                            ],
                            "confidence": 0.9,
                        },
                        "StateTaxInfos": {
                            "valueArray": [
                                {
                                    "valueObject": {
                                        "State": {"valueString": "CA", "confidence": 0.92},
                                        "StateWagesTipsEtc": {
                                            "valueNumber": 88000,
                                            "confidence": 0.91,
                                        },
                                        "StateIncomeTax": {
                                            "valueNumber": 6000,
                                            "confidence": 0.9,
                                        },
                                    }
                                }
                            ]
                        },
                        "LocalTaxInfos": {
                            "valueArray": [
                                {
                                    "valueObject": {
                                        "LocalityName": {"valueString": "SF", "confidence": 0.9},
                                        "LocalWagesTipsEtc": {
                                            "valueNumber": 88000,
                                            "confidence": 0.9,
                                        },
                                        "LocalIncomeTax": {
                                            "valueNumber": 1000,
                                            "confidence": 0.9,
                                        },
                                    }
                                }
                            ]
                        },
                    }
                }
            ],
        }

        result = adapter.extract({"blobUri": "https://example/w2.pdf"})

        self.assertEqual(result["extractedData"]["taxYear"], 2024)
        self.assertEqual(result["extractedData"]["employerName"], "Contoso Ltd")
        self.assertEqual(result["extractedData"]["employeeSSN"], "XXX-XX-6789")
        self.assertEqual(result["extractedData"]["boxes"]["Box1"], 88000)
        self.assertEqual(result["extractedData"]["boxes"]["Box12"][0]["code"], "D")
        self.assertEqual(result["extractedData"]["stateLocal"][0]["localityName"], "SF")
        self.assertEqual(result["fieldConfidence"]["employeeSSN"], 0.96)
        self.assertEqual(result["rawResult"]["documentCount"], 1)

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

    def test_form_generation_outputs_1040_artifact(self):
        extraction_result = ExtractionAgent.process({"correlationId": "corr-004a"})
        mapping_result = TaxMappingAgent.process(
            {"correlationId": "corr-004a", "extractionResult": extraction_result}
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = Form1040GenerationAgent.process(
                {
                    "correlationId": "corr-004a",
                    "tenantId": "tenant-001",
                    "taxpayerId": "taxpayer-123",
                    "taxYear": 2024,
                    "mappingResult": mapping_result,
                },
                AgentSettings(form_1040_artifact_path=temp_dir),
            )
            artifact_exists = Path(result["artifact"]["path"]).exists()

        self.assertEqual(result["generationStatus"], "success")
        self.assertEqual(result["documentType"], "irs-form-1040")
        self.assertEqual(result["fieldValues"]["wagesLine1a"], "75000.00")
        self.assertEqual(result["artifact"]["contentType"], "text/html")
        self.assertTrue(artifact_exists)

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
        with tempfile.TemporaryDirectory() as temp_dir:
            form_generation_result = Form1040GenerationAgent.process(
                {
                    "correlationId": "corr-005",
                    "tenantId": "tenant-001",
                    "taxpayerId": "taxpayer-123",
                    "taxYear": 2024,
                    "mappingResult": mapping_result,
                },
                AgentSettings(form_1040_artifact_path=temp_dir),
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
                "formGenerationResult": form_generation_result,
            }
        )

        self.assertEqual(result["complianceStatus"], "passed")
        self.assertEqual(
            result["auditEvent"]["eventType"], "TaxPipelineComplianceEvaluated"
        )
        self.assertTrue(result["checks"]["piiMaskedForLogs"])
        self.assertTrue(result["checks"]["form1040Generated"])


if __name__ == "__main__":
    unittest.main()
