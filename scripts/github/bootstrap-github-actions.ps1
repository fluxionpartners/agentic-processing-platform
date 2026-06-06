param(
    [Parameter(Mandatory = $true)]
    [string]$SubscriptionId,

    [Parameter(Mandatory = $true)]
    [string]$TenantId,

    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,

    [ValidateSet("dev", "test", "uat", "prod")]
    [string]$Environment = "dev",

    [string]$Location = "eastus",

    [string]$NamePrefix = "taxai",

    [string]$GitHubOwner = "",

    [string]$GitHubRepo = "",

    [string]$AppRegistrationName = "",

    [string]$FoundryProjectEndpoint = "",

    [string]$FoundryAccountName = "",

    [string]$FoundryProjectName = "",

    [string]$FoundryModelDeploymentName = "",

    [string]$FoundryOpenApiConnectionName = "w2toolsfnkey",

    [string]$FoundryProjectRoleName = "Foundry Project Manager",

    [switch]$ProvisionFoundry,

    [string]$FoundryLocation = "",

    [string]$FoundryModelName = "gpt-4o-mini",

    [string]$FoundryModelVersion = "2024-07-18",

    [ValidateSet("Standard", "GlobalStandard", "DataZoneStandard")]
    [string]$FoundryModelSkuName = "GlobalStandard",

    [int]$FoundryModelSkuCapacity = 10,

    [switch]$SkipFoundryModelDeployment,

    [switch]$GrantUserAccessAdministrator
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found on PATH."
    }
}

function Assert-GuidValue {
    param(
        [string]$Name,
        [string]$Value
    )

    $parsed = [Guid]::Empty
    if (-not [Guid]::TryParse($Value, [ref]$parsed)) {
        throw "$Name must be an Azure GUID value. Received '$Value'. Run 'az account show --query `"{subscriptionId:id, tenantId:tenantId}`" -o table' and pass the real value."
    }
}

function Get-RepoContext {
    if ($GitHubOwner -and $GitHubRepo) {
        return @{
            Owner = $GitHubOwner
            Repo = $GitHubRepo
        }
    }

    $repoJson = gh repo view --json owner,name | ConvertFrom-Json
    return @{
        Owner = $repoJson.owner.login
        Repo = $repoJson.name
    }
}

function Ensure-RoleAssignment {
    param(
        [string]$Assignee,
        [string]$RoleName,
        [string]$Scope
    )

    $existing = az role assignment list `
        --assignee $Assignee `
        --role $RoleName `
        --scope $Scope `
        --query "[0].id" `
        --output tsv

    if ($existing) {
        Write-Host "Role assignment already exists: $RoleName"
        return
    }

    az role assignment create `
        --assignee $Assignee `
        --role $RoleName `
        --scope $Scope `
        --only-show-errors | Out-Null
    Write-Host "Created role assignment: $RoleName"
}

function Ensure-ResourceProviderRegistration {
    param([string[]]$Namespaces)

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

function Get-ServicePrincipalObjectId {
    param([string]$ApplicationId)

    return az ad sp list `
        --filter "appId eq '$ApplicationId'" `
        --query "[0].id" `
        --output tsv
}

function Ensure-ServicePrincipal {
    param([string]$ApplicationId)

    $objectId = Get-ServicePrincipalObjectId -ApplicationId $ApplicationId
    if ($objectId) {
        Write-Host "Using existing service principal: $objectId"
        return $objectId
    }

    Write-Host "Creating service principal for app registration: $ApplicationId"
    az ad sp create --id $ApplicationId --only-show-errors | Out-Null

    for ($attempt = 1; $attempt -le 12; $attempt++) {
        $objectId = Get-ServicePrincipalObjectId -ApplicationId $ApplicationId
        if ($objectId) {
            Write-Host "Created service principal: $objectId"
            return $objectId
        }
        Write-Host "Waiting for service principal propagation ($attempt/12)..."
        Start-Sleep -Seconds 5
    }

    throw "Service principal for app registration '$ApplicationId' was not visible after waiting."
}

function New-FederatedCredentialFile {
    param(
        [string]$Path,
        [string]$Name,
        [string]$Subject,
        [string]$Description
    )

    @{
        name = $Name
        issuer = "https://token.actions.githubusercontent.com"
        subject = $Subject
        audiences = @("api://AzureADTokenExchange")
        description = $Description
    } | ConvertTo-Json -Depth 5 | Set-Content -Path $Path -Encoding utf8
}

function Test-FederatedCredentialMatches {
    param(
        [object]$Credential,
        [string]$ExpectedSubject
    )

    if (-not $Credential) {
        return $false
    }
    if (($Credential.issuer | Out-String).Trim() -ne "https://token.actions.githubusercontent.com") {
        return $false
    }
    if (($Credential.subject | Out-String).Trim() -ne $ExpectedSubject) {
        return $false
    }
    $audiences = @($Credential.audiences)
    if (-not $audiences -or $audiences -notcontains "api://AzureADTokenExchange") {
        return $false
    }
    return $true
}

function Write-FederatedCredentialDetails {
    param(
        [string]$Label,
        [object]$Credential
    )

    if (-not $Credential) {
        Write-Host "${Label}: <none>"
        return
    }

    Write-Host "${Label}:"
    Write-Host "  name: $($Credential.name)"
    Write-Host "  issuer: $($Credential.issuer)"
    Write-Host "  subject: $($Credential.subject)"
    Write-Host "  audiences: $(@($Credential.audiences) -join ', ')"
}

function Ensure-FederatedCredential {
    param(
        [string]$ApplicationId,
        [string]$CredentialName,
        [string]$Subject,
        [string]$Description
    )

    $credentials = az ad app federated-credential list `
        --id $ApplicationId `
        --output json | ConvertFrom-Json

    $existing = $credentials | Where-Object { $_.name -eq $CredentialName } | Select-Object -First 1
    if (Test-FederatedCredentialMatches -Credential $existing -ExpectedSubject $Subject) {
        Write-Host "Federated credential already matches expected GitHub subject: $CredentialName"
        Write-FederatedCredentialDetails -Label "Federated credential" -Credential $existing
        return
    }

    if ($existing) {
        Write-Host "Federated credential exists but does not match expected OIDC settings. Recreating: $CredentialName"
        Write-FederatedCredentialDetails -Label "Existing federated credential" -Credential $existing
        Write-Host "Expected subject: $Subject"
        az ad app federated-credential delete `
            --id $ApplicationId `
            --federated-credential-id $existing.id `
            --only-show-errors
    }

    $credentialPath = Join-Path $env:TEMP "$CredentialName.json"
    New-FederatedCredentialFile `
        -Path $credentialPath `
        -Name $CredentialName `
        -Subject $Subject `
        -Description $Description

    az ad app federated-credential create `
        --id $ApplicationId `
        --parameters "@$credentialPath" `
        --only-show-errors | Out-Null
    Remove-Item -Path $credentialPath -Force

    $created = az ad app federated-credential list `
        --id $ApplicationId `
        --output json | ConvertFrom-Json |
        Where-Object { $_.name -eq $CredentialName } |
        Select-Object -First 1

    if (-not (Test-FederatedCredentialMatches -Credential $created -ExpectedSubject $Subject)) {
        Write-FederatedCredentialDetails -Label "Created federated credential" -Credential $created
        Write-Host "Expected issuer: https://token.actions.githubusercontent.com"
        Write-Host "Expected subject: $Subject"
        Write-Host "Expected audience: api://AzureADTokenExchange"
        throw "Federated credential '$CredentialName' was created but does not match the expected GitHub OIDC settings."
    }

    Write-Host "Created federated credential: $CredentialName"
    Write-FederatedCredentialDetails -Label "Federated credential" -Credential $created
}

Require-Command az
Require-Command gh

Assert-GuidValue -Name "SubscriptionId" -Value $SubscriptionId
Assert-GuidValue -Name "TenantId" -Value $TenantId

az account set --subscription $SubscriptionId

$requiredResourceProviders = @(
    "Microsoft.ApiManagement",
    "Microsoft.Authorization",
    "Microsoft.CognitiveServices",
    "Microsoft.DocumentDB",
    "Microsoft.Insights",
    "Microsoft.KeyVault",
    "Microsoft.OperationalInsights",
    "Microsoft.ServiceBus",
    "Microsoft.Storage",
    "Microsoft.Web"
)

Ensure-ResourceProviderRegistration -Namespaces $requiredResourceProviders

$resourceGroupExists = az group exists --name $ResourceGroupName | ConvertFrom-Json
if (-not $resourceGroupExists) {
    Write-Host "Creating resource group: $ResourceGroupName"
    az group create `
        --name $ResourceGroupName `
        --location $Location `
        --only-show-errors | Out-Null
}

$resourceGroup = az group show `
    --name $ResourceGroupName `
    --query "{ id:id, name:name, location:location }" `
    --output json | ConvertFrom-Json

$repo = Get-RepoContext
$owner = $repo.Owner
$repoName = $repo.Repo

if (-not $AppRegistrationName) {
    $AppRegistrationName = "github-$repoName-$Environment"
}

if ($ProvisionFoundry) {
    if (-not $FoundryAccountName) {
        $FoundryAccountName = "$NamePrefix$Environment-foundry"
    }
    if (-not $FoundryProjectName) {
        $FoundryProjectName = "$NamePrefix-$Environment-project"
    }
    if (-not $FoundryModelDeploymentName) {
        $FoundryModelDeploymentName = "$FoundryModelName-$Environment"
    }
    if (-not $FoundryLocation) {
        $FoundryLocation = $Location
    }

    $ensureFoundryScript = Resolve-Path -Path "scripts/foundry/Ensure-FoundryProject.ps1" -ErrorAction SilentlyContinue
    if (-not $ensureFoundryScript) {
        throw "Foundry provisioning script not found: scripts/foundry/Ensure-FoundryProject.ps1"
    }

    $foundryArgs = @(
        "-SubscriptionId", $SubscriptionId,
        "-ResourceGroupName", $ResourceGroupName,
        "-FoundryAccountName", $FoundryAccountName,
        "-FoundryProjectName", $FoundryProjectName,
        "-Location", $FoundryLocation,
        "-ModelDeploymentName", $FoundryModelDeploymentName,
        "-ModelName", $FoundryModelName,
        "-ModelVersion", $FoundryModelVersion,
        "-ModelSkuName", $FoundryModelSkuName,
        "-ModelSkuCapacity", $FoundryModelSkuCapacity
    )
    if ($SkipFoundryModelDeployment) {
        $foundryArgs += "-SkipModelDeployment"
    }

    & $ensureFoundryScript.Path @foundryArgs
    $FoundryProjectEndpoint = "https://$FoundryAccountName.services.ai.azure.com/api/projects/$FoundryProjectName"
}

Write-Host "Repository: $owner/$repoName"
Write-Host "Environment: $Environment"
Write-Host "Resource group: $($resourceGroup.name)"
Write-Host "App registration: $AppRegistrationName"

$appId = az ad app list `
    --display-name $AppRegistrationName `
    --query "[0].appId" `
    --output tsv

if (-not $appId) {
    $appId = az ad app create `
        --display-name $AppRegistrationName `
        --query appId `
        --output tsv
    Write-Host "Created app registration: $appId"
} else {
    Write-Host "Using existing app registration: $appId"
}

$servicePrincipalObjectId = Ensure-ServicePrincipal -ApplicationId $appId

$federatedCredentialName = "github-$owner-$repoName-$Environment".ToLower() -replace "[^a-z0-9-]", "-"
$subject = "repo:${owner}/${repoName}:environment:${Environment}"
$federatedCredentialDescription = "GitHub Actions OIDC for $owner/$repoName environment $Environment"

Write-Host "GitHub OIDC subject: $subject"
Ensure-FederatedCredential `
    -ApplicationId $appId `
    -CredentialName $federatedCredentialName `
    -Subject $subject `
    -Description $federatedCredentialDescription

Ensure-RoleAssignment `
    -Assignee $appId `
    -RoleName "Contributor" `
    -Scope $resourceGroup.id

if ($GrantUserAccessAdministrator) {
    Ensure-RoleAssignment `
        -Assignee $appId `
        -RoleName "User Access Administrator" `
        -Scope $resourceGroup.id
}

if ($FoundryAccountName -and $FoundryProjectName) {
    $foundryProjectScope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName/providers/Microsoft.CognitiveServices/accounts/$FoundryAccountName/projects/$FoundryProjectName"
    Write-Host "Configuring Foundry project RBAC scope: $foundryProjectScope"
    Ensure-RoleAssignment `
        -Assignee $appId `
        -RoleName $FoundryProjectRoleName `
        -Scope $foundryProjectScope
}
elseif ($FoundryProjectEndpoint -or $FoundryModelDeploymentName) {
    Write-Warning "Foundry project RBAC was not configured because FoundryAccountName and FoundryProjectName were not both provided. Agent registration needs a Foundry data-plane role such as '$FoundryProjectRoleName' at the project scope."
}

gh api `
    --method PUT `
    "repos/$owner/$repoName/environments/$Environment" `
    --silent

gh secret set AZURE_CLIENT_ID --env $Environment --body $appId
gh secret set AZURE_TENANT_ID --env $Environment --body $TenantId
gh secret set AZURE_SUBSCRIPTION_ID --env $Environment --body $SubscriptionId

gh variable set AZURE_RESOURCE_GROUP --env $Environment --body $ResourceGroupName
gh variable set AZURE_LOCATION --env $Environment --body $Location
gh variable set NAME_PREFIX --env $Environment --body $NamePrefix

if ($FoundryProjectEndpoint) {
    gh variable set FOUNDRY_PROJECT_ENDPOINT --env $Environment --body $FoundryProjectEndpoint
}
if ($FoundryAccountName) {
    gh variable set FOUNDRY_ACCOUNT_NAME --env $Environment --body $FoundryAccountName
}
if ($FoundryProjectName) {
    gh variable set FOUNDRY_PROJECT_NAME --env $Environment --body $FoundryProjectName
}
if ($FoundryModelDeploymentName) {
    gh variable set FOUNDRY_MODEL_DEPLOYMENT_NAME --env $Environment --body $FoundryModelDeploymentName
}
if ($FoundryOpenApiConnectionName) {
    gh variable set FOUNDRY_OPENAPI_CONNECTION_NAME --env $Environment --body $FoundryOpenApiConnectionName
}

Write-Host ""
Write-Host "GitHub Actions bootstrap complete."
Write-Host "Configured environment secrets: AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID"
Write-Host "Configured environment variables: AZURE_RESOURCE_GROUP, AZURE_LOCATION, NAME_PREFIX"
if ($FoundryProjectEndpoint -or $FoundryAccountName -or $FoundryProjectName -or $FoundryModelDeploymentName -or $FoundryOpenApiConnectionName) {
    Write-Host "Configured Foundry variables when provided: FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_ACCOUNT_NAME, FOUNDRY_PROJECT_NAME, FOUNDRY_MODEL_DEPLOYMENT_NAME, FOUNDRY_OPENAPI_CONNECTION_NAME"
    if ($FoundryAccountName -and $FoundryProjectName) {
        Write-Host "Configured Foundry project RBAC for the GitHub Actions service principal: $FoundryProjectRoleName"
    }
}
Write-Host ""
Write-Host "Next: run the 'Deploy Agentic Processing Platform' workflow for environment '$Environment'."
