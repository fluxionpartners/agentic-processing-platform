param(
    [Parameter(Mandatory = $true)]
    [string] $ProjectEndpoint,

    [Parameter(Mandatory = $true)]
    [string] $ModelDeploymentName,

    [Parameter(Mandatory = $true)]
    [string] $ToolEndpointBaseUrl,

    [Parameter(Mandatory = $true)]
    [string] $OpenApiProjectConnectionId,

    [string] $AgentSourceRoot = "src/foundry_agents",
    [string] $OpenApiPath = "src/services/foundry-tools/openapi.json",
    [string] $Environment = "dev",
    [string] $OutputDirectory = "artifacts/foundry-registration",
    [string] $ApiVersion = "v1",
    [switch] $PrepareOnly
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $true
}

function Resolve-RequiredPath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Description
    )

    $resolvedPath = Resolve-Path -Path $Path -ErrorAction SilentlyContinue
    if (-not $resolvedPath) {
        throw "$Description not found: $Path"
    }

    return $resolvedPath.Path
}

function Read-AgentYamlScalar {
    param(
        [Parameter(Mandatory = $true)]
        [string[]] $Lines,

        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $match = $Lines | Where-Object { $_ -match "^\s*$([regex]::Escape($Name))\s*:\s*(.+?)\s*$" } | Select-Object -First 1
    if (-not $match) {
        return $null
    }

    return ($match -replace "^\s*$([regex]::Escape($Name))\s*:\s*", "").Trim().Trim('"')
}

function Assert-ValidOperationIds {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject] $OpenApi
    )

    $invalidIds = New-Object System.Collections.Generic.List[string]
    foreach ($pathProperty in $OpenApi.paths.PSObject.Properties) {
        foreach ($methodProperty in $pathProperty.Value.PSObject.Properties) {
            $operationId = $methodProperty.Value.operationId
            if ([string]::IsNullOrWhiteSpace($operationId)) {
                $invalidIds.Add("$($methodProperty.Name.ToUpperInvariant()) $($pathProperty.Name) is missing operationId")
            }
            elseif ($operationId -notmatch "^[A-Za-z_-]+$") {
                $invalidIds.Add("$operationId contains unsupported characters")
            }
        }
    }

    if ($invalidIds.Count -gt 0) {
        throw "OpenAPI operationId validation failed: $($invalidIds -join '; ')"
    }
}

if ([string]::IsNullOrWhiteSpace($ProjectEndpoint)) {
    throw "ProjectEndpoint is required. Use the Foundry project endpoint, for example https://<resource>.services.ai.azure.com/api/projects/<project>."
}

if ([string]::IsNullOrWhiteSpace($ModelDeploymentName)) {
    throw "ModelDeploymentName is required. Use the deployed model name in the Foundry project."
}

if ([string]::IsNullOrWhiteSpace($ToolEndpointBaseUrl)) {
    throw "ToolEndpointBaseUrl is required. This should come from the deployed foundry-tools Bicep output."
}

if ([string]::IsNullOrWhiteSpace($OpenApiProjectConnectionId)) {
    throw "OpenApiProjectConnectionId is required. Create a Foundry project connection that stores the Function key as header x-functions-key, then pass that connection resource ID."
}

$agentYamlPath = Resolve-RequiredPath -Path (Join-Path $AgentSourceRoot "agent.yaml") -Description "Foundry agent manifest"
$promptPath = Resolve-RequiredPath -Path (Join-Path $AgentSourceRoot "prompts/supervisor.md") -Description "Foundry supervisor prompt"
$openApiResolvedPath = Resolve-RequiredPath -Path $OpenApiPath -Description "Foundry tools OpenAPI specification"

$agentYamlLines = Get-Content -Path $agentYamlPath
$agentName = Read-AgentYamlScalar -Lines $agentYamlLines -Name "name"
$agentVersion = Read-AgentYamlScalar -Lines $agentYamlLines -Name "version"
$agentDescription = Read-AgentYamlScalar -Lines $agentYamlLines -Name "description"

if ([string]::IsNullOrWhiteSpace($agentName)) {
    throw "Agent manifest is missing a top-level name."
}

if ([string]::IsNullOrWhiteSpace($agentVersion)) {
    $agentVersion = "0.1.0"
}

if ([string]::IsNullOrWhiteSpace($agentDescription)) {
    $agentDescription = "Governed W-2 tax orchestration agent."
}

$instructions = (Get-Content -Path $promptPath -Raw).Trim()
$openApi = Get-Content -Path $openApiResolvedPath -Raw | ConvertFrom-Json

if ($ToolEndpointBaseUrl.EndsWith("/")) {
    $ToolEndpointBaseUrl = $ToolEndpointBaseUrl.TrimEnd("/")
}

$openApi.servers = @(
    [ordered]@{
        url = $ToolEndpointBaseUrl
    }
)

if (-not $openApi.components) {
    $openApi | Add-Member -MemberType NoteProperty -Name components -Value ([pscustomobject]@{})
}

if (-not $openApi.components.securitySchemes) {
    $openApi.components | Add-Member -MemberType NoteProperty -Name securitySchemes -Value ([pscustomobject]@{})
}

$openApi.components.securitySchemes | Add-Member -Force -MemberType NoteProperty -Name functionKeyHeader -Value ([ordered]@{
    type = "apiKey"
    name = "x-functions-key"
    in = "header"
})
$openApi | Add-Member -Force -MemberType NoteProperty -Name security -Value @(
    [ordered]@{
        functionKeyHeader = @()
    }
)

Assert-ValidOperationIds -OpenApi $openApi

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$resolvedOpenApiPath = Join-Path $OutputDirectory "openapi.resolved.json"
$registrationPayloadPath = Join-Path $OutputDirectory "agent-registration.payload.json"
$summaryPath = Join-Path $OutputDirectory "registration-summary.json"

$openApi | ConvertTo-Json -Depth 100 | Set-Content -Path $resolvedOpenApiPath -Encoding utf8

$registrationPayload = [ordered]@{
    name = $agentName
    model = $ModelDeploymentName
    description = $agentDescription
    instructions = $instructions
    metadata = [ordered]@{
        source = "github-actions"
        environment = $Environment
        manifestVersion = $agentVersion
        toolEndpointBaseUrl = $ToolEndpointBaseUrl
    }
    tools = @(
        [ordered]@{
            type = "openapi"
            openapi = [ordered]@{
                name = "w2_tax_pipeline"
                description = "Governed W-2 intake, extraction, validation, tax mapping, Form 1040 generation, compliance, and persistence HTTP tools."
                spec = $openApi
                auth = [ordered]@{
                    type = "connection"
                    security_scheme = [ordered]@{
                        connection_id = $OpenApiProjectConnectionId
                    }
                }
            }
        }
    )
}

$registrationPayload | ConvertTo-Json -Depth 100 | Set-Content -Path $registrationPayloadPath -Encoding utf8

$summary = [ordered]@{
    agentName = $agentName
    agentVersion = $agentVersion
    environment = $Environment
    projectEndpoint = $ProjectEndpoint
    modelDeploymentName = $ModelDeploymentName
    toolEndpointBaseUrl = $ToolEndpointBaseUrl
    openApiProjectConnectionId = $OpenApiProjectConnectionId
    resolvedOpenApiPath = $resolvedOpenApiPath
    registrationPayloadPath = $registrationPayloadPath
    prepareOnly = [bool]$PrepareOnly
}
$summary | ConvertTo-Json -Depth 20 | Set-Content -Path $summaryPath -Encoding utf8

Write-Host "Prepared Foundry registration artifacts:"
Write-Host "  OpenAPI: $resolvedOpenApiPath"
Write-Host "  Payload: $registrationPayloadPath"
Write-Host "  Summary: $summaryPath"

if ($PrepareOnly) {
    Write-Host "PrepareOnly was selected; remote Foundry registration was not executed."
    return
}

$token = az account get-access-token --scope "https://ai.azure.com/.default" --query accessToken --output tsv
if ([string]::IsNullOrWhiteSpace($token)) {
    throw "Unable to acquire an Azure AI Foundry access token. Verify azure/login completed successfully and the identity has Contributor or Owner on the Foundry project."
}

$uri = "$($ProjectEndpoint.TrimEnd('/'))/assistants?api-version=$ApiVersion"
Write-Host "Registering Foundry agent with: $uri"

$response = az rest `
    --method post `
    --uri $uri `
    --headers "Authorization=Bearer $token" "Content-Type=application/json" `
    --body "@$registrationPayloadPath" `
    --only-show-errors

$responsePath = Join-Path $OutputDirectory "registration-response.json"
$response | Set-Content -Path $responsePath -Encoding utf8
Write-Host "Foundry agent registration response written to: $responsePath"

if ([string]::IsNullOrWhiteSpace($response)) {
    throw "Foundry agent registration returned an empty response."
}

$responseObject = $response | ConvertFrom-Json
if ($responseObject.name -and $responseObject.name -ne $agentName) {
    throw "Foundry returned agent name '$($responseObject.name)' but the manifest requested '$agentName'."
}

Write-Host "Registered Foundry supervisor agent: $agentName"
