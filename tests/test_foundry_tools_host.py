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


if __name__ == "__main__":
    unittest.main()
