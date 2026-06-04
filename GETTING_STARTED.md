# Getting Started

Welcome to the Microsoft Foundry Tax Intelligence Platform. This guide will help you set up your environment and test the agent orchestration pipeline locally.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.11 or higher** — [Download](https://www.python.org/downloads/)
- **Git** — [Download](https://git-scm.com/)
- **Azure CLI** (optional, for cloud deployment) — [Install](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
- **PowerShell 7+** (for deployment scripts) — [Install](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell)

## Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/agentic-processing-platform.git
cd agentic-processing-platform
```

## Step 2: Set Up Python Environment

### On Windows

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip
```

### On macOS/Linux

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
python -m pip install --upgrade pip
```

## Step 3: Install Dependencies

Install the required Python packages:

```bash
# Install foundry agents dependencies
pip install -r src/foundry_agents/requirements.txt

# Install W-2 intake service dependencies (for local testing)
pip install -r src/services/w2-intake/requirements.txt
```

Currently minimal dependencies are set up for local testing. When integrating with Microsoft Foundry and Azure services, additional packages will be installed.

## Step 4: Run Local Tests

### Test the Agent Orchestration Pipeline

```bash
cd src/foundry_agents
python manual_test_harness.py
```

**Expected Output:**
```
[PIPELINE] Starting W-2 processing pipeline...
[INTAKE AGENT] Received W-2 document. Correlation ID: ...
[EXTRACTION AGENT] Extracted fields: Box 1-4, EIN, SSN...
[VALIDATION AGENT] Applied business rules. Issues found: ...
[AUDIT AGENT] Governance checks passed.
[COMPLIANCE AGENT] Record compliant.
[PIPELINE COMPLETE] Final result: ...
```

### Test Specific Scenarios

The test harness supports two scenarios:

**1. Full Pipeline (No Issues)**
```bash
python manual_test_harness.py --scenario=full
```

**2. Pipeline with Human Review**
```bash
python manual_test_harness.py --scenario=human-review
```

## Step 5: Explore the Codebase

### Understand the Service Architecture

```
src/services/                    # Enterprise services
├── w2-intake/                   # Production W-2 intake
├── document-extraction/         # Extraction service
├── data-validation/             # Validation service
├── tax-mapping/                 # Tax mapping service
└── audit-monitoring/            # Compliance service
```

Start with:
- `src/services/w2-intake/function_app.py` — See how W-2 documents are ingested
- `src/services/w2-intake/README.md` — Understand the intake service design

### Understand Agent Orchestration

```
src/foundry_agents/             # Agent definitions
├── supervisor/orchestrator.py   # Pipeline coordinator
├── intake/agent.py              # Intake agent
├── extraction/agent.py          # Extraction agent
├── validation/agent.py          # Validation agent
├── tax_mapping/agent.py         # Tax mapping agent
├── compliance/agent.py          # Compliance agent
└── human_review/agent.py        # Human review agent
```

Start with:
- `src/foundry_agents/supervisor/orchestrator.py` — See how the pipeline is orchestrated
- `src/foundry_agents/manual_test_harness.py` — See how agents are invoked

### Review Architecture Documentation

- `docs/architecture.md` — Logical architecture with Mermaid diagrams
- `docs/solution-overview.md` — Service pipeline overview
- `enterprise-foundry-tax-ai-blueprint.md` — Full implementation blueprint

## Step 6: Deploy to Azure (Optional)

When ready to deploy to Azure:

1. **Set up Azure subscription** — [Create free account](https://azure.microsoft.com/en-us/free/)

2. **Install Azure CLI**
   ```bash
   az login
   az account show  # Verify you're in the right subscription
   ```

3. **Deploy services** — See [Deployment Guide](DEPLOYMENT_GUIDE.md)

```bash
cd scripts/services/w2-intake
./deploy-all.ps1
```

## Common Tasks

### Run Tests

```bash
# Agent orchestration (no Azure required)
cd src/foundry_agents
python manual_test_harness.py

# Unit tests
python -m unittest discover -s tests

# Integration tests (requires Azure, coming soon)
pytest tests/integration/
```

### Update Dependencies

```bash
# List installed packages
pip list

# Upgrade packages
pip install --upgrade -r src/foundry_agents/requirements.txt
```

### Check Python Environment

```bash
python --version
pip show azure-functions
pip show azure-storage-blob
```

### Deactivate Virtual Environment

```bash
# On Windows
deactivate

# On macOS/Linux
deactivate
```

## Troubleshooting

### Python Not Found

Ensure Python 3.11+ is installed and added to PATH:
```bash
python --version
```

If not found, reinstall Python and ensure "Add Python to PATH" is checked.

### Virtual Environment Activation Failed

- **Windows**: Use `venv\Scripts\activate.bat` instead of `activate`
- **macOS/Linux**: Use `source venv/bin/activate` (with `source`)

### Module Not Found Errors

Ensure virtual environment is activated and dependencies are installed:
```bash
# Verify activation (should show venv in prompt)
which python  # or `where python` on Windows

# Reinstall dependencies
pip install -r src/foundry_agents/requirements.txt
```

### Azure CLI Authentication Issues

```bash
# Clear cache and re-authenticate
az logout
az login
```

## Next Steps

1. ✅ **Tested locally** — Agent orchestration works
2. 📖 **Explore documentation** — Read architecture and design docs
3. 🏗️ **Understand services** — Review W-2 intake implementation
4. 🚀 **Deploy to Azure** — Follow [Deployment Guide](DEPLOYMENT_GUIDE.md)
5. 🧪 **Add tests** — Contribute unit and integration tests
6. 🤖 **Integrate Foundry** — Wire real AI agents to Foundry services

## Additional Resources

- **Microsoft Foundry Documentation** — [https://aka.ms/foundry](https://aka.ms/foundry)
- **Azure Functions (Python)** — [https://learn.microsoft.com/en-us/azure/azure-functions/](https://learn.microsoft.com/en-us/azure/azure-functions/)
- **Azure Storage** — [https://learn.microsoft.com/en-us/azure/storage/](https://learn.microsoft.com/en-us/azure/storage/)
- **Infrastructure as Code (Bicep)** — [https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/)

## Need Help?

- **GitHub Issues** — Report bugs or ask questions
- **GitHub Discussions** — Discuss architecture and design
- **Documentation** — See [docs/](docs/) for comprehensive guides

---

**Happy coding! 🚀**

