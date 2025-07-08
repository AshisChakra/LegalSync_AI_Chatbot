import json
import time
from confluent_kafka import Producer
from models import QueryRequest
from uuid import uuid4
from datetime import datetime

p = Producer({'bootstrap.servers': 'localhost:9092'})

def generate_reqid(user_id, session_id):
    return f"{user_id}_{session_id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

def send_query(user_id, session_id, query):
    reqid = generate_reqid(user_id, session_id)
    request = QueryRequest(
        user_id=user_id,
        session_id=session_id,
        reqid=reqid,
        query=query
    )
    p.produce("legal-query-topic", value=request.model_dump_json())
    p.flush()
    print(f"[✔️] Sent: {request.model_dump_json()}")
