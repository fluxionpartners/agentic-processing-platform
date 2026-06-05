# Getting Started

This guide gets the solution running locally without Azure. Local execution uses
the same configuration contract as deployed environments, but defaults to
deterministic adapters so tests are repeatable.

## Prerequisites

- Python 3.11 or newer.
- Git.
- PowerShell 7 or newer.
- Azure CLI, optional for Bicep validation and deployment.

## Clone And Create A Virtual Environment

```powershell
git clone https://github.com/<your-org>/<your-repo>.git
cd <your-repo>

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## Install Dependencies

```powershell
python -m pip install -r src/foundry_agents/requirements.txt
python -m pip install -r src/services/w2-intake/requirements.txt
python -m pip install -r src/services/foundry-tools/requirements.txt
```

## Configure Local Settings

Local defaults work without a `.env` file. To customize local behavior:

```powershell
Copy-Item .env.example .env
```

The `.env` file is ignored by Git. Process environment variables always win,
which mirrors Azure Function App settings in deployed environments.

Useful local settings:

| Setting | Local value |
| --- | --- |
| `W2_EXTRACTION_MODE` | `local` |
| `TAX_FACT_PERSISTENCE_MODE` | `local-json` |
| `FORM_1040_ARTIFACT_MODE` | `local-file` |
| `HUMAN_REVIEW_MODE` | `local-auto-approve` |
| `COMPLIANCE_MODE` | `development` |

## Run The Test Suite

```powershell
python -m unittest discover -s tests
python -m compileall src tests
```

The tests cover:

- configuration loading and production guardrails
- agent adapters
- W-2 extraction and mapping
- draft Form 1040 generation
- compliance checks
- Cosmos/local persistence behavior
- Foundry tool manifest and OpenAPI binding consistency
- local agent-to-agent simulation

## Run The Manual Pipeline Harness

```powershell
python src/foundry_agents/manual_test_harness.py
```

The harness executes the pipeline with deterministic W-2 data:

```text
intake
  -> extraction
  -> validation
  -> tax_mapping
  -> form_generation
  -> compliance
  -> persistence
```

It also exercises a human-review scenario. Local runs may create files under
`.local_state/`; that folder is ignored by Git.

## Validate Infrastructure Templates

Azure CLI is required for this step:

```powershell
az bicep build --file infrastructure/services/w2-intake/bicep/main.bicep
az bicep build --file infrastructure/services/foundry-tools/bicep/main.bicep
```

Bicep may emit provider type or linter warnings depending on your local Bicep
version. The important result is that the build command exits successfully.

## Learn The System

Recommended reading order:

1. [Agent Flow](docs/agent-flow.md)
2. [Architecture](docs/architecture.md)
3. [Foundry Tool Execution Flow](docs/foundry-tool-execution-flow.md)
4. [Deploy Your Own Environment](docs/deploy-your-own.md)
5. [GitHub Actions Deployment](docs/github-actions-deployment.md)

## Deploy Later

When local validation is green, use GitHub Actions for Azure deployment:

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

Then run **Deploy Agentic Processing Platform** in GitHub Actions.
