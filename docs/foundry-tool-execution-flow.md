# Foundry Tool Execution Flow

This solution uses a Foundry supervisor agent with governed HTTP tools. The
supervisor chooses the next action, but deterministic Python workers perform
the regulated business operations.

## Runtime Flow

```text
Foundry supervisor agent
  -> OpenAPI tool binding
  -> Foundry Tools Azure Function endpoint
  -> foundry_tools_app.ROUTE_TO_TOOL
  -> foundry_agents.tools.w2_pipeline_tools.TOOL_REGISTRY
  -> governed Python agent worker
  -> configured adapter
```

Example:

```text
POST /api/generate-form-1040-document
  -> generate_form_1040_document
  -> Form1040GenerationAgent.process
  -> HtmlForm1040GenerationAdapter
  -> local file or Blob artifact store
```

## Pipeline Sequence

The complete governed W-2 flow is:

```text
intake
  -> extraction
  -> validation
  -> human_review when required
  -> tax_mapping
  -> form_generation
  -> compliance
  -> persistence
```

Tax mapping creates the `form1040` data payload. Form generation turns that
payload into a draft document artifact and records storage metadata. Compliance
then verifies extraction, validation, mapping, generated artifact, audit, and
PII controls before final persistence.

## Binding Files

- `src/foundry_agents/agent.yaml` defines the supervisor and runtime settings.
- `src/foundry_agents/prompts/supervisor.md` instructs the tool sequence.
- `src/foundry_agents/tools/w2_pipeline_tools.json` defines logical tool schemas.
- `src/services/foundry-tools/openapi.json` exposes HTTP operation IDs.
- `src/services/foundry-tools/function_app.py` defines Azure Functions routes.
- `src/services/foundry-tools/foundry_tools_app.py` maps routes to registry keys.
- `src/foundry_agents/tools/w2_pipeline_tools.py` calls the Python agent workers.
