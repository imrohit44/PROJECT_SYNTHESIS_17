param(
    [string]$ApiBaseUrl = "http://localhost:8000/api/v1"
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
    if ($Token) { $headers.Authorization = "Bearer $Token" }
    $params = @{ Method = $Method; Uri = $Uri; Headers = $headers }
    if ($null -ne $Body) { $params.Body = ($Body | ConvertTo-Json -Depth 8) }
    Invoke-RestMethod @params
}

$stamp = Get-Date -Format "yyyyMMddHHmmss"
$email = "cache-benchmark-$stamp@example.com"
$password = "BenchmarkPass123!"

$registered = Invoke-Json Post "$ApiBaseUrl/auth/register" @{
    name = "Cache Benchmark"
    email = $email
    password = $password
}
$tokens = Invoke-Json Post "$ApiBaseUrl/auth/login" @{
    email = $email
    password = $password
}
$account = Invoke-Json Post "$ApiBaseUrl/accounts" @{
    customer_id = $registered.customer_id
    account_type = "savings"
    opening_balance = "100.00"
} $tokens.access_token

$cold = Measure-Command {
    Invoke-Json Get "$ApiBaseUrl/accounts/$($account.account_id)" $null $tokens.access_token | Out-Null
}
$warm = Measure-Command {
    Invoke-Json Get "$ApiBaseUrl/accounts/$($account.account_id)" $null $tokens.access_token | Out-Null
}

Write-Output "Cold account read ms: $([math]::Round($cold.TotalMilliseconds, 2))"
Write-Output "Warm account read ms: $([math]::Round($warm.TotalMilliseconds, 2))"
Write-Output "Check backend logs for cache miss followed by cache hit when DEBUG logging is enabled."
