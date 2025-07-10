project:
  name: LegalCaseSync AI Chatbot
  description: >
    A scalable Kafka-based Azure OpenAI-powered RAG legal chatbot that allows users to ask questions about legal cases
    and receive structured JSON responses using LangChain, FAISS, and Pydantic. It supports dynamic user sessions and parallel processing via Kafka consumers.
  version: 1.0.0
  author: Ashis Chakraborty

environment:
  python_version: ">=3.10"
  requirements:
    - langchain
    - langchain-openai
    - langchain-community
    - faiss-cpu
    - PyPDF2
    - pydantic
    - python-dotenv
    - confluent-kafka
    - streamlit
    - fastapi
    - uvicorn

env_variables:
  AZURE_API_KEY: "Your Azure API Key"
  AZURE_ENDPOINT: "https://<your-resource>.openai.azure.com/"
  CHAT_DEPLOYMENT_NAME: "gpt-35-turbo"
  CHAT_API_VERSION: "2024-02-15-preview"
  EMBEDDING_DEPLOYMENT_NAME: "text-embedding-ada-002"
  EMBEDDING_API_VERSION: "2024-02-15-preview"
  EMBEDDING_MODEL_NAME: "text-embedding-ada-002"

structure:
  folders:
    - assets
    - chatbot
    - docker
  files:
    - assets/sample.pdf
    - assets/sample.csv (generated)
    - chatbot/rag_service.py
    - chatbot/kafka_producer.py
    - chatbot/kafka_query_consumer.py
    - chatbot/kafka_response_consumer.py
    - chatbot/client.py
    - chatbot/models.py
    - chatbot/api.py (optional)
    - docker/docker-compose.yml
    - .env
    - .gitignore
    - README.md

architecture:
  tools:
    - LangChain Agents
    - Azure OpenAI GPT
    - Azure OpenAI Embeddings
    - FAISS Vector Store
    - Kafka & Zookeeper
    - Docker Compose
    - Pydantic
    - Streamlit UI
  kafka_topics:
    - request_topic: legal-query-topic
    - response_topic: legal-response-topic
  flow:
    - Streamlit/Client sends query ➝ Kafka Producer ➝ Request Topic
    - Kafka Consumer listens ➝ Calls `process_query` from RAG
    - RAG uses LangChain + FAISS + GPT to respond
    - Response is pushed to Kafka Response Topic
    - UI/Client consumes the response and displays it based on `reqid`

usage:
  setup:
    - git clone https://github.com/AshisChakra/LegalSync_AI_Chatbot.git
    - cd LegalSync_AI_Chatbot
    - pip install -r requirements.txt
    - update .env with Azure API values
  kafka:
    - cd docker
    - docker-compose up -d
  consumers:
    - python chatbot/kafka_query_consumer.py
    - python chatbot/kafka_response_consumer.py
  client:
    - streamlit run chatbot/client.py
  backend (optional):
    - python chatbot/api.py

examples:
  query_payload:
    user_id: "u1"
    session_id: "s1"
    query: "Explain the Verma case verdict"
    reqid: "u1_s1_202507071234567890"
  response_payload:
    reqid: "u1_s1_202507071234567890"
    title: "Sarla Verma & Ors vs Delhi Transport Corp"
    page_number: [14]
    court_level: "Supreme Court"
    location: "New Delhi"
    domain: "civil"
    response_text: "The Sarla Verma case addresses..."

notes:
  - Ensure `.env` is excluded from git commits.
  - System supports unlimited concurrent queries with dynamic threading.
  - Designed to scale using Kafka partitions and multi-threading logic.
  - RAG pipeline is powered by LangChain with semantic search and prompt-based GPT-4/3.5 completion.


