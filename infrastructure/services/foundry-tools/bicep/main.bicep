@description('Name prefix for all resources')
param namePrefix string = 'taxai'

param location string = resourceGroup().location

@description('Deployment environment: dev, test, uat, or prod')
param environment string = 'dev'

@description('Runtime extraction mode for the tool host')
@allowed([
  'local'
  'document-intelligence'
])
param extractionMode string = 'local'

@description('Validation strictness for the tool host')
@allowed([
  'standard'
  'strict'
])
param validationStrictness string = 'standard'

@description('Human review behavior for the tool host')
@allowed([
  'local-auto-approve'
  'queue'
  'manual'
])
param humanReviewMode string = 'local-auto-approve'

@description('Compliance mode for the tool host')
@allowed([
  'development'
  'regulated'
])
param complianceMode string = 'development'

@description('Azure OpenAI deployment name used by the Foundry supervisor agent')
param azureOpenAIDeploymentName string = ''

@description('Azure AI Document Intelligence endpoint')
param documentIntelligenceEndpoint string = ''

@description('Azure AI Document Intelligence model ID')
param documentIntelligenceModelId string = 'prebuilt-tax.us.w2'

@description('Existing Cosmos DB account name created by the W2 intake infrastructure')
param cosmosAccountName string = toLower('${namePrefix}${environment}cosmos')

@description('Cosmos DB database name for governed tax facts')
param cosmosDatabaseName string = 'tax-intelligence'

@description('Cosmos DB container name for governed tax facts')
param cosmosContainerName string = 'tax-facts'

@description('Form 1040 generation mode')
@allowed([
  'html-template'
])
param form1040GenerationMode string = 'html-template'

@description('Form 1040 template version')
param form1040TemplateVersion string = 'irs-1040-2024-html-v1'

@description('Form 1040 artifact storage container')
param form1040BlobContainerName string = 'tax-artifacts'

var storageAccountName = toLower('${namePrefix}${environment}toolstg')
var functionAppName = toLower('${namePrefix}${environment}toolsfn')
var appServicePlanName = toLower('${namePrefix}${environment}toolsplan')
var keyVaultName = toLower('${namePrefix}${environment}toolskv')
var logWorkspaceName = toLower('${namePrefix}${environment}toolslaw')
var appInsightsName = toLower('${namePrefix}${environment}toolsai')
var storageConnectionStringSecretName = 'foundry-tools-storage-connection-string'
var form1040ArtifactMode = 'azure-blob'

resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_GRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
    }
    encryption: {
      services: {
        blob: {
          enabled: true
        }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}

resource form1040ArtifactContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  name: '${storageAccount.name}/default/${form1040BlobContainerName}'
  properties: {
    publicAccess: 'None'
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enabledForDeployment: true
    enabledForTemplateDeployment: true
    enableSoftDelete: true
    enablePurgeProtection: true
    accessPolicies: []
  }
}

resource storageConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: storageConnectionStringSecretName
  properties: {
    value: storageConnectionString
  }
}

resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logWorkspace.id
  }
}

resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  kind: 'functionapp,linux'
  properties: {
    reserved: true
  }
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      appSettings: [
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'AzureWebJobsStorage'
          value: storageConnectionStringKeyVaultReference
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'APP_ENV'
          value: environment
        }
        {
          name: 'AZURE_OPENAI_DEPLOYMENT_NAME'
          value: azureOpenAIDeploymentName
        }
        {
          name: 'W2_EXTRACTION_MODE'
          value: extractionMode
        }
        {
          name: 'W2_VALIDATION_STRICTNESS'
          value: validationStrictness
        }
        {
          name: 'HUMAN_REVIEW_MODE'
          value: humanReviewMode
        }
        {
          name: 'TAX_MAPPING_PROFILE'
          value: 'us-federal-2024'
        }
        {
          name: 'FORM_1040_GENERATION_MODE'
          value: form1040GenerationMode
        }
        {
          name: 'FORM_1040_TEMPLATE_VERSION'
          value: form1040TemplateVersion
        }
        {
          name: 'FORM_1040_ARTIFACT_MODE'
          value: form1040ArtifactMode
        }
        {
          name: 'FORM_1040_BLOB_CONTAINER_NAME'
          value: form1040BlobContainerName
        }
        {
          name: 'FORM_1040_STORAGE_ACCOUNT_URL'
          value: storageAccount.properties.primaryEndpoints.blob
        }
        {
          name: 'FORM_1040_STORAGE_CONNECTION_STRING'
          value: storageConnectionStringKeyVaultReference
        }
        {
          name: 'COMPLIANCE_MODE'
          value: complianceMode
        }
        {
          name: 'LOW_CONFIDENCE_THRESHOLD'
          value: '0.85'
        }
        {
          name: 'REQUIRE_MASKED_PII_IN_LOGS'
          value: 'true'
        }
        {
          name: 'AUDIT_EVENT_ENABLED'
          value: 'true'
        }
        {
          name: 'AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT'
          value: documentIntelligenceEndpoint
        }
        {
          name: 'AZURE_DOCUMENT_INTELLIGENCE_MODEL_ID'
          value: documentIntelligenceModelId
        }
        {
          name: 'TAX_FACT_PERSISTENCE_MODE'
          value: 'cosmos'
        }
        {
          name: 'AZURE_COSMOS_ENDPOINT'
          value: cosmosAccount.properties.documentEndpoint
        }
        {
          name: 'AZURE_COSMOS_DATABASE_NAME'
          value: cosmosDatabaseName
        }
        {
          name: 'AZURE_COSMOS_CONTAINER_NAME'
          value: cosmosContainerName
        }
        {
          name: 'ALLOW_FULL_PII_PERSISTENCE'
          value: 'false'
        }
      ]
    }
  }
}

resource functionAppKeyVaultAccessPolicy 'Microsoft.KeyVault/vaults/accessPolicies@2023-07-01' = {
  parent: keyVault
  name: 'add'
  properties: {
    accessPolicies: [
      {
        tenantId: subscription().tenantId
        objectId: functionApp.identity.principalId
        permissions: {
          secrets: [
            'get'
            'list'
          ]
        }
      }
    ]
  }
}

resource cosmosDataContributorAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, functionApp.id, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: functionApp.identity.principalId
    scope: cosmosAccount.id
  }
}

resource storageBlobDataContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionApp.id, 'Storage Blob Data Contributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    )
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output functionAppName string = functionApp.name
output functionAppDefaultHostName string = functionApp.properties.defaultHostName
output keyVaultName string = keyVault.name
output storageAccountName string = storageAccount.name
output form1040BlobContainerName string = form1040ArtifactContainer.name
output storageConnectionStringSecretName string = storageConnectionStringSecret.name
output toolEndpointBaseUrl string = 'https://${functionApp.properties.defaultHostName}/api'

var storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${listKeys(storageAccount.id, storageAccount.apiVersion).keys[0].value};EndpointSuffix=${az.environment().suffixes.storage}'
var storageConnectionStringKeyVaultReference = '@Microsoft.KeyVault(SecretUri=${storageConnectionStringSecret.properties.secretUri})'
