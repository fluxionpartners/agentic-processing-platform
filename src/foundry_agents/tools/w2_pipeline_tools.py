"""Callable tool bindings for Foundry agents and MCP hosts.

These functions are intentionally thin wrappers around the governed agent
workers. They support thread-based native runs in the Azure AI Projects environment.
"""

import json
from typing import Any, Callable, Dict

from foundry_agents.compliance.agent import ComplianceAgent
from foundry_agents.config import AgentSettings, load_agent_settings
from foundry_agents.extraction.agent import ExtractionAgent
from foundry_agents.form_generation.agent import Form1040GenerationAgent
from foundry_agents.human_review.agent import HumanReviewAgent
from foundry_agents.intake.agent import IntakeAgent
from foundry_agents.persistence import (
    persist_tax_pipeline_checkpoint,
    persist_tax_pipeline_state,
)
from foundry_agents.pipeline import process_w2_ingestion_event, AgentPipeline
from foundry_agents.supervisor.orchestrator import SupervisorOrchestrator
from foundry_agents.tax_mapping.agent import TaxMappingAgent
from foundry_agents.validation.agent import ValidationAgent
from foundry_agents.utils.azure_helpers import get_project_client


ToolCallable = Callable[[Dict[str, Any]], Dict[str, Any]]


def run_w2_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run the complete W-2 orchestration pipeline from an intake event."""
    return process_w2_ingestion_event(payload, settings=load_agent_settings())


def start_w2_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create the initial orchestrator state for an intake event."""
    settings = load_agent_settings()
    orchestrator = SupervisorOrchestrator(settings=settings)
    # Instantiate the pipeline/thread
    result = orchestrator.run(payload)
    return result


def _get_thread_context(payload: Dict[str, Any]) -> tuple:
    settings = load_agent_settings()
    project_client = get_project_client(settings)
    thread_id = payload.get("threadId") or payload.get("thread_id")
    if not thread_id:
        thread = project_client.agents.create_thread()
        thread_id = thread.id
        project_client.agents.create_message(
            thread_id=thread_id,
            role="user",
            content=json.dumps(payload)
        )
    return thread_id, project_client, settings


def process_w2_intake(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run the intake worker for an already-uploaded W-2 document."""
    thread_id, project_client, settings = _get_thread_context(payload)
    run = IntakeAgent.process(thread_id, project_client, settings)
    return {
        "threadId": thread_id,
        "runId": run.id,
        "status": run.status,
    }


def extract_w2_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract normalized W-2 facts using the configured extraction adapter."""
    thread_id, project_client, settings = _get_thread_context(payload)
    run = ExtractionAgent.process(thread_id, project_client, settings)
    return {
        "threadId": thread_id,
        "runId": run.id,
        "status": run.status,
    }


def validate_w2_facts(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate normalized W-2 facts and decide whether review is needed."""
    thread_id, project_client, settings = _get_thread_context(payload)
    run = ValidationAgent.process(thread_id, project_client, settings)
    return {
        "threadId": thread_id,
        "runId": run.id,
        "status": run.status,
    }


def submit_w2_human_review(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create or route a human-review packet for flagged W-2 facts."""
    settings = load_agent_settings()
    # Human review remains a custom python adapter run outside the thread container
    return HumanReviewAgent.process(payload, settings)


def map_w2_tax_facts(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Map validated W-2 facts into 1040-ready and planning facts."""
    thread_id, project_client, settings = _get_thread_context(payload)
    run = TaxMappingAgent.process(thread_id, project_client, settings)
    return {
        "threadId": thread_id,
        "runId": run.id,
        "status": run.status,
    }


def generate_form_1040_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a Form 1040 artifact from mapped tax facts."""
    thread_id, project_client, settings = _get_thread_context(payload)
    run = Form1040GenerationAgent.process(thread_id, project_client, settings)
    return {
        "threadId": thread_id,
        "runId": run.id,
        "status": run.status,
    }


def evaluate_w2_compliance(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate compliance controls and emit an audit envelope."""
    thread_id, project_client, settings = _get_thread_context(payload)
    run = ComplianceAgent.process(thread_id, project_client, settings)
    return {
        "threadId": thread_id,
        "runId": run.id,
        "status": run.status,
    }


def persist_w2_pipeline_checkpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a governed checkpoint for the supplied pipeline state."""
    # Checkpoint methods are removed/stubbed out as they are managed via native threads.
    # Return a dummy success payload to keep tooling compat.
    return {
        "persistenceStatus": "skipped",
        "message": "Manual checkpointing is replaced by native thread tracking.",
    }


def persist_completed_w2_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist the governed final pipeline state."""
    settings = load_agent_settings()
    state = payload.get("state") or payload
    return persist_tax_pipeline_state(state, settings)


def get_runtime_configuration(_: Dict[str, Any]) -> Dict[str, Any]:
    """Return non-secret runtime configuration visible to an orchestrating agent."""
    settings: AgentSettings = load_agent_settings()
    return settings.as_runtime_metadata()


TOOL_REGISTRY: Dict[str, ToolCallable] = {
    "run_w2_pipeline": run_w2_pipeline,
    "start_w2_pipeline": start_w2_pipeline,
    "process_w2_intake": process_w2_intake,
    "extract_w2_document": extract_w2_document,
    "validate_w2_facts": validate_w2_facts,
    "submit_w2_human_review": submit_w2_human_review,
    "map_w2_tax_facts": map_w2_tax_facts,
    "generate_form_1040_document": generate_form_1040_document,
    "evaluate_w2_compliance": evaluate_w2_compliance,
    "persist_w2_pipeline_checkpoint": persist_w2_pipeline_checkpoint,
    "persist_completed_w2_pipeline": persist_completed_w2_pipeline,
    "get_runtime_configuration": get_runtime_configuration,
}
