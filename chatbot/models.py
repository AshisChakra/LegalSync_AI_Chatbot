from pydantic import BaseModel
from typing import List

class QueryRequest(BaseModel):
    user_id: str
    session_id: str
    reqid: str
    query: str

class LegalCaseResult(BaseModel):
    case: str
    year: int
    details: str

class QueryResponse(BaseModel):
    reqid: str
    query: str
    results: List[LegalCaseResult]

class QueryResponse(BaseModel):
    reqid: str
    query: str
    title: str
    page_number: List[int]
    court_level: str
    location: str
    domain: str
    response_text: str

class ErrorResponse(BaseModel):
    reqid: str
    query: str
    error: str

