import json
import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from foundry_agents.tools.w2_pipeline_tools import TOOL_REGISTRY


AGENT_ROOT = SRC_ROOT / "foundry_agents"


class FoundryBindingTests(unittest.TestCase):
    def test_tool_manifest_matches_python_registry(self):
        manifest_path = AGENT_ROOT / "tools" / "w2_pipeline_tools.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        manifest_tools = {tool["name"] for tool in manifest["tools"]}

        self.assertEqual(manifest_tools, set(TOOL_REGISTRY))

    def test_agent_yaml_references_existing_prompt_tool_and_eval_files(self):
        agent_yaml = (AGENT_ROOT / "agent.yaml").read_text(encoding="utf-8")

        self.assertIn("prompts/supervisor.md", agent_yaml)
        self.assertIn("tools/w2_pipeline_tools.json", agent_yaml)
        self.assertIn("eval.yaml", agent_yaml)
        self.assertTrue((AGENT_ROOT / "prompts" / "supervisor.md").exists())
        self.assertTrue((AGENT_ROOT / "tools" / "w2_pipeline_tools.json").exists())
        self.assertTrue((AGENT_ROOT / "eval.yaml").exists())

    def test_prompt_files_reference_governed_tools(self):
        supervisor_prompt = (AGENT_ROOT / "prompts" / "supervisor.md").read_text(
            encoding="utf-8"
        )

        for tool_name in TOOL_REGISTRY:
            if tool_name in {
                "get_runtime_configuration",
                "persist_completed_w2_pipeline",
            }:
                continue
            self.assertIn(tool_name, supervisor_prompt)

    def test_metadata_references_local_eval_dataset(self):
        metadata = (AGENT_ROOT / ".foundry" / "agent-metadata.yaml").read_text(
            encoding="utf-8"
        )

        self.assertIn(".foundry/datasets/w2_orchestration_smoke.jsonl", metadata)
        self.assertTrue(
            (
                AGENT_ROOT
                / ".foundry"
                / "datasets"
                / "w2_orchestration_smoke.jsonl"
            ).exists()
        )

    def test_foundry_tools_openapi_operations_match_registry(self):
        openapi_path = (
            SRC_ROOT / "services" / "foundry-tools" / "openapi.json"
        )
        openapi = json.loads(openapi_path.read_text(encoding="utf-8"))

        operation_ids = {
            operation["operationId"]
            for path in openapi["paths"].values()
            for operation in path.values()
        }

        self.assertEqual(operation_ids, set(TOOL_REGISTRY))


if __name__ == "__main__":
    unittest.main()
