# API Documentation

This document provides comprehensive API documentation for the Microsoft Foundry Tax Intelligence Platform services.

## Table of Contents

1. [W-2 Intake Service API](#w2-intake-service-api)
2. [Agent Orchestration APIs](#agent-orchestration-apis)
3. [Error Handling](#error-handling)
4. [Authentication](#authentication)
5. [Rate Limiting](#rate-limiting)
6. [Examples](#examples)

## W-2 Intake Service API

The W-2 Intake Service is a secure HTTP endpoint for uploading W-2 documents and initiating the processing pipeline.

### Endpoint

```
POST https://{function-app}.azurewebsites.net/api/upload-w2
```

### Authentication

Use API Management gateway with Azure Key Vault stored credentials or managed identities.

### Request

#### Headers

```
Content-Type: application/json
Authorization: Bearer {token}  (if required by API Management)
```

#### Request Body

```json
{
  "tenantId": "string",
  "taxpayerId": "string",
  "documentName": "string",
  "documentBase64": "string",
  "metadata": {
    "taxYear": 2024,
    "uploadedBy": "string",
    "source": "string"
  }
}
```

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenantId` | string | Yes | Organization tenant identifier |
| `taxpayerId` | string | Yes | Individual taxpayer identifier (e.g., SSN, EIN) |
| `documentName` | string | Yes | Original document filename (e.g., "w2-2024.pdf") |
| `documentBase64` | string | Yes | Base64-encoded document bytes |
| `metadata` | object | No | Additional metadata (optional) |
| `metadata.taxYear` | integer | No | Tax year for the W-2 |
| `metadata.uploadedBy` | string | No | User or system uploading document |
| `metadata.source` | string | No | Document source (e.g., "employer-portal") |

### Response

#### Success Response (202 Accepted)

```json
{
  "correlationId": "550e8400-e29b-41d4-a716-446655440000",
  "blobUri": "https://storage.blob.core.windows.net/raw-w2/tenant-id/taxpayer-id/2024/20240104-120530-550e8400.pdf",
  "messageId": "550e8400-e29b-41d4-a716-446655440001",
  "status": "accepted",
  "pipeline": {
    "stage": "intake",
    "nextStage": "extraction",
    "estimatedProcessingTime": "2-5 minutes"
  },
  "timestamp": "2024-01-04T12:05:30Z"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `correlationId` | UUID | Unique identifier for tracking this document through the pipeline |
| `blobUri` | string | Storage location of the uploaded document |
| `messageId` | UUID | Service Bus message identifier |
| `status` | string | Current status: `accepted`, `processing`, `completed`, `failed` |
| `pipeline` | object | Pipeline execution details |
| `pipeline.stage` | string | Current pipeline stage |
| `pipeline.nextStage` | string | Next stage in the workflow |
| `pipeline.estimatedProcessingTime` | string | Estimated time to completion |
| `timestamp` | ISO 8601 | Timestamp of the response |

#### Error Responses

**400 Bad Request**
```json
{
  "error": "INVALID_REQUEST",
  "message": "Missing required field: documentBase64",
  "timestamp": "2024-01-04T12:05:30Z",
  "traceId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**401 Unauthorized**
```json
{
  "error": "UNAUTHORIZED",
  "message": "Invalid or missing authentication token",
  "timestamp": "2024-01-04T12:05:30Z"
}
```

**413 Payload Too Large**
```json
{
  "error": "DOCUMENT_TOO_LARGE",
  "message": "Document size exceeds maximum allowed size of 50MB",
  "timestamp": "2024-01-04T12:05:30Z"
}
```

**500 Internal Server Error**
```json
{
  "error": "INTERNAL_ERROR",
  "message": "An unexpected error occurred during document upload",
  "details": "Contact support with traceId",
  "traceId": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-04T12:05:30Z"
}
```

### Example Requests

#### cURL

```bash
# Prepare document
DOCUMENT=$(cat w2-2024.pdf | base64)

# Upload
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR-TOKEN" \
  -d '{
    "tenantId": "tenant-123",
    "taxpayerId": "employee-456",
    "documentName": "w2-2024.pdf",
    "documentBase64": "'$DOCUMENT'",
    "metadata": {
      "taxYear": 2024,
      "source": "employer-portal"
    }
  }' \
  https://taxai-func.azurewebsites.net/api/upload-w2
```

#### Python

```python
import requests
import base64

# Read and encode document
with open('w2-2024.pdf', 'rb') as f:
    document_base64 = base64.b64encode(f.read()).decode('utf-8')

# Prepare payload
payload = {
    "tenantId": "tenant-123",
    "taxpayerId": "employee-456",
    "documentName": "w2-2024.pdf",
    "documentBase64": document_base64,
    "metadata": {
        "taxYear": 2024,
        "source": "employer-portal"
    }
}

# Make request
response = requests.post(
    "https://taxai-func.azurewebsites.net/api/upload-w2",
    json=payload,
    headers={"Authorization": "Bearer YOUR-TOKEN"}
)

# Check response
if response.status_code == 202:
    result = response.json()
    print(f"Document accepted. Correlation ID: {result['correlationId']}")
else:
    print(f"Error: {response.text}")
```

#### PowerShell

```powershell
# Read and encode document
$document = [Convert]::ToBase64String(
  [System.IO.File]::ReadAllBytes("w2-2024.pdf")
)

# Prepare body
$body = @{
    tenantId = "tenant-123"
    taxpayerId = "employee-456"
    documentName = "w2-2024.pdf"
    documentBase64 = $document
    metadata = @{
        taxYear = 2024
        source = "employer-portal"
    }
} | ConvertTo-Json

# Make request
$response = Invoke-WebRequest `
  -Uri "https://taxai-func.azurewebsites.net/api/upload-w2" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{"Authorization" = "Bearer YOUR-TOKEN"} `
  -Body $body

$response.Content | ConvertFrom-Json
```

## Agent Orchestration APIs

The agent orchestration framework provides internal APIs for agent communication and pipeline coordination.

### Supervisor Orchestrator API

#### `orchestrate(intake_event: Dict) -> Dict`

Orchestrates a document through the complete processing pipeline.

**Parameters:**

- `intake_event` (Dict): Intake trigger event with document metadata

**Returns:** Pipeline execution result with all agent outputs

**Example:**

```python
from foundry_agents.supervisor.orchestrator import SupervisorOrchestrator

orchestrator = SupervisorOrchestrator()
event = {
    "correlationId": "550e8400-e29b-41d4-a716-446655440000",
    "blobUri": "https://storage.blob.core.windows.net/...",
    "tenantId": "tenant-123",
    "taxpayerId": "employee-456"
}

result = orchestrator.orchestrate(event)
print(result)
```

### Agent API

All agents implement a common interface:

#### `agent.process(context: AgentContext) -> AgentResult`

**Parameters:**

- `context` (AgentContext): Processing context with document and metadata

**Returns:** Agent result with output and next stage

**Example:**

```python
from foundry_agents.extraction.agent import ExtractionAgent

agent = ExtractionAgent()
result = agent.process(context)

print(f"Status: {result['status']}")
print(f"Extracted fields: {result['output']}")
print(f"Next stage: {result['nextStage']}")
```

## Error Handling

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_REQUEST` | 400 | Invalid request format or missing fields |
| `DOCUMENT_TOO_LARGE` | 413 | Document exceeds size limit |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Document format not supported |
| `UNAUTHORIZED` | 401 | Authentication failed |
| `FORBIDDEN` | 403 | Access denied |
| `NOT_FOUND` | 404 | Resource not found |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

### Error Response Structure

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": "Additional technical details (optional)",
  "traceId": "UUID for tracking",
  "timestamp": "ISO 8601 timestamp"
}
```

### Retry Strategy

- **Retryable errors** (5xx): Use exponential backoff (1s, 2s, 4s, 8s, max 60s)
- **Non-retryable errors** (4xx): Fix the request and retry
- **Rate limiting** (429): Respect `Retry-After` header

## Authentication

### For Local Testing

No authentication required for local test harness:

```python
python src/foundry_agents/manual_test_harness.py
```

### For Azure Deployment

#### API Management

API Management endpoint requires authentication:

```bash
# Obtain token
TOKEN=$(az account get-access-token --resource-type ms-graph -o tsv --query accessToken)

# Use in request
curl -H "Authorization: Bearer $TOKEN" ...
```

#### Managed Identity

When deployed to Azure Function with managed identity:

```python
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
token = credential.get_token("https://management.azure.com/.default")
```

## Rate Limiting

### Limits

- **Per tenant**: 1000 requests/hour
- **Per function instance**: 100 concurrent requests
- **Document size**: 50 MB maximum

### Rate Limit Headers

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1704379200
```

When rate limit exceeded:

```
HTTP 429 Too Many Requests
Retry-After: 60
```

## Examples

### Complete Workflow

```bash
# 1. Upload W-2 document
RESPONSE=$(curl -X POST https://taxai-func.azurewebsites.net/api/upload-w2 \
  -H "Content-Type: application/json" \
  -d @payload.json)

CORRELATION_ID=$(echo $RESPONSE | jq -r '.correlationId')

# 2. Poll for status (coming soon)
while true; do
  STATUS=$(curl https://taxai-func.azurewebsites.net/api/status/$CORRELATION_ID)
  echo "Status: $(echo $STATUS | jq -r '.status')"
  
  if [[ $(echo $STATUS | jq -r '.status') == "completed" ]]; then
    break
  fi
  
  sleep 5
done

# 3. Retrieve results
curl https://taxai-func.azurewebsites.net/api/results/$CORRELATION_ID
```

## Support

- **API Issues**: Open a GitHub issue with request/response details
- **Documentation**: See comprehensive guides in [docs/](../docs/)
- **Examples**: Check [src/services/](../src/services/) for service implementations

---

**Last Updated**: January 2024
**Version**: 1.0.0

