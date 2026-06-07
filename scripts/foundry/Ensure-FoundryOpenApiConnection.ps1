param(
    [Parameter(Mandatory = $true)]
    [string] $SubscriptionId,

    [Parameter(Mandatory = $true)]
    [string] $ResourceGroupName,

    [Parameter(Mandatory = $true)]
    [string] $FoundryAccountName,

    [Parameter(Mandatory = $true)]
    [string] $FoundryProjectName,

    [Parameter(Mandatory = $true)]
    [string] $ConnectionName,

    [Parameter(Mandatory = $true)]
    [string] $FunctionAppName,

    [Parameter(Mandatory = $true)]
    [string] $ToolEndpointBaseUrl,

    [string] $Environment = "dev",
    [string] $OutputDirectory = "artifacts/foundry-registration",
    [string] $ApiVersion = "2025-06-01"
)

$ErrorActionPreference = "Stop"

if ($ConnectionName -notmatch "^[a-zA-Z0-9][a-zA-Z0-9_-]{2,32}$") {
    throw "ConnectionName must match Azure Foundry connection naming rules: ^[a-zA-Z0-9][a-zA-Z0-9_-]{2,32}$"
}

if ($ToolEndpointBaseUrl.EndsWith("/")) {
    $ToolEndpointBaseUrl = $ToolEndpointBaseUrl.TrimEnd("/")
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

Write-Host "Retrieving Foundry tools Function App host key."
$functionKey = az functionapp keys list `
    --resource-group $ResourceGroupName `
    --name $FunctionAppName `
    --query "functionKeys.default" `
    --output tsv

if ([string]::IsNullOrWhiteSpace($functionKey)) {
    throw "Unable to retrieve the default host key from Function App '$FunctionAppName'. Verify RBAC and that the Function App exists."
}

$connectionUri = "https://management.azure.com/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName/providers/Microsoft.CognitiveServices/accounts/$FoundryAccountName/projects/$FoundryProjectName/connections/$ConnectionName" +
    "?api-version=$ApiVersion"

$connectionResourceId = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName/providers/Microsoft.CognitiveServices/accounts/$FoundryAccountName/projects/$FoundryProjectName/connections/$ConnectionName"

$requestBody = [ordered]@{
    properties = [ordered]@{
        category = "CustomKeys"
        authType = "CustomKeys"
        target = $ToolEndpointBaseUrl
        isSharedToAll = $false
        metadata = [ordered]@{
            environment = $Environment
            purpose = "foundry-openapi-tool-auth"
            headerName = "x-functions-key"
        }
        credentials = [ordered]@{
            keys = [ordered]@{
                "x-functions-key" = $functionKey
            }
        }
    }
}

$bodyPath = Join-Path $OutputDirectory "foundry-openapi-connection.request.json"
$responsePath = Join-Path $OutputDirectory "foundry-openapi-connection.response.json"
$summaryPath = Join-Path $OutputDirectory "foundry-openapi-connection-summary.json"

$requestBody | ConvertTo-Json -Depth 20 | Set-Content -Path $bodyPath -Encoding utf8

Write-Host "Creating or updating Foundry OpenAPI project connection."
$response = az rest `
    --method put `
    --uri $connectionUri `
    --body "@$bodyPath"

$response | Set-Content -Path $responsePath -Encoding utf8

$summary = [ordered]@{
    connectionName = $ConnectionName
    connectionResourceId = $connectionResourceId
    foundryAccountName = $FoundryAccountName
    foundryProjectName = $FoundryProjectName
    functionAppName = $FunctionAppName
    toolEndpointBaseUrl = $ToolEndpointBaseUrl
    environment = $Environment
    requestPath = $bodyPath
    responsePath = $responsePath
}
$summary | ConvertTo-Json -Depth 20 | Set-Content -Path $summaryPath -Encoding utf8

if ($env:GITHUB_OUTPUT) {
    "openapi_project_connection_id=$connectionResourceId" | Out-File -FilePath $env:GITHUB_OUTPUT -Append -Encoding utf8
}

Write-Host "Foundry OpenAPI project connection is ready."
