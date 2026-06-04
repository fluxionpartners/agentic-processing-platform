param(
    [string]$resourceGroupName = 'taxai-dev-rg',
    [string]$location = 'eastus'
)

Write-Host "Starting deployment of all pipeline service infrastructure for $resourceGroupName"
Import-Module Az.Accounts -ErrorAction Stop

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$services = @(
    'w2-intake',
    'document-extraction',
    'data-validation',
    'tax-mapping',
    'audit-monitoring'
)

foreach ($service in $services) {
    $serviceScript = Join-Path $scriptDir "services\$service\deploy.ps1"
    if (-not (Test-Path $serviceScript)) {
        Write-Host "Skipping missing deploy script for service: $service"
        continue
    }
    Write-Host "Deploying infrastructure for service: $service"
    & $serviceScript -resourceGroupName $resourceGroupName -location $location
}

Write-Host "All available service infrastructure deployments complete."
