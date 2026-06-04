param(
    [string]$resourceGroupName = 'taxai-dev-rg',
    [string]$location = 'eastus',
    [string]$bicepFile = 'infrastructure/w2-intake/bicep/main.bicep',
    [string]$parametersFile = 'infrastructure/w2-intake/bicep/parameters.dev.json'
)

Write-Host "Deploying W-2 intake infrastructure to resource group $resourceGroupName in $location"

if (-not (Get-AzResourceGroup -Name $resourceGroupName -ErrorAction SilentlyContinue)) {
    Write-Host "Creating resource group $resourceGroupName"
    New-AzResourceGroup -Name $resourceGroupName -Location $location | Out-Null
}

New-AzResourceGroupDeployment -ResourceGroupName $resourceGroupName -TemplateFile $bicepFile -TemplateParameterFile $parametersFile -Verbose
