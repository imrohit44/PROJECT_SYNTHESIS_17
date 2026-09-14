# Phase 10: Learning Objectives

1. **Service Boundaries**: Understand how to draw a logical boundary around a specific business capability (Fraud Detection) and extract it from a monolith.
2. **Data Ownership**: Learn why microservices must own their own data and why shared databases lead to tight coupling.
3. **Event-Driven Communication**: Use Kafka to decouple services asynchronously.
4. **Consumer Groups**: Learn how consumer groups (`pybank-audit-consumer` vs `pybank-fraud-consumer`) allow multiple services to independently process the exact same event stream.
5. **Idempotency**: Learn how to use a `processed_events` table to safely handle duplicate Kafka messages (at-least-once delivery).
6. **Failure Isolation**: Observe how a failure in the Fraud Service does not prevent the Banking Service from completing transfers.
