param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory = $true)]
    [string]$Location,

    [Parameter(Mandatory = $false)]
    [string]$CosmosLocation,

    [Parameter(Mandatory = $true)]
    [string]$Environment,

    [Parameter(Mandatory = $true)]
    [string]$NamePrefix
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-AzChecked {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Arguments -join ' ')"
    }
}

function Ensure-ResourceProviderRegistration {
    param([string[]]$Namespaces)

    foreach ($namespace in $Namespaces) {
        $state = az provider show `
            --namespace $namespace `
            --query registrationState `
            --output tsv

        if ($LASTEXITCODE -ne 0) {
            throw "Azure CLI command failed: az provider show --namespace $namespace"
        }

        if ($state -eq 'Registered') {
            Write-Host "Resource provider already registered: $namespace"
            continue
        }

        Write-Host "Registering resource provider: $namespace"
        az provider register `
            --namespace $namespace `
            --wait `
            --only-show-errors | Out-Null

        if ($LASTEXITCODE -ne 0) {
            throw "Unable to register Azure resource provider '$namespace'. Register it with an identity that has subscription-level provider registration permissions, then rerun preflight."
        }

        Write-Host "Registered resource provider: $namespace"
    }
}

function Get-AzJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $json = & az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Arguments -join ' ')"
    }

    if ([string]::IsNullOrWhiteSpace($json)) {
        return $null
    }

    return $json | ConvertFrom-Json
}

function Test-AzureResourceExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ResourceType,

        [Parameter(Mandatory = $true)]
        [string]$ResourceName
    )

    $resources = Get-AzJson @(
        'resource'
        'list'
        '--resource-group'
        $ResourceGroupName
        '--resource-type'
        $ResourceType
        '--name'
        $ResourceName
        '--query'
        '[].id'
        '--output'
        'json'
    )

    return ($null -ne $resources -and @($resources).Count -gt 0)
}

function Assert-ProvisioningState {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Resource,

        [Parameter(Mandatory = $true)]
        [string]$ResourceKind
    )

    if ($null -eq $Resource) {
        return
    }

    if ($Resource.provisioningState -eq 'Failed') {
        throw @"
Existing Azure resource is in Failed provisioning state and will block ARM what-if/deployment.

Resource kind: $ResourceKind
Resource: $($Resource.id)

Delete or repair this failed partial resource, then rerun preflight. For example:
az resource delete --ids "$($Resource.id)"
"@
    }
}

function Test-ExistingCosmosAccountHealth {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AccountName
    )

    if (-not (Test-AzureResourceExists `
        -ResourceType 'Microsoft.DocumentDB/databaseAccounts' `
        -ResourceName $AccountName)) {
        return
    }

    $resource = Get-AzJson @(
        'cosmosdb'
        'show'
        '--resource-group'
        $ResourceGroupName
        '--name'
        $AccountName
        '--query'
        '{id:id, provisioningState:provisioningState}'
        '--output'
        'json'
    )

    Assert-ProvisioningState -Resource $resource -ResourceKind 'Cosmos DB account'
}

function Test-ExistingApiManagementHealth {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServiceName
    )

    if (-not (Test-AzureResourceExists `
        -ResourceType 'Microsoft.ApiManagement/service' `
        -ResourceName $ServiceName)) {
        return
    }

    $resource = Get-AzJson @(
        'apim'
        'show'
        '--resource-group'
        $ResourceGroupName
        '--name'
        $ServiceName
        '--query'
        '{id:id, provisioningState:provisioningState}'
        '--output'
        'json'
    )

    Assert-ProvisioningState -Resource $resource -ResourceKind 'API Management service'
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
if ([string]::IsNullOrWhiteSpace($CosmosLocation)) {
    $CosmosLocation = $Location
}

$w2CosmosAccountName = "$($NamePrefix.ToLower())$($Environment.ToLower())cosmos"
$w2ApiManagementName = "$($NamePrefix.ToLower())$($Environment.ToLower())apim"

$requiredResourceProviders = @(
    'Microsoft.ApiManagement',
    'Microsoft.Authorization',
    'Microsoft.DocumentDB',
    'Microsoft.Insights',
    'Microsoft.KeyVault',
    'Microsoft.OperationalInsights',
    'Microsoft.ServiceBus',
    'Microsoft.Storage',
    'Microsoft.Web'
)

$templates = @(
    @{
        Name = 'w2-intake'
        File = Join-Path $repoRoot 'infrastructure\services\w2-intake\bicep\main.bicep'
    },
    @{
        Name = 'foundry-tools'
        File = Join-Path $repoRoot 'infrastructure\services\foundry-tools\bicep\main.bicep'
    }
)

Write-Host "Azure deployment preflight"
Write-Host "Resource group: $ResourceGroupName"
Write-Host "Environment: $Environment"
Write-Host "Location: $Location"
Write-Host "Cosmos location: $CosmosLocation"
Write-Host "Name prefix: $NamePrefix"

Write-Host ""
Write-Host "Checking Azure resource provider registrations"
Ensure-ResourceProviderRegistration -Namespaces $requiredResourceProviders

Write-Host ""
Write-Host "Checking existing Azure resource health"
Test-ExistingCosmosAccountHealth -AccountName $w2CosmosAccountName
Test-ExistingApiManagementHealth -ServiceName $w2ApiManagementName

foreach ($template in $templates) {
    Write-Host ""
    Write-Host "Compiling Bicep: $($template.Name)"
    Invoke-AzChecked @(
        'bicep'
        'build'
        '--file'
        $template.File
    )
}

foreach ($template in $templates) {
    $deploymentName = "preflight-$($template.Name)-$Environment"
    $parameters = @(
        "namePrefix=$NamePrefix"
        "environment=$Environment"
        "location=$Location"
    )

    if ($template.Name -eq 'w2-intake') {
        $parameters += "cosmosLocation=$CosmosLocation"
    }

    Write-Host ""
    Write-Host "Running ARM what-if: $($template.Name)"
    Invoke-AzChecked @(
        'deployment'
        'group'
        'what-if'
        '--name'
        $deploymentName
        '--resource-group'
        $ResourceGroupName
        '--template-file'
        $template.File
        '--parameters'
        $parameters
        '--result-format'
        'ResourceIdOnly'
    )
}

Write-Host ""
Write-Host "Azure deployment preflight completed successfully."
