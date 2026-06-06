# Foundry Registration Automation

The repository automates the current Foundry registration path for a prompt
supervisor agent with OpenAPI tools. The registration job is opt-in during
manual GitHub Actions dispatch so ordinary pushes can validate the public repo
without requiring Azure or Foundry credentials.

## What Gets Registered

The workflow uses these source artifacts:

```text
src/foundry_agents/agent.yaml
src/foundry_agents/prompts/supervisor.md
src/foundry_agents/eval.yaml
src/foundry_agents/.foundry/
src/services/foundry-tools/openapi.json
```

The deployed runtime is:

```text
Foundry supervisor agent
  -> OpenAPI tool definition
  -> Foundry project connection with x-functions-key
  -> Foundry tools Function App /api endpoints
  -> governed Python tool registry and agent workers
```

## Foundry Provisioning

Foundry provisioning is available as a separate script so a central AI platform
team or another department can run it independently of this repository's GitHub
Actions bootstrap:

```powershell
.\scripts\foundry\Ensure-FoundryProject.ps1 `
  -SubscriptionId "<subscription-id>" `
  -ResourceGroupName "rg-agentic-tax-dev" `
  -FoundryAccountName "taxaidevfoundry" `
  -FoundryProjectName "taxai-dev-project" `
  -Location eastus `
  -ModelDeploymentName "gpt-4o-mini-dev"
```

For a single lower-environment setup, the GitHub bootstrap script can also call
that provisioning script before configuring GitHub Actions:

```powershell
.\scripts\github\bootstrap-github-actions.ps1 `
  -SubscriptionId "<subscription-id>" `
  -TenantId "<tenant-id>" `
  -ResourceGroupName "rg-agentic-tax-dev" `
  -Environment dev `
  -Location eastus `
  -NamePrefix taxai `
  -ProvisionFoundry `
  -FoundryAccountName "taxaidevfoundry" `
  -FoundryProjectName "taxai-dev-project" `
  -FoundryModelDeploymentName "gpt-4o-mini-dev" `
  -FoundryOpenApiConnectionName "w2toolsfnkey"
```

This calls:

```text
scripts/foundry/Ensure-FoundryProject.ps1
infrastructure/foundry/bicep/main.bicep
```

The Foundry Bicep template creates:

- Azure AI Foundry account: `Microsoft.CognitiveServices/accounts`, kind
  `AIServices`
- Foundry project:
  `Microsoft.CognitiveServices/accounts/projects`
- Optional model deployment:
  `Microsoft.CognitiveServices/accounts/deployments`

The script can be rerun safely for the same environment. If model deployment is
centrally managed, pass `-SkipFoundryModelDeployment` to bootstrap and provide
the existing `-FoundryModelDeploymentName`.

## Required Environment Values

For each GitHub Environment, these values are set through the bootstrap script
or supplied as workflow dispatch inputs:

| Value | Purpose |
| --- | --- |
| `FOUNDRY_PROJECT_ENDPOINT` | Foundry project endpoint, for example `https://<resource>.services.ai.azure.com/api/projects/<project>`. |
| `FOUNDRY_ACCOUNT_NAME` | Azure AI Foundry account resource name. |
| `FOUNDRY_PROJECT_NAME` | Azure AI Foundry project resource name. |
| `FOUNDRY_MODEL_DEPLOYMENT_NAME` | Model deployment used by the supervisor agent. |
| `FOUNDRY_OPENAPI_CONNECTION_NAME` | Project connection name. Defaults to `w2toolsfnkey`. |

`FOUNDRY_OPENAPI_CONNECTION_ID` is optional. If supplied, the workflow uses that
existing connection. If omitted, the workflow creates or updates the connection.

## Bootstrap Without Provisioning

If your organization already owns the Foundry account/project/model deployment,
run bootstrap without `-ProvisionFoundry` and pass the existing values:

```powershell
.\scripts\github\bootstrap-github-actions.ps1 `
  -SubscriptionId "<subscription-id>" `
  -TenantId "<tenant-id>" `
  -ResourceGroupName "rg-agentic-tax-dev" `
  -Environment dev `
  -Location eastus `
  -NamePrefix taxai `
  -FoundryProjectEndpoint "https://<foundry-resource>.services.ai.azure.com/api/projects/<project>" `
  -FoundryAccountName "<foundry-account-name>" `
  -FoundryProjectName "<foundry-project-name>" `
  -FoundryModelDeploymentName "<model-deployment-name>" `
  -FoundryOpenApiConnectionName "w2toolsfnkey"
```

The bootstrap script configures GitHub OIDC, resource group scoped Azure RBAC,
provider registration, and the Foundry environment variables.

## Workflow Sequence

When `deploy_foundry_registration` is selected, GitHub Actions performs this
sequence after infrastructure and Function App deployment:

```text
1. Capture the deployed Foundry tools endpoint from Bicep.
2. Retrieve the deployed tools Function App default host key.
3. Create or update a Foundry project connection.
4. Store the key in that connection as custom key x-functions-key.
5. Resolve openapi.json to the deployed /api endpoint.
6. Add the OpenAPI apiKey security scheme for x-functions-key.
7. Build the agent registration payload from agent.yaml and supervisor.md.
8. Register the supervisor agent through the Foundry project endpoint.
9. Upload resolved registration artifacts for audit and troubleshooting.
```

The Function key is not stored in source control, GitHub secrets, or workflow
inputs. It is read by the GitHub OIDC identity at deployment time and stored in
the Foundry project connection.

## Scripts

```text
scripts/foundry/Ensure-FoundryOpenApiConnection.ps1
scripts/foundry/Register-FoundryAgent.ps1
```

`Ensure-FoundryOpenApiConnection.ps1` is idempotent. It creates or updates the
project connection under:

```text
Microsoft.CognitiveServices/accounts/{account}/projects/{project}/connections/{connection}
```

`Register-FoundryAgent.ps1` prepares the resolved OpenAPI document and
registration payload, then calls the Foundry agent REST endpoint. Use
`prepare_foundry_registration_only` in the workflow to generate the artifacts
without making the remote registration call.

## OpenAPI Naming

Foundry OpenAPI tool operation IDs must use supported characters. The HTTP
routes still use the business tool names, such as `/api/run-w2-pipeline`, while
`operationId` values use Foundry-compatible names such as
`run_w_two_pipeline`.

The binding test verifies that every Python registry tool has a matching HTTP
route and that the OpenAPI operation IDs satisfy the Foundry naming rule.

## Current Scope

Automated:

- GitHub OIDC bootstrap and environment variables.
- Azure infrastructure and Function App deployment.
- Foundry tools Function App endpoint capture.
- Foundry project connection creation/update for Function-key auth.
- Supervisor prompt agent registration with OpenAPI tool binding.
- Resolved registration artifact upload.

Not yet automated:

- Creating the Foundry account/project itself.
- Deploying the model into the Foundry project.
- Registering/running Foundry evaluation suites.

Those are separate lifecycle steps because many teams manage Foundry projects
and model deployments centrally. The workflow is ready to consume those
environment-specific values once they exist.
