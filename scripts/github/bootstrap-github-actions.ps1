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

Require-Command az
Require-Command gh

az account set --subscription $SubscriptionId

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

$servicePrincipalObjectId = az ad sp show `
    --id $appId `
    --query id `
    --output tsv 2>$null

if (-not $servicePrincipalObjectId) {
    $servicePrincipalObjectId = az ad sp create `
        --id $appId `
        --query id `
        --output tsv
    Write-Host "Created service principal: $servicePrincipalObjectId"
} else {
    Write-Host "Using existing service principal: $servicePrincipalObjectId"
}

$federatedCredentialName = "github-$owner-$repoName-$Environment".ToLower() -replace "[^a-z0-9-]", "-"
$subject = "repo:$owner/$repoName:environment:$Environment"

$existingFederatedCredential = az ad app federated-credential list `
    --id $appId `
    --query "[?name=='$federatedCredentialName'].name | [0]" `
    --output tsv

if (-not $existingFederatedCredential) {
    $credentialPath = Join-Path $env:TEMP "$federatedCredentialName.json"
    @{
        name = $federatedCredentialName
        issuer = "https://token.actions.githubusercontent.com"
        subject = $subject
        audiences = @("api://AzureADTokenExchange")
        description = "GitHub Actions OIDC for $owner/$repoName environment $Environment"
    } | ConvertTo-Json -Depth 5 | Set-Content -Path $credentialPath -Encoding utf8

    az ad app federated-credential create `
        --id $appId `
        --parameters "@$credentialPath" `
        --only-show-errors | Out-Null
    Remove-Item -Path $credentialPath -Force
    Write-Host "Created federated credential: $federatedCredentialName"
} else {
    Write-Host "Federated credential already exists: $federatedCredentialName"
}

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

Write-Host ""
Write-Host "GitHub Actions bootstrap complete."
Write-Host "Configured environment secrets: AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID"
Write-Host "Configured environment variables: AZURE_RESOURCE_GROUP, AZURE_LOCATION, NAME_PREFIX"
Write-Host ""
Write-Host "Next: run the 'Deploy Agentic Processing Platform' workflow for environment '$Environment'."
