# PDF Text Extraction and Embedding Generator
 
This Python script processes PDF files to extract text, chunk it based on token limits, generate embeddings using Azure OpenAI, extract keywords using TF-IDF, and save the results to a CSV file. It is designed for processing legal or structured PDF documents, extracting metadata from the file path, and handling multiple PDFs concurrently using threading.
 
## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Directory Structure](#directory-structure)
- [Configuration](#configuration)
- [Usage](#usage)
- [Output](#output)
- [How It Works](#how-it-works)
- [License](#license)
 
## Features
- **Text Extraction**: Extracts text from PDFs with page numbers using PyMuPDF.
- **Text Chunking**: Splits text into chunks based on a token limit (default: 2000 tokens) using `tiktoken`.
- **Embedding Generation**: Generates text embeddings using Azure OpenAI's embedding model.
- **Keyword Extraction**: Extracts top keywords from each chunk using TF-IDF (scikit-learn).
- **Metadata Extraction**: Derives court, domain, and year from the PDF file path.
- **Concurrent Processing**: Processes PDFs in batches using `ThreadPoolExecutor` for efficiency.
- **CSV Output**: Saves chunked data, metadata, keywords, and embeddings to a CSV file.
 
## Prerequisites
- **Python**: Version 3.8 or higher.
- **Libraries**:
  - `pymupdf` (PyMuPDF): For PDF text extraction.
  - `tiktoken`: For token counting.
  - `python-dotenv`: For loading environment variables.
  - `scikit-learn`: For TF-IDF keyword extraction.
  - `openai`: For Azure OpenAI embeddings.
- **Azure OpenAI Account**: Required for embedding generation.
- **PDF Files**:
 
## Installation
 
1. **Install Dependencies**:
   ```bash
   pip install pymupdf tiktoken python-dotenv scikit-learn openai
   ```
 
2. **Set Up Environment Variables**:
   Create a `.env` file in the project root with the following:
   ```env
   AZURE_OPENAI_KEY=your_azure_openai_key
   EMBEDDING_API_VERSION=2023-05-15
   AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
   EMBEDDING_MODEL=text-embedding-ada-002
   ```
   Replace the values with your Azure OpenAI credentials and endpoint.
 
## Directory Structure
The script expects PDFs in a specific directory structure to extract metadata (court, year, domain):
```
./classified_pdf
└── <court>
    └── <year>
        └── <domain>
            └── <file>.pdf
```
Example:
```
./classified_pdf
└── SupremeCourt
    └── 2023
        └── Civil
            ├── case1.pdf
            └── case2.pdf
```
 
- **Court**: The court name (e.g., `SupremeCourt`).
- **Year**: The year of the document (e.g., `2023`).
- **Domain**: The domain or category (e.g., `Civil`).
- **File**: The PDF file (e.g., `case1.pdf`).
 
Ensure your PDFs are organized this way, or modify the `extract_metadata` function if your structure differs.
 
## Configuration
- **Token Limit**: The script chunks text at a maximum of 2000 tokens (configurable in `chunk_across_pages_stream`).
- **Batch Size**: PDFs are processed in batches of 2 (configurable in the script as `batch_size`).
- **ThreadPoolExecutor**: Uses 5 workers for concurrent processing (configurable as `max_workers`).
- **CSV Output**: Outputs to `pdf_chunks.csv` in the project root. Modify `csv_file_path` to change the output location.
 
## Usage
1. **Prepare PDFs**: Place PDF files in the `./classified_pdf` directory with the expected structure.
2. **Run the Script**:
   ```
   python script.py
   ```
   Replace `script.py` with the name of your Python file.
3. **Monitor Output**:
   - The script prints the PDF batches being processed.
   - It logs each chunk written to the CSV with its `chunk_id`.
 
## Output
The script generates a `pdf_chunks.csv` file with the following columns:
- `file_name`: Name of the PDF file (e.g., `case1.pdf`).
- `blob_path`: Full path to the PDF file.
- `page_numbers`: List of page numbers for the chunk (e.g., `[1, 2, 3]`).
- `chunk_text`: Extracted text chunk.
- `chunk_id`: Unique ID for the chunk (e.g., `case1.pdf_p1-3_c0`).
- `keywords`: Top keywords extracted via TF-IDF (comma-separated).
- `domain`: Domain from the file path (e.g., `Civil`).
- `court`: Court from the file path (e.g., `SupremeCourt`).
- `year`: Year from the file path (e.g., `2023`).
- `chunk_vector`: Text embedding as a stringified list of floats.
 
Example CSV row:
```csv
file_name,blob_path,page_numbers,chunk_text,chunk_id,keywords,domain,court,year,chunk_vector
case1.pdf,./classified_pdf/SupremeCourt/2023/Civil/case1.pdf,"[1, 2]","Sample text...","case1.pdf_p1-2_c0","court, case, law, ruling, judge",Civil,SupremeCourt,2023,"[0.123456, -0.789012, ...]"
```
 
## How It Works
1. **PDF Collection**: Walks the `./classified_pdf` directory to collect all `.pdf` files.
2. **Text Extraction**: Uses PyMuPDF to extract text from each page, associating page numbers.
3. **Chunking**: Splits text into chunks based on a token limit (2000 tokens) using ` tiktoken`, preserving page number metadata.
4. **Embedding Generation**: Sends each chunk to Azure OpenAI to generate embeddings.
5. **Keyword Extraction**: Uses TF-IDF to extract the top 5 keywords from each chunk.
6. **Metadata Extraction**: Parses the file path to extract court, domain, and year.
7. **CSV Writing**: Writes chunk data to `pdf_chunks.csv` with concurrent processing using `ThreadPoolExecutor`.
 
## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.