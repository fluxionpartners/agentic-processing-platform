import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from foundry_agents.tools.w2_pipeline_tools import TOOL_REGISTRY
from foundry_agents.config import load_agent_settings
from foundry_agents.persistence.store import create_tax_fact_store
from foundry_agents.pipeline import process_w2_ingestion_event
from foundry_agents.utils.azure_helpers import get_project_client


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

FOUNDRY_API_VERSION = os.getenv("FOUNDRY_API_VERSION", "v1")
FOUNDRY_PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "").strip().rstrip("/")
FOUNDRY_SUPERVISOR_AGENT_ID = os.getenv("FOUNDRY_SUPERVISOR_AGENT_ID", "").strip()
FOUNDRY_SUPERVISOR_AGENT_NAME = os.getenv(
    "FOUNDRY_SUPERVISOR_AGENT_NAME",
    "foundry-w2-tax-orchestrator",
).strip()


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


def _foundry_access_token() -> str:
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    return credential.get_token("https://ai.azure.com/.default").token


def _foundry_request(
    method: str,
    relative_path: str,
    token: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not FOUNDRY_PROJECT_ENDPOINT:
        raise ValueError("FOUNDRY_PROJECT_ENDPOINT is not configured.")

    separator = "&" if "?" in relative_path else "?"
    url = f"{FOUNDRY_PROJECT_ENDPOINT}{relative_path}{separator}api-version={FOUNDRY_API_VERSION}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Foundry API request failed: {exc.code} {error_body}") from exc

    return json.loads(response_body) if response_body else {}


def _object_id(value: Dict[str, Any]) -> str:
    return str(value.get("id") or value.get("assistant_id") or value.get("thread_id") or "").strip()


def _resolve_supervisor_agent_id(token: str) -> str:
    if FOUNDRY_SUPERVISOR_AGENT_ID:
        return FOUNDRY_SUPERVISOR_AGENT_ID
    if not FOUNDRY_SUPERVISOR_AGENT_NAME:
        raise ValueError("FOUNDRY_SUPERVISOR_AGENT_ID or FOUNDRY_SUPERVISOR_AGENT_NAME must be configured.")

    route_suffix = "/assistants" if FOUNDRY_API_VERSION == "v1" else "/agents"
    response = _foundry_request("GET", route_suffix, token)
    candidates = response.get("data") if isinstance(response.get("data"), list) else response.get("value")
    if not isinstance(candidates, list):
        candidates = []

    for candidate in candidates:
        if isinstance(candidate, dict) and candidate.get("name") == FOUNDRY_SUPERVISOR_AGENT_NAME:
            agent_id = _object_id(candidate)
            if agent_id:
                return agent_id

    raise ValueError(f"Foundry supervisor agent was not found by name: {FOUNDRY_SUPERVISOR_AGENT_NAME}")


def _build_agent_prompt(payload: Dict[str, Any]) -> str:
    safe_payload = {
        "correlationId": payload.get("correlationId"),
        "tenantId": payload.get("tenantId"),
        "taxpayerId": payload.get("taxpayerId"),
        "documentName": payload.get("documentName"),
        "blobUri": payload.get("blobUri"),
        "taxYear": payload.get("taxYear"),
        "executionMode": "foundry-agent",
    }
    return (
        "Run the governed W-2 to draft Form 1040 workflow for this intake event. "
        "Use the available W-2 tax pipeline tools, persist checkpoints, and return only the final status summary.\n\n"
        f"Intake event JSON:\n{json.dumps(safe_payload, indent=2)}"
    )


def invoke_foundry_supervisor_agent(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    required_fields = ["correlationId", "tenantId", "taxpayerId", "documentName", "blobUri"]
    missing = [field for field in required_fields if not payload.get(field)]
    if missing:
        return {
            "error": "invalid_request",
            "message": f"Missing required fields: {', '.join(missing)}",
        }, 400

    try:
        settings = load_agent_settings()
        project_client = get_project_client(settings)

        # Resolve supervisor agent/assistant ID
        agent_id = FOUNDRY_SUPERVISOR_AGENT_ID
        if not agent_id:
            # Fallback: list assistants to find one matching name
            try:
                assistants = project_client.agents.list_agents()
                for asst in getattr(assistants, "data", []):
                    if getattr(asst, "name", "") == FOUNDRY_SUPERVISOR_AGENT_NAME:
                        agent_id = asst.id
                        break
            except Exception:
                pass
        
        if not agent_id:
            agent_id = FOUNDRY_SUPERVISOR_AGENT_NAME

        # Create thread via SDK
        thread = project_client.agents.create_thread(
            metadata={
                "correlationId": str(payload.get("correlationId")),
                "tenantId": str(payload.get("tenantId")),
                "executionMode": "foundry-agent",
            }
        )
        thread_id = thread.id

        # Add initial prompt message
        project_client.agents.create_message(
            thread_id=thread_id,
            role="user",
            content=_build_agent_prompt(payload),
        )

        # Create execution run
        run = project_client.agents.create_run(
            thread_id=thread_id,
            assistant_id=agent_id,
            metadata={
                "correlationId": str(payload.get("correlationId")),
                "tenantId": str(payload.get("tenantId")),
                "executionMode": "foundry-agent",
            },
        )
        run_id = run.id

        run_status = str(run.status or "").lower()
        if bool(payload.get("waitForAgentRun")):
            terminal_statuses = {"completed", "failed", "cancelled", "expired"}
            deadline = time.time() + int(payload.get("agentRunTimeoutSeconds") or 120)
            while run_status not in terminal_statuses and time.time() < deadline:
                time.sleep(2)
                run = project_client.agents.get_run(thread_id=thread_id, run_id=run_id)
                run_status = str(run.status or "").lower()

            if run_status != "completed":
                return {
                    "error": "foundry_agent_run_incomplete",
                    "message": f"Foundry supervisor run ended with status '{run_status or 'unknown'}'.",
                    "correlationId": payload.get("correlationId"),
                    "threadId": thread_id,
                    "runId": run_id,
                    "runStatus": run_status,
                }, 502

        return {
            "status": "accepted",
            "executionMode": "foundry-agent",
            "correlationId": payload.get("correlationId"),
            "threadId": thread_id,
            "runId": run_id,
            "messageId": run_id,
            "runStatus": run_status,
            "agentName": FOUNDRY_SUPERVISOR_AGENT_NAME,
        }, 202
    except Exception as exc:
        logging.exception("Foundry supervisor invocation failed.")
        return {
            "error": "foundry_agent_invocation_failed",
            "message": str(exc),
            "correlationId": payload.get("correlationId"),
        }, 500
