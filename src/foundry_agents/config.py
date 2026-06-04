import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


APP_ENV_LOCAL = "local"
APP_ENV_DEV = "dev"
APP_ENV_TEST = "test"
APP_ENV_UAT = "uat"
APP_ENV_PROD = "prod"

EXTRACTION_MODE_LOCAL = "local"
EXTRACTION_MODE_DOCUMENT_INTELLIGENCE = "document-intelligence"

VALIDATION_STRICTNESS_STANDARD = "standard"
VALIDATION_STRICTNESS_STRICT = "strict"

HUMAN_REVIEW_MODE_LOCAL_AUTO_APPROVE = "local-auto-approve"
HUMAN_REVIEW_MODE_QUEUE = "queue"
HUMAN_REVIEW_MODE_MANUAL = "manual"

TAX_MAPPING_PROFILE_US_FEDERAL_2024 = "us-federal-2024"

COMPLIANCE_MODE_DEVELOPMENT = "development"
COMPLIANCE_MODE_REGULATED = "regulated"

TAX_FACT_PERSISTENCE_DISABLED = "disabled"
TAX_FACT_PERSISTENCE_LOCAL_JSON = "local-json"
TAX_FACT_PERSISTENCE_COSMOS = "cosmos"

SUPPORTED_APP_ENVS = {APP_ENV_LOCAL, APP_ENV_DEV, APP_ENV_TEST, APP_ENV_UAT, APP_ENV_PROD}
SUPPORTED_EXTRACTION_MODES = {
    EXTRACTION_MODE_LOCAL,
    EXTRACTION_MODE_DOCUMENT_INTELLIGENCE,
}
SUPPORTED_VALIDATION_STRICTNESS = {VALIDATION_STRICTNESS_STANDARD, VALIDATION_STRICTNESS_STRICT}
SUPPORTED_HUMAN_REVIEW_MODES = {
    HUMAN_REVIEW_MODE_LOCAL_AUTO_APPROVE,
    HUMAN_REVIEW_MODE_QUEUE,
    HUMAN_REVIEW_MODE_MANUAL,
}
SUPPORTED_TAX_MAPPING_PROFILES = {TAX_MAPPING_PROFILE_US_FEDERAL_2024}
SUPPORTED_COMPLIANCE_MODES = {COMPLIANCE_MODE_DEVELOPMENT, COMPLIANCE_MODE_REGULATED}
SUPPORTED_TAX_FACT_PERSISTENCE_MODES = {
    TAX_FACT_PERSISTENCE_DISABLED,
    TAX_FACT_PERSISTENCE_LOCAL_JSON,
    TAX_FACT_PERSISTENCE_COSMOS,
}


@dataclass(frozen=True)
class AgentSettings:
    """Runtime settings for the full agent pipeline.

    Environment variables remain the deployment mechanism. This dataclass is the
    typed application contract that validates and exposes those values to agents.
    """

    app_env: str = APP_ENV_LOCAL
    extraction_mode: str = EXTRACTION_MODE_LOCAL
    validation_strictness: str = VALIDATION_STRICTNESS_STANDARD
    human_review_mode: str = HUMAN_REVIEW_MODE_LOCAL_AUTO_APPROVE
    tax_mapping_profile: str = TAX_MAPPING_PROFILE_US_FEDERAL_2024
    compliance_mode: str = COMPLIANCE_MODE_DEVELOPMENT
    low_confidence_threshold: float = 0.85
    require_masked_pii_in_logs: bool = True
    audit_event_enabled: bool = True
    document_intelligence_endpoint: str = ""
    document_intelligence_key: str = ""
    document_intelligence_model_id: str = "prebuilt-tax.us.w2"
    tax_fact_persistence_mode: str = TAX_FACT_PERSISTENCE_DISABLED
    tax_fact_persistence_path: str = ".local_state/tax-facts"
    cosmos_endpoint: str = ""
    cosmos_database_name: str = ""
    cosmos_container_name: str = ""
    cosmos_key: str = ""
    allow_full_pii_persistence: bool = False

    @property
    def is_local(self) -> bool:
        return self.app_env == APP_ENV_LOCAL

    @property
    def is_regulated(self) -> bool:
        return self.compliance_mode == COMPLIANCE_MODE_REGULATED

    def as_runtime_metadata(self) -> Dict[str, object]:
        """Return non-secret settings metadata suitable for logs and audit payloads."""
        return {
            "appEnv": self.app_env,
            "extractionMode": self.extraction_mode,
            "validationStrictness": self.validation_strictness,
            "humanReviewMode": self.human_review_mode,
            "taxMappingProfile": self.tax_mapping_profile,
            "complianceMode": self.compliance_mode,
            "lowConfidenceThreshold": self.low_confidence_threshold,
            "requireMaskedPiiInLogs": self.require_masked_pii_in_logs,
            "auditEventEnabled": self.audit_event_enabled,
            "documentIntelligenceModelId": self.document_intelligence_model_id,
            "taxFactPersistenceMode": self.tax_fact_persistence_mode,
            "cosmosDatabaseName": self.cosmos_database_name,
            "cosmosContainerName": self.cosmos_container_name,
            "allowFullPiiPersistence": self.allow_full_pii_persistence,
        }


def load_agent_settings(env: Optional[Dict[str, str]] = None) -> AgentSettings:
    """Load and validate agent settings from environment variables."""
    values = env if env is not None else load_environment()
    app_env = _read_choice(values, "APP_ENV", APP_ENV_LOCAL, SUPPORTED_APP_ENVS)
    extraction_mode = _read_choice(
        values, "W2_EXTRACTION_MODE", EXTRACTION_MODE_LOCAL, SUPPORTED_EXTRACTION_MODES
    )
    validation_strictness = _read_choice(
        values,
        "W2_VALIDATION_STRICTNESS",
        VALIDATION_STRICTNESS_STANDARD,
        SUPPORTED_VALIDATION_STRICTNESS,
    )
    human_review_mode = _read_choice(
        values,
        "HUMAN_REVIEW_MODE",
        HUMAN_REVIEW_MODE_LOCAL_AUTO_APPROVE,
        SUPPORTED_HUMAN_REVIEW_MODES,
    )
    tax_mapping_profile = _read_choice(
        values,
        "TAX_MAPPING_PROFILE",
        TAX_MAPPING_PROFILE_US_FEDERAL_2024,
        SUPPORTED_TAX_MAPPING_PROFILES,
    )
    compliance_mode = _read_choice(
        values,
        "COMPLIANCE_MODE",
        COMPLIANCE_MODE_DEVELOPMENT,
        SUPPORTED_COMPLIANCE_MODES,
    )
    tax_fact_persistence_mode = _read_choice(
        values,
        "TAX_FACT_PERSISTENCE_MODE",
        TAX_FACT_PERSISTENCE_DISABLED,
        SUPPORTED_TAX_FACT_PERSISTENCE_MODES,
    )

    settings = AgentSettings(
        app_env=app_env,
        extraction_mode=extraction_mode,
        validation_strictness=validation_strictness,
        human_review_mode=human_review_mode,
        tax_mapping_profile=tax_mapping_profile,
        compliance_mode=compliance_mode,
        low_confidence_threshold=_read_float(values, "LOW_CONFIDENCE_THRESHOLD", 0.85),
        require_masked_pii_in_logs=_read_bool(values, "REQUIRE_MASKED_PII_IN_LOGS", True),
        audit_event_enabled=_read_bool(values, "AUDIT_EVENT_ENABLED", True),
        document_intelligence_endpoint=values.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", ""),
        document_intelligence_key=values.get("AZURE_DOCUMENT_INTELLIGENCE_KEY", ""),
        document_intelligence_model_id=values.get(
            "AZURE_DOCUMENT_INTELLIGENCE_MODEL_ID", "prebuilt-tax.us.w2"
        ),
        tax_fact_persistence_mode=tax_fact_persistence_mode,
        tax_fact_persistence_path=values.get(
            "TAX_FACT_PERSISTENCE_PATH", ".local_state/tax-facts"
        ),
        cosmos_endpoint=values.get("AZURE_COSMOS_ENDPOINT", ""),
        cosmos_database_name=values.get("AZURE_COSMOS_DATABASE_NAME", ""),
        cosmos_container_name=values.get("AZURE_COSMOS_CONTAINER_NAME", ""),
        cosmos_key=values.get("AZURE_COSMOS_KEY", ""),
        allow_full_pii_persistence=_read_bool(values, "ALLOW_FULL_PII_PERSISTENCE", False),
    )
    _validate_cross_field_settings(settings)
    return settings


def load_environment(dotenv_path: Optional[Path] = None) -> Dict[str, str]:
    """Return environment values after loading local .env defaults.

    Real environment variables take precedence. This mirrors Azure app settings:
    production resources provide process environment variables directly, while
    local development can fill missing values from a Git-ignored .env file.
    """
    values = dict(os.environ)
    if values.get("APP_ENV", "").strip().lower() == APP_ENV_PROD:
        return values

    path = dotenv_path or _find_repo_dotenv()
    if path is None or not path.exists():
        return values

    for key, value in parse_dotenv(path).items():
        values.setdefault(key, value)
    return values


def parse_dotenv(path: Path) -> Dict[str, str]:
    """Parse simple KEY=VALUE dotenv files without expanding variables."""
    parsed: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        parsed[key] = value
    return parsed


def _find_repo_dotenv() -> Optional[Path]:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
    return None


def _read_choice(
    values: Dict[str, str], name: str, default: str, supported_values: Iterable[str]
) -> str:
    value = values.get(name, default).strip().lower()
    supported = set(supported_values)
    if value not in supported:
        supported_list = ", ".join(sorted(supported))
        raise ValueError(f"Unsupported {name} '{value}'. Supported values: {supported_list}.")
    return value


def _read_bool(values: Dict[str, str], name: str, default: bool) -> bool:
    raw_value = values.get(name)
    if raw_value is None or raw_value == "":
        return default
    value = raw_value.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value.")


def _read_float(values: Dict[str, str], name: str, default: float) -> float:
    raw_value = values.get(name)
    if raw_value is None or raw_value == "":
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a numeric value.") from exc
    if value < 0 or value > 1:
        raise ValueError(f"{name} must be between 0 and 1.")
    return value


def _validate_cross_field_settings(settings: AgentSettings) -> None:
    if settings.app_env == APP_ENV_PROD and settings.extraction_mode == EXTRACTION_MODE_LOCAL:
        raise ValueError("APP_ENV=prod cannot use W2_EXTRACTION_MODE=local.")
    if settings.app_env == APP_ENV_PROD and settings.compliance_mode != COMPLIANCE_MODE_REGULATED:
        raise ValueError("APP_ENV=prod requires COMPLIANCE_MODE=regulated.")
    if settings.app_env == APP_ENV_PROD and settings.human_review_mode == HUMAN_REVIEW_MODE_LOCAL_AUTO_APPROVE:
        raise ValueError("APP_ENV=prod cannot use HUMAN_REVIEW_MODE=local-auto-approve.")
    if settings.app_env == APP_ENV_PROD and settings.tax_fact_persistence_mode == TAX_FACT_PERSISTENCE_LOCAL_JSON:
        raise ValueError("APP_ENV=prod cannot use TAX_FACT_PERSISTENCE_MODE=local-json.")
    if settings.app_env == APP_ENV_PROD and settings.tax_fact_persistence_mode == TAX_FACT_PERSISTENCE_DISABLED:
        raise ValueError("APP_ENV=prod requires durable TAX_FACT_PERSISTENCE_MODE.")
    if settings.tax_fact_persistence_mode == TAX_FACT_PERSISTENCE_COSMOS:
        missing = []
        if not settings.cosmos_endpoint:
            missing.append("AZURE_COSMOS_ENDPOINT")
        if not settings.cosmos_database_name:
            missing.append("AZURE_COSMOS_DATABASE_NAME")
        if not settings.cosmos_container_name:
            missing.append("AZURE_COSMOS_CONTAINER_NAME")
        if missing:
            raise ValueError(
                "TAX_FACT_PERSISTENCE_MODE=cosmos requires "
                + ", ".join(missing)
                + "."
            )
