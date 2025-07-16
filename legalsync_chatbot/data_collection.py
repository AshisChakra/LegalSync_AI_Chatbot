from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import uvicorn
import os
import requests
import pymupdf  # PyMuPDF
import re
import json
import pdfplumber
import shutil
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from collections import defaultdict
from openai import AzureOpenAI
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from typing import List
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# Allow requests from React frontend running on localhost:3000
origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

counts = 0


@app.post("/download")
async def download_files(urls: list[str]):
    print("backend call..");
    if any(s.strip() == "" for s in urls):
        return {"message": "No URLs provided"}

    output_dir = 'download_pdf'
    crawl_and_download_pdfs(urls, output_dir, max_workers=5)
    return {"message": 'download completed'}

### code to crawl & download
def download_pdf(url, output_path):

    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded {url} to {output_path}")
        # json_str, counts = process_pdf_llm(output_path)
        json_str = process_pdf(output_path)
        move_pdf_basedOn_json_string(json_str, output_path, "classified_pdf")
    except requests.exceptions.RequestException as e:
        print(f"Failed to download {url}: {e}")

def crawl_and_download_pdfs(start_urls, output_dir, max_workers=5):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for start_url in start_urls:
        print(f"Crawling {start_url}...")
        try:
            response = requests.get(start_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.endswith('.pdf'):
                    full_url = urljoin(start_url, href)
                    file_name = os.path.join(output_dir, os.path.basename(href))
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                     # Submit each download task
                          future_to_item = {
                              executor.submit(download_pdf, full_url, file_name)
                         }

        except requests.exceptions.RequestException as e:
            print(f"Failed to retrieve {start_url}: {e}")

###  read pdf file
client = AzureOpenAI(
    api_key=os.getenv("AZURE_API_KEY"),
    api_version=os.getenv("CHAT_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
)

def extract_pages(path, num_pages=3):
    with pdfplumber.open(path) as pdf:
        return [pdf.pages[i].extract_text() or "" for i in range(min(num_pages, len(pdf.pages)))]

def analyze_with_llm(text):
    """Ask gpt-4o-mini to extract level, year, category, summary."""
    prompt = f"""You are a legal assistant. For the given document excerpt, identify:
- Court Level: "Supreme Court", "High Court", "District Court" or "Unknown"
- Year: first 4-digit year (1800–2099) if present, else "Unknown"
- Category: "Family", "Criminal", or "Other"
- Summary: one concise sentence.

Provide your answer in JSON format like:
{{"level":"...", "year":"...", "category":"...", "summary":"..."}}

Text excerpt:
\"\"\"{text[:2000]}\"\"\"
"""

    resp = client.chat.completions.create(
        model=chat_deployment,
        messages=[
            {"role":"system", "content":"You are a precise legal document classifier."},
            {"role":"user", "content":prompt}
        ],
        temperature=0.7,
        max_tokens=200
    )
    try:
        return resp.choices[0].message.content.strip()
    except:
        return '{}'

def process_pdf_llm(path):
    global counts
    pages = extract_pages(path, num_pages=3)
    results = []


    analysis = analyze_with_llm(pages)
        # parse JSON safely
    if analysis is None:
        analysis = {"level":"Unknown","year":"Unknown","category":"Other","summary":""}
#    key = f"{info['category'].lower()}_{info['level'].lower().replace(' ','')}_{info['year']}"
    counts+= 1

    return analysis, counts


### move from download_pdf to particular pdf

def move_pdf_basedOn_json_string(json_str, pdf_file_path, destination_base):
    """
    Moves a PDF file to a structured directory based on metadata provided as a JSON string.

    Parameters:
        json_str (str): JSON string containing metadata with 'level', 'year', and 'category'.
        pdf_file_path (str): Full path to the PDF file to be moved.
        destination_base (str): Base path where the structured directories will be created.

    Returns:
        str: Message indicating the result of the operation.
    """
    try:
        # Parse the JSON string
        metadata = json.loads(json_str.strip('```json\n').strip('```'))

        # Validate required keys
        if not all(key in metadata for key in ['level', 'year', 'category']):
            return "Error: JSON metadata must contain 'level', 'year', and 'category'."

        # Construct the target directory path
        target_dir = os.path.join(destination_base, str(metadata['level']), str(metadata['year']), str(metadata['category']))

        # Create the target directory if it doesn't exist
        os.makedirs(target_dir, exist_ok=True)

        # Define destination file path
        destination_pdf = os.path.join(target_dir, os.path.basename(pdf_file_path))

        # Move the PDF file
        if os.path.exists(pdf_file_path):
            shutil.move(pdf_file_path, destination_pdf)
            return f"Moved '{os.path.basename(pdf_file_path)}' to '{destination_pdf}'"
        else:
            return f"Error: File '{pdf_file_path}' not found."

    except json.JSONDecodeError:
        return "Error: Invalid JSON string."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

def process_pdf(pdf_path):
    # Open the PDF file
    doc = pymupdf.open(pdf_path)

    # Extract text from the first three pages
    text = ""
    for page_num in range(min(3, len(doc))):
        page = doc.load_page(page_num)
        text += page.get_text("text")

    # Define patterns for extraction
    patterns = {
        "level": r"(Supreme Court|High Court|District Court|Unknown)",
        "year": r"\b(18|19|20)\d{2}\b",
        "category": r"(Family|Criminal|Other)",
        "summary": r"([^.]*\.)"  # Extracts the first sentence
    }

    # Extract information using the defined patterns
    extracted_info = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            extracted_info[key] = match.group(0)
        else:
            extracted_info[key] = "Unknown"

    # Format the extracted information as JSON
    json_output = json.dumps(extracted_info, ensure_ascii=False, indent=2)
    return json_output


# Start server
if __name__ == "__main__":
   uvicorn.run(app, host="localhost", port=9000, log_level="info")