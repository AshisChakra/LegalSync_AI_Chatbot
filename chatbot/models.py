from pydantic import BaseModel
from typing import List

# ✅ Request Model
class QueryRequest(BaseModel):
    user_id: str
    session_id: str
    reqid: str
    query: str

# ✅ Successful LLM Response
class LegalResponse(BaseModel):
    reqid: str
    query: str
    title: str
    page_number: List[int]
    court_level: str
    location: str
    domain: str
    response_text: str

# ✅ Error Fallback
class ErrorResponse(BaseModel):
    reqid: str
    query: str
    error: str
