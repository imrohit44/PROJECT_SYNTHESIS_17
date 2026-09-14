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
$email = "kafka-failure-$stamp@example.com"
$password = "KafkaFailure123!"

$registered = Invoke-Json Post "$ApiBaseUrl/auth/register" @{
    name = "Kafka Failure"
    email = $email
    password = $password
}
$tokens = Invoke-Json Post "$ApiBaseUrl/auth/login" @{ email = $email; password = $password }
$account = Invoke-Json Post "$ApiBaseUrl/accounts" @{
    customer_id = $registered.customer_id
    account_type = "savings"
    opening_balance = "100.00"
} $tokens.access_token

docker compose -f docker-compose.yml stop kafka | Out-Null
Start-Sleep -Seconds 2

$deposit = Invoke-Json Post "$ApiBaseUrl/accounts/$($account.account_id)/deposit" @{
    amount = "30.00"
} $tokens.access_token
if ($deposit.balance -ne "130.00") {
    throw "Expected deposit to succeed while Kafka is stopped."
}

Start-Sleep -Seconds 3
$eventId = DbScalar "select id from outbox_events where event_type='deposit.completed' and aggregate_id='$($account.account_id)' and published_at is null order by created_at desc limit 1;"
$eventId = $eventId.Trim()
if (-not $eventId) {
    throw "Expected deposit event to remain pending while Kafka is stopped."
}

docker compose -f docker-compose.yml start kafka | Out-Null

for ($i = 0; $i -lt 30; $i++) {
    $published = DbScalar "select count(*) from outbox_events where id='$eventId' and published_at is not null;"
    $processed = DbScalar "select count(*) from processed_events where event_id='$eventId';"
    if ($published.Trim() -eq "1" -and $processed.Trim() -eq "1") {
        break
    }
    Start-Sleep -Seconds 2
}

if ($published.Trim() -ne "1") {
    throw "Expected pending event to publish after Kafka recovery."
}
if ($processed.Trim() -ne "1") {
    throw "Expected recovered event to be processed after Kafka recovery."
}

Write-Output "Kafka failure recovery check passed for deposit event $eventId"
