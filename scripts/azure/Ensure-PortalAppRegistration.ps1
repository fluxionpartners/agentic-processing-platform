param(
    [Parameter(Mandatory = $true)]
    [string]$TenantId,

    [Parameter(Mandatory = $true)]
    [string]$Environment,

    [string]$NamePrefix = "taxai",

    [string]$ApiAppDisplayName = "",

    [string]$SpaAppDisplayName = "",

    [string[]]$RedirectUris = @("http://localhost:5173"),

    [string]$ScopeValue = "W2Intake.Upload",

    [string]$SmokeTestAppRoleValue = "W2Intake.SmokeTest"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $true
}

function Ensure-Guid {
    param([string]$Seed)
    return ([guid]::NewGuid()).Guid
}

function Get-AppByDisplayName {
    param([string]$DisplayName)
    $apps = az ad app list `
        --display-name $DisplayName `
        --output json | ConvertFrom-Json

    return @($apps) | Select-Object -First 1
}

function Get-AppObject {
    param([string]$AppId)
    return az ad app show --id $AppId --output json | ConvertFrom-Json
}

function Get-OptionalArray {
    param(
        [object]$Object,
        [string]$PropertyName
    )

    if (-not $Object) {
        return @()
    }

    $property = $Object.PSObject.Properties[$PropertyName]
    if (-not $property -or $null -eq $property.Value) {
        return @()
    }

    return @($property.Value)
}

if (-not $ApiAppDisplayName) {
    $ApiAppDisplayName = "$NamePrefix-$Environment-w2-intake-api"
}
if (-not $SpaAppDisplayName) {
    $SpaAppDisplayName = "$NamePrefix-$Environment-w2-upload-portal"
}

$normalizedRedirectUris = @($RedirectUris | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)
if ($normalizedRedirectUris.Count -eq 0) {
    throw "At least one redirect URI is required for the portal SPA app registration."
}

Write-Host "Ensuring portal API app registration: $ApiAppDisplayName"
$apiApp = Get-AppByDisplayName -DisplayName $ApiAppDisplayName
if (-not $apiApp) {
    $apiAppId = az ad app create `
        --display-name $ApiAppDisplayName `
        --sign-in-audience AzureADMyOrg `
        --query appId `
        --output tsv
    if (-not $apiAppId) {
        $createdApiApp = Get-AppByDisplayName -DisplayName $ApiAppDisplayName
        if ($createdApiApp -and $createdApiApp.PSObject.Properties["appId"]) {
            $apiAppId = $createdApiApp.appId
        }
    }
    if (-not $apiAppId) {
        throw "Created API app registration, but could not resolve its appId: $ApiAppDisplayName"
    }
    $apiApp = Get-AppObject -AppId $apiAppId
    Write-Host "Created portal API app registration: $apiAppId"
}
else {
    Write-Host "Using existing portal API app registration: $($apiApp.appId)"
}

$apiApp = Get-AppObject -AppId $apiApp.appId
$identifierUri = "api://$($apiApp.appId)"
if (@($apiApp.identifierUris) -notcontains $identifierUri) {
    az ad app update `
        --id $apiApp.appId `
        --identifier-uris $identifierUri `
        --only-show-errors | Out-Null
    Write-Host "Configured API app identifier URI: $identifierUri"
}

$apiApp = Get-AppObject -AppId $apiApp.appId
$apiScopes = @()
if ($apiApp.PSObject.Properties["api"] -and $apiApp.api.PSObject.Properties["oauth2PermissionScopes"]) {
    $apiScopes = @($apiApp.api.oauth2PermissionScopes)
}

$existingScope = $apiScopes |
    Where-Object { $_.value -eq $ScopeValue } |
    Select-Object -First 1

$scopeId = if ($existingScope) { $existingScope.id } else { (Ensure-Guid -Seed $ScopeValue) }
$scopeDefinition = [ordered]@{
    id = $scopeId
    adminConsentDescription = "Allow the W-2 upload portal to submit intake requests through API Management."
    adminConsentDisplayName = "Upload W-2 intake documents"
    isEnabled = $true
    type = "User"
    userConsentDescription = "Submit synthetic or governed W-2 documents to the intake API."
    userConsentDisplayName = "Upload W-2 documents"
    value = $ScopeValue
}

$existingAppRole = Get-OptionalArray -Object $apiApp -PropertyName "appRoles" |
    Where-Object { $_.value -eq $SmokeTestAppRoleValue } |
    Select-Object -First 1

$appRoleId = if ($existingAppRole) { $existingAppRole.id } else { (Ensure-Guid -Seed $SmokeTestAppRoleValue) }
$appRoleDefinition = [ordered]@{
    id = $appRoleId
    allowedMemberTypes = @("Application")
    description = "Allow trusted CI/CD automation to run W-2 end-to-end smoke tests through API Management."
    displayName = "Run W-2 smoke tests"
    isEnabled = $true
    value = $SmokeTestAppRoleValue
}

$preservedAppRoles = Get-OptionalArray -Object $apiApp -PropertyName "appRoles" |
    Where-Object { $_.value -ne $SmokeTestAppRoleValue }

$apiPatch = @{
    api = @{
        requestedAccessTokenVersion = 2
        oauth2PermissionScopes = @($scopeDefinition)
    }
    appRoles = @($preservedAppRoles + $appRoleDefinition)
} | ConvertTo-Json -Depth 20

$apiPatchPath = Join-Path $env:TEMP "portal-api-app-$Environment.json"
$apiPatch | Set-Content -Path $apiPatchPath -Encoding utf8
az rest `
    --method PATCH `
    --uri "https://graph.microsoft.com/v1.0/applications/$($apiApp.id)" `
    --headers "Content-Type=application/json" `
    --body "@$apiPatchPath" `
    --only-show-errors | Out-Null
Remove-Item -Path $apiPatchPath -Force

Write-Host "Ensuring portal SPA app registration: $SpaAppDisplayName"
$spaApp = Get-AppByDisplayName -DisplayName $SpaAppDisplayName
if (-not $spaApp) {
    $spaAppId = az ad app create `
        --display-name $SpaAppDisplayName `
        --sign-in-audience AzureADMyOrg `
        --query appId `
        --output tsv
    if (-not $spaAppId) {
        $createdSpaApp = Get-AppByDisplayName -DisplayName $SpaAppDisplayName
        if ($createdSpaApp -and $createdSpaApp.PSObject.Properties["appId"]) {
            $spaAppId = $createdSpaApp.appId
        }
    }
    if (-not $spaAppId) {
        throw "Created SPA app registration, but could not resolve its appId: $SpaAppDisplayName"
    }
    $spaApp = Get-AppObject -AppId $spaAppId
    Write-Host "Created portal SPA app registration: $spaAppId"
}
else {
    Write-Host "Using existing portal SPA app registration: $($spaApp.appId)"
}

$spaApp = Get-AppObject -AppId $spaApp.appId

$requiredResourceAccess = @(
    [ordered]@{
        resourceAppId = $apiApp.appId
        resourceAccess = @(
            [ordered]@{
                id = $scopeId
                type = "Scope"
            }
        )
    }
)

$spaPatch = @{
    spa = @{
        redirectUris = $normalizedRedirectUris
    }
    requiredResourceAccess = $requiredResourceAccess
} | ConvertTo-Json -Depth 20

$spaPatchPath = Join-Path $env:TEMP "portal-spa-app-$Environment.json"
$spaPatch | Set-Content -Path $spaPatchPath -Encoding utf8
az rest `
    --method PATCH `
    --uri "https://graph.microsoft.com/v1.0/applications/$($spaApp.id)" `
    --headers "Content-Type=application/json" `
    --body "@$spaPatchPath" `
    --only-show-errors | Out-Null
Remove-Item -Path $spaPatchPath -Force

$result = [ordered]@{
    tenantId = $TenantId
    apiClientId = $apiApp.appId
    spaClientId = $spaApp.appId
    smokeTestAppRoleId = $appRoleId
    smokeTestAppRoleValue = $SmokeTestAppRoleValue
    scope = "$identifierUri/$ScopeValue"
    audience = $identifierUri
    redirectUris = $normalizedRedirectUris
}

Write-Host "Portal app registration complete."
$result | ConvertTo-Json -Depth 10 -Compress
