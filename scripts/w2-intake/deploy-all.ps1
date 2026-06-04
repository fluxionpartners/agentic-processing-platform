param(
    [string]$resourceGroupName = 'taxai-dev-rg',
    [string]$location = 'eastus'
)

Write-Host "Starting W-2 intake deployment for resource group $resourceGroupName"
Import-Module Az.Accounts -ErrorAction Stop

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

& "$scriptDir\deploy.ps1" -resourceGroupName $resourceGroupName -location $location
& "$scriptDir\deploy-function.ps1" -resourceGroupName $resourceGroupName

Write-Host "W-2 intake deployment complete."
