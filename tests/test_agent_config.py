import sys
import tempfile
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from foundry_agents.config import (
    APP_ENV_PROD,
    COMPLIANCE_MODE_REGULATED,
    HUMAN_REVIEW_MODE_QUEUE,
    EXTRACTION_MODE_DOCUMENT_INTELLIGENCE,
    EXTRACTION_MODE_LOCAL,
    TAX_FACT_PERSISTENCE_COSMOS,
    TAX_FACT_PERSISTENCE_LOCAL_JSON,
    VALIDATION_STRICTNESS_STRICT,
    load_environment,
    load_agent_settings,
    parse_dotenv,
)
from foundry_agents.extraction.adapters import (
    DocumentIntelligenceW2ExtractionAdapter,
    LocalW2ExtractionAdapter,
    create_extraction_adapter,
)


class AgentConfigTests(unittest.TestCase):
    def test_default_extraction_mode_is_local(self):
        settings = load_agent_settings({})

        self.assertEqual(settings.extraction_mode, EXTRACTION_MODE_LOCAL)
        self.assertIsInstance(create_extraction_adapter(settings), LocalW2ExtractionAdapter)

    def test_document_intelligence_mode_selects_real_adapter(self):
        settings = load_agent_settings(
            {
                "W2_EXTRACTION_MODE": EXTRACTION_MODE_DOCUMENT_INTELLIGENCE,
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "https://example.cognitiveservices.azure.com/",
            }
        )

        self.assertEqual(settings.extraction_mode, EXTRACTION_MODE_DOCUMENT_INTELLIGENCE)
        self.assertIsInstance(
            create_extraction_adapter(settings), DocumentIntelligenceW2ExtractionAdapter
        )

    def test_invalid_extraction_mode_fails_fast(self):
        with self.assertRaises(ValueError):
            load_agent_settings({"W2_EXTRACTION_MODE": "sample-ish"})

    def test_document_intelligence_mode_requires_endpoint(self):
        settings = load_agent_settings({"W2_EXTRACTION_MODE": EXTRACTION_MODE_DOCUMENT_INTELLIGENCE})
        adapter = create_extraction_adapter(settings)

        with self.assertRaisesRegex(RuntimeError, "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"):
            adapter.extract({"blobUri": "https://example/w2.pdf"})

    def test_enterprise_settings_are_loaded_from_environment(self):
        settings = load_agent_settings(
            {
                "APP_ENV": "uat",
                "W2_EXTRACTION_MODE": EXTRACTION_MODE_DOCUMENT_INTELLIGENCE,
                "W2_VALIDATION_STRICTNESS": VALIDATION_STRICTNESS_STRICT,
                "HUMAN_REVIEW_MODE": HUMAN_REVIEW_MODE_QUEUE,
                "COMPLIANCE_MODE": COMPLIANCE_MODE_REGULATED,
                "LOW_CONFIDENCE_THRESHOLD": "0.9",
                "REQUIRE_MASKED_PII_IN_LOGS": "true",
                "AUDIT_EVENT_ENABLED": "true",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4.1-prod",
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "https://example.cognitiveservices.azure.com/",
                "TAX_FACT_PERSISTENCE_MODE": TAX_FACT_PERSISTENCE_COSMOS,
                "AZURE_COSMOS_ENDPOINT": "https://example.documents.azure.com:443/",
                "AZURE_COSMOS_DATABASE_NAME": "tax-intelligence",
                "AZURE_COSMOS_CONTAINER_NAME": "tax-facts",
                "ALLOW_FULL_PII_PERSISTENCE": "false",
            }
        )

        self.assertEqual(settings.validation_strictness, VALIDATION_STRICTNESS_STRICT)
        self.assertEqual(settings.human_review_mode, HUMAN_REVIEW_MODE_QUEUE)
        self.assertEqual(settings.compliance_mode, COMPLIANCE_MODE_REGULATED)
        self.assertEqual(settings.low_confidence_threshold, 0.9)
        self.assertEqual(settings.azure_openai_deployment_name, "gpt-4.1-prod")
        self.assertEqual(
            settings.as_runtime_metadata()["azureOpenAIDeploymentName"],
            "gpt-4.1-prod",
        )
        self.assertEqual(settings.tax_fact_persistence_mode, TAX_FACT_PERSISTENCE_COSMOS)
        self.assertEqual(settings.cosmos_database_name, "tax-intelligence")
        self.assertEqual(settings.cosmos_container_name, "tax-facts")
        self.assertFalse(settings.allow_full_pii_persistence)

    def test_prod_cannot_use_local_extraction(self):
        with self.assertRaisesRegex(ValueError, "APP_ENV=prod cannot use"):
            load_agent_settings({"APP_ENV": APP_ENV_PROD})

    def test_prod_requires_regulated_compliance(self):
        with self.assertRaisesRegex(ValueError, "COMPLIANCE_MODE=regulated"):
            load_agent_settings(
                {
                    "APP_ENV": APP_ENV_PROD,
                    "W2_EXTRACTION_MODE": EXTRACTION_MODE_DOCUMENT_INTELLIGENCE,
                    "HUMAN_REVIEW_MODE": HUMAN_REVIEW_MODE_QUEUE,
                    "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "https://example.cognitiveservices.azure.com/",
                }
            )

    def test_prod_cannot_use_local_json_persistence(self):
        with self.assertRaisesRegex(ValueError, "TAX_FACT_PERSISTENCE_MODE=local-json"):
            load_agent_settings(
                {
                    "APP_ENV": APP_ENV_PROD,
                    "W2_EXTRACTION_MODE": EXTRACTION_MODE_DOCUMENT_INTELLIGENCE,
                    "HUMAN_REVIEW_MODE": HUMAN_REVIEW_MODE_QUEUE,
                    "COMPLIANCE_MODE": COMPLIANCE_MODE_REGULATED,
                    "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "https://example.cognitiveservices.azure.com/",
                    "TAX_FACT_PERSISTENCE_MODE": TAX_FACT_PERSISTENCE_LOCAL_JSON,
                }
            )

    def test_prod_requires_durable_tax_fact_persistence(self):
        with self.assertRaisesRegex(ValueError, "durable TAX_FACT_PERSISTENCE_MODE"):
            load_agent_settings(
                {
                    "APP_ENV": APP_ENV_PROD,
                    "W2_EXTRACTION_MODE": EXTRACTION_MODE_DOCUMENT_INTELLIGENCE,
                    "HUMAN_REVIEW_MODE": HUMAN_REVIEW_MODE_QUEUE,
                    "COMPLIANCE_MODE": COMPLIANCE_MODE_REGULATED,
                    "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "https://example.cognitiveservices.azure.com/",
                }
            )

    def test_cosmos_persistence_requires_endpoint_database_and_container(self):
        with self.assertRaisesRegex(ValueError, "AZURE_COSMOS_ENDPOINT"):
            load_agent_settings({"TAX_FACT_PERSISTENCE_MODE": TAX_FACT_PERSISTENCE_COSMOS})

    def test_parse_dotenv_reads_simple_key_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text(
                "\n".join(
                    [
                        "# comment",
                        "APP_ENV=local",
                        "QUOTED='hello world'",
                        'DOUBLE_QUOTED="hello again"',
                    ]
                ),
                encoding="utf-8",
            )

            values = parse_dotenv(dotenv_path)

        self.assertEqual(values["APP_ENV"], "local")
        self.assertEqual(values["QUOTED"], "hello world")
        self.assertEqual(values["DOUBLE_QUOTED"], "hello again")

    def test_load_environment_uses_dotenv_for_missing_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text("APP_ENV=local\nW2_EXTRACTION_MODE=local\n", encoding="utf-8")

            values = load_environment(dotenv_path)

        self.assertEqual(values["APP_ENV"], "local")
        self.assertEqual(values["W2_EXTRACTION_MODE"], "local")

    def test_process_environment_overrides_dotenv_values(self):
        previous_value = __import__("os").environ.get("W2_EXTRACTION_MODE")
        __import__("os").environ["W2_EXTRACTION_MODE"] = EXTRACTION_MODE_DOCUMENT_INTELLIGENCE
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                dotenv_path = Path(temp_dir) / ".env"
                dotenv_path.write_text("W2_EXTRACTION_MODE=local\n", encoding="utf-8")

                values = load_environment(dotenv_path)
        finally:
            if previous_value is None:
                __import__("os").environ.pop("W2_EXTRACTION_MODE", None)
            else:
                __import__("os").environ["W2_EXTRACTION_MODE"] = previous_value

        self.assertEqual(values["W2_EXTRACTION_MODE"], EXTRACTION_MODE_DOCUMENT_INTELLIGENCE)


if __name__ == "__main__":
    unittest.main()
