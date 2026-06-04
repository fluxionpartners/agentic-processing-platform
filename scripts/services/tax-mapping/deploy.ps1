param(
    [string]$resourceGroupName = 'taxai-dev-rg',
    [string]$location = 'eastus',
    [string]$bicepFile = 'infrastructure/services/tax-mapping/bicep/main.bicep',
    [string]$parametersFile = 'infrastructure/services/tax-mapping/bicep/parameters.dev.json'
)

Write-Host "Deploying Tax Mapping infrastructure to resource group $resourceGroupName in $location"

if (-not (Get-AzResourceGroup -Name $resourceGroupName -ErrorAction SilentlyContinue)) {
    Write-Host "Creating resource group $resourceGroupName"
    New-AzResourceGroup -Name $resourceGroupName -Location $location | Out-Null
}

New-AzResourceGroupDeployment -ResourceGroupName $resourceGroupName -TemplateFile $bicepFile -TemplateParameterFile $parametersFile -Verbose
