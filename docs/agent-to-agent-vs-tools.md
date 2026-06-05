# Agent-To-Agent vs Supervisor-With-Tools

This solution currently uses a supervisor-with-tools architecture.

```text
Foundry supervisor agent
  -> HTTP tools
      -> Foundry tools Function App
          -> deterministic Python agent workers
```

This is different from a true agent-to-agent architecture.

## Current Pattern: Supervisor With Tools

The Foundry supervisor is the only LLM-facing agent. It uses tools such as:

```text
extract_w2_document
validate_w2_facts
map_w2_tax_facts
evaluate_w2_compliance
```

Those tools are implemented by governed Python code. This is the safer default
for regulated W-2 and tax workflows because extraction, validation, mapping,
compliance, and persistence remain deterministic and auditable.

## True Agent-To-Agent Pattern

A true agent-to-agent version would make each specialist an independently
registered Foundry agent:

```text
Supervisor Foundry Agent
  -> Extraction Foundry Agent
  -> Validation Foundry Agent
  -> Human Review Foundry Agent
  -> Tax Mapping Foundry Agent
  -> Compliance Foundry Agent
```

Each child agent may have its own:

- `agent.yaml`
- prompt instructions
- model deployment
- tools
- evaluation suite
- deployment identity
- telemetry and traces

## Local Agent-To-Agent Simulation

The test file `tests/test_agent_to_agent_simulation.py` demonstrates the
agent-to-agent shape locally without requiring a live Foundry project.

It wraps each Python worker as a local child-agent endpoint:

```text
SupervisorOrchestrator
  -> LocalAgentEndpoint("extraction-agent")
  -> LocalAgentEndpoint("validation-agent")
  -> LocalAgentEndpoint("tax-mapping-agent")
  -> LocalAgentEndpoint("compliance-agent")
```

This test is not a Foundry deployment. It is a learning and design test that
shows the message-passing shape a true multi-agent deployment would use.

## When To Use Each Pattern

Use supervisor-with-tools when:

- the workflow is regulated
- each step must be deterministic
- data persistence and auditability are more important than autonomous reasoning
- the tool implementation already has clear business logic

Use agent-to-agent when:

- child agents need independent reasoning
- child agents need different models or prompts
- child agents have independent lifecycles
- child agents may be reused by multiple supervisors
- evaluation and tracing need to be isolated per specialist agent

## Recommended Direction For This Platform

Keep the current supervisor-with-tools pattern for the core W-2 processing
pipeline.

Add true agent-to-agent later for reasoning-heavy extensions, such as:

- exception analysis
- human-review summarization
- tax planning narrative generation
- taxpayer-specific advisory exploration
- compliance remediation recommendations

This keeps the regulated processing path controlled while still allowing
agent-to-agent experimentation and learning.
