import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from foundry_agents.config import (
    AgentSettings,
    TAX_FACT_PERSISTENCE_COSMOS,
    TAX_FACT_PERSISTENCE_LOCAL_JSON,
)
from foundry_agents.pipeline import AgentPipeline
from foundry_agents.persistence.store import (
    CosmosTaxFactStore,
    LocalJsonTaxFactStore,
    build_tax_fact_record,
)


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
    @classmethod
    def setUpClass(cls):
        cls.real_modules = {}
        for mod_name in ["azure", "azure.cosmos", "azure.identity"]:
            if mod_name in sys.modules:
                cls.real_modules[mod_name] = sys.modules[mod_name]

        cls.mock_cosmos = MagicMock()
        cls.mock_identity = MagicMock()
        sys.modules["azure"] = MagicMock()
        sys.modules["azure.cosmos"] = cls.mock_cosmos
        sys.modules["azure.identity"] = cls.mock_identity

    @classmethod
    def tearDownClass(cls):
        for mod_name in ["azure", "azure.cosmos", "azure.identity"]:
            if mod_name in cls.real_modules:
                sys.modules[mod_name] = cls.real_modules[mod_name]
            else:
                sys.modules.pop(mod_name, None)

    def setUp(self):
        CosmosTaxFactStore._client_cache.clear()
        self.mock_cosmos.CosmosClient.reset_mock()
        self.mock_identity.DefaultAzureCredential.reset_mock()

        mock_client = self.mock_cosmos.CosmosClient.return_value
        mock_db = mock_client.get_database_client.return_value
        mock_container = mock_db.get_container_client.return_value

        mock_container.read_item.side_effect = None
        mock_container.read_item.return_value = MagicMock()
        mock_container.query_items.side_effect = None
        mock_container.query_items.return_value = MagicMock()
        mock_container.upsert_item.side_effect = None
        mock_container.upsert_item.return_value = MagicMock()

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

    def test_cosmos_store_uses_default_credentials(self):
        settings = AgentSettings(
            tax_fact_persistence_mode=TAX_FACT_PERSISTENCE_COSMOS,
            cosmos_endpoint="https://example.documents.azure.com:443/",
            cosmos_database_name="tax-intelligence",
            cosmos_container_name="tax-facts",
            cosmos_key="",
        )
        self.mock_cosmos.CosmosClient.reset_mock()
        self.mock_identity.DefaultAzureCredential.reset_mock()

        mock_client = self.mock_cosmos.CosmosClient.return_value
        mock_db = mock_client.get_database_client.return_value
        mock_container = mock_db.get_container_client.return_value
        mock_container.upsert_item.return_value = {"_etag": "etag-002"}

        record = build_tax_fact_record(
            {
                "correlationId": "cosmos-test-002",
                "pipelineId": "pipeline-cosmos-test-002",
                "tenantId": "tenant-002",
                "taxpayerId": "taxpayer-456",
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

        store = CosmosTaxFactStore(settings)
        result = store.save(record)

        self.assertEqual(result["persistenceStatus"], "saved")
        self.assertEqual(result["etag"], "etag-002")
        self.mock_identity.DefaultAzureCredential.assert_called_once()
        self.mock_cosmos.CosmosClient.assert_called_once_with(
            url="https://example.documents.azure.com:443/",
            credential=self.mock_identity.DefaultAzureCredential.return_value
        )

    def test_cosmos_store_uses_explicit_key(self):
        settings = AgentSettings(
            tax_fact_persistence_mode=TAX_FACT_PERSISTENCE_COSMOS,
            cosmos_endpoint="https://example.documents.azure.com:443/",
            cosmos_database_name="tax-intelligence",
            cosmos_container_name="tax-facts",
            cosmos_key="some-secret-key",
        )
        self.mock_cosmos.CosmosClient.reset_mock()
        mock_client = self.mock_cosmos.CosmosClient.return_value
        mock_db = mock_client.get_database_client.return_value
        mock_container = mock_db.get_container_client.return_value
        mock_container.upsert_item.return_value = {"_etag": "etag-003"}

        record = build_tax_fact_record(
            {
                "correlationId": "cosmos-test-003",
                "pipelineId": "pipeline-cosmos-test-003",
                "tenantId": "tenant-002",
                "taxpayerId": "taxpayer-456",
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

        store = CosmosTaxFactStore(settings)
        result = store.save(record)

        self.assertEqual(result["persistenceStatus"], "saved")
        self.assertEqual(result["etag"], "etag-003")
        self.mock_cosmos.CosmosClient.assert_called_once_with(
            url="https://example.documents.azure.com:443/",
            credential="some-secret-key"
        )

    def test_cosmos_store_caches_container_client(self):
        settings = AgentSettings(
            tax_fact_persistence_mode=TAX_FACT_PERSISTENCE_COSMOS,
            cosmos_endpoint="https://example.documents.azure.com:443/",
            cosmos_database_name="tax-intelligence",
            cosmos_container_name="tax-facts",
            cosmos_key="some-secret-key-cache",
        )
        self.mock_cosmos.CosmosClient.reset_mock()
        mock_client = self.mock_cosmos.CosmosClient.return_value
        mock_db = mock_client.get_database_client.return_value
        mock_container = mock_db.get_container_client.return_value
        mock_container.upsert_item.return_value = {"_etag": "etag-004"}

        record = build_tax_fact_record(
            {
                "correlationId": "cosmos-test-004",
                "pipelineId": "pipeline-cosmos-test-004",
                "tenantId": "tenant-002",
                "taxpayerId": "taxpayer-456",
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

        CosmosTaxFactStore._client_cache.clear()

        store1 = CosmosTaxFactStore(settings)
        store1.save(record)

        store2 = CosmosTaxFactStore(settings)
        store2.save(record)

        self.mock_cosmos.CosmosClient.assert_called_once()

    def test_local_json_store_load(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = AgentSettings(
                tax_fact_persistence_mode=TAX_FACT_PERSISTENCE_LOCAL_JSON,
                tax_fact_persistence_path=temp_dir,
            )
            record = build_tax_fact_record(
                {
                    "correlationId": "json-load-001",
                    "tenantId": "tenant-json",
                    "taxpayerId": "taxpayer-json",
                    "taxYear": 2024,
                    "documentName": "W2.pdf",
                    "blobUri": "https://example/w2.pdf",
                    "extractionResult": {
                        "extractionStatus": "success",
                        "extractedData": {"taxYear": 2024, "employeeSSN": "123-45-6789"},
                    },
                },
                settings,
                "extraction",
            )
            store = LocalJsonTaxFactStore(temp_dir)
            store.save(record)

            loaded = store.load("tax-facts-json-load-001")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["recordId"], "tax-facts-json-load-001")
            self.assertEqual(loaded["tenantId"], "tenant-json")
            self.assertEqual(loaded["extraction"]["extractedData"]["employeeSSN"], "XXX-XX-6789")
            self.assertIsNone(store.load("tax-facts-non-existent"))

    def test_cosmos_store_load_with_partition_key(self):
        settings = AgentSettings(
            tax_fact_persistence_mode=TAX_FACT_PERSISTENCE_COSMOS,
            cosmos_endpoint="https://example.documents.azure.com:443/",
            cosmos_database_name="tax-intelligence",
            cosmos_container_name="tax-facts",
            cosmos_key="some-secret-key",
        )
        self.mock_cosmos.CosmosClient.reset_mock()
        mock_client = self.mock_cosmos.CosmosClient.return_value
        mock_db = mock_client.get_database_client.return_value
        mock_container = mock_db.get_container_client.return_value

        mock_container.read_item.return_value = {
            "id": "tax-facts-load-001",
            "correlationId": "load-001",
            "tenantId": "tenant-cosmos",
        }

        store = CosmosTaxFactStore(settings)
        loaded = store.load("tax-facts-load-001", partition_key="tenant-cosmos")

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["id"], "tax-facts-load-001")
        mock_container.read_item.assert_called_once_with(
            item="tax-facts-load-001",
            partition_key="tenant-cosmos"
        )

    def test_cosmos_store_load_without_partition_key_fallback_to_query(self):
        settings = AgentSettings(
            tax_fact_persistence_mode=TAX_FACT_PERSISTENCE_COSMOS,
            cosmos_endpoint="https://example.documents.azure.com:443/",
            cosmos_database_name="tax-intelligence",
            cosmos_container_name="tax-facts",
            cosmos_key="some-secret-key",
        )
        self.mock_cosmos.CosmosClient.reset_mock()
        mock_client = self.mock_cosmos.CosmosClient.return_value
        mock_db = mock_client.get_database_client.return_value
        mock_container = mock_db.get_container_client.return_value

        mock_container.query_items.return_value = [
            {
                "id": "tax-facts-load-002",
                "correlationId": "load-002",
                "tenantId": "tenant-cosmos-2",
            }
        ]

        store = CosmosTaxFactStore(settings)
        loaded = store.load("tax-facts-load-002")

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["id"], "tax-facts-load-002")
        mock_container.query_items.assert_called_once()

    def test_cosmos_store_load_not_found(self):
        settings = AgentSettings(
            tax_fact_persistence_mode=TAX_FACT_PERSISTENCE_COSMOS,
            cosmos_endpoint="https://example.documents.azure.com:443/",
            cosmos_database_name="tax-intelligence",
            cosmos_container_name="tax-facts",
            cosmos_key="some-secret-key",
        )
        self.mock_cosmos.CosmosClient.reset_mock()
        mock_client = self.mock_cosmos.CosmosClient.return_value
        mock_db = mock_client.get_database_client.return_value
        mock_container = mock_db.get_container_client.return_value

        class MockCosmosError(Exception):
            def __init__(self):
                self.status_code = 404
        mock_container.read_item.side_effect = MockCosmosError()

        store = CosmosTaxFactStore(settings)
        loaded = store.load("tax-facts-load-003", partition_key="tenant-cosmos-3")
        self.assertIsNone(loaded)

    def test_pipeline_resumption_and_idempotency(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = AgentSettings(
                tax_fact_persistence_mode=TAX_FACT_PERSISTENCE_LOCAL_JSON,
                tax_fact_persistence_path=temp_dir,
                human_review_mode="manual",
            )

            correlation_id = "resume-test-001"
            pipeline = AgentPipeline(settings=settings)

            trigger_payload = {
                "correlationId": correlation_id,
                "tenantId": "tenant-resume",
                "taxpayerId": "taxpayer-resume",
                "documentName": "W2.pdf",
                "blobUri": "https://example/w2.pdf",
                "taxYear": 2024,
                "mockExtractionOverrides": {"employeeSSN": "123-45-6789", "employerEIN": ""},
            }

            first_run_result = pipeline.run(trigger_payload)
            self.assertEqual(first_run_result["status"], "waiting")
            self.assertEqual(first_run_result["nextStep"], "awaiting_human_decision")

            store = LocalJsonTaxFactStore(temp_dir)
            checkpoint = store.load(f"tax-facts-{correlation_id}")
            self.assertIsNotNone(checkpoint)
            self.assertEqual(checkpoint["checkpointStage"], "await_human_review")

            checkpoint["humanReview"] = {
                "status": "approved",
                "reason": "resolved",
                "submittedForReview": "2024-06-04T12:00:00Z",
                "assignedQueue": "queue",
            }
            store.save(checkpoint)

            resume_pipeline = AgentPipeline(settings=settings)
            second_run_result = resume_pipeline.run(trigger_payload)

            self.assertEqual(second_run_result["status"], "complete")

            recorded_stages = [step["stage"] for step in resume_pipeline.execution_log]
            self.assertNotIn("intake", recorded_stages)
            self.assertNotIn("extraction", recorded_stages)
            self.assertNotIn("validation", recorded_stages)
            self.assertIn("tax_mapping", recorded_stages)
            self.assertIn("compliance", recorded_stages)


if __name__ == "__main__":
    unittest.main()
