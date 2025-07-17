import json
import threading
import time
from typing import List, Union
from kafka import KafkaConsumer, KafkaProducer
from models import QueryRequest
from rag_service import process_query, LegalResponse, ErrorResponse

REQUEST_TOPIC = "legal-query-topic"
RESPONSE_TOPIC = "legal-response-topic"
BOOTSTRAP_SERVERS = "localhost:9092"
BATCH_SIZE = 5
BATCH_TIMEOUT = 3  # seconds

print("🟢 Kafka Query Consumer Running...")

consumer = KafkaConsumer(
    REQUEST_TOPIC,
    bootstrap_servers=BOOTSTRAP_SERVERS,
    group_id="rag-query-consumer",
    value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    auto_offset_reset="earliest",
    enable_auto_commit=True,
)

producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP_SERVERS,
    value_serializer=lambda x: json.dumps(x).encode("utf-8")
)

lock = threading.Lock()
message_batch: List[dict] = []

def process_batch(batch: List[dict]):
    threads = []

    def handle(req_data: dict):
        try:
            req = QueryRequest(**req_data)
            response_obj: Union[LegalResponse, ErrorResponse, dict] = process_query(req)

            # Ensure we get a dict
            if isinstance(response_obj, (LegalResponse, ErrorResponse)):
                response_dict = response_obj.model_dump()
            else:
                response_dict = response_obj  # Already a dict

            # Ensure required fields are present
            response_dict.setdefault("reqid", req.reqid)
            response_dict.setdefault("query", req.query)

            producer.send(RESPONSE_TOPIC, value=response_dict)

        except Exception as e:
            print(f"❌ Error processing request {req_data.get('reqid')}: {e}")

    for item in batch:
        thread = threading.Thread(target=handle, args=(item,))
        threads.append(thread)
        thread.start()

    for t in threads:
        t.join()

def batch_consumer():
    global message_batch
    last_batch_time = time.time()

    for msg in consumer:
        with lock:
            message_batch.append(msg.value)

        now = time.time()
        with lock:
            if len(message_batch) >= BATCH_SIZE or (now - last_batch_time) >= BATCH_TIMEOUT:
                batch_to_process = message_batch.copy()
                message_batch.clear()
                last_batch_time = now
                threading.Thread(target=process_batch, args=(batch_to_process,)).start()

if __name__ == "__main__":
    batch_consumer()
