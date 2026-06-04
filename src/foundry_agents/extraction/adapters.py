from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Optional, Tuple

from foundry_agents.config import (
    AgentSettings,
    EXTRACTION_MODE_DOCUMENT_INTELLIGENCE,
    EXTRACTION_MODE_LOCAL,
)
from foundry_agents.domain import default_field_confidence, default_w2_record, deep_merge


class W2ExtractionAdapter(ABC):
    """Adapter contract for turning a source document into normalized W-2 data."""

    name: str

    @abstractmethod
    def extract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return extractedData and fieldConfidence for the given pipeline payload."""


class LocalW2ExtractionAdapter(W2ExtractionAdapter):
    """Deterministic local extraction adapter for tests and offline development."""

    name = "local-deterministic-w2-v1"

    def extract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        extracted_data = default_w2_record(payload.get("taxYear"))
        extracted_data = deep_merge(extracted_data, payload.get("mockExtractionOverrides", {}))

        field_confidence = default_field_confidence(extracted_data)
        field_confidence.update(payload.get("mockConfidenceOverrides", {}))

        return {
            "extractedData": extracted_data,
            "fieldConfidence": field_confidence,
            "rawResult": None,
        }


class DocumentIntelligenceW2ExtractionAdapter(W2ExtractionAdapter):
    """Azure AI Document Intelligence extraction adapter."""

    name = "azure-document-intelligence-w2"

    def __init__(self, settings: AgentSettings):
        self.settings = settings

    def extract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.settings.document_intelligence_endpoint:
            raise RuntimeError(
                "W2_EXTRACTION_MODE=document-intelligence requires "
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT. The real extraction adapter "
                "is intentionally explicit so sample data is never used by accident."
            )
        blob_uri = payload.get("blobUri")
        if not blob_uri:
            raise RuntimeError(
                "W2_EXTRACTION_MODE=document-intelligence requires payload.blobUri "
                "so Azure AI Document Intelligence can analyze the uploaded document."
            )

        analyze_result = self._analyze_document(blob_uri)
        result_dict = _to_dict(analyze_result)
        document = _first_document(result_dict)
        fields = document.get("fields", {}) if document else {}

        extracted_data, field_confidence = _map_document_fields(fields, payload.get("taxYear"))

        return {
            "extractedData": extracted_data,
            "fieldConfidence": field_confidence,
            "rawResult": {
                "apiVersion": result_dict.get("apiVersion"),
                "modelId": self.settings.document_intelligence_model_id,
                "documentCount": len(result_dict.get("documents", [])),
            },
        }

    def _analyze_document(self, blob_uri: str) -> Any:
        try:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
            from azure.core.credentials import AzureKeyCredential
            from azure.identity import DefaultAzureCredential
        except ImportError as exc:
            raise RuntimeError(
                "Document Intelligence extraction requires azure-ai-documentintelligence "
                "and azure-identity. Install src/foundry_agents/requirements.txt before "
                "using W2_EXTRACTION_MODE=document-intelligence."
            ) from exc

        credential = (
            AzureKeyCredential(self.settings.document_intelligence_key)
            if self.settings.document_intelligence_key
            else DefaultAzureCredential()
        )
        client = DocumentIntelligenceClient(
            endpoint=self.settings.document_intelligence_endpoint,
            credential=credential,
        )
        poller = client.begin_analyze_document(
            model_id=self.settings.document_intelligence_model_id,
            body=AnalyzeDocumentRequest(url_source=blob_uri),
        )
        return poller.result()


def _map_document_fields(
    fields: Dict[str, Any], fallback_tax_year: Optional[int]
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    employer_fields = _object_fields(_first_field(fields, "Employer"))
    employee_fields = _object_fields(_first_field(fields, "Employee"))

    extracted_data = {
        "taxYear": _first_value(fields, "TaxYear") or fallback_tax_year,
        "employerEIN": _first_value(
            employer_fields,
            "IdNumber",
            "TaxId",
            "TIN",
            source_fields=fields,
            source_names=("EmployerEIN", "EmployerTIN"),
        ),
        "employerName": _first_value(
            employer_fields,
            "Name",
            source_fields=fields,
            source_names=("EmployerName",),
        ),
        "employeeSSN": _mask_ssn(
            _first_value(
                employee_fields,
                "SocialSecurityNumber",
                "IdNumber",
                "SSN",
                source_fields=fields,
                source_names=("EmployeeSSN", "EmployeeSocialSecurityNumber"),
            )
        ),
        "employeeName": _first_value(
            employee_fields,
            "Name",
            source_fields=fields,
            source_names=("EmployeeName",),
        ),
        "controlNumber": _first_value(fields, "ControlNumber"),
        "boxes": {
            "Box1": _first_value(fields, "WagesTipsAndOtherCompensation", "Box1"),
            "Box2": _first_value(fields, "FederalIncomeTaxWithheld", "Box2"),
            "Box3": _first_value(fields, "SocialSecurityWages", "Box3"),
            "Box4": _first_value(fields, "SocialSecurityTaxWithheld", "Box4"),
            "Box5": _first_value(fields, "MedicareWagesAndTips", "Box5"),
            "Box6": _first_value(fields, "MedicareTaxWithheld", "Box6"),
            "Box12": _map_box12(fields),
        },
        "stateLocal": _map_state_local(fields),
    }

    field_confidence = {}
    _add_confidence(field_confidence, "taxYear", fields, "TaxYear")
    _add_confidence(field_confidence, "employerEIN", employer_fields, "IdNumber", "TaxId", "TIN")
    _add_confidence(field_confidence, "employerName", employer_fields, "Name")
    _add_confidence(
        field_confidence, "employeeSSN", employee_fields, "SocialSecurityNumber", "IdNumber", "SSN"
    )
    _add_confidence(field_confidence, "employeeName", employee_fields, "Name")
    _add_confidence(field_confidence, "boxes.Box1", fields, "WagesTipsAndOtherCompensation", "Box1")
    _add_confidence(field_confidence, "boxes.Box2", fields, "FederalIncomeTaxWithheld", "Box2")
    _add_confidence(field_confidence, "boxes.Box3", fields, "SocialSecurityWages", "Box3")
    _add_confidence(field_confidence, "boxes.Box4", fields, "SocialSecurityTaxWithheld", "Box4")
    _add_confidence(field_confidence, "boxes.Box5", fields, "MedicareWagesAndTips", "Box5")
    _add_confidence(field_confidence, "boxes.Box6", fields, "MedicareTaxWithheld", "Box6")

    return extracted_data, field_confidence


def _map_box12(fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    box12_entries = []
    for item in _array_items(_first_field(fields, "AdditionalInfo", "Box12")):
        item_fields = _object_fields(item)
        box12_entries.append(
            {
                "code": _first_value(item_fields, "LetterCode", "Code"),
                "amount": _first_value(item_fields, "Amount"),
                "description": _first_value(item_fields, "Description"),
            }
        )
    return box12_entries


def _map_state_local(fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    state_items = [_object_fields(item) for item in _array_items(_first_field(fields, "StateTaxInfos"))]
    local_items = [_object_fields(item) for item in _array_items(_first_field(fields, "LocalTaxInfos"))]
    record_count = max(len(state_items), len(local_items))
    state_local = []

    for index in range(record_count):
        state_fields = state_items[index] if index < len(state_items) else {}
        local_fields = local_items[index] if index < len(local_items) else {}
        state_local.append(
            {
                "state": _first_value(state_fields, "State", "StateCode"),
                "stateWages": _first_value(
                    state_fields, "StateWagesTipsEtc", "StateWages", "Wages"
                ),
                "stateTaxWithheld": _first_value(
                    state_fields, "StateIncomeTax", "StateTaxWithheld", "IncomeTax"
                ),
                "localityName": _first_value(local_fields, "LocalityName", "Locality"),
                "localWages": _first_value(local_fields, "LocalWagesTipsEtc", "LocalWages"),
                "localTaxWithheld": _first_value(
                    local_fields, "LocalIncomeTax", "LocalTaxWithheld"
                ),
            }
        )

    return state_local


def _first_document(result_dict: Dict[str, Any]) -> Dict[str, Any]:
    documents = result_dict.get("documents", [])
    return documents[0] if documents else {}


def _to_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    raise RuntimeError("Document Intelligence returned an unsupported result type.")


def _first_value(
    fields: Dict[str, Any],
    *names: str,
    source_fields: Optional[Dict[str, Any]] = None,
    source_names: Iterable[str] = (),
) -> Any:
    field = _first_field(fields, *names)
    if field is None and source_fields is not None:
        field = _first_field(source_fields, *source_names)
    return _field_value(field)


def _first_field(fields: Dict[str, Any], *names: str) -> Optional[Dict[str, Any]]:
    for name in names:
        field = fields.get(name)
        if field is not None:
            return field
    return None


def _field_value(field: Optional[Dict[str, Any]]) -> Any:
    if not field:
        return None
    for key in (
        "valueString",
        "valueNumber",
        "valueInteger",
        "valueDate",
        "valuePhoneNumber",
        "content",
    ):
        if key in field and field[key] not in (None, ""):
            return field[key]
    currency = field.get("valueCurrency")
    if isinstance(currency, dict):
        return currency.get("amount")
    return None


def _object_fields(field: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not field:
        return {}
    return field.get("valueObject") or field.get("value_object") or {}


def _array_items(field: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not field:
        return []
    return field.get("valueArray") or field.get("value_array") or []


def _field_confidence(field: Optional[Dict[str, Any]]) -> Optional[float]:
    if not field or field.get("confidence") is None:
        return None
    return float(field["confidence"])


def _add_confidence(
    target: Dict[str, float], output_name: str, fields: Dict[str, Any], *source_names: str
) -> None:
    confidence = _field_confidence(_first_field(fields, *source_names))
    if confidence is not None:
        target[output_name] = confidence


def _mask_ssn(value: Any) -> Any:
    if value is None:
        return None
    digits = "".join(character for character in str(value) if character.isdigit())
    if len(digits) == 9:
        return f"XXX-XX-{digits[-4:]}"
    return value


def create_extraction_adapter(settings: AgentSettings) -> W2ExtractionAdapter:
    if settings.extraction_mode == EXTRACTION_MODE_LOCAL:
        return LocalW2ExtractionAdapter()
    if settings.extraction_mode == EXTRACTION_MODE_DOCUMENT_INTELLIGENCE:
        return DocumentIntelligenceW2ExtractionAdapter(settings)
    raise ValueError(f"Unsupported extraction mode: {settings.extraction_mode}")
