from decimal import Decimal

import pytest

from backend.app.domain.exceptions import InsufficientFundsError
from backend.app.infrastructure.outbox import OutboxRepository
from backend.app.infrastructure.persistence.models import OutboxEventModel


def test_successful_account_creation_records_outbox_event(bank_service) -> None:
    customer = bank_service.register_customer("Alice", "alice@example.com")
    account = bank_service.create_savings_account(customer.customer_id)

    events = OutboxRepository(bank_service._session_factory).pending()

    assert len(events) == 1
    assert events[0].event_type == "account.created"
    assert events[0].aggregate_id == account.account_id


def test_failed_withdraw_does_not_record_outbox_event(bank_service) -> None:
    customer = bank_service.register_customer("Alice", "alice@example.com")
    account = bank_service.create_savings_account(customer.customer_id)
    repository = OutboxRepository(bank_service._session_factory)
    repository.mark_published(repository.pending()[0].id)

    with pytest.raises(InsufficientFundsError):
        bank_service.withdraw(account.account_id, Decimal("1.00"))

    assert repository.pending() == []


def test_outbox_mark_published_and_failure_metadata(bank_service) -> None:
    customer = bank_service.register_customer("Alice", "alice@example.com")
    bank_service.create_savings_account(customer.customer_id)
    repository = OutboxRepository(bank_service._session_factory)
    event = repository.pending()[0]

    repository.record_failure(event.id, RuntimeError("kafka down"))
    repository.mark_published(event.id)

    with bank_service._session_factory() as session:
        model = session.get(OutboxEventModel, event.id)
        assert model is not None
        assert model.published_at is not None
        assert model.attempt_count == 1
        assert model.last_error is None
