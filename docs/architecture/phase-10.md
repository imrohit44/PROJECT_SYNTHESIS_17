# Phase 10: Fraud/Risk Service Extraction

## Architecture

This phase introduces the first independent microservice in the PyBank ecosystem: the Fraud/Risk Service. 

### Why Microservices?
Microservices allow teams to independently develop, deploy, and scale specific domains of an application. The fraud domain is an excellent candidate for extraction because:
- Its data (`fraud_assessments`) is logically separate from core banking data (`accounts`, `balances`).
- It can process data asynchronously (eventual consistency) without blocking critical banking transactions like transfers.

### Kafka as the Boundary
The Banking Service and Fraud Service do not share Python code or databases. They communicate exclusively through Apache Kafka. 
- The Banking Service publishes `transfer.completed` events using a transactional outbox pattern.
- The Fraud Service consumes these events using a dedicated consumer group (`pybank-fraud-consumer`).
- The Fraud Service evaluates rules and publishes `risk.assessed` events.

### Data Ownership
The Banking Service owns banking tables. The Fraud Service owns its own independent PostgreSQL database `pybank_fraud`. Direct cross-service database queries are prohibited.

### Microservice Tradeoffs
Microservices are not a silver bullet. They introduce significant complexity:
- **Network calls**: Slower than in-process calls.
- **Serialization**: Overhead of converting objects to JSON and back.
- **Eventual Consistency**: A transfer might be completed in the Banking service, but the Fraud assessment might take seconds to appear.
- **Deployment & Monitoring Complexity**: More moving parts.

### Scaling Limitations
To demonstrate scaling, multiple instances of the Fraud Service can be spun up (e.g. `docker compose up -d --scale fraud=2`). However, Kafka partition rules apply: a consumer group can only have as many active consumers as there are partitions in the topic. Since our topic has 1 partition, only 1 instance will actively consume while the other remains idle.
