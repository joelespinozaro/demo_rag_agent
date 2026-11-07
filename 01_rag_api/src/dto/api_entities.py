from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

class ChatRequest(BaseModel):
    question: str
    user: str
    session_id: Optional[str] = None

class Fuente(BaseModel):
    id: str              # [C1] chunk del vector DB, [G1] ficha del grafo
    tipo: str            # chunk | grafo
    source_file: str     # archivo de origen: el final de la cadena de citas
    extracto: str

class Grounding(BaseModel):
    oraciones: int
    citadas: int
    ratio: float
    sin_cita: List[str] = []
    cita_invalida: List[str] = []

class ChatResponse(BaseModel):
    user: str
    answer: str
    session_id: UUID
    trace_id: UUID
    sources: List[Fuente] = []
    grounding: Optional[Grounding] = None

class HistoryItem(BaseModel):
    question: str
    answer: str
    trace_id: UUID
    session_id: UUID
    user: Optional[str] = None
    retrieved_contexts: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class UserSessionsResponse(BaseModel):
    user: str
    sessions: List[str]

class LLMResponse(BaseModel):
    answer: str
    input_tokens: int
    output_tokens: int