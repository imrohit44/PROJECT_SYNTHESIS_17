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
$email = "cache-check-$stamp@example.com"
$password = "CacheCheck123!"

$registered = Invoke-Json Post "$ApiBaseUrl/auth/register" @{
    name = "Cache Check"
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

Invoke-Json Get "$ApiBaseUrl/accounts/$($account.account_id)" $null $tokens.access_token | Out-Null
$cacheKey = "pybank:account:$($account.account_id)"
$existsBefore = docker compose -f docker-compose.yml exec -T redis redis-cli EXISTS $cacheKey
if ($existsBefore.Trim() -ne "1") {
    throw "Expected account cache key to exist before mutation."
}

$deposit = Invoke-Json Post "$ApiBaseUrl/accounts/$($account.account_id)/deposit" @{
    amount = "25.00"
} $tokens.access_token
if ($deposit.balance -ne "125.00") {
    throw "Expected deposit response balance to be 125.00."
}

$existsAfter = docker compose -f docker-compose.yml exec -T redis redis-cli EXISTS $cacheKey
if ($existsAfter.Trim() -ne "0") {
    throw "Expected account cache key to be invalidated after mutation."
}

$fresh = Invoke-Json Get "$ApiBaseUrl/accounts/$($account.account_id)" $null $tokens.access_token
if ($fresh.balance -ne "125.00") {
    throw "Expected fresh account read balance to be 125.00."
}

Write-Output "Cache invalidation check passed for account $($account.account_id)"
