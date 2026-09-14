param(
    [string]$EventType = "transfer.completed"
)

$ErrorActionPreference = "Stop"

$eventId = docker compose -f docker-compose.yml exec -T postgres psql -U pybank -d pybank_docker -t -A -c "select id from outbox_events where event_type='$EventType' and published_at is not null order by created_at desc limit 1;"
$eventId = $eventId.Trim()
if (-not $eventId) {
    throw "No published $EventType event found."
}

$before = docker compose -f docker-compose.yml exec -T postgres psql -U pybank -d pybank_docker -t -A -c "select count(*) from processed_events where event_id='$eventId';"
docker compose -f docker-compose.yml exec -T backend python -c "from backend.app.core.config import get_settings; from backend.app.infrastructure.kafka import KafkaEventProducer; from backend.app.infrastructure.persistence.database import create_session_factory; from backend.app.infrastructure.persistence.models import OutboxEventModel; s=get_settings(); sf=create_session_factory(s.database_url); topic=f'{s.kafka_topic_prefix}.events'; session=sf(); event=session.get(OutboxEventModel, '$eventId'); KafkaEventProducer(s.kafka_bootstrap_servers, topic).publish(event.aggregate_id, event.payload); session.close(); print('$eventId')" | Out-Null

Start-Sleep -Seconds 6
$after = docker compose -f docker-compose.yml exec -T postgres psql -U pybank -d pybank_docker -t -A -c "select count(*) from processed_events where event_id='$eventId';"

if ($before.Trim() -ne "1" -or $after.Trim() -ne "1") {
    throw "Expected duplicate event to keep exactly one processed_events row."
}

Write-Output "Duplicate event check passed for event $eventId"
