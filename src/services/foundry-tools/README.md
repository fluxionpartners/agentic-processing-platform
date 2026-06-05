# Foundry Tools Function App

This Azure Functions host exposes the Foundry tool registry as HTTP endpoints.

Each endpoint maps to a logical tool name in
`foundry_agents.tools.w2_pipeline_tools.TOOL_REGISTRY`.

Example:

```text
POST /api/extract-w2-document
  -> extract_w2_document
  -> ExtractionAgent
  -> configured extraction adapter
```

The Form 1040 endpoint follows the same pattern:

```text
POST /api/generate-form-1040-document
  -> generate_form_1040_document
  -> Form1040GenerationAgent
  -> configured document artifact adapter
```

The host is intended to be called by the Azure AI Foundry supervisor agent after
the tool manifest is bound to these HTTP endpoints.

Secrets and connection strings should be supplied as Azure app settings backed
by Key Vault references. Production access to Cosmos DB should use managed
identity and Cosmos DB SQL RBAC. Generated 1040 draft artifacts are stored in
the configured artifact store; local development writes HTML files under
`.local_state/form-1040`, while deployed environments use the tools storage
account Blob container.
