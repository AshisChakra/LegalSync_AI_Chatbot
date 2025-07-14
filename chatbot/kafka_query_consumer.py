# import json
# from confluent_kafka import Consumer, Producer
# from models import QueryRequest
# from rag_service import process_query

# consumer = Consumer({
#     'bootstrap.servers': 'localhost:9092',
#     'group.id': 'legal-query-consumer',
#     'auto.offset.reset': 'earliest'
# })
# producer = Producer({'bootstrap.servers': 'localhost:9092'})
# consumer.subscribe(["legal-query-topic"])

# print("🟢 Kafka Query Consumer Running...")

# while True:
#     msg = consumer.poll(1.0)
#     if msg is None:
#         continue
#     if msg.error():
#         print(f"⚠️ Consumer error: {msg.error()}")
#         continue

#     try:
#         payload = json.loads(msg.value())
#         query = QueryRequest(**payload)
#         response = process_query(query)
#         producer.produce("legal-response-topic", value=response.model_dump_json())
#         producer.flush()
#         print(f"✅ Processed and sent response for reqid: {query.reqid}")
#     except Exception as e:
#         print(f"❌ Failed to process message: {e}")

from kafka import KafkaConsumer, KafkaProducer
from models import QueryRequest
from rag_service import process_query
import json
import threading
import time

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
REQUEST_TOPIC = "legal-query-topic"
RESPONSE_TOPIC = "legal-response-topic"
BATCH_SIZE = 5
BATCH_TIMEOUT = 3  # seconds

consumer = KafkaConsumer(
    REQUEST_TOPIC,
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='legal-batch-group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    value_serializer=lambda x: json.dumps(x).encode('utf-8')
)

print("🟢 Kafka Query Consumer Running...")

def handle_batch(batch):
    threads = []

    def worker(payload):
        try:
            req = QueryRequest(**payload)
            response = process_query(req)
            producer.send(RESPONSE_TOPIC, value=response.model_dump())
        except Exception as e:
            print(f"❌ Error processing request {payload.get('reqid')}: {e}")

    for item in batch:
        t = threading.Thread(target=worker, args=(item,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

def consume_in_batches():
    batch = []
    last_batch_time = time.time()

    for message in consumer:
        batch.append(message.value)
        if len(batch) >= BATCH_SIZE or (time.time() - last_batch_time >= BATCH_TIMEOUT):
            handle_batch(batch)
            batch = []
            last_batch_time = time.time()

if __name__ == "__main__":
    consume_in_batches()
