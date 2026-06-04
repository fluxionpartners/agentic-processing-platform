# Logical Architecture

This document provides a clear, professional logical architecture for the Microsoft Foundry Tax Intelligence Platform. It is designed for enterprise review and highlights component responsibilities, data flows, and security boundaries.

## Architecture Overview

The platform is structured into four logical zones:

1. Ingestion and API boundary
2. Foundry Agent orchestration and AI reasoning
3. Data storage and knowledge services
4. Governance, security, and observability

These zones support a secure, event-driven, multi-agent workflow for W-2 processing and tax intelligence.

## Logical Architecture Diagram

```mermaid
flowchart TD
  subgraph Ingestion[Ingestion & API Boundary]
    direction TB
    APIM[API Management]
    IntakeSvc[Intake Service / Azure Functions]
    Storage[Azure Storage (raw W-2 / artifacts)]
  end

  subgraph Orchestration[Foundry Orchestration]
    direction TB
    Foundry[Foundry Agent Service]
    Orchestrator[Orchestrator Agent]
    Agents[Agent Set]
    Memory[Foundry Memory]
  end

  subgraph Cognitive[Cognitive AI]
    direction TB
    DocInt[Azure AI Document Intelligence]
    OpenAI[Azure OpenAI Models]
    AISearch[Azure AI Search]
  end

  subgraph Data[Data & Storage]
    direction TB
    SQL[Azure SQL]
    Cosmos[Cosmos DB]
    KeyVault[Azure Key Vault]
    Purview[Microsoft Purview]
    DataLake[Azure Storage Data Lake]
  end

  subgraph Integration[Integration & Eventing]
    direction TB
    ServiceBus[Service Bus]
    EventGrid[Event Grid]
    Durable[Durable Functions]
  end

  subgraph Governance[Governance & Observability]
    direction TB
    Monitor[Azure Monitor / Application Insights]
    Defender[Microsoft Defender for Cloud]
    Entra[Entra ID]
  end

  APIM -->|Secure API / Upload| IntakeSvc
  IntakeSvc -->|Store raw document| Storage
  IntakeSvc -->|Publish ingestion event| EventGrid
  EventGrid -->|Trigger workflow| Orchestrator
  Orchestrator -->|Invoke| Agents
  Agents --> Foundry
  Agents -->|Use AI tool| DocInt
  Agents -->|Use AI reasoning| OpenAI
  Agents -->|Knowledge retrieval| AISearch
  Agents -->|Persist structured data| SQL
  Agents -->|Persist memory / semantic artifacts| Cosmos
  Agents -->|Store knowledge artifacts| DataLake
  Agents -->|Secrets access| KeyVault
  Orchestrator -->|Workflow state| Memory
  IntakeSvc -->|Integration events| ServiceBus
  Durable -->|Orchestrate long-running workflows| ServiceBus
  IntakeSvc -->|Audit / logs| Monitor
  Agents -->|Telemetry| Monitor
  SQL -->|Data governance| Purview
  Cosmos -->|Data governance| Purview
  KeyVault -->|Identity access| Entra
  APIM -->|Authentication| Entra
  Monitor -->|Security alerts| Defender
  Defender -->|Security posture| Entra
```

## Component Responsibilities

### API Management / Intake Service
- Expose secure ingress for W-2 uploads and query APIs.
- Authenticate requests using Entra ID.
- Route ingestion payloads to Azure Functions and Event Grid.
- Apply request validation, throttling, and DLP policies.

### Azure Storage
- Store raw W-2 documents, extracted JSON artifacts, and evidence packages.
- Manage private endpoint access and encryption.
- Serve as the raw asset layer for downstream extraction.

### Event Grid / Service Bus / Durable Functions
- Orchestrate asynchronous event-driven processing.
- Provide message durability, retries, and dead-letter handling.
- Manage long-lived review workflows and compensation logic.

### Foundry Agent Service
- Host the multi-agent orchestration layer.
- Manage agent definitions, memory, tools, and iterations.
- Execute the supervisor pattern and coordinate specialized agents.

### Foundry Memory
- Store short-term workflow state and session context.
- Provide retrieval for agent continuity and review state.
- Enforce retention and tiered access.

### Azure AI Document Intelligence
- Perform OCR and structured W-2 field extraction.
- Provide confidence scores and field provenance.
- Enable document classification and form recognition.

### Azure OpenAI Models
- Power classification, mapping, planning, and advisory reasoning.
- Support prompt-based decisioning with policy guardrails.
- Provide explainable narrative outputs with citations.

### Azure AI Search
- Store semantic knowledge, tax rules, and policy content.
- Provide retrieval-based reasoning for tax and compliance knowledge.
- Support vector search and content ranking.

### Azure SQL
- Host normalized relational tax data models.
- Store taxpayer profiles, W-2 assets, and review records.
- Support transactional delivery and BI reporting.

### Cosmos DB
- Store flexible long-term memory and semantic artifacts.
- Support query patterns for agent retrieval and knowledge associations.
- Host audit-friendly event and session records.

### Key Vault
- Manage secrets, API keys, and encryption keys.
- Provide secure access for Foundry, Functions, and AI tools.
- Enable CMK-based encryption for critical data stores.

### Purview
- Apply data classification and governance across tax assets.
- Catalog PII, sensitive fields, and lineage.
- Enforce policies for data retention and access.

### Azure Monitor / Application Insights
- Capture telemetry from agent executions, tool calls, and APIs.
- Provide alerting for errors, latency, and security events.
- Maintain dashboards for operational health and compliance.

### Microsoft Defender for Cloud
- Monitor cloud security posture and configuration drift.
- Detect anomalous access and data exposure.
- Provide guidance for best practices and hardening.

### Entra ID
- Authenticate users, services, and managed identities.
- Enforce RBAC and ABAC across the platform.
- Support MFA and conditional access for privileged operations.

## Security Boundaries

The architecture enforces the following boundaries:

- Ingress is limited to API Management and secured through Entra ID.
- Document storage and data stores are accessible only via private endpoints.
- AI tools and Foundry agents access data using managed identities.
- Governance and monitoring are separated from business data.
- Audit and compliance telemetry is collected independently of application data.

## Data Flow Summary

1. User uploads a W-2 through API Management.
2. Intake Service stores the raw file in Azure Storage.
3. Intake Service publishes an ingestion event to Event Grid.
4. The Foundry Orchestrator receives the event and triggers the agent workflow.
5. Agents call Azure AI Document Intelligence and Azure OpenAI for extraction and reasoning.
6. Validated tax assets are stored in Azure SQL and Cosmos DB.
7. Knowledge retrieval is performed from Azure AI Search.
8. Telemetry and audit events are recorded in Azure Monitor.

## Diagram Notes

- The diagram is intentionally abstracted for enterprise review.
- Implementation details such as specific subnet placement or SKU sizing are captured in the blueprint.
- This logical view emphasizes secure zones, major service groups, and event-driven orchestration.
