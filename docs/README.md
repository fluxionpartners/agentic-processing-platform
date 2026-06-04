# Documentation Index

This documentation folder contains comprehensive reference materials for the Microsoft Foundry Tax Intelligence Platform.

## 📚 Core Documentation

### Architecture & Design

- **[Logical Architecture](architecture.md)** — Component structure, data flows, and security boundaries with Mermaid diagrams
- **[Solution Overview](solution-overview.md)** — Service pipeline architecture and integration points
- **[W-2 Intake Service Design](w2-intake-service-design.md)** — Detailed intake service specification

### Implementation

- **[API Documentation](API.md)** — Complete API reference for W-2 intake and agent orchestration endpoints
- **[Enterprise Blueprint](../enterprise-foundry-tax-ai-blueprint.md)** — Full implementation strategy and design rationale
- **[Implementation Phases](../implementation-phases.md)** — Phased delivery roadmap with milestones

## 🚀 Getting Started

- **[Getting Started Guide](../GETTING_STARTED.md)** — Setup, dependencies, and local testing
- **[Deployment Guide](../DEPLOYMENT_GUIDE.md)** — Step-by-step Azure deployment instructions
- **[Contributing Guidelines](../CONTRIBUTING.md)** — How to contribute code and documentation

## 📋 Quick Reference

### Services

| Service | Status | Purpose |
|---------|--------|---------|
| W-2 Intake | ✅ Production | Secure document upload and ingestion |
| Document Extraction | 🟡 In progress | Local deterministic extraction plus Azure Document Intelligence adapter |
| Data Validation | 🟡 Scaffolded | Business rules and compliance validation |
| Tax Mapping | 🟡 In progress | Tax data mapping to 1040 payloads and planning facts |
| Audit Monitoring | 🟡 Scaffolded | Governance, audit logging, and compliance |

### Agents

| Agent | Status | Purpose |
|-------|--------|---------|
| Supervisor Orchestrator | ✅ Complete | Pipeline orchestration and routing |
| Intake Agent | ✅ Complete | Document reception and validation |
| Extraction Agent | ✅ In progress | Local deterministic parsing plus Azure Document Intelligence mode |
| Validation Agent | ✅ Mocked | Business rules engine |
| Tax Mapping Agent | ✅ In progress | Tax payload generation and normalized planning facts |
| Compliance Agent | ✅ In progress | Governance checks and audit envelope |
| Human Review Agent | ✅ Mocked | Manual review routing |
| Tax Fact Persistence | ✅ In progress | Governed local JSON records and Azure Cosmos DB upserts |

## 🏗️ Architecture Overview

```
Client API
    ↓
W-2 Intake Service (Azure Function)
    ↓
Service Bus Event
    ↓
Foundry Orchestrator
    ├─ Extraction Agent (Document Intelligence)
    ├─ Validation Agent (Business Rules)
    ├─ Tax Mapping Agent (1040 Generation)
    ├─ Compliance Agent (Governance)
    └─ Human Review Agent (Manual Review)
    ↓
Persistent Storage (Blob, SQL, Cosmos DB)
```

See [Logical Architecture](architecture.md) for detailed diagrams.

The current agent pipeline writes governed tax fact records through a dedicated persistence boundary. The same record is checkpointed after key stages so extracted W-2 facts survive later-stage failures. The persisted shape includes normalized W-2 facts, validation and review status, planning facts, compliance metadata, lifecycle status, and a restricted tax PII sensitivity label. Raw extraction responses are not persisted, and SSNs are masked by default.

## 📖 Documentation Structure

```
docs/
├── README.md                           # This file
├── architecture.md                     # Logical architecture with diagrams
├── solution-overview.md                # Service pipeline and integration
├── w2-intake-service-design.md        # Intake service specification
└── API.md                             # API reference documentation

Root-level documentation:
├── GETTING_STARTED.md                 # Setup and local testing
├── DEPLOYMENT_GUIDE.md                # Azure deployment steps
├── CONTRIBUTING.md                    # Contribution guidelines
├── enterprise-foundry-tax-ai-blueprint.md  # Full implementation blueprint
└── implementation-phases.md            # Delivery roadmap
```

## 🎯 Finding Information

### I want to...

**Understand the architecture**
- Start with [Logical Architecture](architecture.md)
- Review [Solution Overview](solution-overview.md)
- Check [Enterprise Blueprint](../enterprise-foundry-tax-ai-blueprint.md)

**Get started locally**
- See [Getting Started Guide](../GETTING_STARTED.md)
- Run `python src/foundry_agents/manual_test_harness.py`
- Review agent code in `src/foundry_agents/`

**Deploy to Azure**
- Follow [Deployment Guide](../DEPLOYMENT_GUIDE.md)
- Run `scripts/services/w2-intake/deploy-all.ps1`
- Monitor with Application Insights

**Integrate services**
- See [API Documentation](API.md)
- Review service READMEs in `src/services/`
- Check Bicep templates in `infrastructure/services/`

**Contribute code**
- Read [Contributing Guidelines](../CONTRIBUTING.md)
- Follow commit message conventions
- Write tests for new features

**Understand data flow**
- See [W-2 Intake Design](w2-intake-service-design.md)
- Review agent orchestration in `src/foundry_agents/supervisor/`
- Check event schema in Service Bus

**Plan implementation**
- Review [Implementation Phases](../implementation-phases.md)
- Check service status in table above
- See roadmap milestones and dependencies

## 🔑 Key Concepts

### Event-Driven Architecture

Documents flow through the pipeline via:
1. HTTP upload to W-2 Intake Service
2. Service Bus event publication
3. Agent orchestrator routing
4. Sequential agent processing
5. Persistent storage updates

### Service-Based Layout

Each service is independently deployable:
- `src/services/<service>/` — Application code
- `infrastructure/services/<service>/bicep/` — Azure resources
- `scripts/services/<service>/` — Deployment scripts

### Agent Orchestration

Supervisor-worker pattern:
- **Supervisor**: Routes documents through pipeline stages
- **Workers**: Specialized agents handle each processing step
- **Memory**: State tracking for correlation and audit trails

### Security & Compliance

- Managed identities (RBAC, no secrets in code)
- Encryption at rest (Storage, SQL, Cosmos)
- Encryption in transit (TLS 1.2)
- Audit logging (Application Insights)
- Network isolation (Service Bus policies)

## 📊 Technology Stack

**Infrastructure**
- Azure Functions (Python 3.11, Consumption)
- Azure Storage (GRS, blob containers)
- Azure Service Bus (event messaging)
- Azure SQL Database
- Cosmos DB (semantic memory)
- Azure Key Vault (secrets)

**AI & Cognitive**
- Microsoft Foundry (orchestration)
- Azure Document Intelligence (parsing)
- Azure OpenAI (reasoning)
- Azure AI Search (retrieval)

**Development**
- Python 3.11+
- Bicep (Infrastructure as Code)
- PowerShell (automation)
- Git & GitHub

## 🔗 Related Resources

- **Microsoft Foundry** — https://aka.ms/foundry
- **Azure Functions** — https://learn.microsoft.com/en-us/azure/azure-functions/
- **Bicep Documentation** — https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/
- **Azure Design Patterns** — https://learn.microsoft.com/en-us/azure/architecture/

## ❓ Common Questions

**Q: Can I test locally without Azure?**
A: Yes! Run `python src/foundry_agents/manual_test_harness.py` for complete pipeline testing.

**Q: What are the deployment costs?**
A: Approximately $14-26/month for dev environment. See Deployment Guide for details.

**Q: Is this production-ready?**
A: W-2 Intake Service is production-ready. Other services are scaffolded and ready for implementation.

**Q: Can I customize the pipeline?**
A: Yes! The architecture supports custom agents and service implementations. See Contributing Guidelines.

**Q: How do I report issues?**
A: Open a GitHub issue with detailed description, steps to reproduce, and environment details.

## 📞 Support

- **Questions**: Open GitHub Discussions
- **Bugs**: Report via GitHub Issues
- **Contributions**: See Contributing Guidelines
- **Documentation**: Submit documentation PRs

---

**Last Updated**: January 2024  
**Version**: 1.0.0  
**Status**: Production Ready (Intake Service), Reference Architecture (Full Platform)

