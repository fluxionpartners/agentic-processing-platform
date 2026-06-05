"""Callable tool bindings for Foundry agents and MCP hosts.

These functions are intentionally thin wrappers around the governed agent
workers. A Foundry prompt agent, hosted agent, or MCP server can expose these
functions as tools while keeping the regulated processing logic in Python.
"""

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
from foundry_agents.pipeline import process_w2_ingestion_event
from foundry_agents.supervisor.orchestrator import SupervisorOrchestrator
from foundry_agents.tax_mapping.agent import TaxMappingAgent
from foundry_agents.validation.agent import ValidationAgent


ToolCallable = Callable[[Dict[str, Any]], Dict[str, Any]]


def run_w2_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run the complete W-2 orchestration pipeline from an intake event."""
    return process_w2_ingestion_event(payload, settings=load_agent_settings())


def start_w2_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create the initial orchestrator state for an intake event."""
    settings = load_agent_settings()
    orchestrator = SupervisorOrchestrator()
    return orchestrator.start_pipeline(payload, runtime_settings=settings.as_runtime_metadata())


def process_w2_intake(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run the intake worker for an already-uploaded W-2 document."""
    return IntakeAgent.process(payload, load_agent_settings())


def extract_w2_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract normalized W-2 facts using the configured extraction adapter."""
    return ExtractionAgent.process(payload, load_agent_settings())


def validate_w2_facts(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate normalized W-2 facts and decide whether review is needed."""
    return ValidationAgent.process(payload, load_agent_settings())


def submit_w2_human_review(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create or route a human-review packet for flagged W-2 facts."""
    return HumanReviewAgent.process(payload, load_agent_settings())


def map_w2_tax_facts(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Map validated W-2 facts into 1040-ready and planning facts."""
    return TaxMappingAgent.process(payload, load_agent_settings())


def generate_form_1040_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a Form 1040 artifact from mapped tax facts."""
    return Form1040GenerationAgent.process(payload, load_agent_settings())


def evaluate_w2_compliance(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate compliance controls and emit an audit envelope."""
    return ComplianceAgent.process(payload, load_agent_settings())


def persist_w2_pipeline_checkpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a governed checkpoint for the supplied pipeline state."""
    settings = load_agent_settings()
    stage = payload.get("checkpointStage") or payload.get("stage")
    state = payload.get("state") or payload
    return persist_tax_pipeline_checkpoint(state, settings, stage)


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
