param(
    [Parameter(Mandatory = $true)]
    [string] $SubscriptionId,

    [Parameter(Mandatory = $true)]
    [string] $ResourceGroupName,

    [Parameter(Mandatory = $true)]
    [string] $FoundryAccountName,

    [Parameter(Mandatory = $true)]
    [string] $FoundryProjectName,

    [string] $Location = "eastus",
    [string] $ModelDeploymentName = "gpt-4o-mini-dev",
    [string] $ModelName = "gpt-4o-mini",
    [string] $ModelVersion = "2024-07-18",
    [ValidateSet("Standard", "GlobalStandard", "DataZoneStandard")]
    [string] $ModelSkuName = "GlobalStandard",
    [int] $ModelSkuCapacity = 10,
    [switch] $SkipModelDeployment,
    [string] $TemplateFile = "infrastructure/foundry/bicep/main.bicep",
    [string] $OutputDirectory = "artifacts/foundry-bootstrap"
)

$ErrorActionPreference = "Stop"

function Assert-GuidValue {
    param(
        [string] $Name,
        [string] $Value
    )

    $parsed = [Guid]::Empty
    if (-not [Guid]::TryParse($Value, [ref] $parsed)) {
        throw "$Name must be an Azure GUID value. Received '$Value'."
    }
}

function Ensure-ResourceProviderRegistration {
    param([string[]] $Namespaces)

    foreach ($namespace in $Namespaces) {
        $state = az provider show `
            --namespace $namespace `
            --query registrationState `
            --output tsv

        if ($state -eq "Registered") {
            Write-Host "Resource provider already registered: $namespace"
            continue
        }

        Write-Host "Registering resource provider: $namespace"
        az provider register `
            --namespace $namespace `
            --wait `
            --only-show-errors | Out-Null
        Write-Host "Registered resource provider: $namespace"
    }
}

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI 'az' was not found on PATH."
}

Assert-GuidValue -Name "SubscriptionId" -Value $SubscriptionId

az account set --subscription $SubscriptionId
Ensure-ResourceProviderRegistration -Namespaces @("Microsoft.CognitiveServices")

$resourceGroupExists = az group exists --name $ResourceGroupName | ConvertFrom-Json
if (-not $resourceGroupExists) {
    Write-Host "Creating resource group: $ResourceGroupName"
    az group create `
        --name $ResourceGroupName `
        --location $Location `
        --only-show-errors | Out-Null
}

$templatePath = Resolve-Path -Path $TemplateFile -ErrorAction SilentlyContinue
if (-not $templatePath) {
    throw "Foundry Bicep template not found: $TemplateFile"
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

Write-Host "Provisioning Foundry account/project/model deployment"
Write-Host "Resource group: $ResourceGroupName"
Write-Host "Foundry account: $FoundryAccountName"
Write-Host "Foundry project: $FoundryProjectName"
Write-Host "Model deployment: $ModelDeploymentName"
Write-Host "Model: $ModelName $ModelVersion"
Write-Host "Model SKU: $ModelSkuName capacity $ModelSkuCapacity"
Write-Host "Deploy model: $(-not [bool]$SkipModelDeployment)"

$deploymentOutputs = az deployment group create `
    --name "foundry-project-bootstrap" `
    --resource-group $ResourceGroupName `
    --template-file $templatePath.Path `
    --parameters `
        foundryAccountName=$FoundryAccountName `
        foundryProjectName=$FoundryProjectName `
        location=$Location `
        modelDeploymentName=$ModelDeploymentName `
        modelName=$ModelName `
        modelVersion=$ModelVersion `
        modelSkuName=$ModelSkuName `
        modelSkuCapacity=$ModelSkuCapacity `
        deployModel=$(-not [bool]$SkipModelDeployment) `
    --query "properties.outputs" `
    --output json | ConvertFrom-Json

$summary = [ordered]@{
    foundryAccountName = $deploymentOutputs.foundryAccountName.value
    foundryProjectName = $deploymentOutputs.foundryProjectName.value
    foundryProjectEndpoint = $deploymentOutputs.foundryProjectEndpoint.value
    foundryModelDeploymentName = $deploymentOutputs.foundryModelDeploymentName.value
    resourceGroupName = $ResourceGroupName
    location = $Location
    deployModel = -not [bool]$SkipModelDeployment
}

$summaryPath = Join-Path $OutputDirectory "foundry-bootstrap-summary.json"
$summary | ConvertTo-Json -Depth 20 | Set-Content -Path $summaryPath -Encoding utf8

Write-Host ""
Write-Host "Foundry bootstrap complete."
Write-Host "  FOUNDRY_PROJECT_ENDPOINT: $($summary.foundryProjectEndpoint)"
Write-Host "  FOUNDRY_ACCOUNT_NAME: $($summary.foundryAccountName)"
Write-Host "  FOUNDRY_PROJECT_NAME: $($summary.foundryProjectName)"
Write-Host "  FOUNDRY_MODEL_DEPLOYMENT_NAME: $($summary.foundryModelDeploymentName)"
Write-Host "Summary written to: $summaryPath"
