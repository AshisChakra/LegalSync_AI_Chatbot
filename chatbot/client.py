# import requests
# import streamlit as st

# def get_chat_response(topic):
#     url = "http://localhost:8000/legal-analysis/invoke" 
#     headers = {"Content-Type": "application/json"}
#     data = {"input": {"topic": topic}} 
    
#     response = requests.post(url, json=data, headers=headers)
    
#     if response.status_code == 200:
#         return response.json().get("output", "No output received.")
#     else:
#         return f"Error: {response.status_code} - {response.text}"

# # Streamlit app
# st.title("Chatbot Client")
# st.set_page_config(page_title="Chatbot Client", layout="wide")

# input_text = st.text_input("Enter a topic for the legal:")

# if input_text:
#     with st.spinner("Generating legal..."):
#         output = get_chat_response(input_text)
#         st.write("Generated legal:")
#         st.write(output)





import streamlit as st
import requests
from kafka_producer import send_query_to_kafka

def fetch_latest_response():
    try:
        res = requests.get("http://localhost:8000/last-response")
        if res.status_code == 200:
            return res.json()
    except:
        return None

st.set_page_config(page_title="Legal Chatbot Client", layout="wide")
st.title("Legal Chatbot Client (Kafka-enabled)")

user_input = st.text_input("🔍 Ask a legal question:")

if st.button("🚀 Send to Kafka"):
    send_query_to_kafka(user_input)
    st.success(f"✅ Query sent to Kafka: {user_input}")

    with st.spinner("⏳ Waiting for response from consumer..."):
        import time
        for _ in range(20):
            time.sleep(1)
            result = fetch_latest_response()
            if result:
                st.json(result)
                break
        else:
            st.warning("⚠️ Timed out waiting for response.")