import json
from kafka import KafkaConsumer
from pydantic import ValidationError
from models import QueryResponse, ErrorResponse

consumer = KafkaConsumer(
    'legal-response-topic',
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    group_id='response-consumer-group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

print("🟢 Kafka Response Consumer Running...")

for message in consumer:
    try:
        data = message.value

        if "error" in data:
            err = ErrorResponse(**data)
            print(f"⚠️ Error for {err.reqid}: {err.error}")
        else:
            res = QueryResponse(**data)
            print(f"\n✅ Response for {res.reqid}:")
            print(f"🧠 Query: {res.query}")
            print(f"📄 Title: {res.title}")
            print(f"📚 Pages: {res.page_number}")
            print(f"🏛 Court: {res.court_level} @ {res.location}")
            print(f"🗂 Domain: {res.domain}")
            print(f"📝 Answer:\n{res.response_text}")

    except ValidationError as e:
        print(f"❌ Failed to decode response: {e}")
