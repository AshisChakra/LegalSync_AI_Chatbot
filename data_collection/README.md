# PDF Downloader and Classifier Application
 
This project is a web-based tool built using **FastAPI** and **Streamlit** that allows users to input URLs of websites containing PDF files. The application crawls the provided URLs, downloads the PDF files, and classifies them based on extracted metadata using either regex-based parsing or Azure OpenAI LLM.
 
---
 
## 🚀 Features
 
- ✅ Streamlit frontend for user input and interaction  
- ✅ FastAPI backend for crawling, downloading, and processing PDFs  
- ✅ PDF classification based on court level, year, category, and summary  
- ✅ Integration with Azure OpenAI for intelligent document analysis  
- ✅ Automatic organization of PDFs into structured directories  
 
---
 
## 🛠️ Technologies Used
 
- Python  
- FastAPI  
- Streamlit  
- PyMuPDF  
- pdfplumber  
- BeautifulSoup  
- Azure OpenAI  
- Uvicorn  
 
---
 
## ⚙️ Setup Instructions
 
 
 
1. **Clone the repository**   
   git clone <repository-url>
   cd <repository-folder>

 
2. Install dependencies
pip install -r requirements.txt
Set environment variables
 
You need to set the following environment variables for Azure OpenAI integration:
 
AZURE_API_KEY
 
AZURE_API_BASE
 
AZURE_API_VERSION
 
AZURE_DEPLOYMENT_NAME
 
Run the FastAPI backend
uvicorn main:app --reload
Run the Streamlit frontend
streamlit run streamlit_app.py


🧪 How to Use
Open the Streamlit app in your browser
 
Enter one or more URLs (comma-separated) that contain PDF links.
 
Click Submit.
 
The backend will crawl the URLs, download PDFs, and classify them.
 
PDFs will be automatically moved into folders based on extracted metadata, e.g.:
 

classified_pdf/
  └── Supreme Court/
      └── 2021/
          └── Criminal/
              └── file.pdf
📡 API Endpoint
POST /download
Request Body:json
 

{
  "urls": [http://localhost:9000/download]
}
Response:json
{
  "status": "success",
  "downloaded_pdfs": 10,
  "classified_pdfs": 10
}
📁 Output Structure
download_pdf/ – Raw downloaded PDFs
 
classified_pdf/ – PDFs organized by metadata folders (court level, year, category)