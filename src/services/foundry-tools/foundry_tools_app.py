import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Tuple


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from foundry_agents.tools.w2_pipeline_tools import TOOL_REGISTRY


ROUTE_TO_TOOL = {
    "run-w2-pipeline": "run_w2_pipeline",
    "start-w2-pipeline": "start_w2_pipeline",
    "process-w2-intake": "process_w2_intake",
    "extract-w2-document": "extract_w2_document",
    "validate-w2-facts": "validate_w2_facts",
    "submit-w2-human-review": "submit_w2_human_review",
    "map-w2-tax-facts": "map_w2_tax_facts",
    "generate-form-1040-document": "generate_form_1040_document",
    "evaluate-w2-compliance": "evaluate_w2_compliance",
    "persist-w2-pipeline-checkpoint": "persist_w2_pipeline_checkpoint",
    "persist-completed-w2-pipeline": "persist_completed_w2_pipeline",
    "get-runtime-configuration": "get_runtime_configuration",
}


def parse_json_body(req: Any) -> Tuple[Dict[str, Any], str]:
    """Parse an Azure Functions request body into a JSON object."""
    try:
        payload = req.get_json()
    except ValueError:
        return {}, "Request body must be valid JSON."

    if payload is None:
        return {}, {}
    if not isinstance(payload, dict):
        return {}, "Request body must be a JSON object."
    return payload, ""


def execute_tool(route_name: str, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """Execute a registered tool by its HTTP route name."""
    tool_name = ROUTE_TO_TOOL.get(route_name)
    if not tool_name:
        return {"error": "unknown_tool_route", "route": route_name}, 404

    tool = TOOL_REGISTRY.get(tool_name)
    if not tool:
        return {"error": "tool_not_registered", "toolName": tool_name}, 500

    try:
        result = tool(payload)
    except Exception as exc:
        logging.exception("Foundry tool execution failed: %s", tool_name)
        return {
            "error": "tool_execution_failed",
            "toolName": tool_name,
            "message": str(exc),
        }, 500

    return {
        "toolName": tool_name,
        "result": result,
    }, 200


def json_response(func_module: Any, payload: Dict[str, Any], status_code: int):
    return func_module.HttpResponse(
        json.dumps(payload),
        status_code=status_code,
        mimetype="application/json",
    )
