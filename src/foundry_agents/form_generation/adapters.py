from abc import ABC, abstractmethod
from html import escape
from pathlib import Path
from typing import Any, Dict

from foundry_agents.config import (
    AgentSettings,
    FORM_1040_ARTIFACT_MODE_BLOB,
    FORM_1040_ARTIFACT_MODE_LOCAL,
    FORM_1040_GENERATION_MODE_HTML,
)
from foundry_agents.time_utils import utc_iso


class Form1040GenerationAdapter(ABC):
    """Adapter contract for rendering Form 1040 artifacts."""

    name: str

    @abstractmethod
    def generate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Render a Form 1040 artifact from mapped tax facts."""


class HtmlForm1040GenerationAdapter(Form1040GenerationAdapter):
    """Deterministic Form 1040 HTML renderer for local and hosted execution."""

    name = "irs-1040-html-renderer-v1"

    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings

    def generate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mapping_result = payload.get("mappingResult") or {}
        form1040 = mapping_result.get("form1040") or {}
        federal = form1040.get("federal") or {}
        field_values = _build_1040_field_values(payload, federal)
        artifact_id = _artifact_id(payload)
        file_name = f"{artifact_id}.html"
        html = _render_html_document(field_values, self.settings.form_1040_template_version)
        artifact = _create_artifact(self.settings, payload, artifact_id, file_name, html)

        return {
            "templateVersion": self.settings.form_1040_template_version,
            "documentType": "irs-form-1040",
            "taxYear": field_values["taxYear"],
            "fieldValues": field_values,
            "artifact": artifact,
        }


def create_form_1040_generation_adapter(settings: AgentSettings) -> Form1040GenerationAdapter:
    if settings.form_1040_generation_mode == FORM_1040_GENERATION_MODE_HTML:
        return HtmlForm1040GenerationAdapter(settings)
    raise ValueError(
        f"Unsupported Form 1040 generation mode: {settings.form_1040_generation_mode}"
    )


def _build_1040_field_values(payload: Dict[str, Any], federal: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "taxYear": federal.get("taxYear") or payload.get("taxYear"),
        "filingStatus": federal.get("filingStatus"),
        "taxpayerId": payload.get("taxpayerId"),
        "wagesLine1a": _money(federal.get("wagesLine1a")),
        "federalIncomeTaxWithheld": _money(federal.get("federalIncomeTaxWithheld")),
        "socialSecurityWages": _money(federal.get("socialSecurityWages")),
        "socialSecurityTaxWithheld": _money(federal.get("socialSecurityTaxWithheld")),
        "medicareWages": _money(federal.get("medicareWages")),
        "medicareTaxWithheld": _money(federal.get("medicareTaxWithheld")),
    }


def _render_html_document(field_values: Dict[str, Any], template_version: str) -> str:
    rows = "\n".join(
        f"<tr><th>{escape(_label(key))}</th><td>{escape(str(value or ''))}</td></tr>"
        for key, value in field_values.items()
    )
    generated_at = utc_iso()
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <title>Form 1040 Draft</title>\n"
        "  <style>\n"
        "    body { font-family: Arial, sans-serif; margin: 32px; color: #1f2933; }\n"
        "    h1 { font-size: 24px; margin-bottom: 4px; }\n"
        "    .meta { color: #52606d; font-size: 13px; margin-bottom: 24px; }\n"
        "    table { border-collapse: collapse; width: 100%; max-width: 840px; }\n"
        "    th, td { border: 1px solid #bcccdc; padding: 10px 12px; text-align: left; }\n"
        "    th { width: 42%; background: #f0f4f8; }\n"
        "    .notice { margin-top: 24px; font-size: 12px; color: #52606d; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>Form 1040 Draft</h1>\n"
        f"  <div class=\"meta\">Template {escape(template_version)} | Generated {escape(generated_at)}</div>\n"
        f"  <table>{rows}</table>\n"
        "  <p class=\"notice\">Draft artifact generated from validated W-2 facts. "
        "Official filing requires final taxpayer review and approved IRS form binding.</p>\n"
        "</body>\n"
        "</html>\n"
    )


def _create_artifact(
    settings: AgentSettings,
    payload: Dict[str, Any],
    artifact_id: str,
    file_name: str,
    content: str,
) -> Dict[str, Any]:
    if settings.form_1040_artifact_mode == FORM_1040_ARTIFACT_MODE_LOCAL:
        return _write_local_artifact(settings, payload, artifact_id, file_name, content)
    if settings.form_1040_artifact_mode == FORM_1040_ARTIFACT_MODE_BLOB:
        return _write_blob_artifact(settings, payload, artifact_id, file_name, content)
    raise ValueError(f"Unsupported Form 1040 artifact mode: {settings.form_1040_artifact_mode}")


def _write_local_artifact(
    settings: AgentSettings,
    payload: Dict[str, Any],
    artifact_id: str,
    file_name: str,
    content: str,
) -> Dict[str, Any]:
    tenant_id = _safe_path_part(payload.get("tenantId") or "unknown-tenant")
    tax_year = _safe_path_part(str(payload.get("taxYear") or "unknown-year"))
    directory = Path(settings.form_1040_artifact_path) / tenant_id / tax_year
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / file_name
    path.write_text(content, encoding="utf-8")
    return {
        "artifactId": artifact_id,
        "storageMode": FORM_1040_ARTIFACT_MODE_LOCAL,
        "contentType": "text/html",
        "path": str(path),
        "fileName": file_name,
    }


def _write_blob_artifact(
    settings: AgentSettings,
    payload: Dict[str, Any],
    artifact_id: str,
    file_name: str,
    content: str,
) -> Dict[str, Any]:
    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient, ContentSettings
    except ImportError as exc:
        raise RuntimeError(
            "Azure Blob Form 1040 artifacts require azure-identity and azure-storage-blob. "
            "Install src/foundry_agents/requirements.txt before using "
            "FORM_1040_ARTIFACT_MODE=azure-blob."
        ) from exc

    tenant_id = _safe_path_part(payload.get("tenantId") or "unknown-tenant")
    tax_year = _safe_path_part(str(payload.get("taxYear") or "unknown-year"))
    blob_name = f"{tenant_id}/{tax_year}/{file_name}"
    if settings.form_1040_storage_account_url:
        service_client = BlobServiceClient(
            account_url=settings.form_1040_storage_account_url,
            credential=DefaultAzureCredential(),
        )
    else:
        service_client = BlobServiceClient.from_connection_string(
            settings.form_1040_storage_connection_string
        )
    container_client = service_client.get_container_client(
        settings.form_1040_blob_container_name
    )
    try:
        container_client.create_container()
    except Exception as exc:
        if getattr(exc, "error_code", None) != "ContainerAlreadyExists":
            raise
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(
        content.encode("utf-8"),
        overwrite=True,
        content_settings=ContentSettings(content_type="text/html"),
    )
    return {
        "artifactId": artifact_id,
        "storageMode": FORM_1040_ARTIFACT_MODE_BLOB,
        "contentType": "text/html",
        "containerName": settings.form_1040_blob_container_name,
        "blobName": blob_name,
        "uri": blob_client.url,
        "fileName": file_name,
    }


def _artifact_id(payload: Dict[str, Any]) -> str:
    correlation_id = payload.get("correlationId") or "unknown-correlation"
    return f"form-1040-{_safe_path_part(correlation_id)}"


def _money(value: Any) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _label(value: str) -> str:
    labels = {
        "taxYear": "Tax year",
        "filingStatus": "Filing status",
        "taxpayerId": "Taxpayer identifier",
        "wagesLine1a": "Line 1a wages",
        "federalIncomeTaxWithheld": "Federal income tax withheld",
        "socialSecurityWages": "Social Security wages",
        "socialSecurityTaxWithheld": "Social Security tax withheld",
        "medicareWages": "Medicare wages",
        "medicareTaxWithheld": "Medicare tax withheld",
    }
    return labels.get(value, value)


def _safe_path_part(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)
