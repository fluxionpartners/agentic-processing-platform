param(
    [Parameter(Mandatory = $true)]
    [string]$IntakeApiUrl,

    [Parameter(Mandatory = $true)]
    [string]$StatusApiUrl,

    [string]$TenantId = "tenant-smoke",

    [string]$TaxpayerId = "taxpayer-smoke-001",

    [int]$TaxYear = 2024,

    [string]$BearerToken = "",

    [int]$TimeoutSeconds = 180,

    [int]$PollIntervalSeconds = 5
)

$ErrorActionPreference = "Stop"

function ConvertTo-Base64Utf8 {
    param([Parameter(Mandatory = $true)][string]$Value)
    return [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Value))
}

function Invoke-JsonRequest {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Uri,
        [hashtable]$Headers = @{},
        [object]$Body = $null
    )

    $request = @{
        Method = $Method
        Uri = $Uri
        Headers = $Headers
        ContentType = "application/json"
    }

    if ($null -ne $Body) {
        $request.Body = ($Body | ConvertTo-Json -Depth 20)
    }

    return Invoke-RestMethod @request
}

$correlationId = "smoke-w2-$([guid]::NewGuid().ToString("N"))"
$documentName = "synthetic-w2-smoke-$TaxYear.txt"
$syntheticW2 = @"
Synthetic W-2 Document
Employer: Contoso Payroll Services
Employer EIN: 12-3456789
Employee: Alex Smoke
Employee SSN: XXX-XX-1234
Tax Year: $TaxYear
Box 1 Wages: 85000.00
Box 2 Federal Income Tax Withheld: 11250.00
Box 3 Social Security Wages: 85000.00
Box 4 Social Security Tax Withheld: 5270.00
Box 5 Medicare Wages: 85000.00
Box 6 Medicare Tax Withheld: 1232.50
"@

$headers = @{
    "correlation-id" = $correlationId
}

if (-not [string]::IsNullOrWhiteSpace($BearerToken)) {
    $headers["Authorization"] = "Bearer $BearerToken"
}

Write-Host "Starting W-2 end-to-end smoke test"
Write-Host "Correlation ID: $correlationId"
Write-Host "Intake API: $IntakeApiUrl"
Write-Host "Status API: $StatusApiUrl"

$intakePayload = @{
    correlationId = $correlationId
    tenantId = $TenantId
    taxpayerId = $TaxpayerId
    documentName = $documentName
    taxYear = $TaxYear
    documentBase64 = ConvertTo-Base64Utf8 -Value $syntheticW2
}

$intakeResponse = Invoke-JsonRequest -Method "POST" -Uri $IntakeApiUrl -Headers $headers -Body $intakePayload

if ($intakeResponse.status -ne "accepted") {
    throw "Expected intake status 'accepted' but received '$($intakeResponse.status)'."
}

if ([string]::IsNullOrWhiteSpace($intakeResponse.blobUri)) {
    throw "Intake response did not include blobUri."
}

Write-Host "Intake accepted. Polling pipeline status..."

$statusBase = $StatusApiUrl.TrimEnd("/")
$encodedCorrelationId = [System.Uri]::EscapeDataString($correlationId)
$encodedTenantId = [System.Uri]::EscapeDataString($TenantId)
$statusUrl = "$statusBase/$encodedCorrelationId`?tenantId=$encodedTenantId"
$deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
$lastStatus = $null

while ([DateTimeOffset]::UtcNow -lt $deadline) {
    try {
        $lastStatus = Invoke-JsonRequest -Method "GET" -Uri $statusUrl -Headers $headers
    }
    catch {
        Write-Host "Status poll failed: $($_.Exception.Message)"
        Start-Sleep -Seconds $PollIntervalSeconds
        continue
    }

    Write-Host "Pipeline status: $($lastStatus.status)"
    if ($lastStatus.status -eq "complete") {
        $artifact = $lastStatus.form1040Document.artifact
        if ($null -eq $artifact -or [string]::IsNullOrWhiteSpace([string]$artifact.artifactId)) {
            throw "Pipeline completed but no Form 1040 artifact metadata was returned."
        }

        Write-Host "Smoke test completed successfully."
        Write-Host "Form 1040 artifact: $($artifact.artifactId)"
        return
    }

    Start-Sleep -Seconds $PollIntervalSeconds
}

$lastStatusJson = if ($null -eq $lastStatus) { "<no status response>" } else { $lastStatus | ConvertTo-Json -Depth 20 }
throw "Pipeline did not reach complete within $TimeoutSeconds seconds. Last status: $lastStatusJson"
