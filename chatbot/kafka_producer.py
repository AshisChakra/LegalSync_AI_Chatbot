from kafka import KafkaProducer
import json
import os

producer = KafkaProducer(
    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def send_query_to_kafka(query: str):
    payload = {"topic": query}
    producer.send("legal-query-topic", value=payload)
    producer.flush()
    print(f"✅ Sent to Kafka: {query}")
