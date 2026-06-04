import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from foundry_agents.config import (
    AgentSettings,
    TAX_FACT_PERSISTENCE_COSMOS,
    TAX_FACT_PERSISTENCE_LOCAL_JSON,
)
from foundry_agents.pipeline import AgentPipeline
from foundry_agents.persistence.store import CosmosTaxFactStore, build_tax_fact_record


class FakeCosmosContainer:
    def __init__(self):
        self.upserted_item = None

    def upsert_item(self, body):
        self.upserted_item = body
        return {"_etag": "etag-001"}


class TestableCosmosTaxFactStore(CosmosTaxFactStore):
    def __init__(self, settings, container):
        super().__init__(settings)
        self.container = container

    def _get_container(self):
        return self.container


class TaxFactPersistenceTests(unittest.TestCase):
    def test_pipeline_persists_governed_tax_facts_with_masked_identity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = AgentSettings(
                tax_fact_persistence_mode=TAX_FACT_PERSISTENCE_LOCAL_JSON,
                tax_fact_persistence_path=temp_dir,
            )
            result = AgentPipeline(settings=settings).run(
                {
                    "correlationId": "persist-test-001",
                    "tenantId": "tenant-001",
                    "taxpayerId": "taxpayer-123",
                    "documentName": "W2.pdf",
                    "blobUri": "https://example.blob.core.windows.net/raw-w2/W2.pdf",
                    "taxYear": 2024,
                    "mockExtractionOverrides": {"employeeSSN": "123-45-6789"},
                }
            )

            persistence_result = result["payload"]["persistenceResult"]
            saved_record = json.loads(Path(persistence_result["path"]).read_text(encoding="utf-8"))
            checkpoint_stages = [
                checkpoint["checkpointStage"]
                for checkpoint in result["payload"]["persistenceCheckpoints"]
            ]

        self.assertEqual(persistence_result["persistenceStatus"], "saved")
        self.assertEqual(persistence_result["checkpointStage"], "complete")
        self.assertEqual(persistence_result["lifecycleStatus"], "complete")
        self.assertFalse(persistence_result["containsFullPii"])
        self.assertEqual(
            checkpoint_stages,
            ["intake", "extraction", "validation", "tax_mapping", "compliance"],
        )
        self.assertEqual(saved_record["sensitivityLabel"], "restricted-tax-pii")
        self.assertEqual(saved_record["checkpointStage"], "complete")
        self.assertEqual(saved_record["lifecycleStatus"], "complete")
        self.assertEqual(
            saved_record["extraction"]["extractedData"]["employeeSSN"], "XXX-XX-6789"
        )
        self.assertNotIn("rawResult", saved_record["extraction"])
        self.assertEqual(
            saved_record["taxPlanning"]["normalizedTaxFacts"]["incomeSummary"]["w2Wages"],
            75000.00,
        )
        self.assertFalse(saved_record["governance"]["rawExtractionPersisted"])

    def test_cosmos_store_upserts_governed_record(self):
        settings = AgentSettings(
            tax_fact_persistence_mode=TAX_FACT_PERSISTENCE_COSMOS,
            cosmos_endpoint="https://example.documents.azure.com:443/",
            cosmos_database_name="tax-intelligence",
            cosmos_container_name="tax-facts",
        )
        record = build_tax_fact_record(
            {
                "correlationId": "cosmos-test-001",
                "pipelineId": "pipeline-cosmos-test-001",
                "tenantId": "tenant-001",
                "taxpayerId": "taxpayer-123",
                "taxYear": 2024,
                "documentName": "W2.pdf",
                "blobUri": "https://example.blob.core.windows.net/raw-w2/W2.pdf",
                "extractionResult": {
                    "extractionStatus": "success",
                    "extractedData": {"taxYear": 2024, "employeeSSN": "123-45-6789"},
                },
            },
            settings,
            "extraction",
        )
        container = FakeCosmosContainer()
        store = TestableCosmosTaxFactStore(settings, container)

        result = store.save(record)

        self.assertEqual(result["persistenceStatus"], "saved")
        self.assertEqual(result["mode"], TAX_FACT_PERSISTENCE_COSMOS)
        self.assertEqual(result["etag"], "etag-001")
        self.assertEqual(container.upserted_item["id"], "tax-facts-cosmos-test-001")
        self.assertEqual(container.upserted_item["recordId"], "tax-facts-cosmos-test-001")
        self.assertEqual(container.upserted_item["tenantId"], "tenant-001")
        self.assertEqual(
            container.upserted_item["extraction"]["extractedData"]["employeeSSN"],
            "XXX-XX-6789",
        )


if __name__ == "__main__":
    unittest.main()
