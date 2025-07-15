import os
from typing import Union
import uuid
import ast
import json
import pandas as pd
from PyPDF2 import PdfReader
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
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
PDF_PATH = "../assets/sample.pdf"
CSV_PATH = "../assets/sample.csv"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

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

# PDF to CSV embedding
def extract_pdf_to_csv():
    if os.path.exists(CSV_PATH) and os.stat(CSV_PATH).st_size > 0:
        return
    reader = PdfReader(str(PDF_PATH))
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        import csv
        writer = csv.DictWriter(f, fieldnames=["file_name", "page_number", "year", "chunk_vector", "chunk_id"])
        writer.writeheader()
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text:
                continue
            chunks = splitter.split_text(text)
            vectors = embeddings.embed_documents(chunks)
            for chunk, vector in zip(chunks, vectors):
                writer.writerow({
                    "file_name": os.path.basename(PDF_PATH),
                    "page_number": i + 1,
                    "year": "2009",
                    "chunk_vector": json.dumps(vector),
                    "chunk_id": str(uuid.uuid4())
                })

# Tool: semantic vector lookup
@tool
def query_csv_chunks(query: str) -> str:
    """Semantic search over legal case chunks stored in the CSV."""
    df = pd.read_csv(CSV_PATH)
    docs = []
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
    if not docs:
        return json.dumps([])

    vector_store = FAISS.from_documents(docs, embeddings)
    results = vector_store.similarity_search(query, k=3)
    return json.dumps([
        {
            "file_name": r.page_content.split(" page ")[0],
            "page_number": int(r.page_content.split(" page ")[1]),
            "chunk_id": r.metadata["chunk_id"]
        } for r in results
    ])

# Main logic
def retrieve_and_generate(payload: QueryRequest) -> Union[LegalResponse, ErrorResponse]:
    reqid = payload.reqid
    query = payload.query

    extract_pdf_to_csv()

    agent = initialize_agent(
        tools=[Tool.from_function(query_csv_chunks, name="QueryCSV", description="Query legal chunks by topic")],
        llm=chat_model,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False
    )

    instruction = (
        f"You are a legal case assistant. Use the tool 'QueryCSV' only. "
        f"Do not answer directly. Your task is to extract relevant legal chunk metadata "
        f"by running QueryCSV with the input: '{query}'. Return the result as a JSON array. "
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
        reader = PdfReader(str(PDF_PATH))
        context = ""
        pages = []
        for item in chunks_info:
            pg = int(item["page_number"])
            pages.append(pg)
            raw_text = reader.pages[pg - 1].extract_text()
            if raw_text:
                context += raw_text.strip()[:1000] + "\n---\n"

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

        # ✅ Parse as dict and inject required fields
        parsed = json.loads(cleaned)
        parsed["reqid"] = reqid
        parsed["query"] = query

        # ✅ Validate complete data using Pydantic
        return LegalResponse(**parsed)

    except Exception as e:
        return ErrorResponse(
            reqid=reqid,
            query=query,
            error=f"❌ Failed to generate response: {str(e)}"
        )


# ✅ Kafka-compatible entry point
def process_query(payload: QueryRequest) -> dict:
    result = retrieve_and_generate(payload)
    return result.model_dump() if isinstance(result, BaseModel) else result

