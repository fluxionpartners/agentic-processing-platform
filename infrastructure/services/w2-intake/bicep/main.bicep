@description('Name prefix for all resources')
param namePrefix string = 'taxai'
param location string = resourceGroup().location
param environment string = 'dev'

@description('Azure region for Cosmos DB. Cosmos capacity can differ from the rest of the platform region.')
param cosmosLocation string = location

var storageAccountName = toLower('${namePrefix}${environment}stg')
var apiMgmtName = toLower('${namePrefix}${environment}apim')
var functionAppName = toLower('${namePrefix}${environment}fn')
var appServicePlanName = toLower('${namePrefix}${environment}plan')
var keyVaultName = toLower('${namePrefix}${environment}kv')
var serviceBusName = toLower('${namePrefix}${environment}sb')
var logWorkspaceName = toLower('${namePrefix}${environment}law')
var appInsightsName = toLower('${namePrefix}${environment}ai')
var cosmosAccountName = toLower('${namePrefix}${environment}cosmos')
var containerName = 'raw-w2'
var serviceBusQueueName = 'w2-ingestion-queue'
var apiManagementPublisherName = 'TaxAI Publisher'
var apiManagementPublisherEmail = 'audit@contoso.com'

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

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2024-01-01' = {
  parent: storageAccount
  name: 'default'
}

resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  parent: blobService
  name: containerName
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
  dependsOn: [logWorkspace]
}

resource serviceBus 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: serviceBusName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    zoneRedundant: false
  }
}

resource serviceBusQueue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = {
  parent: serviceBus
  name: serviceBusQueueName
  properties: {
    enablePartitioning: true
    maxSizeInMegabytes: 1024
    requiresDuplicateDetection: false
    defaultMessageTimeToLive: 'P14D'
  }
  dependsOn: [serviceBus]
}

resource serviceBusAuthRule 'Microsoft.ServiceBus/namespaces/authorizationRules@2024-01-01' = {
  parent: serviceBus
  name: 'RootManageSharedAccessKey'
  properties: {
    rights: [
      'Listen'
      'Send'
      'Manage'
    ]
  }
  dependsOn: [serviceBus]
}

resource storageConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'w2-storage-connection-string'
  properties: {
    value: storageConnectionString
  }
  dependsOn: [storageAccount]
}

resource serviceBusConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'w2-servicebus-connection-string'
  properties: {
    value: serviceBusConnectionString
  }
  dependsOn: [serviceBusAuthRule]
}

resource apiManagement 'Microsoft.ApiManagement/service@2022-08-01' = {
  name: apiMgmtName
  location: location
  sku: {
    name: 'Consumption'
    capacity: 0
  }
  properties: {
    publisherEmail: apiManagementPublisherEmail
    publisherName: apiManagementPublisherName
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
          name: 'W2_STORAGE_CONNECTION_STRING'
          value: storageConnectionStringKeyVaultReference
        }
        {
          name: 'W2_CONTAINER_NAME'
          value: containerName
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
          name: 'TAX_FACT_PERSISTENCE_MODE'
          value: 'cosmos'
        }
        {
          name: 'AZURE_COSMOS_ENDPOINT'
          value: cosmosAccount.properties.documentEndpoint
        }
        {
          name: 'AZURE_COSMOS_DATABASE_NAME'
          value: 'tax-intelligence'
        }
        {
          name: 'AZURE_COSMOS_CONTAINER_NAME'
          value: 'tax-facts'
        }
      ]
    }
  }
  dependsOn: [
    appServicePlan
    storageConnectionStringSecret
    serviceBusConnectionStringSecret
    appInsights
    cosmosAccount
  ]
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

output storageAccountName string = storageAccount.name
output blobContainerName string = blobContainer.name
output keyVaultName string = keyVault.name
output logWorkspaceName string = logWorkspace.name
output serviceBusName string = serviceBus.name
output serviceBusQueueName string = serviceBusQueue.name
output functionAppName string = functionApp.name
output apiManagementName string = apiManagement.name
output cosmosAccountName string = cosmosAccount.name
output storageConnectionStringSecretName string = storageConnectionStringSecret.name
output serviceBusConnectionStringSecretName string = serviceBusConnectionStringSecret.name

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: cosmosAccountName
  location: cosmosLocation
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: cosmosLocation
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
  }
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: 'tax-intelligence'
  properties: {
    resource: {
      id: 'tax-intelligence'
    }
  }
}

resource cosmosContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: cosmosDatabase
  name: 'tax-facts'
  properties: {
    resource: {
      id: 'tax-facts'
      partitionKey: {
        paths: [
          '/tenantId'
        ]
        kind: 'Hash'
      }
    }
  }
}

resource sqlRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, functionApp.id, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: functionApp.identity.principalId
    scope: cosmosAccount.id
  }
}

var storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${listKeys(storageAccount.id, storageAccount.apiVersion).keys[0].value};EndpointSuffix=${az.environment().suffixes.storage}'
var serviceBusConnectionString = listKeys(serviceBusAuthRule.id, serviceBusAuthRule.apiVersion).primaryConnectionString
var storageConnectionStringKeyVaultReference = '@Microsoft.KeyVault(SecretUri=${storageConnectionStringSecret.properties.secretUri})'
var serviceBusConnectionStringKeyVaultReference = '@Microsoft.KeyVault(SecretUri=${serviceBusConnectionStringSecret.properties.secretUri})'
