import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from .infrastructure.database import get_db, engine
from .infrastructure.models import FraudAssessmentModel, Base
from .infrastructure.kafka_consumer import FraudConsumerThread
from .infrastructure.kafka_producer import OutboxPublisherThread

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "pybank-fraud-consumer")
KAFKA_TOPIC_PREFIX = os.getenv("KAFKA_TOPIC_PREFIX", "pybank")
RUN_MIGRATIONS = os.getenv("RUN_MIGRATIONS", "true").lower() == "true"

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not RUN_MIGRATIONS:
        Base.metadata.create_all(bind=engine)
        
    logger.info("Starting Kafka Consumer Thread...")
    consumer_thread = FraudConsumerThread(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=KAFKA_CONSUMER_GROUP,
        topic_prefix=KAFKA_TOPIC_PREFIX
    )
    consumer_thread.start()

    logger.info("Starting Outbox Publisher Thread...")
    publisher_thread = OutboxPublisherThread(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        topic_prefix=KAFKA_TOPIC_PREFIX
    )
    publisher_thread.start()
    
    yield
    
    logger.info("Shutting down Fraud Service...")

app = FastAPI(title="PyBank Fraud Service", version="0.1.0", lifespan=lifespan)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "fraud"}

@app.get("/api/v1/risk-assessments/{transaction_id}")
def get_risk_assessment(transaction_id: str, db: Session = Depends(get_db)):
    assessment = db.query(FraudAssessmentModel).filter(FraudAssessmentModel.transaction_id == transaction_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Risk assessment not found")
    return {
        "assessment_id": assessment.assessment_id,
        "event_id": assessment.event_id,
        "transaction_id": assessment.transaction_id,
        "risk_score": assessment.risk_score,
        "risk_level": assessment.risk_level,
        "reasons": assessment.reasons,
        "created_at": assessment.created_at.isoformat()
    }
