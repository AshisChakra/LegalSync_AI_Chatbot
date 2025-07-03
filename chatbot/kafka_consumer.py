# File: chatbot/kafka_consumer.py
from kafka import KafkaConsumer
import json
from rag_service import retrieve_and_generate
from fastapi import FastAPI
import uvicorn
import threading

last_response = None

def start_consumer():
    global last_response
    consumer = KafkaConsumer(
        'legal-query-topic',
        bootstrap_servers='localhost:9092',
        group_id='legal-rag-group',
        auto_offset_reset='earliest',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )

    print("🟢 Kafka Consumer Running...")

    for msg in consumer:
        query_data = msg.value
        print("📩 Received Query:", query_data)
        last_response = retrieve_and_generate(query_data)
        print("🧠 Legal Response:", json.dumps(last_response, indent=2))

# Run FastAPI endpoint to serve latest response
app = FastAPI()

@app.get("/last-response")
def get_response():
    return last_response or {}

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == '__main__':
    threading.Thread(target=start_consumer, daemon=True).start()
    run_api()