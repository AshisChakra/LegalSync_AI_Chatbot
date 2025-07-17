import os
import fitz  # PyMuPDF
import tiktoken
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from openai import AzureOpenAI
from threading import Lock
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

load_dotenv()

# Validate Azure environment variables
required_env_vars = ["AZURE_API_KEY", "EMBEDDING_API_VERSION", "AZURE_ENDPOINT", "EMBEDDING_DEPLOYMENT_NAME"]
for var in required_env_vars:
    if not os.getenv(var):
        raise EnvironmentError(f"Missing required environment variable: {var}")

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB_NAME")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION_NAME")
mongo_available = False
mongo_client = None
mongo_collection = None

# Check MongoDB availability and configuration
if not all([MONGO_URI, MONGO_DB, MONGO_COLLECTION]):
    print("One or more MongoDB environment variables (MONGO_URI, MONGO_DB_NAME, MONGO_COLLECTION_NAME) are missing. Falling back to CSV-only storage.")
else:
    try:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        mongo_client.admin.command('ping')  # Test connection
        if not isinstance(MONGO_DB, str):
            raise ValueError(f"MONGO_DB_NAME must be a string, got {type(MONGO_DB)}: {MONGO_DB}")
        if not isinstance(MONGO_COLLECTION, str):
            raise ValueError(f"MONGO_COLLECTION_NAME must be a string, got {type(MONGO_COLLECTION)}: {MONGO_COLLECTION}")
        mongo_db = mongo_client[MONGO_DB]
        mongo_collection = mongo_db[MONGO_COLLECTION]
        mongo_available = True
        print("MongoDB connection established.")
    except (ConnectionFailure, ValueError) as e:
        print(f"MongoDB connection or configuration failed: {e}. Falling back to CSV-only storage.")

# Tokenizer setup
tokenizer = tiktoken.encoding_for_model("text-embedding-ada-002")

# Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_API_KEY"),
    api_version=os.getenv("EMBEDDING_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_ENDPOINT")
)

# CSV lock for thread safety
csv_lock = Lock()

# Embedding function (batch)
def get_embeddings_batch(texts):
    response = client.embeddings.create(
        input=texts,
        model=os.getenv("EMBEDDING_DEPLOYMENT_NAME")
    )
    return [data.embedding for data in response.data]

# TF-IDF keyword extraction
def extract_keywords_tfidf(text, top_n=5):
    vectorizer = TfidfVectorizer(stop_words='english', max_features=top_n)
    tfidf_matrix = vectorizer.fit_transform([text])
    keywords = vectorizer.get_feature_names_out()
    return ", ".join(keywords)

# Extract text from PDF with page numbers
def extract_text_with_page_numbers(pdf_path):
    doc = fitz.open(pdf_path)
    return [(i + 1, page.get_text()) for i, page in enumerate(doc)]

# Split large paragraphs
def split_large_paragraph(para, max_tokens):
    tokens = tokenizer.encode(para)
    if len(tokens) <= max_tokens:
        return [para]
    words = para.split()
    sub_paras = []
    current_para = []
    current_tokens = 0
    for word in words:
        word_tokens = len(tokenizer.encode(word))
        if current_tokens + word_tokens > max_tokens:
            sub_paras.append(" ".join(current_para))
            current_para = [word]
            current_tokens = word_tokens
        else:
            current_para.append(word)
            current_tokens += word_tokens
    if current_para:
        sub_paras.append(" ".join(current_para))
    return sub_paras

# Chunk generator
def chunk_across_pages_stream(pages, max_tokens=1500):
    buffer_paragraphs = []
    buffer_pages = set()
    token_count = 0

    for page_num, text in pages:
        if not text:
            continue
        for para in text.split("\n"):
            para = para.strip()
            if para and not para.isnumeric() and len(para) > 10:
                for sub_para in split_large_paragraph(para, max_tokens):
                    tokens = tokenizer.encode(sub_para)
                    para_token_count = len(tokens)

                    if token_count + para_token_count > max_tokens:
                        chunk_text = " ".join(buffer_paragraphs).strip()
                        yield (chunk_text, sorted(buffer_pages))
                        buffer_paragraphs = []
                        buffer_pages = set()
                        token_count = 0

                    buffer_paragraphs.append(sub_para)
                    buffer_pages.add(page_num)
                    token_count += para_token_count

    if buffer_paragraphs:
        chunk_text = " ".join(buffer_paragraphs).strip()
        yield (chunk_text, sorted(buffer_pages))

# Metadata
def extract_metadata(filepath):
    parts = filepath.split(os.sep)
    court = parts[-4]
    year = parts[-3]
    domain = parts[-2]
    return court, domain, year

# Process a single PDF and store chunks in CSV and MongoDB (if available)
def process_pdf_stream_to_csv_and_mongo(filepath, csv_writer, error_log):
    filename = os.path.basename(filepath)
    court, domain, year = extract_metadata(filepath)
    try:
        pages = extract_text_with_page_numbers(filepath)
    except Exception as e:
        error_log.append(f"Failed to read PDF {filepath}: {e}")
        return

    chunks = []
    chunk_page_nums = []
    for idx, (chunk_text, page_nums) in enumerate(chunk_across_pages_stream(pages, max_tokens=2000)):
        if not chunk_text.strip() or chunk_text.strip().isnumeric():
            continue
        chunks.append(chunk_text)
        chunk_page_nums.append(page_nums)

    # Generate embeddings in batch
    try:
        embeddings = get_embeddings_batch(chunks)
    except Exception as e:
        error_log.append(f"Embedding failed for {filepath}: {e}")
        return

    for idx, (chunk_text方, page_nums, vector) in enumerate(zip(chunks, chunk_page_nums, embeddings)):
        keywords = extract_keywords_tfidf(chunk_text)
        vector_str = "[" + ", ".join([f"{v:.6f}" for v in vector]) + "]"
        chunk_id = f"{filename}_p{min(page_nums)}-{max(page_nums)}_c{idx}"

        chunk_doc = {
            "file_name": filename,
            "blob_path": filepath,
            "page_numbers": str(page_nums),
            "chunk_text": chunk_text,
            "chunk_id": chunk_id,
            "keywords": keywords,
            "domain": domain,
            "court": court,
            "year": year,
            "chunk_vector": vector_str  # Store as string in CSV
        }

        # Write to CSV
        with csv_lock:
            try:
                csv_writer.writerow(chunk_doc)
                print(f"Wrote chunk to CSV: {chunk_doc['chunk_id']}")
            except Exception as e:
                error_log.append(f"CSV writing failed for chunk {chunk_doc['chunk_id']}: {e}")

        # Write to MongoDB if available
        if mongo_available:
            try:
                # Convert vector_str to list for MongoDB storage
                chunk_doc_mongo = chunk_doc.copy()
                chunk_doc_mongo["chunk_vector"] = [float(v) for v in vector]  # Store as list in MongoDB
                mongo_collection.insert_one(chunk_doc_mongo)
                print(f"Wrote chunk to MongoDB: {chunk_doc['chunk_id']}")
            except Exception as e:
                error_log.append(f"MongoDB insertion failed for chunk {chunk_doc['chunk_id']}: {e}")

# Collect all PDF files
pdf_dir = "./classified_pdf"
pdf_files = [os.path.join(root, file)
             for root, _, files in os.walk(pdf_dir)
             for file in files if file.lower().endswith(".pdf")]

# CSV setup
csv_file_path = "pdf_chunks.csv"
fieldnames = [
    "file_name", "blob_path", "page_numbers", "chunk_text", "chunk_id",
    "keywords", "domain", "court", "year", "chunk_vector"
]

error_log = []

with open(csv_file_path, mode='w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()

    # Process PDFs in batches using threads
    batch_size = 2
    pdf_batches = [pdf_files[i:i + batch_size] for i in range(0, len(pdf_files), batch_size)]
    print("The pdf_batches are", pdf_batches)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for batch in pdf_batches:
            futures.append(executor.submit(
                lambda b=batch: [process_pdf_stream_to_csv_and_mongo(filepath, writer, error_log) for filepath in b]
            ))

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                error_log.append(f"Error processing batch: {e}")

# Close MongoDB connection if open
if mongo_client:
    mongo_client.close()
    print("MongoDB connection closed.")

# Print error log
if error_log:
    print("\nErrors encountered during processing:")
    for error in error_log:
        print(error)