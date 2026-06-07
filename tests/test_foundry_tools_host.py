import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
SERVICE_ROOT = SRC_ROOT / "services" / "foundry-tools"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

MODULE_PATH = SERVICE_ROOT / "foundry_tools_app.py"
spec = importlib.util.spec_from_file_location("foundry_tools_app", MODULE_PATH)
foundry_tools_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(foundry_tools_app)


class FakeRequest:
    def __init__(self, payload=None, raises=False):
        self.payload = payload
        self.raises = raises

    def get_json(self):
        if self.raises:
            raise ValueError("bad json")
        return self.payload


class FoundryToolsHostTests(unittest.TestCase):
    def test_each_route_maps_to_registered_tool(self):
        registry = foundry_tools_app.TOOL_REGISTRY

        for tool_name in foundry_tools_app.ROUTE_TO_TOOL.values():
            self.assertIn(tool_name, registry)

    def test_parse_json_body_rejects_invalid_json(self):
        payload, error = foundry_tools_app.parse_json_body(FakeRequest(raises=True))

        self.assertEqual(payload, {})
        self.assertEqual(error, "Request body must be valid JSON.")

    def test_parse_json_body_rejects_non_object_json(self):
        payload, error = foundry_tools_app.parse_json_body(FakeRequest(payload=[]))

        self.assertEqual(payload, {})
        self.assertEqual(error, "Request body must be a JSON object.")

    def test_execute_tool_uses_route_mapping_and_registry(self):
        with patch.dict(
            foundry_tools_app.TOOL_REGISTRY,
            {"run_w2_pipeline": lambda payload: {"received": payload["correlationId"]}},
        ):
            result, status_code = foundry_tools_app.execute_tool(
                "run-w2-pipeline",
                {"correlationId": "test-123"},
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(result["toolName"], "run_w2_pipeline")
        self.assertEqual(result["result"], {"received": "test-123"})

    def test_execute_tool_returns_404_for_unknown_route(self):
        result, status_code = foundry_tools_app.execute_tool("unknown", {})

        self.assertEqual(status_code, 404)
        self.assertEqual(result["error"], "unknown_tool_route")

    def test_get_pipeline_status_returns_processing_when_record_not_found(self):
        class EmptyStore:
            def load(self, record_id, partition_key=None):
                self.record_id = record_id
                self.partition_key = partition_key
                return None

        store = EmptyStore()
        with patch.object(foundry_tools_app, "load_agent_settings", return_value=object()):
            with patch.object(foundry_tools_app, "create_tax_fact_store", return_value=store):
                result, status_code = foundry_tools_app.get_pipeline_status(
                    "corr-001",
                    "tenant-001",
                )

        self.assertEqual(status_code, 202)
        self.assertEqual(result["status"], "processing")
        self.assertFalse(result["recordFound"])
        self.assertEqual(store.record_id, "tax-facts-corr-001")
        self.assertEqual(store.partition_key, "tenant-001")

    def test_get_pipeline_status_returns_completed_record_summary(self):
        class CompletedStore:
            def load(self, record_id, partition_key=None):
                return {
                    "lifecycleStatus": "complete",
                    "checkpointStage": "complete",
                    "correlationId": "corr-002",
                    "tenantId": "tenant-001",
                    "taxpayerId": "taxpayer-001",
                    "taxYear": 2024,
                    "document": {"documentName": "W2.pdf"},
                    "extraction": {"status": "success", "overallConfidence": 0.96},
                    "validation": {"status": "passed"},
                    "taxPlanning": {"mappingStatus": "success"},
                    "form1040Document": {
                        "status": "success",
                        "artifact": {"artifactId": "form-1040-corr-002"},
                    },
                    "compliance": {"status": "passed"},
                    "governance": {"containsFullPii": False},
                }

        with patch.object(foundry_tools_app, "load_agent_settings", return_value=object()):
            with patch.object(foundry_tools_app, "create_tax_fact_store", return_value=CompletedStore()):
                result, status_code = foundry_tools_app.get_pipeline_status("corr-002")

        self.assertEqual(status_code, 200)
        self.assertEqual(result["status"], "complete")
        self.assertTrue(result["recordFound"])
        self.assertEqual(result["form1040Document"]["artifact"]["artifactId"], "form-1040-corr-002")

    def test_process_service_bus_event_validates_required_fields(self):
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            foundry_tools_app.process_service_bus_event('{"correlationId":"corr-003"}')

    def test_process_service_bus_event_invokes_pipeline(self):
        payload = {
            "correlationId": "corr-004",
            "tenantId": "tenant-001",
            "taxpayerId": "taxpayer-001",
            "documentName": "W2.pdf",
            "blobUri": "https://example/w2.pdf",
        }

        with patch.object(foundry_tools_app, "load_agent_settings", return_value=object()):
            with patch.object(
                foundry_tools_app,
                "process_w2_ingestion_event",
                return_value={"status": "complete", "correlationId": "corr-004"},
            ) as process_mock:
                result = foundry_tools_app.process_service_bus_event(
                    __import__("json").dumps(payload)
                )

        self.assertEqual(result["status"], "complete")
        process_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
