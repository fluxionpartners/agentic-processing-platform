# Deployment Guide

This guide provides step-by-step instructions for deploying the Microsoft Foundry Tax Intelligence Platform to Azure.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Deploying W-2 Intake Service](#deploying-w2-intake-service)
4. [Deploying All Services](#deploying-all-services)
5. [Verifying Deployment](#verifying-deployment)
6. [Troubleshooting](#troubleshooting)
7. [Cost Estimation](#cost-estimation)

## Prerequisites

Before deploying, ensure you have:

### Required Software

- **Azure CLI** — [Install](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
- **PowerShell 7+** — [Install](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell)
- **Git**
- **Python 3.11+**

### Azure Subscription

- Active Azure subscription with sufficient quota
- Permissions to create resource groups and deploy resources
- Appropriate IAM roles (e.g., Contributor, Owner)

### Local Repository

```bash
git clone https://github.com/your-org/agentic-processing-platform.git
cd agentic-processing-platform
```

## Environment Setup

### Step 1: Authenticate with Azure

```bash
# Log in to Azure
az login

# Set your default subscription (if you have multiple)
az account set --subscription "YOUR-SUBSCRIPTION-ID"

# Verify you're authenticated
az account show
```

### Step 2: Configure Deployment Parameters

Edit `infrastructure/services/w2-intake/parameters.dev.json`:

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "namePrefix": {
      "value": "taxai"  // Change to your prefix
    },
    "environment": {
      "value": "dev"    // dev, test, prod
    },
    "location": {
      "value": "eastus" // Azure region
    }
  }
}
```

**Important Parameters:**
- `namePrefix`: Creates uniquely named resources (e.g., `taxaistorage`, `taxaifunc`)
- `environment`: Stage identifier (dev/test/prod)
- `location`: Azure region (eastus, westus2, etc.)

### Step 3: Validate Bicep Templates

```bash
# Navigate to infrastructure directory
cd infrastructure/services/w2-intake/bicep

# Validate Bicep template (no resources created)
az bicep build --file main.bicep
az deployment group validate \
  --resource-group "taxai-rg-dev" \
  --template-file main.bicep \
  --parameters ../parameters.dev.json
```

## Deploying W-2 Intake Service

### Single-Step Deployment

```bash
cd scripts/services/w2-intake
./deploy-all.ps1
```

This PowerShell script automates:
1. Resource group creation
2. Bicep template deployment
3. Function app deployment
4. Configuration updates

### Manual Step-by-Step Deployment

#### Step 1: Create Resource Group

```bash
az group create \
  --name "taxai-rg-dev" \
  --location "eastus"
```

#### Step 2: Deploy Infrastructure with Bicep

```bash
az deployment group create \
  --resource-group "taxai-rg-dev" \
  --template-file infrastructure/services/w2-intake/bicep/main.bicep \
  --parameters infrastructure/services/w2-intake/parameters.dev.json
```

Expected output shows deployed resources:
```
storageAccountName: taxaistoragevdev
functionAppName: taxaifuncvdev
serviceBusNamespaceName: taxaisbvdev
...
```

#### Step 3: Deploy Function App Code

```bash
# From the repository root
cd scripts/services/w2-intake
./deploy-function.ps1 -resourceGroupName "taxai-rg-dev"
```

This script:
1. Compresses the function code
2. Uploads to Azure Functions
3. Configures environment variables

### Monitoring Deployment

```bash
# Watch deployment progress
az deployment group list --resource-group "taxai-rg-dev" -o table

# Check specific resource status
az resource show \
  --resource-group "taxai-rg-dev" \
  --name "taxaifuncvdev" \
  --resource-type "Microsoft.Web/sites" \
  --query "properties.state"
```

## Deploying All Services

### Deploy Complete Platform

```bash
cd scripts
./deploy-all-services.ps1
```

This deploys all services in sequence:
1. W-2 Intake (production-ready)
2. Document Extraction (scaffolded)
3. Data Validation (scaffolded)
4. Tax Mapping (scaffolded)
5. Audit Monitoring (scaffolded)

### Deployment Phases

**Phase 1: Core Services**
- W-2 Intake Service ✅ (Production)
- Infrastructure foundation ✅

**Phase 2: Processing Services** (Ready to implement)
- Document Extraction
- Data Validation
- Tax Mapping

**Phase 3: Orchestration & AI** (Ready to implement)
- Foundry Agent integration
- AI service wiring

**Phase 4: Governance** (Ready to implement)
- Audit and monitoring
- Compliance workflows

**Phase 5: Production** (Ready to implement)
- Performance optimization
- Security hardening
- DR/HA configuration

See [Implementation Phases](implementation-phases.md) for detailed roadmap.

## Verifying Deployment

### Check Azure Resources

```bash
# List all resources in resource group
az resource list --resource-group "taxai-rg-dev" -o table

# Check function app status
az functionapp show \
  --resource-group "taxai-rg-dev" \
  --name "taxaifuncvdev" \
  --query "state"

# View application insights
az monitor app-insights component show \
  --resource-group "taxai-rg-dev" \
  --app "taxaiappinsightvdev"
```

### Test the Intake Endpoint

```bash
# Get function app URL
FUNC_URL=$(az functionapp show \
  --resource-group "taxai-rg-dev" \
  --name "taxaifuncvdev" \
  --query "defaultHostName" -o tsv)

# Upload test W-2 document
curl -X POST \
  -H "Content-Type: application/json" \
  -d @test-payload.json \
  "https://$FUNC_URL/api/upload-w2"
```

### View Logs in Application Insights

```bash
# Query recent logs
az monitor app-insights query \
  --app "taxaiappinsightvdev" \
  --analytics-query "traces | limit 50" \
  -o table
```

## Troubleshooting

### Deployment Errors

#### Error: "Resource already exists"

```bash
# Delete the resource group and retry
az group delete --name "taxai-rg-dev" --yes

# Redeploy
./deploy-all-services.ps1
```

#### Error: "Insufficient quota"

```bash
# Check current quotas
az vm list-usage --location eastus -o table

# Request quota increase or deploy to different region
```

#### Error: "Function app deployment failed"

```bash
# Check function app logs
az functionapp log tail \
  --resource-group "taxai-rg-dev" \
  --name "taxaifuncvdev"

# Verify local.settings.json
cat src/services/w2-intake/local.settings.json
```

### Connectivity Issues

#### Cannot reach function endpoint

```bash
# Verify function app is running
az functionapp show \
  --resource-group "taxai-rg-dev" \
  --name "taxaifuncvdev" \
  --query "state"

# Check network rules
az storage account network-rule list \
  --account-name "taxaistoragevdev" \
  --resource-group "taxai-rg-dev"
```

#### Service Bus connection issues

```bash
# Test Service Bus connection
az servicebus queue show \
  --resource-group "taxai-rg-dev" \
  --namespace-name "taxaisbvdev" \
  --name "w2-ingestion-queue"

# Check shared access policies
az servicebus namespace authorization-rule list \
  --resource-group "taxai-rg-dev" \
  --namespace-name "taxaisbvdev"
```

## Cost Estimation

### Azure Service Costs (Monthly Estimates)

| Service | Tier | Est. Cost |
|---------|------|-----------|
| Azure Functions | Consumption | $0.20-2.00 |
| Storage Account | GRS Standard | $1.00-5.00 |
| Service Bus | Standard | $10.00 |
| SQL Database | (Not deployed yet) | $0.00 |
| Cosmos DB | (Not deployed yet) | $0.00 |
| API Management | Consumption | $1.35 |
| Application Insights | Pay-as-you-go | $0.50-2.00 |
| Key Vault | Standard | $0.67 |
| **Total** | | **~$14-26/month** |

### Cost Optimization Tips

1. **Use Consumption tiers** — Functions, API Management
2. **Monitor usage** — Set up billing alerts
3. **Use managed identities** — Avoid credential costs
4. **Clean up resources** — Delete unused deployments
5. **Use dev/test subscriptions** — Reduced pricing

## Post-Deployment Steps

### 1. Configure CI/CD Pipeline

Set up GitHub Actions for automated deployment:
```bash
mkdir -p .github/workflows
# Create workflow file for deployment automation
```

### 2. Enable Monitoring

```bash
# Set up alerts for function errors
az monitor metrics alert create \
  --resource-group "taxai-rg-dev" \
  --name "function-error-alert" \
  --scopes "taxaifuncvdev" \
  --condition "total Exceptions > 5"
```

### 3. Configure Backup & Disaster Recovery

```bash
# Enable soft delete for Key Vault
az keyvault update \
  --resource-group "taxai-rg-dev" \
  --name "taxaikvvdev" \
  --enable-soft-delete true
```

### 4. Implement Security Hardening

- Enable Azure Defender for Cloud
- Configure network security groups
- Enable audit logging
- Review IAM permissions

## Rollback Procedures

If deployment fails or needs to be reverted:

```bash
# Delete all resources
az group delete --name "taxai-rg-dev" --yes

# Redeploy from scratch
./scripts/deploy-all-services.ps1
```

## Support & Documentation

- **Azure Documentation** — [https://learn.microsoft.com/en-us/azure/](https://learn.microsoft.com/en-us/azure/)
- **Bicep Documentation** — [https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/)
- **PowerShell Azure** — [https://learn.microsoft.com/en-us/powershell/azure/](https://learn.microsoft.com/en-us/powershell/azure/)
- **GitHub Issues** — Report deployment issues

---

**Ready to deploy? Start with `./scripts/services/w2-intake/deploy-all.ps1` 🚀**
