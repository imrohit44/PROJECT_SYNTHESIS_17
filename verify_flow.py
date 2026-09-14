import httpx
import time
import psycopg
import json
import uuid
import os

BASE_URL = "http://localhost:8000/api/v1"
DB_URL = "postgresql://pybank:pybank_docker_password@localhost:5433/pybank_fraud"

def main():
    client = httpx.Client(base_url=BASE_URL)
    
    print("1. Registering user...")
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    pwd = "TestPassword123!"
    r = client.post("/auth/register", json={"username": username, "email": f"{username}@example.com", "password": pwd, "full_name": "Test User"})
    r.raise_for_status()

    print("2. Login...")
    r = client.post("/auth/token", data={"username": username, "password": pwd})
    r.raise_for_status()
    token = r.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    print("3. Create source account...")
    r = client.post("/accounts/", json={"currency": "USD"})
    r.raise_for_status()
    source_acc = r.json()["id"]

    print("4. Create destination account...")
    r = client.post("/accounts/", json={"currency": "USD"})
    r.raise_for_status()
    dest_acc = r.json()["id"]

    print("5. Deposit to source...")
    r = client.post(f"/accounts/{source_acc}/deposit", json={"amount": 15000})
    r.raise_for_status()

    print("6. Transfer from source to dest...")
    r = client.post("/transfers/", json={
        "source_account_id": source_acc,
        "destination_account_id": dest_acc,
        "amount": 12000,
        "description": "Test Transfer"
    })
    r.raise_for_status()
    transfer_data = r.json()
    source_txn_id = transfer_data["source_transaction_id"]
    
    print(f"Transfer successful. Source Txn: {source_txn_id}")
    
    print("7. Waiting for Kafka and Fraud Service...")
    time.sleep(5)
    
    print("8. Checking Fraud Service API...")
    r_fraud = httpx.get(f"http://localhost:8001/api/v1/risk-assessments/{source_txn_id}")
    print(r_fraud.status_code, r_fraud.text)
    
    print("9. Checking Fraud DB directly...")
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT risk_level, reasons FROM fraud_assessments WHERE transaction_id = %s", (source_txn_id,))
            res = cur.fetchone()
            print("Fraud Assessment:", res)
            
            cur.execute("SELECT COUNT(*) FROM processed_events")
            res2 = cur.fetchone()
            print("Processed Events count:", res2[0])
            
            cur.execute("SELECT COUNT(*) FROM outbox_events WHERE event_type = 'risk.assessed'")
            res3 = cur.fetchone()
            print("Outbox Risk Assessed count:", res3[0])

if __name__ == "__main__":
    main()
