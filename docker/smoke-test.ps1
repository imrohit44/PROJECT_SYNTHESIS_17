param(
    [string]$ApiBaseUrl = "http://localhost:8000/api/v1",
    [string]$FrontendUrl = "http://localhost:8080"
)

$ErrorActionPreference = "Stop"

function Invoke-Json {
    param(
        [string]$Method,
        [string]$Uri,
        [object]$Body = $null,
        [string]$Token = $null
    )

    $headers = @{ "Content-Type" = "application/json" }
    if ($Token) {
        $headers.Authorization = "Bearer $Token"
    }

    $params = @{
        Method = $Method
        Uri = $Uri
        Headers = $headers
    }
    if ($null -ne $Body) {
        $params.Body = ($Body | ConvertTo-Json -Depth 8)
    }

    Invoke-RestMethod @params
}

$stamp = Get-Date -Format "yyyyMMddHHmmss"
$email = "docker-smoke-$stamp@example.com"
$password = "SmokePass123!"

Invoke-RestMethod -Uri "$ApiBaseUrl/health" | Out-Null
Invoke-WebRequest -Uri $FrontendUrl -UseBasicParsing | Out-Null

$registered = Invoke-Json -Method Post -Uri "$ApiBaseUrl/auth/register" -Body @{
    name = "Docker Smoke"
    email = $email
    password = $password
    phone = "555-0100"
}

$tokens = Invoke-Json -Method Post -Uri "$ApiBaseUrl/auth/login" -Body @{
    email = $email
    password = $password
}

$me = Invoke-Json -Method Get -Uri "$ApiBaseUrl/auth/me" -Token $tokens.access_token
if ($me.email -ne $email) {
    throw "Authenticated user mismatch."
}

$source = Invoke-Json -Method Post -Uri "$ApiBaseUrl/accounts" -Token $tokens.access_token -Body @{
    customer_id = $registered.customer_id
    account_type = "savings"
    opening_balance = "100.00"
    interest_rate = "0.04"
    minimum_balance = "0.00"
}

$destination = Invoke-Json -Method Post -Uri "$ApiBaseUrl/accounts" -Token $tokens.access_token -Body @{
    customer_id = $registered.customer_id
    account_type = "current"
    opening_balance = "25.00"
    overdraft_limit = "0.00"
}

Invoke-Json -Method Post -Uri "$ApiBaseUrl/accounts/$($source.account_id)/deposit" -Token $tokens.access_token -Body @{
    amount = "50.00"
} | Out-Null

Invoke-Json -Method Post -Uri "$ApiBaseUrl/accounts/$($source.account_id)/withdraw" -Token $tokens.access_token -Body @{
    amount = "20.00"
} | Out-Null

Invoke-Json -Method Post -Uri "$ApiBaseUrl/transfers" -Token $tokens.access_token -Body @{
    source_account_id = $source.account_id
    destination_account_id = $destination.account_id
    amount = "10.00"
} | Out-Null

$transactions = Invoke-Json -Method Get -Uri "$ApiBaseUrl/accounts/$($source.account_id)/transactions" -Token $tokens.access_token
if ($transactions.Count -lt 3) {
    throw "Expected at least 3 source account transactions."
}

Write-Output "Docker smoke test passed for $email"
