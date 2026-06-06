# Solution Overview

This repository implements an enterprise-grade Microsoft Foundry Tax
Intelligence Platform as one versioned solution with multiple deployment
boundaries.

## Deployable Units

| Unit | Source | Azure host | Purpose |
| --- | --- | --- | --- |
| W-2 intake | `src/services/w2-intake` | Azure Functions | Accept W-2 upload requests, store raw documents, and publish ingestion events. |
| Foundry tools | `src/services/foundry-tools` | Azure Functions | Expose governed HTTP tools for the Foundry supervisor agent. |
| Foundry supervisor | `src/foundry_agents/agent.yaml` and prompts | Azure AI Foundry | Coordinate the workflow through OpenAPI tool calls. |
| Agent workers | `src/foundry_agents` | Packaged with the tools Function App | Execute deterministic intake, extraction, validation, review, mapping, form generation, compliance, and persistence logic. |

## Runtime Flow

```text
W-2 upload
  -> W2 intake Function App
  -> raw document storage and ingestion event
  -> Foundry supervisor agent
  -> OpenAPI tool binding
  -> Foundry project connection for x-functions-key
  -> Foundry tools Function App
  -> Python tool registry and agent workers
  -> Cosmos DB checkpoints and Blob 1040 artifacts
```

## CI/CD Flow

GitHub Actions validates the repository on every push. Azure provisioning and
deployment run only from manual `workflow_dispatch`.

When deployment is manually started, the workflow:

1. Runs tests and Bicep validation.
2. Packages the W-2 intake Function App.
3. Packages the Foundry tools Function App with the shared agent code.
4. Packages Foundry agent artifacts.
5. Provisions or updates Azure infrastructure.
6. Deploys both Function Apps.
7. Optionally creates or updates the Foundry OpenAPI project connection.
8. Optionally registers the Foundry supervisor agent.

## Configuration And Security

- GitHub Actions authenticates to Azure through OIDC federation.
- The GitHub service principal is scoped to the environment resource group.
- Runtime Function Apps use managed identities.
- Business secrets are stored in Key Vault and referenced from app settings.
- Cosmos DB access uses managed identity and Cosmos DB SQL RBAC.
- The Foundry tools Function key is retrieved during deployment and stored in a
  Foundry project connection, not in source control or GitHub secrets.

## Current Scope

Implemented:

- Local and deployed W-2 orchestration pipeline.
- Local and Azure Document Intelligence extraction paths.
- Validation, human review modes, tax mapping, Form 1040 draft generation, and
  compliance checks.
- Cosmos DB checkpoint persistence and Blob artifact storage.
- GitHub Actions deployment for multiple Azure hosts.
- Opt-in Foundry supervisor registration with OpenAPI tool authentication.

Planned extensions:

- Foundry project/model provisioning automation.
- Foundry evaluation suite registration and execution.
- API Management ingress and authenticated external API smoke tests.
