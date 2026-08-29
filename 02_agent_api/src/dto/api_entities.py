import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

class ChatRequest(BaseModel):
    question: str
    user: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    user: str
    answer: str
    session_id: UUID
    trace_id: UUID

class HistoryItem(BaseModel):
    question: str
    answer: str
    trace_id: UUID
    session_id: UUID
    user: Optional[str] = None
    retrieved_contexts: Optional[List[Dict[str, Any]]] = None
    created_at: datetime

    @field_validator("retrieved_contexts", mode="before")
    @classmethod
    def parse_retrieved_contexts(cls, value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value) if value else None
        return value

    class Config:
        from_attributes = True

class UserSessionsResponse(BaseModel):
    user: str
    sessions: List[str]