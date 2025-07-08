import streamlit as st
import requests
import uuid
from datetime import datetime

# 🔧 Function to generate payload with dynamic user_id, session_id, reqid
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

# 🌐 API endpoint (FastAPI-based Kafka producer)
API_URL = "http://localhost:8000/legal-analysis/send"

# 🖼️ Streamlit UI
st.set_page_config(page_title="Legal Chatbot (Kafka-enabled)", layout="wide")
st.title("⚖️ Legal Chatbot Client (Kafka-enabled)")
user_input = st.text_input("🔍 Ask a legal question:")

if st.button("🚀 Send to Kafka") and user_input:
    payload = generate_request_payload(user_input)
    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        if response.status_code == 200:
            st.success(f"✅ Query sent to Kafka: {payload['query']}")
        else:
            st.error(f"❌ Error from server: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"🚨 Request failed: {str(e)}")
