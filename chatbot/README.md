# ⚖️ LegalCaseSync AI Chatbot

A scalable Kafka-based, Azure OpenAI-powered RAG legal chatbot that allows users to ask questions about legal cases and receive structured JSON responses using LangChain, FAISS, and Pydantic.  
It supports dynamic user sessions and concurrent processing using Kafka consumers.

---

## 📦 Features

- Streamlit UI interface to send natural language legal queries  
- Automatically generates `user_id`, `session_id`, and `reqid` for each query  
- Uses LangChain with FAISS and Azure OpenAI GPT models for legal reasoning  
- Two Kafka topics: one for queries and one for responses  
- Each request is matched with a corresponding response using `reqid`  
- Pydantic schema ensures structured response validation  
- Scales dynamically: one processing thread per incoming user request  

---

## 🚀 Tech Stack

| Layer        | Tool/Library                     |
|--------------|----------------------------------|
| Frontend     | Streamlit                        |
| Backend      | FastAPI (optional)               |
| LLM          | Azure OpenAI GPT (`gpt-4o mini`) |
| Embeddings   | `text-embedding-ada-002`         |
| RAG Engine   | LangChain + FAISS                |
| Messaging    | Apache Kafka + Zookeeper (Docker)|
| Vector Store | FAISS (in-memory)                |
| Data Format  | JSON (Pydantic modeled)          |

---

## 🛠 Environment Setup

### Prerequisites

- Python >= 3.10  
- Docker + Docker Compose  
- Azure OpenAI resource with deployments:
  - gpt-35-turbo
  - text-embedding-ada-002

---

### Environment Variables (.env)

Create a `.env` file at the root:

```
AZURE_API_KEY=your_azure_key
AZURE_ENDPOINT=https://<your-resource>.openai.azure.com/
CHAT_DEPLOYMENT_NAME=gpt-35-turbo
CHAT_API_VERSION=2024-02-15-preview
EMBEDDING_DEPLOYMENT_NAME=text-embedding-ada-002
EMBEDDING_API_VERSION=2024-02-15-preview
EMBEDDING_MODEL_NAME=text-embedding-ada-002
```

---

## 📁 Project Structure

```
LegalCaseSync_AI_Chatbot/
├── assets/
│   ├── sample.pdf
│   └── sample.csv
├── chatbot/
│   ├── api.py
│   ├── client.py
│   ├── kafka_producer.py
│   ├── kafka_query_consumer.py
│   ├── kafka_response_consumer.py
│   ├── models.py
│   └── rag_service.py
├── docker/
│   └── docker-compose.yml
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🧠 System Architecture

### Kafka Topics

- Request Topic: `legal-query-topic`  
- Response Topic: `legal-response-topic`  

---

## 🔁 Flow Summary

1. User submits query via `Streamlit UI` (`client.py`)
2. System auto-generates:
   - `user_id`
   - `session_id`
   - `reqid` (format: `u_<uid>_s_<sid>_<timestamp>`)
3. Query is sent to `legal-query-topic` via Kafka
4. `kafka_query_consumer.py`:
   - Receives query
   - Performs semantic search + GPT completion using LangChain
   - Sends structured JSON response to `legal-response-topic`
5. `kafka_response_consumer.py`:
   - Consumes responses
   - Displays them on the UI (matched via `reqid`)

---

## 🔍 Example Request JSON

```
{
  "user_id": "u_ab12cd34",
  "session_id": "s_ef56gh78",
  "reqid": "u_ab12cd34_s_ef56gh78_202507071235012345",
  "query": "Explain the Sarla Verma case"
}
```

---

## ✅ Example Response JSON

```
{
  "reqid": "u_ab12cd34_s_ef56gh78_202507071235012345",
  "query": "Explain the Sarla Verma case",
  "title": "Sarla Verma & Ors vs Delhi Transport Corp & Anr",
  "page_number": [14],
  "court_level": "Supreme Court",
  "location": "New Delhi",
  "domain": "civil",
  "response_text": "The Sarla Verma case involved motor accident compensation..."
}
```

---

## ▶️ Running the System

Open 3 terminals and run:

```
# Terminal 1: Start Kafka Query Consumer
python chatbot/kafka_query_consumer.py
```

```
# Terminal 2: Start Kafka Response Consumer
python chatbot/kafka_response_consumer.py
```

```
# Terminal 3: Launch Streamlit UI
streamlit run chatbot/client.py
```

```
# Terminal 4: Start FastAPI
python chatbot/api.py


# Terminal 5: Start Docker
docker-compose up -d
```

---

## 📬 Notes

- Ensure Kafka and Zookeeper are running: `docker-compose up -d`  
- `.env` must contain valid Azure OpenAI keys and endpoints  

---

## 👤 Author

**Ashis Chakraborty**  
GitHub: [AshisChakra](https://github.com/AshisChakra)