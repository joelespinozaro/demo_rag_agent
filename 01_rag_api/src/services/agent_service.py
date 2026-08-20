import time
from typing import Optional
import uuid

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy.orm import Session

from src.services.prompt import INSTRUCTIONS
from src.repositories.history_repository import HistoryRepository
from src.repositories.models.history import History
from src.utils.environment import (
    HISTORY_LIMIT
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

class AgentService:
    def __init__(self, db: Session) -> None:
        self._repo = HistoryRepository(db)

    async def chat(self, question: str, user: str, session_id: Optional[str]) -> dict:
        is_new_session = not session_id
        if is_new_session:
            logger.info("Creando nueva sesión")
            session_id = str(uuid.uuid4())

        trace_id = str(uuid.uuid4())

        logger.info(
            "Iniciando chat",
            extra={"session_id": session_id, "trace_id": trace_id, "user": user},
        )

        t0 = time.perf_counter()
        history_records = [] if is_new_session else self._repo.get_by_session_id(session_id, limit=HISTORY_LIMIT)
        t_history = time.perf_counter() - t0

        history_messages: List[BaseMessage] = []
        for record in history_records:
            history_messages.append(HumanMessage(content=record.question))
            history_messages.append(AIMessage(content=record.answer))

        t0 = time.perf_counter()
        # Generar respuesta dummy
        result = {
            "answer": "Respuesta dummy",
            "input_tokens": 0,
            "output_tokens": 0,
        }
        retrieved_contexts = None
        t_agent = time.perf_counter() - t0

        t0 = time.perf_counter()
        self._repo.save(
            History(
                trace_id=trace_id,
                session_id=session_id,
                question=question,
                answer=result["answer"],
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
                user=user,
                retrieved_contexts=retrieved_contexts,
            )
        )
        t_save = time.perf_counter() - t0

        logger.info(
            "Chat finalizado",
            extra={
                "trace_id": trace_id,
                "session_id": session_id,
                "t_history_ms": round(t_history * 1000, 2),
                "t_agent_ms": round(t_agent * 1000, 2),
                "t_save_ms": round(t_save * 1000, 2),
                "retrieved_contexts_count": len(retrieved_contexts or []),
            },
        )

        return {
            "user": user,
            "answer": result["answer"],
            "session_id": session_id,
            "trace_id": trace_id,
        }

    
