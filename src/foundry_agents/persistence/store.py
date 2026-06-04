import json
from abc import ABC, abstractmethod
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from foundry_agents.config import (
    AgentSettings,
    TAX_FACT_PERSISTENCE_COSMOS,
    TAX_FACT_PERSISTENCE_DISABLED,
    TAX_FACT_PERSISTENCE_LOCAL_JSON,
)
from foundry_agents.time_utils import utc_iso


SENSITIVITY_RESTRICTED_TAX_PII = "restricted-tax-pii"


class TaxFactStore(ABC):
    """Persistence adapter for governed tax facts."""

    @abstractmethod
    def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Persist a governed tax fact record and return storage metadata."""


class DisabledTaxFactStore(TaxFactStore):
    def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "persistenceStatus": "skipped",
            "reason": "TAX_FACT_PERSISTENCE_MODE=disabled",
            "recordId": record["recordId"],
        }


class LocalJsonTaxFactStore(TaxFactStore):
    """Local development store that writes governed JSON records to disk."""

    def __init__(self, root_path: str) -> None:
        self.root_path = Path(root_path)

    def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        tenant_id = _safe_path_part(record.get("tenantId") or "unknown-tenant")
        tax_year = _safe_path_part(str(record.get("taxYear") or "unknown-year"))
        record_id = _safe_path_part(record["recordId"])
        directory = self.root_path / tenant_id / tax_year
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{record_id}.json"
        path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        return {
            "persistenceStatus": "saved",
            "mode": TAX_FACT_PERSISTENCE_LOCAL_JSON,
            "recordId": record["recordId"],
            "path": str(path),
        }


class CosmosTaxFactStore(TaxFactStore):
    """Azure Cosmos DB store for governed tax fact checkpoints."""

    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings

    def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        item = dict(record)
        item["id"] = record["recordId"]
        container = self._get_container()
        response = container.upsert_item(body=item)
        return {
            "persistenceStatus": "saved",
            "mode": TAX_FACT_PERSISTENCE_COSMOS,
            "recordId": record["recordId"],
            "databaseName": self.settings.cosmos_database_name,
            "containerName": self.settings.cosmos_container_name,
            "etag": response.get("_etag") if isinstance(response, dict) else None,
        }

    def _get_container(self) -> Any:
        try:
            from azure.cosmos import CosmosClient
            from azure.identity import DefaultAzureCredential
        except ImportError as exc:
            raise RuntimeError(
                "Cosmos DB persistence requires azure-cosmos and azure-identity. "
                "Install src/foundry_agents/requirements.txt before using "
                "TAX_FACT_PERSISTENCE_MODE=cosmos."
            ) from exc

        credential = self.settings.cosmos_key or DefaultAzureCredential()
        client = CosmosClient(
            url=self.settings.cosmos_endpoint,
            credential=credential,
        )
        database = client.get_database_client(self.settings.cosmos_database_name)
        return database.get_container_client(self.settings.cosmos_container_name)


def persist_tax_pipeline_state(
    pipeline_state: Dict[str, Any], settings: AgentSettings
) -> Dict[str, Any]:
    """Build and store governed tax facts from a completed pipeline state."""
    return persist_tax_pipeline_checkpoint(pipeline_state, settings, "complete")


def persist_tax_pipeline_checkpoint(
    pipeline_state: Dict[str, Any], settings: AgentSettings, checkpoint_stage: str
) -> Dict[str, Any]:
    """Upsert a governed checkpoint for the current pipeline state."""
    record = build_tax_fact_record(pipeline_state, settings, checkpoint_stage)
    store = create_tax_fact_store(settings)
    result = store.save(record)
    result["checkpointStage"] = checkpoint_stage
    result["lifecycleStatus"] = record["lifecycleStatus"]
    result["sensitivityLabel"] = record["sensitivityLabel"]
    result["containsFullPii"] = record["governance"]["containsFullPii"]
    result["persistedAt"] = utc_iso()
    return result


def create_tax_fact_store(settings: AgentSettings) -> TaxFactStore:
    if settings.tax_fact_persistence_mode == TAX_FACT_PERSISTENCE_DISABLED:
        return DisabledTaxFactStore()
    if settings.tax_fact_persistence_mode == TAX_FACT_PERSISTENCE_LOCAL_JSON:
        return LocalJsonTaxFactStore(settings.tax_fact_persistence_path)
    if settings.tax_fact_persistence_mode == TAX_FACT_PERSISTENCE_COSMOS:
        return CosmosTaxFactStore(settings)
    raise ValueError(f"Unsupported tax fact persistence mode: {settings.tax_fact_persistence_mode}")


def build_tax_fact_record(
    pipeline_state: Dict[str, Any], settings: AgentSettings, checkpoint_stage: str = "complete"
) -> Dict[str, Any]:
    extraction_result = pipeline_state.get("extractionResult", {})
    validation_result = pipeline_state.get("validationResult", {})
    human_review_result = pipeline_state.get("humanReviewResult")
    mapping_result = pipeline_state.get("mappingResult", {})
    compliance_result = pipeline_state.get("finalResult", {})
    extracted_data = _sanitize_extracted_data(
        extraction_result.get("extractedData", {}),
        allow_full_pii=settings.allow_full_pii_persistence,
    )

    correlation_id = pipeline_state.get("correlationId")
    record_id = f"tax-facts-{correlation_id}"
    contains_full_pii = settings.allow_full_pii_persistence and _contains_full_ssn(
        extraction_result.get("extractedData", {})
    )

    return {
        "recordId": record_id,
        "recordType": "TaxFactRecord",
        "schemaVersion": "2024-06-04",
        "checkpointStage": checkpoint_stage,
        "lifecycleStatus": _lifecycle_status(pipeline_state, checkpoint_stage),
        "sensitivityLabel": SENSITIVITY_RESTRICTED_TAX_PII,
        "tenantId": pipeline_state.get("tenantId"),
        "taxpayerId": pipeline_state.get("taxpayerId"),
        "taxYear": pipeline_state.get("taxYear") or extracted_data.get("taxYear"),
        "correlationId": correlation_id,
        "pipelineId": pipeline_state.get("pipelineId"),
        "document": {
            "documentName": pipeline_state.get("documentName"),
            "blobUri": pipeline_state.get("blobUri"),
            "documentType": "w2",
            "sourceStatus": pipeline_state.get("intakeResult", {}).get("intakeStatus"),
        },
        "extraction": {
            "status": extraction_result.get("extractionStatus"),
            "source": extraction_result.get("source"),
            "extractedData": extracted_data,
            "fieldConfidence": extraction_result.get("fieldConfidence", {}),
            "overallConfidence": extraction_result.get("overallConfidence"),
            "extractionTimestamp": extraction_result.get("extractionTimestamp"),
        },
        "validation": {
            "status": validation_result.get("validationStatus"),
            "needsReview": validation_result.get("needsReview"),
            "reviewReason": validation_result.get("reviewReason"),
            "issues": validation_result.get("issues", []),
            "warnings": validation_result.get("warnings", []),
        },
        "humanReview": _build_human_review_summary(human_review_result),
        "taxPlanning": {
            "mappingStatus": mapping_result.get("mappingStatus"),
            "mappingProfile": mapping_result.get("mappingProfile"),
            "normalizedTaxFacts": mapping_result.get("normalizedTaxFacts", {}),
            "form1040": mapping_result.get("form1040", {}),
        },
        "compliance": {
            "status": compliance_result.get("complianceStatus"),
            "mode": compliance_result.get("complianceMode"),
            "checks": compliance_result.get("checks", {}),
            "auditEvent": compliance_result.get("auditEvent"),
        },
        "governance": {
            "containsFullPii": contains_full_pii,
            "fullPiiPersistenceAllowed": settings.allow_full_pii_persistence,
            "rawExtractionPersisted": False,
            "identityPolicy": "masked-by-default",
            "classification": SENSITIVITY_RESTRICTED_TAX_PII,
        },
        "createdAt": utc_iso(),
        "updatedAt": utc_iso(),
    }


def _lifecycle_status(pipeline_state: Dict[str, Any], checkpoint_stage: str) -> str:
    if pipeline_state.get("status") == "waiting":
        return "awaiting_human_review"
    if pipeline_state.get("status") == "error":
        return "failed"
    stage_to_status = {
        "intake": "accepted",
        "extraction": "extracted",
        "validation": "validated",
        "human_review": "reviewed",
        "await_human_review": "awaiting_human_review",
        "tax_mapping": "mapped",
        "compliance": "compliance_evaluated",
        "complete": "complete",
    }
    return stage_to_status.get(checkpoint_stage, checkpoint_stage)


def _sanitize_extracted_data(
    extracted_data: Dict[str, Any], *, allow_full_pii: bool
) -> Dict[str, Any]:
    sanitized = deepcopy(extracted_data)
    if not allow_full_pii:
        sanitized["employeeSSN"] = _mask_ssn(sanitized.get("employeeSSN"))
    return sanitized


def _build_human_review_summary(human_review_result: Any) -> Dict[str, Any]:
    if not human_review_result:
        return {
            "required": False,
            "status": None,
        }
    return {
        "required": True,
        "status": human_review_result.get("reviewStatus"),
        "reason": human_review_result.get("reviewReason"),
        "assignedQueue": human_review_result.get("assignedQueue"),
        "submittedForReview": human_review_result.get("submittedForReview"),
    }


def _mask_ssn(value: Any) -> Any:
    if value is None:
        return None
    digits = "".join(character for character in str(value) if character.isdigit())
    if len(digits) == 9:
        return f"XXX-XX-{digits[-4:]}"
    return value


def _contains_full_ssn(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_full_ssn(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_full_ssn(item) for item in value)
    digits = "".join(character for character in str(value) if character.isdigit())
    return len(digits) == 9


def _safe_path_part(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)
