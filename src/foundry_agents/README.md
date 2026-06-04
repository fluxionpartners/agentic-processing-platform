# Foundry Agents

This folder contains the Microsoft Foundry agent definitions for the tax processing pipeline.

## Architecture

The agent orchestration follows a supervisor-worker pattern:

- **Supervisor Orchestrator** — coordinates the pipeline workflow
- **Intake Agent** — receives and validates W-2 documents
- **Extraction Agent** — parses documents and extracts structured data
- **Validation Agent** — applies business rules and compliance checks
- **Tax Mapping Agent** — maps data into 1040/tax payloads
- **Compliance Agent** — applies final governance and compliance checks
- **Human Review Agent** — routes flagged records for human decision-making

## Manual Testing Without Azure Deployment

To test the agent orchestration without deploying Azure infrastructure:

### Quick Start

```bash
cd src/foundry_agents
python manual_test_harness.py
```

This will:
1. Create a mock W-2 intake trigger
2. Execute the full agent pipeline
3. Log execution steps
4. Print a summary

## Runtime Configuration

Runtime behavior is selected with environment variables. Deployment platforms
such as Azure Functions, Container Apps, Foundry hosted agents, and CI/CD should
inject these values per environment; application code reads them through
`AgentSettings`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_ENV` | `local` | Runtime environment: `local`, `dev`, `test`, `uat`, or `prod`. |
| `W2_EXTRACTION_MODE` | `local` | `local` uses deterministic development data. `document-intelligence` selects the Azure AI Document Intelligence adapter. |
| `W2_VALIDATION_STRICTNESS` | `standard` | `standard` applies core W-2 rules. `strict` adds additional review-oriented checks. |
| `HUMAN_REVIEW_MODE` | `local-auto-approve` | `local-auto-approve` lets local tests continue. `queue` and `manual` pause the pipeline for human decision. |
| `TAX_MAPPING_PROFILE` | `us-federal-2024` | Selects the tax mapping profile. |
| `COMPLIANCE_MODE` | `development` | `development` applies local controls. `regulated` enables stricter compliance checks. |
| `LOW_CONFIDENCE_THRESHOLD` | `0.85` | Field-confidence threshold below which validation routes to review. |
| `REQUIRE_MASKED_PII_IN_LOGS` | `true` | Requires masked SSN-like values in compliance checks. |
| `AUDIT_EVENT_ENABLED` | `true` | Emits compliance audit envelopes. |
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` | empty | Required when `W2_EXTRACTION_MODE=document-intelligence`. |
| `AZURE_DOCUMENT_INTELLIGENCE_MODEL_ID` | `prebuilt-tax.us.w2` | Model ID used by the future Document Intelligence adapter. |

The local mode exists only for offline development and repeatable tests. Production-like runs should set `W2_EXTRACTION_MODE=document-intelligence`; that mode fails fast until the Azure adapter is fully wired, so sample data is not used accidentally.

Production safety rules are enforced in configuration:
- `APP_ENV=prod` cannot use `W2_EXTRACTION_MODE=local`.
- `APP_ENV=prod` requires `COMPLIANCE_MODE=regulated`.
- `APP_ENV=prod` cannot use `HUMAN_REVIEW_MODE=local-auto-approve`.

For local development, use the repository-level `.env.example` as the safe
template. Real `.env` files should stay local and are ignored by Git.

The local loader mirrors production precedence:
1. Process environment variables win. This is how Azure app settings and hosted
   agent environment variables are surfaced at runtime.
2. Local `.env` fills only missing values for developer convenience.
3. `.env` is skipped when `APP_ENV=prod` is already present in the process
   environment.

### What the Test Does

- **Full Pipeline Test**: Walks through intake → extraction → validation → tax mapping → compliance → finalization
- **Human Review Test**: Injects validation issues and routes to human review before completing

### Expected Output

The test harness prints a JSON log of each agent execution, showing:
- Correlation ID and pipeline ID
- Results from each agent
- Timestamps
- Next step in the workflow

## Integration with Foundry

When ready to integrate with Microsoft Foundry:

1. Each agent will be deployed as a Foundry Agent Service
2. The orchestrator will use Foundry's workflow/orchestration APIs
3. Agents can integrate with Azure AI services (Document Intelligence, Search, etc.)
4. Event-driven triggers will replace manual test harness

## Current Scope

The local agent sequence is implemented with deterministic development adapters:
- **Extraction** produces a normalized W-2 record, source metadata, field confidence, and overall confidence.
- **Validation** applies required-field, EIN/SSN format, numeric amount, withholding, and confidence rules.
- **Human Review** builds a review packet for blocking validation issues or low-confidence extraction.
- **Tax Mapping** emits 1040-ready federal inputs plus reusable tax intelligence facts.
- **Compliance** emits control results and an audit event envelope.

The deterministic extraction adapter is the seam for the future Azure AI Document Intelligence integration. The agent contracts are intentionally stable so hosted Foundry agents and tool calls can replace local adapters without rewriting the supervisor pipeline.

## File Structure

```
foundry_agents/
├── supervisor/
│   └── orchestrator.py    # Pipeline coordinator
├── intake/
│   └── agent.py
├── extraction/
│   └── agent.py
├── validation/
│   └── agent.py
├── tax_mapping/
│   └── agent.py
├── compliance/
│   └── agent.py
├── human_review/
│   └── agent.py
├── domain.py                 # Shared W-2 contracts and rule helpers
├── pipeline.py               # Programmatic pipeline runner
├── manual_test_harness.py  # Trigger point for testing
└── requirements.txt
```

## Next Steps

1. Run the manual test harness to validate the pipeline flow
2. As each service is implemented, wire it into the agent
3. Add Foundry SDK dependencies when ready to deploy agents
4. Create tooling definitions for each agent
5. Deploy agents to Microsoft Foundry

