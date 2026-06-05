# Foundry Registration Automation

The GitHub Actions workflow currently packages Foundry artifacts and includes a
registration hook. The hook exists because the Foundry project endpoint, model
deployment, and final tool authentication choices are environment-specific.

Registration can be automated. The repo already contains most of the inputs:

```text
src/foundry_agents/agent.yaml
src/foundry_agents/prompts/
src/foundry_agents/tools/w2_pipeline_tools.json
src/services/foundry-tools/openapi.json
src/foundry_agents/eval.yaml
src/foundry_agents/.foundry/
```

## What Registration Needs

A fully automated Foundry registration step needs:

- Foundry project endpoint
- Azure OpenAI model deployment name
- supervisor agent name/version
- OpenAPI tool binding URL
- tool authentication type
- Foundry service identity or credentials
- evaluation dataset/suite registration target

## Why It Is A Hook Today

The code and artifacts are ready, but the exact registration command depends on
which Foundry deployment path we choose:

```text
Prompt agent with OpenAPI tools
  Register agent instructions and bind openapi.json to the Foundry tools Function App.

Hosted agent
  Containerize the agent runtime and deploy it to Foundry hosted agent service.

SDK/CLI registration
  Use the Foundry SDK, Azure CLI/azd, or REST API from GitHub Actions.
```

Microsoft's hosted agent guidance supports deploying containerized agent code
with `agent.yaml`, and OpenAPI tools can bind an agent to external HTTP APIs
with anonymous, API key, or managed identity authentication. The exact workflow
should be selected once the Foundry project and authentication model are known.

## Automation Sequence

Once those environment-specific values are available, the workflow hook should
be replaced with scripted steps:

```text
1. Download foundry-agent-artifacts.zip
2. Resolve Foundry project endpoint
3. Resolve Foundry tools Function App endpoint
4. Patch or parameterize openapi.json server URL
5. Register/update OpenAPI tool binding
6. Register/update supervisor agent from agent.yaml and prompts
7. Register/update eval dataset and evaluators
8. Run smoke eval
9. Publish agent/eval metadata back to .foundry metadata or workflow summary
```

## Current Status

Automated now:

- GitHub Actions bootstrap
- Azure resource group creation
- GitHub OIDC identity
- W2 intake infrastructure
- Foundry tools infrastructure
- Function App code deployment
- Foundry artifact packaging

Still a hook:

- Foundry project/model deployment creation
- supervisor agent registration
- OpenAPI tool binding registration
- eval suite registration/execution

The reason is not that it cannot be automated. It can. The reason is that the
project endpoint, chosen Foundry registration method, and tool authentication
model need to be finalized first.
