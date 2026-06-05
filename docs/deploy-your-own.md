# Deploy Your Own Environment

This guide is for a reader who finds the repository on GitHub and wants to
stand up their own lower environment with minimal manual work.

## What Gets Deployed

The GitHub Actions workflow deploys two Azure hosts from the same repository:

| Host | Source | Purpose |
| --- | --- | --- |
| W-2 intake Function App | `src/services/w2-intake` | Accepts W-2 upload requests and emits ingestion events. |
| Foundry tools Function App | `src/services/foundry-tools` | Exposes HTTP tools used by the Foundry supervisor agent. |

The workflow also packages the Foundry agent artifacts from
`src/foundry_agents`. Foundry registration is currently a guarded workflow hook
because project endpoint, model deployment, tool authentication, and final
registration command vary by Foundry environment.

## Prerequisites

- Azure subscription.
- Permission to create a resource group.
- Permission to assign RBAC roles in that resource group. Use
  `-GrantUserAccessAdministrator` during bootstrap if your workflow needs to
  create role assignments.
- Azure CLI authenticated with `az login`.
- GitHub CLI authenticated with `gh auth login`.
- PowerShell 7 or newer.

## Bootstrap GitHub Actions

From the repository root:

```powershell
.\scripts\github\bootstrap-github-actions.ps1 `
  -SubscriptionId "<subscription-id>" `
  -TenantId "<tenant-id>" `
  -ResourceGroupName "rg-agentic-tax-dev" `
  -Environment dev `
  -Location eastus `
  -NamePrefix taxai `
  -GrantUserAccessAdministrator
```

The script creates or reuses:

- Azure resource group.
- Entra app registration.
- Service principal.
- GitHub OIDC federated credential.
- GitHub Environment.
- GitHub environment secrets:
  - `AZURE_CLIENT_ID`
  - `AZURE_TENANT_ID`
  - `AZURE_SUBSCRIPTION_ID`
- GitHub environment variables:
  - `AZURE_RESOURCE_GROUP`
  - `AZURE_LOCATION`
  - `NAME_PREFIX`

The workflow uses OIDC federation, so no Azure client secret is stored in
GitHub.

## Run The Deployment

In GitHub:

1. Open **Actions**.
2. Select **Deploy Agentic Processing Platform**.
3. Choose **Run workflow**.
4. Select the environment, location, and name prefix.
5. Leave `deploy_foundry_registration` disabled until your Foundry project
   registration command is finalized.

The workflow validates tests and Bicep first, then provisions Azure resources
and deploys each Function App package.

## Expected Azure Resources

The Bicep templates provision the core resources required by the current
solution:

- Function Apps for intake and Foundry tools.
- Storage accounts for raw documents, runtime storage, and generated artifacts.
- Blob container for draft Form 1040 artifacts.
- Cosmos DB database/container for governed tax fact checkpoints.
- Key Vault for connection-string secrets.
- Application Insights and Log Analytics.
- Managed identities and role assignments.

## Runtime Configuration

The deployed Function Apps receive environment-specific settings from Bicep.
Important settings include:

| Setting | Purpose |
| --- | --- |
| `W2_EXTRACTION_MODE` | `local` for deterministic dev, `document-intelligence` for Azure extraction. |
| `TAX_FACT_PERSISTENCE_MODE` | `cosmos` in deployed environments. |
| `FORM_1040_ARTIFACT_MODE` | `azure-blob` in deployed environments. |
| `FORM_1040_STORAGE_ACCOUNT_URL` | Blob service URL for managed-identity artifact uploads. |
| `FORM_1040_BLOB_CONTAINER_NAME` | Container for draft 1040 artifacts. |
| `COMPLIANCE_MODE` | `development` or `regulated`. |

Local development can use `.env.example` as a template for a Git-ignored `.env`
file.

## Foundry Registration

The repository includes all Foundry-facing artifacts, but final registration is
environment-specific:

- Foundry project endpoint.
- Azure OpenAI model deployment name.
- Tool endpoint base URL.
- Tool authentication model.
- Agent naming/versioning convention.
- Evaluation target.

See [Foundry Registration Automation](foundry-registration-automation.md) for
the exact remaining hook and the recommended automation sequence.

## Validate After Deployment

Run the same checks locally before pushing:

```powershell
python -m unittest discover -s tests
python -m compileall src tests
az bicep build --file infrastructure/services/w2-intake/bicep/main.bicep
az bicep build --file infrastructure/services/foundry-tools/bicep/main.bicep
```

After deployment, review the GitHub Actions output for Function App names and
Azure deployment status. Authenticated endpoint smoke tests should be added once
API Management or the final Function authentication model is selected.

## Production Notes

For production, use GitHub Environment approvals and environment-specific
variables. Production should not use local extraction, local human review
auto-approval, local JSON persistence, or local file artifact storage. Those
constraints are enforced by the runtime configuration loader.
