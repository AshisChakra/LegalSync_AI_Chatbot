import os
import fitz  # PyMuPDF
import csv
from openai import AzureOpenAI
import tiktoken
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer

load_dotenv()

# Tokenizer setup
tokenizer = tiktoken.encoding_for_model("text-embedding-ada-002")

# Embedding function
def get_embedding(text):
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        api_version=os.getenv("EMBEDDING__API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    response = client.embeddings.create(
        input=[text],
        model=os.getenv("EMBEDDING_MODEL")
    )
    return response.data[0].embedding

def extract_keywords_tfidf(text, top_n=5):
    vectorizer = TfidfVectorizer(stop_words='english', max_features=top_n)
    tfidf_matrix = vectorizer.fit_transform([text])
    keywords = vectorizer.get_feature_names_out()
    return ", ".join(keywords)


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

# Metadata
pdf_dir = "./data1"
csv_file = "pdf_chunks.csv"
domain = "Civil"
court = "Supreme Court"
year = 2009

# Initialize CSV with headers
if not os.path.exists(csv_file):
    with open(csv_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "file_name", "blob_path", "page_numbers", "chunk_text",
            "chunk_id", "keywords", "domain", "court", "year", "chunk_vector"
        ])

# Process a single PDF and write chunks to CSV
def process_pdf_stream(filename):
    filepath = os.path.join(pdf_dir, filename)
    pages = extract_text_with_page_numbers(filepath)

    with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        for idx, (chunk_text, page_nums) in enumerate(chunk_across_pages_stream(pages, max_tokens=2000)):
            if not chunk_text.strip() or chunk_text.strip().isnumeric():
                continue
            keywords = extract_keywords_tfidf(chunk_text)
            vector = get_embedding(chunk_text)
            vector_str = "[" + ", ".join([f"{v:.6f}" for v in vector]) + "]"

            chunk_id = f"{filename}_p{min(page_nums)}-{max(page_nums)}_c{idx}"

            writer.writerow([
                filename,
                filepath,
                str(page_nums),
                chunk_text,
                chunk_id,
                keywords,
                domain,
                court,
                year,
                vector_str
            ])
            print(f"Written chunk to CSV: {chunk_id}")

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
