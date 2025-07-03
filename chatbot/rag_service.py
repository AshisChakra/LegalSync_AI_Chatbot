import os
import uuid
import pandas as pd
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from langchain.tools import tool
from pathlib import Path
from pydantic import BaseModel
import json
import ast

# Load environment
load_dotenv()

# Constants
PDF_PATH = "../assets/sample.pdf"
CSV_PATH = "../assets/sample.csv"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Embeddings + Chat Model
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

# Output Schema
class LegalResponse(BaseModel):
    title: str
    page_number: list[int]
    court_level: str
    location: str
    domain: str
    response_text: str

# CSV Extraction (if not present)
def extract_pdf_to_csv():
    if os.path.exists(CSV_PATH) and os.stat(CSV_PATH).st_size > 0:
        return
    reader = PdfReader(str(PDF_PATH))
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        import csv
        writer = csv.DictWriter(f, fieldnames=["file_name", "page_number", "year", "chunk_vector", "chunk_id"])
        writer.writeheader()
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text:
                continue
            chunks = text_splitter.split_text(text)
            vectors = embeddings.embed_documents(chunks)
            for chunk, vector in zip(chunks, vectors):
                writer.writerow({
                    "file_name": os.path.basename(PDF_PATH),
                    "page_number": i + 1,
                    "year": "2009",
                    "chunk_vector": json.dumps(vector),
                    "chunk_id": str(uuid.uuid4())
                })

# Tool: FAISS-based semantic vector search
@tool
def query_csv_chunks(query: str) -> str:
    """Semantic search over legal case chunks stored in CSV."""
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
        }
        for r in results
    ])

# Main Chain
def retrieve_and_generate(inputs: dict) -> dict:
    topic = inputs["topic"]
    extract_pdf_to_csv()

    agent = initialize_agent(
        tools=[Tool.from_function(query_csv_chunks, name="QueryCSV", description="Query legal chunks by topic")],
        llm=chat_model,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False
    )

    query_instruction = (
        f"You are a legal case assistant. Use the tool 'QueryCSV' only. "
        f"Do not answer directly. Your task is to extract relevant legal chunk metadata "
        f"by running QueryCSV with the input: '{topic}'. Return the result as a JSON array. "
        f"If no match is found, return '[]'."
    )

    agent_response = agent.run(query_instruction)
    print("🧠 Agent raw output:", agent_response)

    try:
        chunks_info = json.loads(agent_response)
        if not chunks_info:
            return {"error": "No relevant legal case chunks found. Please refine your query."}
    except json.JSONDecodeError:
        return {"error": "No structured case data found. Please try a more specific legal term or query."}

    try:
        reader = PdfReader(str(PDF_PATH))
        context = ""
        page_numbers = []
        for item in chunks_info:
            page_number = int(item["page_number"])
            page_numbers.append(page_number)
            context += reader.pages[page_number - 1].extract_text()[:1000] + "\n---\n"

        # Prompt for JSON response with structure
        response_prompt = ChatPromptTemplate.from_template(
            """
            You are a legal analyst. Based on the context below, return a response in valid JSON format with these fields:
            - title: full case title
            - page_number: list of pages this summary is derived from
            - court_level: High Court or Supreme Court
            - location: if mentioned, where the case was heard
            - domain: one of ['criminal', 'civil', 'family', 'constitutional', 'labor', 'tax', 'property']
            - response_text: respond appropriately based on the user input. Use the context to answer the user query.

            Context:
            {context}

            Topic: {topic}
            """
        )

        response_text = (response_prompt | chat_model | StrOutputParser()).invoke({"context": context, "topic": topic})

        cleaned_json = response_text.strip().removeprefix("```json").removesuffix("```").strip()
        return LegalResponse.model_validate_json(cleaned_json).dict()
    except Exception as e:
        return {"error": f"Failed to extract legal response: {str(e)}"}