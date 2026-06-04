param(
    [string]$resourceGroupName = 'taxai-dev-rg',
    [string]$zipPath = 'src/w2-intake/deploy.zip'
)

Write-Host "Packaging and deploying W-2 intake function app code for resource group $resourceGroupName"

if (-not (Test-Path 'src/w2-intake')) {
    throw "Function app source folder src/w2-intake not found."
}

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

Compress-Archive -Path 'src/w2-intake/*' -DestinationPath $zipPath -Force

$deployment = Get-AzResourceGroupDeployment -ResourceGroupName $resourceGroupName | Sort-Object Timestamp -Descending | Select-Object -First 1
if (-not $deployment) {
    throw "No deployment found for resource group $resourceGroupName. Deploy infrastructure first."
}

$functionAppName = $deployment.Outputs.functionAppName.value
if (-not $functionAppName) {
    throw "Unable to find functionAppName in deployment outputs."
}

Write-Host "Deploying code to Function App $functionAppName"
az functionapp deployment source config-zip --resource-group $resourceGroupName --name $functionAppName --src $zipPath | Write-Host
