# from fastapi import FastAPI
# from langserve import add_routes
# from dotenv import load_dotenv
# import uvicorn
# from rag_service import retrieve_and_generate
# from langchain_core.runnables import RunnableLambda  # ✅ import this

# # Load env
# load_dotenv()

# app = FastAPI(
#     title="Legal Case Chatbot API",
#     description="A chatbot API for analyzing legal case topics using Azure OpenAI and LangChain with RAG",
#     version="0.1.0"
# )

# # ✅ Wrap the function in a Runnable
# legal_chain = RunnableLambda(retrieve_and_generate)

# # ✅ Register the route
# add_routes(
#     app,
#     legal_chain,
#     path="/legal-analysis"
# )

# if __name__ == "__main__":
#     uvicorn.run(app, host="localhost", port=8000, log_level="info")


# File: chatbot/api.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from kafka import KafkaProducer
import json
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Legal RAG Chatbot Kafka API")

producer = KafkaProducer(
    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"),
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

class QueryInput(BaseModel):
    topic: str

@app.post("/legal-analysis/send")
async def send_to_kafka(input_data: QueryInput):
    try:
        payload = {"topic": input_data.topic}
        producer.send("legal-query-topic", value=payload)
        producer.flush()
        return {"message": "✅ Query sent to Kafka", "data": payload}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Failed to send to Kafka: {str(e)}")
