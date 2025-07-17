import os
import fitz  # PyMuPDF
import tiktoken
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from openai import AzureOpenAI

load_dotenv()

# Tokenizer setup
tokenizer = tiktoken.encoding_for_model("text-embedding-ada-002")

# Embedding function
client = AzureOpenAI(
    api_key=os.getenv("AZURE_API_KEY"),
    api_version=os.getenv("EMBEDDING_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_ENDPOINT")
)

def get_embedding(text):
    response = client.embeddings.create(
        input=[text],
        model=os.getenv("EMBEDDING_DEPLOYMENT_NAME")
    )
    return response.data[0].embedding

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

# Chunk generator
def chunk_across_pages_stream(pages, max_tokens=3000):
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

# Metadata
def extract_metadata(filepath):
    parts = filepath.split(os.sep)
    court = parts[-4]
    year = parts[-3]
    domain = parts[-2]
    return court, domain, year

# Process a single PDF and store chunks in CSV
def process_pdf_stream_to_csv(filepath, csv_writer):
    filename = os.path.basename(filepath)
    court, domain, year = extract_metadata(filepath)
    pages = extract_text_with_page_numbers(filepath)

    for idx, (chunk_text, page_nums) in enumerate(chunk_across_pages_stream(pages, max_tokens=2000)):
        if not chunk_text.strip() or chunk_text.strip().isnumeric():
            continue

        keywords = extract_keywords_tfidf(chunk_text)
        vector = get_embedding(chunk_text)
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
            "chunk_vector": vector_str
        }

        try:
            csv_writer.writerow(chunk_doc)
            print(f"Wrote chunk to CSV: {chunk_doc['chunk_id']}")
        except Exception as e:
            print(f"CSV writing failed for chunk {chunk_doc['chunk_id']}: {e}")

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

with open(csv_file_path, mode='w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    # Process PDFs in batches using threads
    batch_size = 2
    pdf_batches = [pdf_files[i:i + batch_size] for i in range(0, len(pdf_files), batch_size)]
    print("The pdf_batches are", pdf_batches)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for batch in pdf_batches:
            futures.append(executor.submit(
                lambda b=batch: [process_pdf_stream_to_csv(filepath, writer) for filepath in b]
            ))

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error processing batch: {e}")
