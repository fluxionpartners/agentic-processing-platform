@description('Azure AI Foundry account name. Must be globally unique because it is used as the custom subdomain.')
param foundryAccountName string

@description('Azure AI Foundry project name.')
param foundryProjectName string

@description('Azure region for the Foundry account and project.')
param location string = resourceGroup().location

@description('Model deployment name used by the supervisor agent.')
param modelDeploymentName string = 'gpt-4o-mini-dev'

@description('Model name from the Foundry/OpenAI catalog.')
param modelName string = 'gpt-4o-mini'

@description('Model version. Availability depends on region and subscription quota.')
param modelVersion string = '2024-07-18'

@description('Deployment SKU name. Common values include Standard, GlobalStandard, and DataZoneStandard.')
param modelSkuName string = 'GlobalStandard'

@minValue(1)
@description('Model deployment capacity. For Standard/GlobalStandard OpenAI deployments this is TPM capacity units.')
param modelSkuCapacity int = 10

@description('Whether to create the model deployment. Disable only when model deployments are centrally managed.')
param deployModel bool = true

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryAccountName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: foundryAccountName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundryAccount
  name: foundryProjectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: foundryProjectName
    description: 'Agentic Processing Platform Foundry project'
  }
}

resource supervisorModelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = if (deployModel) {
  parent: foundryAccount
  name: modelDeploymentName
  sku: {
    name: modelSkuName
    capacity: modelSkuCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
}

output foundryAccountName string = foundryAccount.name
output foundryProjectName string = foundryProject.name
output foundryProjectEndpoint string = 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${foundryProjectName}'
output foundryModelDeploymentName string = modelDeploymentName
