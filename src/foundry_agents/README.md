# Foundry Agents

This folder contains the Microsoft Foundry agent definitions for the tax processing pipeline.

## Architecture

The agent orchestration follows a supervisor-worker pattern:

- **Supervisor Orchestrator** - coordinates the pipeline workflow.
- **Intake Agent** - receives W-2 document events.
- **Extraction Agent** - parses documents and extracts structured data.
- **Validation Agent** - applies W-2 business rules and confidence checks.
- **Human Review Agent** - routes flagged records for human decision-making.
- **Tax Mapping Agent** - maps data into 1040-ready and tax planning payloads.
- **Compliance Agent** - applies final governance and compliance checks.
- **Tax Fact Persistence** - checkpoints governed normalized tax facts for resiliency and later tax planning.

## Manual Testing Without Azure Deployment

To test the agent orchestration without deploying Azure infrastructure:

```bash
cd src/foundry_agents
python manual_test_harness.py
```

This will:

1. Create a mock W-2 intake trigger.
2. Execute the full agent pipeline.
3. Log execution steps.
4. Print a summary.

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
| `AZURE_DOCUMENT_INTELLIGENCE_KEY` | empty | Optional local/API-key auth. If empty, the adapter uses Azure identity through `DefaultAzureCredential`. |
| `AZURE_DOCUMENT_INTELLIGENCE_MODEL_ID` | `prebuilt-tax.us.w2` | Model ID used by the Document Intelligence adapter. |
| `TAX_FACT_PERSISTENCE_MODE` | `disabled` | `disabled` skips storage, `local-json` writes governed local JSON records, `cosmos` upserts governed checkpoints to Azure Cosmos DB. |
| `TAX_FACT_PERSISTENCE_PATH` | `.local_state/tax-facts` | Local output folder for `local-json` persistence. This path is ignored by Git. |
| `AZURE_COSMOS_ENDPOINT` | empty | Required when `TAX_FACT_PERSISTENCE_MODE=cosmos`. |
| `AZURE_COSMOS_DATABASE_NAME` | empty | Cosmos DB database used for governed tax fact checkpoints. |
| `AZURE_COSMOS_CONTAINER_NAME` | empty | Cosmos DB container used for governed tax fact checkpoints. Partition key should be `/tenantId`. |
| `AZURE_COSMOS_KEY` | empty | Optional local/API-key auth. If empty, the adapter uses Azure identity through `DefaultAzureCredential`. |
| `ALLOW_FULL_PII_PERSISTENCE` | `false` | Allows full identity values in persisted records only when explicitly enabled. Default persistence masks SSNs. |

The local extraction mode exists only for offline development and repeatable
tests. Production-like runs should set `W2_EXTRACTION_MODE=document-intelligence`;
that mode calls Azure AI Document Intelligence for the uploaded `blobUri` and
maps the response into the normalized W-2 contract.

Production safety rules are enforced in configuration:

- `APP_ENV=prod` cannot use `W2_EXTRACTION_MODE=local`.
- `APP_ENV=prod` requires `COMPLIANCE_MODE=regulated`.
- `APP_ENV=prod` cannot use `HUMAN_REVIEW_MODE=local-auto-approve`.
- `APP_ENV=prod` cannot use `TAX_FACT_PERSISTENCE_MODE=local-json`.
- `APP_ENV=prod` requires durable tax fact persistence.

For local development, use the repository-level `.env.example` as the safe
template. Real `.env` files should stay local and are ignored by Git.

The local loader mirrors production precedence:

1. Process environment variables win. This is how Azure app settings and hosted agent environment variables are surfaced at runtime.
2. Local `.env` fills only missing values for developer convenience.
3. `.env` is skipped when `APP_ENV=prod` is already present in the process environment.

## Current Scope

The agent sequence is implemented with configurable local and Azure-ready adapters:

- **Intake** produces an accepted intake event from an already-uploaded document reference.
- **Extraction** produces a normalized W-2 record, source metadata, field confidence, and overall confidence.
- **Validation** applies required-field, EIN/SSN format, numeric amount, withholding, and confidence rules.
- **Human Review** builds a review packet for blocking validation issues or low-confidence extraction.
- **Tax Mapping** emits 1040-ready federal inputs plus reusable tax intelligence facts.
- **Compliance** emits control results and an audit event envelope.
- **Persistence** checkpoints governed tax fact records for downstream tax planning, resume support, and future analytics.

The Document Intelligence adapter calls the Azure analyze API in
`document-intelligence` mode, while local mode remains deterministic for tests.
The persistence boundary stores normalized facts, not raw extraction responses,
and masks SSN values unless `ALLOW_FULL_PII_PERSISTENCE=true`.

## Agent Adapter Boundaries

Each agent package exposes an adapter boundary:

- **Intake** uses an event/intake adapter for already-uploaded documents.
- **Extraction** switches between local deterministic data and Azure AI Document Intelligence.
- **Validation** keeps W-2 rules behind a validation adapter so rule engines or policy services can replace local rules later.
- **Human Review** switches between local auto-approve, queue-based review, and manual review adapters.
- **Tax Mapping** uses a tax profile adapter, currently `us-federal-2024`.
- **Compliance** keeps control evaluation and audit envelope creation behind a compliance adapter.
- **Persistence** switches between disabled, local JSON, and Cosmos DB checkpoint stores.

Agents stay thin: they load settings, select the adapter, and add orchestration
metadata. This keeps local mock behavior and production-equivalent behavior
aligned behind the same contracts.

## Governed Tax Fact Persistence

Tax planning needs durable facts, but W-2 records are restricted tax PII. The
persistence boundary therefore upserts a governed record as the pipeline
advances. The same record is checkpointed after intake, extraction, validation,
human review when applicable, tax mapping, compliance, and completion.

Each governed record contains:

- document metadata and source reference
- normalized W-2 extraction facts
- field confidence and validation status
- human review summary when applicable
- normalized tax planning facts and 1040-ready mapping output
- compliance/audit metadata
- governance metadata, including sensitivity label and raw extraction policy
- checkpoint stage and lifecycle status, such as `extracted`, `validated`, `mapped`, or `complete`

The default guardrails are:

- raw Document Intelligence output is not persisted
- SSN-like values are masked before storage
- local JSON output is ignored by Git under `.local_state/`
- production cannot use local JSON persistence
- production must configure a durable persistence mode
- Cosmos DB mode requires endpoint, database, and container settings
- Cosmos DB mode uses managed identity by default; API key auth is optional for local/dev only

The extraction checkpoint is intentional: if the pipeline fails after Document
Intelligence succeeds, the normalized W-2 facts have already been persisted and
the document does not need to be re-analyzed just to resume downstream
validation, review, mapping, or compliance work.

## File Structure

```text
foundry_agents/
|-- supervisor/
|   `-- orchestrator.py
|-- intake/
|   |-- adapters.py
|   `-- agent.py
|-- extraction/
|   |-- adapters.py
|   `-- agent.py
|-- validation/
|   |-- adapters.py
|   `-- agent.py
|-- human_review/
|   |-- adapters.py
|   `-- agent.py
|-- tax_mapping/
|   |-- adapters.py
|   `-- agent.py
|-- compliance/
|   |-- adapters.py
|   `-- agent.py
|-- persistence/
|   `-- store.py
|-- config.py
|-- domain.py
|-- pipeline.py
|-- manual_test_harness.py
`-- requirements.txt
```

## Foundry Integration

When ready to integrate with Microsoft Foundry:

1. Deploy each agent worker behind the selected Foundry/Azure hosting model.
2. Configure production app settings instead of local `.env` values.
3. Use Azure AI Document Intelligence for W-2 extraction.
4. Use Cosmos DB for governed tax fact checkpoints.
5. Replace local review behavior with a queue, workflow, or case-management integration.
6. Add Foundry tracing/evaluation around the orchestration and agent calls.
