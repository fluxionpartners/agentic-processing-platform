"""Utility helpers for Azure AI Projects SDK operations."""

import json
import os
from typing import Any, Dict, Optional

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from foundry_agents.config import AgentSettings
from foundry_agents.utils.azure_mock import MockAIProjectClient

def get_project_client(settings: AgentSettings) -> Any:
    """Instantiate AIProjectClient or Mock client depending on settings/environment."""
    import urllib.parse
    conn_str = os.environ.get("AZURE_AI_PROJECT_CONNECTION_STRING") or ""
    if not conn_str:
        endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
        sub_id = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
        rg_name = os.environ.get("AZURE_RESOURCE_GROUP", "")
        if endpoint and sub_id and rg_name:
            try:
                parsed = urllib.parse.urlparse(endpoint)
                host = parsed.netloc
                project_name = parsed.path.rstrip("/").split("/")[-1]
                if host and project_name:
                    conn_str = f"{host};{sub_id};{rg_name};{project_name}"
            except Exception:
                pass

    # If connection string is missing or local/test app env, use mock client
    if not conn_str or settings.app_env in ["local", "test"]:
        return MockAIProjectClient()
        
    return AIProjectClient.from_connection_string(
        conn_str=conn_str,
        credential=DefaultAzureCredential()
    )

def reconstruct_state_from_thread(project_client: Any, thread_id: str) -> Dict[str, Any]:
    """Reconstruct pipeline state dynamically from thread messages."""
    messages = project_client.agents.list_messages(thread_id=thread_id)
    state = {}
    
    # Pass 1: Parse user inputs (from oldest to newest)
    user_payload = {}
    for msg in reversed(getattr(messages, "data", [])):
        if msg.role == "user":
            content_text = ""
            if isinstance(msg.content, list):
                content_text = msg.content[0].text.value if hasattr(msg.content[0], "text") else getattr(msg.content[0], "value", "")
            else:
                content_text = msg.content
            try:
                user_payload = json.loads(content_text)
            except Exception:
                pass
            break
            
    state.update(user_payload)
    if "correlationId" in state:
        state["pipelineId"] = f"pipeline-{state['correlationId']}"
        
    # Pass 2: Parse assistant inputs (from oldest to newest)
    for msg in reversed(getattr(messages, "data", [])):
        if msg.role == "assistant":
            content_text = ""
            if isinstance(msg.content, list):
                content_text = msg.content[0].text.value if hasattr(msg.content[0], "text") else getattr(msg.content[0], "value", "")
            else:
                content_text = msg.content
            try:
                res = json.loads(content_text)
                
                # Check for wrapped result or root fields
                if "humanReviewResult" in res:
                    state["humanReviewResult"] = res["humanReviewResult"]
                if "intakeStatus" in res:
                    state["intakeResult"] = res
                if "extractionStatus" in res:
                    state["extractionResult"] = res
                if "validationStatus" in res:
                    state["validationResult"] = res
                if "mappingStatus" in res:
                    state["mappingResult"] = res
                if "generationStatus" in res:
                    state["formGenerationResult"] = res
                if "complianceStatus" in res:
                    state["complianceResult"] = res
                    state["finalResult"] = res
            except Exception:
                pass
                
    return state
