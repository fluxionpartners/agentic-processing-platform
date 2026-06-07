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

@description('Existing Service Bus namespace name created by the W2 intake infrastructure')
param serviceBusName string = toLower('${namePrefix}${environment}sb')

@description('Service Bus queue that carries W-2 intake events')
param serviceBusQueueName string = 'w2-ingestion-queue'

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

@description('Shared Log Analytics workspace name for this environment')
param sharedLogWorkspaceName string = toLower('${namePrefix}${environment}law')

@description('Shared Application Insights component name for this environment')
param sharedAppInsightsName string = toLower('${namePrefix}${environment}ai')

@description('Existing API Management service name created by the W2 intake infrastructure')
param apiManagementName string = toLower('${namePrefix}${environment}apim')

@description('Portal web endpoint used for APIM CORS.')
param portalWebEndpoint string = ''

@description('Enable Entra ID JWT validation on the APIM W-2 processing operation.')
param portalAuthEnabled bool = false

@description('Tenant ID used by APIM validate-jwt when portal authentication is enabled.')
param portalAuthTenantId string = ''

@description('Expected JWT audience for the W-2 processing API app registration.')
param portalAuthAudience string = ''

var storageAccountName = toLower('${namePrefix}${environment}toolstg')
var functionAppName = toLower('${namePrefix}${environment}toolsfn')
var appServicePlanName = toLower('${namePrefix}${environment}toolsplan')
var keyVaultName = toLower('${namePrefix}${environment}toolskv')
var storageConnectionStringSecretName = 'foundry-tools-storage-connection-string'
var serviceBusConnectionStringSecretName = 'foundry-tools-servicebus-connection-string'
var form1040ArtifactMode = 'azure-blob'
var portalWebOrigin = portalWebEndpoint == '' ? '' : (endsWith(portalWebEndpoint, '/') ? substring(portalWebEndpoint, 0, length(portalWebEndpoint) - 1) : portalWebEndpoint)
var apimCorsOrigins = portalWebOrigin == '' ? '<origin>http://localhost:5173</origin>' : '<origin>${portalWebOrigin}</origin><origin>http://localhost:5173</origin>'
var portalJwtPolicy = portalAuthEnabled ? '<validate-jwt header-name="Authorization" failed-validation-httpcode="401" failed-validation-error-message="Unauthorized. A valid Entra access token is required."><openid-config url="${az.environment().authentication.loginEndpoint}${portalAuthTenantId}/v2.0/.well-known/openid-configuration" /><audiences><audience>${portalAuthAudience}</audience></audiences></validate-jwt>' : ''

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
      defaultAction: 'Allow'
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

resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: sharedLogWorkspaceName
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: sharedAppInsightsName
}

resource apiManagement 'Microsoft.ApiManagement/service@2022-08-01' existing = {
  name: apiManagementName
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

resource serviceBus 'Microsoft.ServiceBus/namespaces@2024-01-01' existing = {
  name: serviceBusName
}

resource serviceBusAuthRule 'Microsoft.ServiceBus/namespaces/authorizationRules@2024-01-01' existing = {
  parent: serviceBus
  name: 'RootManageSharedAccessKey'
}

resource serviceBusConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: serviceBusConnectionStringSecretName
  properties: {
    value: serviceBusConnectionString
  }
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
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'AzureWebJobsFeatureFlags'
          value: 'EnableWorkerIndexing'
        }
        {
          name: 'AzureWebJobsStorage'
          value: storageConnectionString
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
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
        {
          name: 'APP_ENV'
          value: environment
        }
        {
          name: 'W2_SERVICEBUS_CONNECTION_STRING'
          value: serviceBusConnectionStringKeyVaultReference
        }
        {
          name: 'W2_SERVICEBUS_QUEUE_NAME'
          value: serviceBusQueueName
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

resource foundryToolsFunctionKeyNamedValue 'Microsoft.ApiManagement/service/namedValues@2022-08-01' = {
  parent: apiManagement
  name: 'foundry-tools-function-key'
  properties: {
    displayName: 'foundry-tools-function-key'
    secret: true
    value: listKeys('${functionApp.id}/host/default', '2022-03-01').functionKeys.default
  }
}

resource w2ProcessingApi 'Microsoft.ApiManagement/service/apis@2022-08-01' = {
  parent: apiManagement
  name: 'w2-processing'
  properties: {
    displayName: 'W2 Processing API'
    description: 'Secure APIM facade for running the governed W-2 processing pipeline.'
    path: 'w2-processing'
    protocols: [
      'https'
    ]
    serviceUrl: 'https://${functionApp.properties.defaultHostName}/api'
    subscriptionRequired: false
  }
  dependsOn: [
    foundryToolsFunctionKeyNamedValue
  ]
}

resource runW2PipelineOperation 'Microsoft.ApiManagement/service/apis/operations@2022-08-01' = {
  parent: w2ProcessingApi
  name: 'run-w2-pipeline'
  properties: {
    displayName: 'Run W-2 Pipeline'
    method: 'POST'
    urlTemplate: '/run'
    description: 'Runs the complete governed W-2 pipeline and returns processing state.'
    request: {
      queryParameters: []
      headers: [
        {
          name: 'Content-Type'
          required: true
          type: 'string'
          defaultValue: 'application/json'
        }
      ]
      representations: [
        {
          contentType: 'application/json'
        }
      ]
    }
    responses: [
      {
        statusCode: 200
        description: 'Pipeline completed and returned the governed processing state.'
      }
      {
        statusCode: 400
        description: 'Invalid processing request.'
      }
      {
        statusCode: 500
        description: 'Pipeline execution failed.'
      }
    ]
  }
}

resource runW2PipelineOperationPolicy 'Microsoft.ApiManagement/service/apis/operations/policies@2022-08-01' = {
  parent: runW2PipelineOperation
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: '<policies><inbound><base /><cors allow-credentials="false"><allowed-origins>${apimCorsOrigins}</allowed-origins><allowed-methods><method>POST</method><method>OPTIONS</method></allowed-methods><allowed-headers><header>Authorization</header><header>Content-Type</header><header>correlation-id</header></allowed-headers><expose-headers><header>correlation-id</header></expose-headers></cors>${portalJwtPolicy}<rate-limit-by-key calls="30" renewal-period="60" counter-key="@(context.Request.IpAddress)" /><set-header name="x-functions-key" exists-action="override"><value>{{foundry-tools-function-key}}</value></set-header><rewrite-uri template="/run-w2-pipeline" /></inbound><backend><base /></backend><outbound><base /></outbound><on-error><base /></on-error></policies>'
  }
}

resource getW2PipelineStatusOperation 'Microsoft.ApiManagement/service/apis/operations@2022-08-01' = {
  parent: w2ProcessingApi
  name: 'get-w2-pipeline-status'
  properties: {
    displayName: 'Get W-2 Pipeline Status'
    method: 'GET'
    urlTemplate: '/status/{correlationId}'
    description: 'Returns the persisted processing status for a W-2 pipeline correlation ID.'
    templateParameters: [
      {
        name: 'correlationId'
        required: true
        type: 'string'
      }
    ]
    request: {
      queryParameters: [
        {
          name: 'tenantId'
          required: false
          type: 'string'
        }
      ]
    }
    responses: [
      {
        statusCode: 200
        description: 'Pipeline status found.'
      }
      {
        statusCode: 202
        description: 'Pipeline is still processing or has not created a persisted checkpoint yet.'
      }
      {
        statusCode: 400
        description: 'Invalid status request.'
      }
    ]
  }
}

resource getW2PipelineStatusOperationPolicy 'Microsoft.ApiManagement/service/apis/operations/policies@2022-08-01' = {
  parent: getW2PipelineStatusOperation
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: '<policies><inbound><base /><cors allow-credentials="false"><allowed-origins>${apimCorsOrigins}</allowed-origins><allowed-methods><method>GET</method><method>OPTIONS</method></allowed-methods><allowed-headers><header>Authorization</header><header>Content-Type</header><header>correlation-id</header></allowed-headers><expose-headers><header>correlation-id</header></expose-headers></cors>${portalJwtPolicy}<rate-limit-by-key calls="120" renewal-period="60" counter-key="@(context.Request.IpAddress)" /><set-header name="x-functions-key" exists-action="override"><value>{{foundry-tools-function-key}}</value></set-header><rewrite-uri template="/status/{correlationId}" /></inbound><backend><base /></backend><outbound><base /></outbound><on-error><base /></on-error></policies>'
  }
}

output functionAppName string = functionApp.name
output functionAppDefaultHostName string = functionApp.properties.defaultHostName
output keyVaultName string = keyVault.name
output storageAccountName string = storageAccount.name
output sharedLogWorkspaceName string = logWorkspace.name
output sharedAppInsightsName string = appInsights.name
output form1040BlobContainerName string = form1040ArtifactContainer.name
output storageConnectionStringSecretName string = storageConnectionStringSecret.name
output serviceBusConnectionStringSecretName string = serviceBusConnectionStringSecret.name
output toolEndpointBaseUrl string = 'https://${functionApp.properties.defaultHostName}/api'
output w2ProcessingApiUrl string = '${apiManagement.properties.gatewayUrl}/w2-processing/run'
output w2PipelineStatusApiUrl string = '${apiManagement.properties.gatewayUrl}/w2-processing/status'

var storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${listKeys(storageAccount.id, storageAccount.apiVersion).keys[0].value};EndpointSuffix=${az.environment().suffixes.storage}'
var serviceBusConnectionString = listKeys(serviceBusAuthRule.id, serviceBusAuthRule.apiVersion).primaryConnectionString
var storageConnectionStringKeyVaultReference = '@Microsoft.KeyVault(SecretUri=${storageConnectionStringSecret.properties.secretUri})'
var serviceBusConnectionStringKeyVaultReference = '@Microsoft.KeyVault(SecretUri=${serviceBusConnectionStringSecret.properties.secretUri})'
