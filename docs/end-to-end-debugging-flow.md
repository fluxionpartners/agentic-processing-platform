# End-to-End Debugging Flow

This runbook explains how to debug the deployed W-2 to draft 1040 flow from
GitHub Actions through API Management, Azure Functions, Service Bus, Cosmos DB,
and the React upload portal.

## Full Runtime Sequence

```mermaid
sequenceDiagram
    autonumber

    participant Dev as Developer or GitHub Actions
    participant Bicep as Bicep Deployment
    participant Entra as Microsoft Entra ID
    participant APIM as API Management
    participant Portal as Static Web Portal
    participant Intake as W2 Intake Function
    participant Storage as Blob Storage
    participant SB as Service Bus Queue
    participant Tools as Foundry Tools Function
    participant Pipeline as Agent Pipeline
    participant Cosmos as Cosmos DB
    participant Artifact as Draft 1040 Blob

    rect rgb(245,248,252)
    note over Dev,Bicep: 1. Provision infrastructure
    Dev->>Bicep: Deploy W2 intake infrastructure
    Bicep->>APIM: Create /w2-intake/upload-w2
    Bicep->>Intake: Create W2 intake Function App
    Bicep->>Storage: Create raw W2 container
    Bicep->>SB: Create W2 ingestion queue
    Bicep->>Cosmos: Create persisted state container
    Bicep->>Portal: Enable static website storage
    Bicep-->>Dev: Return Function, APIM, and portal outputs

    Dev->>Bicep: Deploy Foundry tools infrastructure
    Bicep->>APIM: Create /w2-processing/run and /status
    Bicep->>Tools: Create Foundry tools Function App
    Bicep->>Artifact: Create draft 1040 artifact container
    Bicep-->>Dev: Return tool host and status API outputs
    end

    rect rgb(248,252,247)
    note over Dev,Portal: 2. Deploy portal
    Dev->>Portal: Build React app with VITE_* API URLs
    Dev->>Portal: Upload dist assets to static website container
    Portal-->>Dev: Static website URL is available
    end

    rect rgb(252,248,245)
    note over Portal,Entra: 3. Browser upload path
    Dev->>Portal: Open static website URL
    Portal->>Entra: User signs in through MSAL
    Entra-->>Portal: Access token for W2 API scope
    Portal->>APIM: POST /w2-intake/upload-w2 with Bearer token
    APIM->>Entra: Validate JWT from OpenID metadata
    APIM->>APIM: Check tenant, issuer, and audience
    APIM->>Intake: Inject backend Function key
    APIM->>Intake: Forward upload request
    Intake->>Storage: Save uploaded W2 document
    Intake->>SB: Publish W2DocumentUploaded event
    Intake-->>APIM: Return accepted response
    APIM-->>Portal: Return correlationId
    end

    rect rgb(247,250,252)
    note over SB,Cosmos: 4. Async processing path
    SB->>Tools: Trigger Service Bus function
    Tools->>Cosmos: Write processing checkpoint
    Tools->>Pipeline: Run governed orchestration
    Pipeline->>Pipeline: Intake agent normalizes request
    Pipeline->>Pipeline: Extraction agent extracts W2 facts
    Pipeline->>Pipeline: Validation agent checks facts
    Pipeline->>Pipeline: Human review agent evaluates review need
    Pipeline->>Pipeline: Tax mapping agent maps 1040 facts
    Pipeline->>Pipeline: Form generation agent creates draft 1040
    Pipeline->>Artifact: Persist draft 1040 artifact
    Pipeline->>Pipeline: Compliance agent creates audit envelope
    Tools->>Cosmos: Persist complete state
    end

    rect rgb(252,252,247)
    note over Portal,Cosmos: 5. Status polling
    loop Until complete or timeout
      Portal->>APIM: GET /w2-processing/status/{correlationId}
      APIM->>Entra: Validate JWT
      APIM->>Tools: Inject backend Function key
      Tools->>Cosmos: Read state by tenant and correlationId
      Cosmos-->>Tools: Return current state
      Tools-->>APIM: Return status payload
      APIM-->>Portal: Return processing status
      Portal->>Portal: Update timeline
    end
    Portal->>Portal: Show draft 1040 artifact metadata
    end
```

## GitHub Actions Smoke Test

The CI smoke test replays the browser flow without a browser.

```mermaid
sequenceDiagram
    autonumber

    participant GHA as GitHub Actions
    participant Entra as Entra ID
    participant APIM as API Management
    participant Intake as W2 Intake Function
    participant SB as Service Bus
    participant Tools as Foundry Tools Function
    participant Cosmos as Cosmos DB

    GHA->>Entra: Request token with API .default scope
    Entra-->>GHA: App-only access token
    GHA->>APIM: POST /w2-intake/upload-w2
    APIM->>APIM: validate-jwt checks token
    APIM->>Intake: Inject Function key
    Intake->>SB: Publish ingestion event
    Intake-->>GHA: Return accepted response

    loop Poll status
      GHA->>APIM: GET /w2-processing/status/{correlationId}
      APIM->>APIM: validate-jwt checks token
      APIM->>Tools: Forward status request
      Tools->>Cosmos: Read checkpoint
      Cosmos-->>Tools: Current state
      Tools-->>GHA: processing or complete
    end
```

## Local Direct Smoke Test

When APIM authentication is being debugged separately, the same smoke script can
test the deployed Function Apps directly with Function keys. This validates the
Function packages, Blob write, Service Bus trigger, Cosmos status read, pipeline
execution, and draft 1040 generation.

```powershell
$w2Key = az functionapp keys list `
  --resource-group "<resource-group>" `
  --name "<w2-intake-function-app>" `
  --query functionKeys.default `
  --output tsv

$toolsKey = az functionapp keys list `
  --resource-group "<resource-group>" `
  --name "<foundry-tools-function-app>" `
  --query functionKeys.default `
  --output tsv

.\scripts\azure\Test-W2EndToEndSmoke.ps1 `
  -IntakeApiUrl "https://<w2-intake-function-app>.azurewebsites.net/api/upload-w2" `
  -StatusApiUrl "https://<foundry-tools-function-app>.azurewebsites.net/api/status" `
  -IntakeFunctionKey $w2Key `
  -StatusFunctionKey $toolsKey `
  -TimeoutSeconds 300 `
  -PollIntervalSeconds 5
```

Expected successful output:

```text
Starting W-2 end-to-end smoke test
Intake accepted. Polling pipeline status...
Pipeline status: complete
Smoke test completed successfully.
Form 1040 artifact metadata was returned.
```

## Local APIM Smoke Test

Use this path when validating APIM and Entra end to end.

```powershell
az login --scope "api://<api-client-id>/W2Intake.Upload"

$token = az account get-access-token `
  --scope "api://<api-client-id>/W2Intake.Upload" `
  --query accessToken `
  --output tsv

.\scripts\azure\Test-W2EndToEndSmoke.ps1 `
  -IntakeApiUrl "https://<apim-name>.azure-api.net/w2-intake/upload-w2" `
  -StatusApiUrl "https://<apim-name>.azure-api.net/w2-processing/status" `
  -BearerToken $token `
  -TimeoutSeconds 300 `
  -PollIntervalSeconds 5
```

## Failure Map

| Symptom | Likely boundary | What to check |
| --- | --- | --- |
| Blank portal page | React startup or static asset load | Browser console, Vite build, undefined variables in render path. |
| `app-name should not be empty` | GitHub job output handoff | Avoid masking values that downstream jobs need as outputs. |
| `401 Unauthorized. A valid Entra access token is required.` | APIM JWT validation | Token audience, tenant, app role/scope, `PORTAL_AUTH_AUDIENCE`, APIM policy. |
| `No module named 'azure.storage'` | Function package dependencies | Ensure `.python_packages/lib/site-packages` is included in the deployed zip. |
| Intake accepted, status always 404 | Async/status boundary | Confirm Service Bus trigger is running and status URL shape is correct. |
| Intake accepted, status stays processing | Pipeline runtime | Check Foundry tools Function logs and Cosmos checkpoints. |
| Complete status without artifact | Form generation | Check artifact mode, storage settings, and Form 1040 generation result. |

## Debugging Order

1. Confirm the portal renders with `npm run build`.
2. Confirm Bicep builds for W2 intake and Foundry tools.
3. Confirm Function packages include dependencies.
4. Run direct Function-key smoke test.
5. Run APIM smoke test with Entra token.
6. Run GitHub Actions workflow manually.
7. Use Cosmos checkpoints to identify the last completed pipeline stage.

