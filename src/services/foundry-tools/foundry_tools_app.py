import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Tuple


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from foundry_agents.tools.w2_pipeline_tools import TOOL_REGISTRY
from foundry_agents.config import load_agent_settings
from foundry_agents.persistence.store import create_tax_fact_store
from foundry_agents.pipeline import process_w2_ingestion_event


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


def process_service_bus_event(message_body: str) -> Dict[str, Any]:
    """Run the governed pipeline for an intake event from Service Bus."""
    try:
        payload = json.loads(message_body)
    except json.JSONDecodeError as exc:
        raise ValueError("Service Bus message body must be valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Service Bus message body must be a JSON object.")

    required_fields = ["correlationId", "tenantId", "taxpayerId", "documentName", "blobUri"]
    missing = [field for field in required_fields if not payload.get(field)]
    if missing:
        raise ValueError(f"Service Bus event missing required fields: {', '.join(missing)}")

    return process_w2_ingestion_event(payload, settings=load_agent_settings())


def get_pipeline_status(correlation_id: str, tenant_id: str = "") -> Tuple[Dict[str, Any], int]:
    """Return persisted pipeline status for browser polling and smoke tests."""
    normalized_correlation_id = (correlation_id or "").strip()
    if not normalized_correlation_id:
        return {
            "error": "invalid_request",
            "message": "correlationId is required.",
        }, 400

    settings = load_agent_settings()
    record_id = f"tax-facts-{normalized_correlation_id}"
    store = create_tax_fact_store(settings)
    record = store.load(record_id, partition_key=tenant_id.strip() or None)

    if not record:
        return {
            "status": "processing",
            "correlationId": normalized_correlation_id,
            "recordFound": False,
            "message": "Pipeline status is not available yet.",
        }, 202

    lifecycle_status = record.get("lifecycleStatus") or record.get("checkpointStage")
    status_code = 200 if lifecycle_status == "complete" else 202
    return {
        "status": lifecycle_status,
        "correlationId": normalized_correlation_id,
        "recordFound": True,
        "checkpointStage": record.get("checkpointStage"),
        "tenantId": record.get("tenantId"),
        "taxpayerId": record.get("taxpayerId"),
        "taxYear": record.get("taxYear"),
        "document": record.get("document", {}),
        "extraction": {
            "status": record.get("extraction", {}).get("status"),
            "overallConfidence": record.get("extraction", {}).get("overallConfidence"),
        },
        "validation": record.get("validation", {}),
        "humanReview": record.get("humanReview", {}),
        "taxPlanning": {
            "mappingStatus": record.get("taxPlanning", {}).get("mappingStatus"),
            "form1040": record.get("taxPlanning", {}).get("form1040", {}),
        },
        "form1040Document": record.get("form1040Document", {}),
        "compliance": record.get("compliance", {}),
        "governance": record.get("governance", {}),
        "updatedAt": record.get("updatedAt"),
    }, status_code


def json_response(func_module: Any, payload: Dict[str, Any], status_code: int):
    return func_module.HttpResponse(
        json.dumps(payload),
        status_code=status_code,
        mimetype="application/json",
    )
