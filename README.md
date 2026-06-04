# Microsoft Foundry Tax Intelligence Platform

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-green)](https://www.python.org/downloads/)
[![Azure Services](https://img.shields.io/badge/Azure-Multi--Service-0078D4)](https://azure.microsoft.com)
[![Microsoft Foundry](https://img.shields.io/badge/Microsoft-Foundry-512BD4)](https://aka.ms/foundry)

An enterprise-grade, agentic processing platform built on **Microsoft Foundry** for intelligent tax document processing. This reference architecture demonstrates how to build AI agent-driven workflows with secure intake, intelligent extraction, validation, and compliance orchestration.

## 🎯 Overview

This platform showcases an enterprise production-ready implementation of:

- **Event-driven service architecture** — Modular, independently deployable services
- **AI agent orchestration** — Supervisor-worker pattern with 7 specialized agents
- **Secure document processing** — W-2 intake with encryption, audit trails, and compliance
- **Local-first testing** — Test the entire pipeline locally before cloud deployment (zero Azure costs)
- **Infrastructure as Code** — Bicep templates for reproducible, enterprise deployments
- **Observability & governance** — Application Insights, Key Vault, managed identities

## 📋 Features

✅ **Production-Ready Services**
- Secure W-2 document intake with base64 handling and hierarchical blob storage
- Event-driven pipeline with Azure Service Bus integration
- Python Azure Functions with async processing

✅ **Agent-Based AI Orchestration**
- Supervisor orchestrator coordinating multi-stage workflows
- 7 specialized agents: Intake → Extraction → Validation → Tax Mapping → Compliance → Human Review
- Local deterministic adapters plus Azure Document Intelligence extraction mode
- Governed tax fact persistence for downstream planning and analytics

✅ **Enterprise Infrastructure**
- Complete Bicep IaC templates with best practices
- Network isolation, encryption at rest/in-transit, managed identities
- Cost-optimized tier selection (Consumption, Standard, GRS)

✅ **Zero-Cost Local Testing**
- Test the entire agent pipeline locally before deploying to Azure
- Manual test harness with two scenarios (full pipeline, with human review)
- Immediate feedback loop for development

✅ **Professional Documentation**
- Logical architecture diagrams (Mermaid)
- Service design specifications
- Deployment guides and API documentation

## 🚀 Quick Start

### Test Locally (No Azure Required)

```bash
# Clone the repository
git clone https://github.com/your-org/agentic-processing-platform.git
cd agentic-processing-platform

# Test the agent orchestration pipeline
cd src/foundry_agents
python manual_test_harness.py
```

**Expected output**: Complete W-2 processing workflow with agent execution logs, timestamps, and final summary.

See [Getting Started](GETTING_STARTED.md) for detailed setup instructions.

### Deploy to Azure

```bash
# Deploy intake service infrastructure and application
cd scripts/services/w2-intake
./deploy-all.ps1
```

See [Deployment Guide](DEPLOYMENT_GUIDE.md) for step-by-step cloud deployment.

## 📂 Repository Structure

```
├── docs/                              # Architecture and reference documentation
│   ├── README.md                      # Documentation index
│   ├── architecture.md                # Logical architecture with diagrams
│   ├── solution-overview.md           # Service pipeline overview
│   └── w2-intake-service-design.md   # W-2 intake service specification
│
├── src/                               # Application source code
│   ├── services/                      # Enterprise service implementations
│   │   ├── w2-intake/                # Secure intake service (production)
│   │   ├── document-extraction/      # Extraction service (scaffolded)
│   │   ├── data-validation/          # Validation service (scaffolded)
│   │   ├── tax-mapping/              # Tax mapping service (scaffolded)
│   │   └── audit-monitoring/         # Compliance service (scaffolded)
│   │
│   └── foundry_agents/                # Agent orchestration (local testable)
│       ├── supervisor/                # Orchestrator agent
│       ├── intake/                    # Intake agent
│       ├── extraction/                # Extraction agent
│       ├── validation/                # Validation agent
│       ├── tax-mapping/               # Tax mapping agent
│       ├── compliance/                # Compliance agent
│       ├── human-review/              # Human review agent
│       ├── manual_test_harness.py    # Local test entry point
│       └── README.md                  # Agent documentation
│
├── infrastructure/                    # IaC: Azure Bicep templates
│   └── services/                      # Service infrastructure modules
│       ├── w2-intake/                # Intake service Azure resources
│       ├── document-extraction/      # Extraction service resources
│       ├── data-validation/          # Validation service resources
│       ├── tax-mapping/              # Tax mapping service resources
│       └── audit-monitoring/         # Compliance service resources
│
├── scripts/                           # Deployment and operational scripts
│   ├── deploy-all-services.ps1       # Deploy entire platform
│   └── services/                      # Service-specific deployment
│       ├── w2-intake/
│       ├── document-extraction/
│       ├── data-validation/
│       ├── tax-mapping/
│       └── audit-monitoring/
│
├── enterprise-foundry-tax-ai-blueprint.md  # Full implementation blueprint
├── implementation-phases.md                 # Phased delivery roadmap
├── LICENSE                                  # Apache 2.0
├── CONTRIBUTING.md                         # Contribution guidelines
├── GETTING_STARTED.md                      # Setup and quick start
├── DEPLOYMENT_GUIDE.md                     # Cloud deployment instructions
└── README.md                                # This file
```

## 🏗️ Architecture

The platform follows a **service-based architecture** with **event-driven agent orchestration**:

```
┌─────────────────────────────────────────────────────────┐
│  Client Application / API Management                    │
└─────────────────┬───────────────────────────────────────┘
                  │ Secure API
┌─────────────────▼───────────────────────────────────────┐
│  W-2 Intake Service (Azure Function)                    │
│  - Document validation & encryption                     │
│  - Hierarchical blob storage                            │
│  - Event publishing (Service Bus)                       │
└─────────────────┬───────────────────────────────────────┘
                  │ Service Bus Event
┌─────────────────▼───────────────────────────────────────┐
│  Foundry Agent Orchestrator                             │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Supervisor: Routes through pipeline stages      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌────────────────────────────────────────────────┐   │
│  │ Agents (7 specialized workers)                  │   │
│  │ • Extraction (AI Document Intelligence)         │   │
│  │ • Validation (Business rules engine)            │   │
│  │ • Tax Mapping (1040 payload generation)         │   │
│  │ • Compliance (Governance checks)                │   │
│  │ • Human Review (Flagged record routing)         │   │
│  └────────────────────────────────────────────────┘   │
└─────────────────┬───────────────────────────────────────┘
                  │ Persistent data
        ┌─────────┴─────────┬─────────────────────┐
        │                   │                     │
    Storage           SQL Database         Cosmos DB
   (Blobs)          (Structured)        (Semantic Memory)
```

See [Architecture Documentation](docs/architecture.md) for detailed diagrams and component responsibilities.

## 📖 Documentation

| Document | Purpose |
|----------|---------|
| [Getting Started](GETTING_STARTED.md) | Setup, dependencies, local testing |
| [Deployment Guide](DEPLOYMENT_GUIDE.md) | Azure deployment, prerequisites, troubleshooting |
| [API Documentation](docs/API.md) | Service endpoints, request/response formats |
| [Architecture](docs/architecture.md) | Logical design, component interactions |
| [Solution Overview](docs/solution-overview.md) | Service pipeline, integration points |
| [Blueprint](enterprise-foundry-tax-ai-blueprint.md) | Full implementation strategy |
| [Implementation Phases](implementation-phases.md) | Phased delivery roadmap |

## 🛠️ Technology Stack

**Azure Services**
- Azure Functions (Python 3.11, Consumption tier)
- Azure Storage (GRS, blob containers)
- Azure Service Bus (Standard, event-driven)
- Azure SQL Database
- Cosmos DB (semantic memory)
- Azure Key Vault (secrets management)
- Application Insights + Log Analytics (observability)
- API Management (API gateway, Consumption tier)

**AI & Cognitive Services**
- Microsoft Foundry (agent orchestration)
- Azure AI Document Intelligence (document parsing)
- Azure OpenAI (reasoning models)
- Azure AI Search (knowledge retrieval)

**Infrastructure & Deployment**
- Bicep (Infrastructure as Code)
- PowerShell (deployment automation)
- Managed Identities (RBAC, zero-secret operations)

## 🔒 Security & Compliance

✅ **Encryption**: TLS 1.2 in-transit, encryption at rest  
✅ **Access Control**: Managed identities, RBAC, service principals  
✅ **Secrets Management**: Azure Key Vault with soft delete & purge protection  
✅ **Audit Trails**: Application Insights, diagnostic logging  
✅ **Network Isolation**: Service Bus with shared access policies  
✅ **Data Governance**: Microsoft Purview integration ready  
✅ **PII Guardrails**: normalized tax facts are persisted without raw extraction output, SSNs are masked by default, and production cannot use local JSON persistence

### Tax Data Persistence Guardrails

The agent pipeline persists planning-ready tax facts through a dedicated governance boundary. The same governed record is checkpointed after intake, extraction, validation, human review when applicable, tax mapping, compliance, and completion. Persisted records include document metadata, normalized W-2 facts, confidence scores, validation/review status, tax planning facts, lifecycle status, and audit metadata.

By default, the platform does not persist raw Document Intelligence responses and masks SSN-like values before storage. Local development can use `TAX_FACT_PERSISTENCE_MODE=local-json`, which writes to `.local_state/`; production should use `TAX_FACT_PERSISTENCE_MODE=cosmos`, which upserts governed checkpoints to Azure Cosmos DB using managed identity by default. The extraction checkpoint allows downstream processing to resume without re-running Document Intelligence after a later-stage failure.

## 🚦 Getting Started

### Prerequisites

- **Python 3.11+**
- **Azure CLI** (for cloud deployment)
- **PowerShell 7+** (for deployment scripts)
- **Git**
- **Azure Subscription** (for cloud deployment; local testing requires none)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/your-org/agentic-processing-platform.git
cd agentic-processing-platform

# Set up Python environment
python -m venv venv
source venv/Scripts/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r src/foundry_agents/requirements.txt
pip install -r src/services/w2-intake/requirements.txt

# Test locally (no Azure costs)
cd src/foundry_agents
python manual_test_harness.py
```

See [Getting Started](GETTING_STARTED.md) for detailed instructions.

## 📊 Testing

**Local Testing** (No Azure Deployment)
```bash
cd src/foundry_agents
python manual_test_harness.py
```
- Tests the full agent orchestration pipeline
- Two scenarios: full pipeline, pipeline with human review
- Mocked data, immediate feedback

**Unit Tests**
```bash
python -m unittest discover -s tests
```

**Integration Tests** (Requires Azure, coming soon)
```bash
pytest tests/integration/
```

## 📝 Contributing

We welcome contributions! Please see [Contributing Guidelines](CONTRIBUTING.md) for:
- Code style and best practices
- Pull request process
- Commit message conventions
- Testing requirements

## 📄 License

This project is licensed under the **Apache License 2.0**. See [LICENSE](LICENSE) for details.

## 🤝 Support

- **Documentation**: See [docs/](docs/) for architecture, design, and deployment guides
- **Issues**: Report bugs or feature requests via GitHub Issues
- **Discussions**: For architecture questions, use GitHub Discussions

## 🎓 Reference & Learning

This is a **reference architecture** demonstrating enterprise patterns for:
- AI agent orchestration with Microsoft Foundry
- Event-driven service architecture on Azure
- Infrastructure as Code with Bicep
- Production-grade document processing pipelines

Perfect for architects, engineers, and teams evaluating multi-agent AI platforms.

---

**Built for Enterprise. Designed for Impact.**

