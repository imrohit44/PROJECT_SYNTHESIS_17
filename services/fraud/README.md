# PyBank Fraud Service

This is the independent Fraud/Risk microservice for PyBank.

## Local Development

If you are running the `postgres` container from a previous phase (where the data volume already exists), the `/docker-entrypoint-initdb.d/init-fraud-db.sql` script will NOT automatically execute.

**To manually initialize the database without destroying your existing data:**
1. Ensure the `postgres` container is running.
2. Run the following command to create the database:
   ```bash
   docker compose exec postgres psql -U pybank -d pybank_docker -c "CREATE DATABASE pybank_fraud;"
   ```

If you are starting fresh (`docker compose down -v`), the initialization script will run automatically.

## Running the Service
```bash
docker compose up -d fraud
```

## Scaling
To test multiple instances:
```bash
docker compose up -d --scale fraud=2
```
*Note: Since the Kafka topic only has 1 partition, only 1 consumer will be active.*
