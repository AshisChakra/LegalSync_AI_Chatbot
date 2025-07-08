from fastapi import FastAPI, HTTPException
from kafka import KafkaProducer
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import json

from models import QueryRequest  # Make sure models.py has the updated QueryRequest model

# Load env
load_dotenv()

app = FastAPI()

# Kafka Producer
producer = KafkaProducer(
    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"),
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

@app.post("/legal-analysis/send")
async def send_to_kafka(request: QueryRequest):  # Now expecting full QueryRequest
    try:
        payload = request.model_dump()
        producer.send("legal-query-topic", value=payload)
        producer.flush()
        return {"message": "✅ Query sent to Kafka", "data": payload}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Failed to send to Kafka: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
