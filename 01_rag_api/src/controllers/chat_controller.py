from typing import List, Optional
from sqlalchemy.orm import Session
from src.repositories.models.history import History
from src.services.agent_service import AgentService
from src.services.history_service import HistoryService
from src.integrations.impl.openai_embedding_integration import OpenAIEmbeddingIntegration
from src.integrations.impl.qdrant_integration import QdrantIntegration
from src.integrations.impl.openai_llm_integration import OpenAILlmIntegration
from src.integrations.impl.openai_query_expansion_integration import OpenAIQueryExpansionIntegration

async def handle_chat(
    question: str,
    user: str,
    session_id: Optional[str],
    db: Session,
) -> dict:
    embedding = OpenAIEmbeddingIntegration()
    dbVectorial = QdrantIntegration()
    llm = OpenAILlmIntegration()
    query_expansion = OpenAIQueryExpansionIntegration()

    service = AgentService(
        embedding=embedding,
        dbVectorial=dbVectorial,
        llm_integration=llm,
        query_expansion=query_expansion,
        db=db,
    )
    return await service.chat(question=question, user=user, session_id=session_id)

def get_history(session_id: str, db: Session) -> List[History]:
    service = HistoryService(db)
    return service.get_by_session(session_id)

def get_sessions(user: str, db: Session) -> List[str]:
    service = HistoryService(db)
    return service.get_sessions_by_user(user)
