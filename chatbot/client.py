import streamlit as st
import requests
import uuid
import json
from datetime import datetime
from kafka import KafkaConsumer
from pydantic import BaseModel, ValidationError
from typing import List, Optional

# ------------------- Models -------------------

class LegalResponse(BaseModel):
    reqid: str
    query: str
    title: str
    page_number: List[int]
    court_level: str
    location: str
    domain: str
    response_text: str

class ErrorResponse(BaseModel):
    reqid: str
    query: str
    error: str

# ------------------- Settings -------------------

API_URL = "http://localhost:8000/legal-analysis/send"
RESPONSE_TOPIC = "legal-response-topic"
BOOTSTRAP_SERVERS = "localhost:9092"

# ------------------- Utilities -------------------

def generate_request_payload(user_input: str):
    user_id = f"u_{str(uuid.uuid4())[:8]}"
    session_id = f"s_{str(uuid.uuid4())[:8]}"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    reqid = f"{user_id}_{session_id}_{timestamp}"
    return {
        "user_id": user_id,
        "session_id": session_id,
        "reqid": reqid,
        "query": user_input
    }

def listen_for_response(expected_reqid: str, timeout: int = 30) -> Optional[dict]:
    consumer = KafkaConsumer(
        RESPONSE_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        auto_offset_reset="earliest",
        group_id=f"streamlit-client-{expected_reqid}",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        consumer_timeout_ms=timeout * 1000
    )

    for message in consumer:
        response = message.value
        if response.get("reqid") == expected_reqid:
            consumer.close()
            return response
    consumer.close()
    return None

# ------------------- UI -------------------

st.set_page_config(page_title="Legal Chatbot (Kafka-enabled)", layout="wide")
st.title("⚖️ Legal Chatbot Client (Kafka-enabled)")
user_input = st.text_input("🔍 Ask a legal question:")

if st.button("🚀 Send to Kafka") and user_input:
    payload = generate_request_payload(user_input)
    st.session_state["reqid"] = payload["reqid"]

    with st.spinner("📤 Sending query..."):
        try:
            response = requests.post(API_URL, json=payload, timeout=10)
            if response.status_code == 200:
                st.success("✅ Query sent successfully! Listening for response...")

                with st.spinner("🧠 Waiting for chatbot response..."):
                    res = listen_for_response(payload["reqid"], timeout=30)

                if res:
                    # ✅ Validate response using Pydantic
                    try:
                        if "error" in res:
                            err = ErrorResponse(**res)
                            st.error(f"⚠️ Error: {err.error}")
                        else:
                            answer = LegalResponse(**res)
                            st.success("✅ Response received!")
                            st.json(answer.model_dump_json(indent=2))
                    except ValidationError as ve:
                        st.error(f"❌ Invalid Pydantic response:\n{ve}")
                        st.json(res)
                else:
                    st.warning("⌛ No response received within timeout.")
            else:
                st.error(f"❌ Server error: {response.status_code} - {response.text}")
        except Exception as e:
            st.error(f"🚨 Request failed: {str(e)}")
