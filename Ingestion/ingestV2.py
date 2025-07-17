import os
import fitz  # PyMuPDF
from openai import AzureOpenAI
import tiktoken
from concurrent.futures import ThreadPoolExecutor, as_completed
from pymongo import MongoClient

# Azure OpenAI setup
AzureOpenAI.api_type = "azure"
AzureOpenAI.api_key = os.getenv("AZURE_API_KEY"),
AzureOpenAI.api_base =os.getenv("EMBEDDING_API_VERSION"),
AzureOpenAI.api_version = os.getenv("AZURE_ENDPOINT"),

# MongoDB setup
mongo_client = MongoClient(os.getenv("MONGO_URI"))
mongo_db = mongo_client[os.getenv("MONGO_DB_NAME")]
mongo_collection = mongo_db[os.getenv("MONGO_COLLECTION_NAME")]

# Tokenizer setup
tokenizer = tiktoken.encoding_for_model("text-embedding-ada-002")

# Optional: Embedding function
def get_embedding(text):
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_API_KEY"),
        api_version="2024-12-01-preview",
        azure_endpoint= os.getenv("AZURE_ENDPOINT"),
    )
    response = client.embeddings.create(
        input=[text],
        model=os.getenv("EMBEDDING_MODEL_NAME")
    )
    return response.data[0].embedding

# Extract text from PDF with page numbers
def extract_text_with_page_numbers(pdf_path):
    doc = fitz.open(pdf_path)
    return [(i + 1, page.get_text()) for i, page in enumerate(doc)]

# Streaming chunk generator
def chunk_across_pages_stream(pages, max_tokens=2000):
    buffer_paragraphs = []
    buffer_pages = set()
    token_count = 0

    for page_num, text in pages:
        if not text:
            continue
        for para in text.split("\n"):
            para = para.strip()
            if para and not para.isnumeric() and len(para) > 10:
                tokens = tokenizer.encode(para)
                para_token_count = len(tokens)

                if token_count + para_token_count > max_tokens:
                    chunk_text = " ".join(buffer_paragraphs).strip()
                    yield (chunk_text, sorted(buffer_pages))
                    buffer_paragraphs = []
                    buffer_pages = set()
                    token_count = 0

                buffer_paragraphs.append(para)
                buffer_pages.add(page_num)
                token_count += para_token_count

    if buffer_paragraphs:
        chunk_text = " ".join(buffer_paragraphs).strip()
        yield (chunk_text, sorted(buffer_pages))

# PDF directory
pdf_dir = "./data1"
print("Files in folder:", os.listdir(pdf_dir))

# Example metadata
domain = "Civil"
court = "Supreme Court"
year = 2009

# Process a single PDF and insert chunks immediately
def process_pdf_stream(filename):
    filepath = os.path.join(pdf_dir, filename)
    pages = extract_text_with_page_numbers(filepath)

    for idx, (chunk_text, page_nums) in enumerate(chunk_across_pages_stream(pages, max_tokens=2000)):
        if not chunk_text.strip() or chunk_text.strip().isnumeric():
            continue

        # Optional embedding
        # vector = get_embedding(chunk_text)
        # vector_str = "[" + ", ".join([f"{v:.6f}" for v in vector]) + "]"

        doc = {
            "file_name": filename,
            "blob_path": filepath,
            "page_numbers": str(page_nums),
            "chunk_text": chunk_text,
            "chunk_id": f"{filename}_p{min(page_nums)}-{max(page_nums)}_c{idx}",
            "keywords": "",
            "domain": domain,
            "court": court,
            "year": year,
            # "chunk_vector": vector_str
        }
        try:
            mongo_collection.insert_one(doc)
            print(f"Inserted chunk into MongoDB: {doc['chunk_id']}")
        except Exception as e:
            if "E11000" in str(e):
                print(f"Duplicate chunk skipped: {doc['chunk_id']}")
            else:
                print(f"MongoDB insertion failed for chunk {doc['chunk_id']}: {e}")

# Collect PDF files
pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]

# Process PDFs in batches using threads
batch_size = 2
pdf_batches = [pdf_files[i:i + batch_size] for i in range(0, len(pdf_files), batch_size)]
print("The pdf_batches are", pdf_batches)

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = []
    for batch in pdf_batches:
        futures.append(executor.submit(
            lambda b=batch: [process_pdf_stream(filename) for filename in b]
        ))

    for future in as_completed(futures):
        try:
            future.result()
        except Exception as e:
            print(f"Error processing batch: {e}")
