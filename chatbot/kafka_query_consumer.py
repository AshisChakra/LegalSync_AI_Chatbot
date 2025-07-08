import json
from confluent_kafka import Consumer, Producer
from models import QueryRequest
from rag_service import process_query

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'legal-query-consumer',
    'auto.offset.reset': 'earliest'
})
producer = Producer({'bootstrap.servers': 'localhost:9092'})
consumer.subscribe(["legal-query-topic"])

print("🟢 Kafka Query Consumer Running...")

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        print(f"⚠️ Consumer error: {msg.error()}")
        continue

    try:
        payload = json.loads(msg.value())
        query = QueryRequest(**payload)
        response = process_query(query)
        producer.produce("legal-response-topic", value=response.model_dump_json())
        producer.flush()
        print(f"✅ Processed and sent response for reqid: {query.reqid}")
    except Exception as e:
        print(f"❌ Failed to process message: {e}")
