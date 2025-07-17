import os
from typing import Union
import ast
import json
import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from pydantic import BaseModel
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from langchain.tools import tool
from models import QueryRequest

# Load environment variables
load_dotenv()

# Constants
CSV_PATH = "./pdf_chunks.csv"

# Embedding and Chat Model
embeddings = AzureOpenAIEmbeddings(
    api_key=os.getenv("AZURE_API_KEY"),
    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
    deployment=os.getenv("EMBEDDING_DEPLOYMENT_NAME"),
    api_version=os.getenv("EMBEDDING_API_VERSION"),
    model=os.getenv("EMBEDDING_MODEL_NAME")
)

chat_model = AzureChatOpenAI(
    api_key=os.getenv("AZURE_API_KEY"),
    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
    azure_deployment=os.getenv("CHAT_DEPLOYMENT_NAME"),
    api_version=os.getenv("CHAT_API_VERSION"),
    model=os.getenv("CHAT_MODEL_NAME")
)

# Output schemas
class LegalResponse(BaseModel):
    reqid: str
    query: str
    title: str
    page_number: list[int]
    court_level: str
    location: str
    domain: str
    response_text: str

class ErrorResponse(BaseModel):
    reqid: str
    query: str
    error: str

# Tool: MongoDB first, fallback to CSV
@tool
def query_case_chunks(query: str) -> str:
    """
    Semantic search over legal case chunks.
    Priority: MongoDB -> CSV fallback.
    """
    docs = []

    try:
        mongo_client = MongoClient(os.getenv("MONGO_URI"), serverSelectionTimeoutMS=2000)
        mongo_client.admin.command("ping")

        db = mongo_client[os.getenv("MONGO_DB_NAME", "legal_db")]
        collection = db[os.getenv("MONGO_COLLECTION_NAME", "pdf_chunks")]

        print("✅ Connected to MongoDB")

        for row in collection.find():
            try:
                vector = row.get("chunk_vector")
                if isinstance(vector, str):
                    vector = ast.literal_eval(vector)

                doc = Document(
                    page_content=f"{row['file_name']} page {row['page_number']}",
                    metadata={"embedding": vector, "chunk_id": row["chunk_id"]}
                )
                docs.append(doc)
            except Exception:
                continue

    except ConnectionFailure:
        print("⚠️ MongoDB unavailable — falling back to CSV.")
        if not os.path.exists(CSV_PATH):
            return json.dumps([])

        df = pd.read_csv(CSV_PATH)
        for _, row in df.iterrows():
            try:
                vector = ast.literal_eval(row["chunk_vector"])
                doc = Document(
                    page_content=f"{row['file_name']} page {row['page_number']}",
                    metadata={"embedding": vector, "chunk_id": row["chunk_id"]}
                )
                docs.append(doc)
            except Exception:
                continue

    # Build vector store and search
    if not docs:
        return json.dumps([])

    try:
        vector_store = FAISS.from_documents(docs, embeddings)
        results = vector_store.similarity_search(query, k=3)
        return json.dumps([
            {
                "file_name": r.page_content.split(" page ")[0],
                "page_number": int(r.page_content.split(" page ")[1]),
                "chunk_id": r.metadata["chunk_id"]
            } for r in results
        ])
    except Exception:
        return json.dumps([])

# Core RAG logic
def retrieve_and_generate(payload: QueryRequest) -> Union[LegalResponse, ErrorResponse]:
    reqid = payload.reqid
    query = payload.query

    agent = initialize_agent(
        tools=[Tool.from_function(query_case_chunks, name="QueryChunks", description="Query legal chunks by topic")],
        llm=chat_model,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False
    )

    instruction = (
        f"You are a legal case assistant. Use the tool 'QueryChunks' only. "
        f"Do not answer directly. Your task is to extract relevant legal chunk metadata "
        f"by running QueryChunks with the input: '{query}'. Return the result as a JSON array. "
        f"If no match is found, return '[]'."
    )

    try:
        agent_response = agent.run(instruction)
        print("🧠 Agent Output:", agent_response)
        chunks_info = json.loads(agent_response)
        if not chunks_info:
            return ErrorResponse(
                reqid=reqid,
                query=query,
                error="⚠️ No relevant legal case chunks found. Please refine your query."
            )
    except Exception as e:
        return ErrorResponse(
            reqid=reqid,
            query=query,
            error=f"Agent chunk extraction failed: {str(e)}"
        )

    try:
        # Use chunk metadata as context since full text is not present
        context = "\n".join([
            f"File: {item['file_name']}, Page: {item['page_number']}, Chunk ID: {item['chunk_id']}"
            for item in chunks_info
        ])

        response_prompt = ChatPromptTemplate.from_template("""
        You are a legal assistant. Based on the context below, return a valid JSON response with:
        - title: full legal case title
        - page_number: list of page numbers from where info was extracted
        - court_level: Supreme Court or High Court
        - location: where the case was heard (if available)
        - domain: criminal, civil, family, constitutional, labor, tax, property
        - response_text: respond appropriately to the user’s query.

        Context:
        {context}

        User Query:
        {topic}
        """)

        raw_response = (response_prompt | chat_model | StrOutputParser()).invoke({
            "context": context,
            "topic": query
        })

        cleaned = raw_response.strip().removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        parsed["reqid"] = reqid
        parsed["query"] = query

        return LegalResponse(**parsed)

    except Exception as e:
        return ErrorResponse(
            reqid=reqid,
            query=query,
            error=f"❌ Failed to generate response: {str(e)}"
        )

# Kafka-compatible entry point
def process_query(payload: QueryRequest) -> dict:
    result = retrieve_and_generate(payload)
    return result.model_dump() if isinstance(result, BaseModel) else result
