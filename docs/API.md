# API Documentation

This document describes the currently implemented HTTP boundaries.

## Hosts

| Host | Purpose |
| --- | --- |
| W-2 intake Function App | Accepts uploaded W-2 documents and publishes ingestion events. |
| Foundry tools Function App | Exposes governed tools for the Foundry supervisor agent. |

## W-2 Intake API

### Upload W-2

```http
POST https://{w2-intake-function-host}/api/upload-w2
Content-Type: application/json
```

Request body:

```json
{
  "correlationId": "optional-correlation-id",
  "tenantId": "tenant-001",
  "taxpayerId": "taxpayer-123",
  "documentName": "w2-2024.pdf",
  "documentBase64": "<base64-document-bytes>",
  "taxYear": 2024
}
```

Required fields:

| Field | Required | Description |
| --- | --- | --- |
| `tenantId` | Yes | Tenant or organization identifier. |
| `taxpayerId` | Yes | Taxpayer identifier used for storage partitioning. |
| `documentName` | Yes | Original document name. |
| `documentBase64` | Yes | Base64-encoded W-2 document bytes. |
| `taxYear` | No | Tax year. Defaults to the current year when omitted. |
| `correlationId` | No | End-to-end trace identifier. |

Success response:

```http
202 Accepted
Content-Type: application/json
```

```json
{
  "status": "accepted",
  "blobUri": "https://<storage-account>.blob.core.windows.net/raw-w2/tenant-001/taxpayer-123/2024/...",
  "messageId": "service-bus-message-id",
  "correlationId": "optional-correlation-id"
}
```

Validation errors return `400`. Runtime configuration or downstream ingestion
errors return `500`.

## Foundry Tools API

The Foundry tools Function App exposes HTTP endpoints backed by
`foundry_agents.tools.w2_pipeline_tools.TOOL_REGISTRY`.

The OpenAPI contract lives at:

```text
src/services/foundry-tools/openapi.json
```

The logical tool manifest lives at:

```text
src/foundry_agents/tools/w2_pipeline_tools.json
```

### Tool Response Envelope

Successful tool responses use this envelope:

```json
{
  "toolName": "generate_form_1040_document",
  "result": {
    "correlationId": "corr-001",
    "generationStatus": "success"
  }
}
```

Tool execution failures return:

```json
{
  "error": "tool_execution_failed",
  "toolName": "generate_form_1040_document",
  "message": "error details"
}
```

### Implemented Tool Endpoints

| Endpoint | Tool name | Purpose |
| --- | --- | --- |
| `POST /api/run-w2-pipeline` | `run_w2_pipeline` | Run the complete governed pipeline. |
| `POST /api/start-w2-pipeline` | `start_w2_pipeline` | Create initial orchestration state. |
| `POST /api/process-w2-intake` | `process_w2_intake` | Process an already-uploaded W-2 document event. |
| `POST /api/extract-w2-document` | `extract_w2_document` | Extract normalized W-2 facts. |
| `POST /api/validate-w2-facts` | `validate_w2_facts` | Validate extracted W-2 facts. |
| `POST /api/submit-w2-human-review` | `submit_w2_human_review` | Route flagged records to human review. |
| `POST /api/map-w2-tax-facts` | `map_w2_tax_facts` | Map W-2 facts into 1040-ready fields and planning facts. |
| `POST /api/generate-form-1040-document` | `generate_form_1040_document` | Generate a draft Form 1040 artifact. |
| `POST /api/evaluate-w2-compliance` | `evaluate_w2_compliance` | Evaluate compliance and audit controls. |
| `POST /api/persist-w2-pipeline-checkpoint` | `persist_w2_pipeline_checkpoint` | Persist a governed checkpoint. |
| `POST /api/persist-completed-w2-pipeline` | `persist_completed_w2_pipeline` | Persist completed pipeline state. |
| `POST /api/get-runtime-configuration` | `get_runtime_configuration` | Return non-secret runtime configuration. |

### Complete Pipeline Tool

```http
POST https://{foundry-tools-host}/api/run-w2-pipeline
Content-Type: application/json
```

```json
{
  "correlationId": "corr-001",
  "tenantId": "tenant-001",
  "taxpayerId": "taxpayer-123",
  "documentName": "w2-2024.pdf",
  "blobUri": "https://<storage-account>.blob.core.windows.net/raw-w2/...",
  "taxYear": 2024
}
```

The result contains the pipeline state, including extraction, validation, tax
mapping, form generation, compliance, and persistence metadata.

### Form 1040 Generation Tool

The form generation tool is normally called after `map_w2_tax_facts`.

```http
POST https://{foundry-tools-host}/api/generate-form-1040-document
Content-Type: application/json
```

```json
{
  "correlationId": "corr-001",
  "tenantId": "tenant-001",
  "taxpayerId": "taxpayer-123",
  "taxYear": 2024,
  "mappingResult": {
    "mappingStatus": "success",
    "form1040": {
      "federal": {
        "taxYear": 2024,
        "filingStatus": "single",
        "wagesLine1a": 75000.0,
        "federalIncomeTaxWithheld": 8500.0
      }
    }
  }
}
```

Example result:

```json
{
  "toolName": "generate_form_1040_document",
  "result": {
    "correlationId": "corr-001",
    "generationStatus": "success",
    "generationMode": "html-template",
    "artifactMode": "azure-blob",
    "documentType": "irs-form-1040",
    "templateVersion": "irs-1040-2024-html-v1",
    "artifact": {
      "artifactId": "form-1040-corr-001",
      "storageMode": "azure-blob",
      "contentType": "text/html",
      "containerName": "tax-artifacts",
      "blobName": "tenant-001/2024/form-1040-corr-001.html"
    }
  }
}
```

## Authentication

The current Function Apps use Azure Functions authentication. In production,
the recommended pattern is to place these endpoints behind API Management or a
Foundry-supported authenticated tool binding.

Runtime access to Azure services uses:

- Key Vault references for connection-string app settings.
- Managed identity for Cosmos DB.
- Managed identity for Blob artifact storage when
  `FORM_1040_STORAGE_ACCOUNT_URL` is configured.

## Local Testing

No HTTP host is required to validate the core pipeline locally:

```powershell
python -m unittest discover -s tests
python src/foundry_agents/manual_test_harness.py
```

The tests verify that OpenAPI operation IDs match the Python tool registry.
