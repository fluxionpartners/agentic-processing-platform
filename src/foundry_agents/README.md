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

All agents are currently mocked implementations suitable for:
- Validating the orchestration flow
- Understanding agent responsibilities
- Testing the pipeline logic without cloud costs

Real implementations will be added as each service is built out.

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
├── tax-mapping/
│   └── agent.py
├── compliance/
│   └── agent.py
├── human-review/
│   └── agent.py
├── manual_test_harness.py  # Trigger point for testing
└── requirements.txt
```

## Next Steps

1. Run the manual test harness to validate the pipeline flow
2. As each service is implemented, wire it into the agent
3. Add Foundry SDK dependencies when ready to deploy agents
4. Create tooling definitions for each agent
5. Deploy agents to Microsoft Foundry

