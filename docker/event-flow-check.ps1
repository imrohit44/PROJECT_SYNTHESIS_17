param(
    [string]$ApiBaseUrl = "http://localhost:8000/api/v1"
)

$ErrorActionPreference = "Stop"

function Invoke-Json {
    param([string]$Method, [string]$Uri, [object]$Body = $null, [string]$Token = $null)
    $headers = @{ "Content-Type" = "application/json" }
    if ($Token) { $headers.Authorization = "Bearer $Token" }
    $params = @{ Method = $Method; Uri = $Uri; Headers = $headers }
    if ($null -ne $Body) { $params.Body = ($Body | ConvertTo-Json -Depth 8) }
    Invoke-RestMethod @params
}

function DbScalar {
    param([string]$Sql)
    docker compose -f docker-compose.yml exec -T postgres psql -U pybank -d pybank_docker -t -A -c $Sql
}

$stamp = Get-Date -Format "yyyyMMddHHmmss"
$email = "event-flow-$stamp@example.com"
$password = "EventFlow123!"

$registered = Invoke-Json Post "$ApiBaseUrl/auth/register" @{
    name = "Event Flow"
    email = $email
    password = $password
}
$tokens = Invoke-Json Post "$ApiBaseUrl/auth/login" @{ email = $email; password = $password }
$source = Invoke-Json Post "$ApiBaseUrl/accounts" @{
    customer_id = $registered.customer_id
    account_type = "savings"
    opening_balance = "100.00"
} $tokens.access_token
$destination = Invoke-Json Post "$ApiBaseUrl/accounts" @{
    customer_id = $registered.customer_id
    account_type = "current"
    opening_balance = "0.00"
} $tokens.access_token

$transfer = Invoke-Json Post "$ApiBaseUrl/transfers" @{
    source_account_id = $source.account_id
    destination_account_id = $destination.account_id
    amount = "15.00"
} $tokens.access_token

for ($i = 0; $i -lt 20; $i++) {
    $published = DbScalar "select count(*) from outbox_events where event_type='transfer.completed' and payload->'payload'->>'source_transaction_id'='$($transfer.source_transaction_id)' and published_at is not null;"
    $processed = DbScalar "select count(*) from processed_events where event_id in (select id from outbox_events where payload->'payload'->>'source_transaction_id'='$($transfer.source_transaction_id)');"
    if ($published.Trim() -eq "1" -and $processed.Trim() -eq "1") {
        break
    }
    Start-Sleep -Seconds 2
}
$sourceBalance = (Invoke-Json Get "$ApiBaseUrl/accounts/$($source.account_id)" $null $tokens.access_token).balance

if ($sourceBalance -ne "85.00") { throw "Expected source balance 85.00." }
if ($published.Trim() -ne "1") { throw "Expected transfer outbox event to be published." }
if ($processed.Trim() -ne "1") { throw "Expected audit consumer to process transfer event." }

Write-Output "Event flow check passed for transfer $($transfer.source_transaction_id)"
