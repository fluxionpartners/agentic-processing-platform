# W-2 Upload Portal

The W-2 upload portal is a lightweight React application for exercising the
deployed intake boundary without exposing Azure Function keys to browser code.

## Runtime Flow

```text
User browser
  -> Static website hosted on Azure Storage
  -> API Management W2 Intake API
  -> W2 intake Function App
  -> Raw W2 Blob Storage
  -> Service Bus ingestion event
  -> Foundry tools Function App Service Bus trigger
  -> governed pipeline through draft Form 1040 generation
  -> Cosmos DB governed status record
  -> API Management W2 Processing Status API
  -> User browser polls status until complete
```

API Management injects backend Function keys through secret named values. The
portal receives only APIM URLs and optional Entra SPA configuration at build
time.

## Security Model

Implemented controls:

- Function key is not stored in source control or frontend JavaScript.
- APIM stores backend Function keys as secret named values.
- APIM applies CORS only for the deployed portal origin and local dev origin.
- APIM can enforce Entra ID JWT validation when portal authentication is
  enabled through bootstrap.
- Storage static website hosting is enabled, while general blob public access
  remains disabled.
- W-2 intake runtime secrets continue to use Key Vault references.

Production hardening options:

- Add custom domains and Conditional Access policies for production tenants.
- Add malware scanning and content-type validation before document persistence.
- Move APIM to a SKU that supports rate-limit policies when gateway-level
  throttling is required.

## Portal App Registration

Bootstrap can create or update the Entra app registrations used by the demo
portal:

```powershell
.\scripts\github\bootstrap-github-actions.ps1 `
  -SubscriptionId "<subscription-id>" `
  -TenantId "<tenant-id>" `
  -ResourceGroupName "rg-agentic-tax-dev" `
  -Environment dev `
  -Location eastus `
  -NamePrefix taxai `
  -EnableUploadPortalAuthentication `
  -UploadPortalRedirectUris @(
    "http://localhost:5173",
    "https://<portal-host>.web.core.windows.net"
  )
```

The script creates:

- An API app registration with delegated scope `W2Intake.Upload`.
- An API application role `W2Intake.SmokeTest` for non-human CI smoke tests.
- A SPA app registration for the React portal.
- GitHub Environment variables:
  - `PORTAL_AUTH_ENABLED`
  - `PORTAL_AUTH_TENANT_ID`
  - `PORTAL_AUTH_CLIENT_ID`
  - `PORTAL_AUTH_SCOPE`
  - `PORTAL_AUTH_AUDIENCE`

The deployment workflow passes `PORTAL_AUTH_AUDIENCE` into Bicep so APIM can
validate bearer tokens, and passes the SPA values into Vite so the browser app
can acquire an access token with MSAL.

Bootstrap also assigns the smoke-test application role to the GitHub Actions
OIDC service principal. That allows the deployment workflow to request a
short-lived token for the APIM audience when authenticated smoke testing is
enabled, without storing a reusable bearer token in GitHub.

## Local Development

```powershell
cd src/apps/w2-upload-portal
npm install
$env:VITE_W2_INTAKE_API_URL = "https://<apim-name>.azure-api.net/w2-intake/upload-w2"
$env:VITE_W2_PROCESSING_API_URL = "https://<apim-name>.azure-api.net/w2-processing/run"
$env:VITE_W2_STATUS_API_URL = "https://<apim-name>.azure-api.net/w2-processing/status"
$env:VITE_AUTH_ENABLED = "false"
npm run dev
```

The local APIM policy allows `http://localhost:5173` for development.

## Deployed Test

After running the GitHub Actions deployment, open the portal URL printed by the
`Deploy W2 Upload Portal` job. Use the built-in synthetic W-2 text first, then
try an explicit test file.

Expected successful response:

```json
{
  "status": "accepted",
  "blobUri": "https://...",
  "messageId": "...",
  "correlationId": "portal-w2-..."
}
```

Verify downstream resources:

- Raw W-2 file in the `raw-w2` container.
- Service Bus message consumed from `w2-ingestion-queue`.
- Pipeline status through the APIM `w2-processing/status/{correlationId}` operation.
- Draft Form 1040 artifact in the configured artifact container.
- Governed tax fact and artifact metadata record in Cosmos DB.
- Function telemetry in Application Insights.
