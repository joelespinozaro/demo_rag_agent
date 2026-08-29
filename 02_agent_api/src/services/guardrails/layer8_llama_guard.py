"""Capa 8 — Llama Guard 4 (clasificador semántico profundo).

Análisis semántico completo del mensaje contra la taxonomía de seguridad
MLCommons (S1-S13) antes de considerarlo apto para el agente. Modelo
`meta-llama/Llama-Guard-4-12B` servido vía Groq API.

`skip_categories` configurable vía config/guardrails/llama_guard_categories.yaml
para omitir un filtro específico según el caso de uso comercial sin tocar
código. Mismo fail-close que la Capa 7: cualquier error/timeout de Groq
bloquea el mensaje.
"""
import asyncio
from typing import Any, Dict, Optional, Set

from groq import AsyncGroq
from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime

from src.services.guardrails.common import block_result, get_latest_human_text, load_yaml_config, log_block
from src.utils.environment import GROQ_API_KEY, GROQ_LLAMA_GUARD_MODEL, GROQ_TIMEOUT_SECONDS
from src.utils.logger import get_logger

logger = get_logger(__name__)

LAYER_NAME = "layer8_llama_guard"

BLOCK_MESSAGE = (
    "Lo sentimos, no podemos ayudarte con esa solicitud. ¿Hay algo más en lo "
    "que pueda asistirte?"
)

SAFE_LABEL = "safe"
UNSAFE_LABEL = "unsafe"


class LlamaGuardMiddleware(AgentMiddleware):
    """Guardrail semántico profundo (Groq Llama Guard 4) con fail-close."""

    def __init__(self, client: Optional[AsyncGroq] = None) -> None:
        super().__init__()
        self._client = client or AsyncGroq(api_key=GROQ_API_KEY)
        self._model = GROQ_LLAMA_GUARD_MODEL
        self._timeout = GROQ_TIMEOUT_SECONDS

        config = load_yaml_config("llama_guard_categories.yaml")
        self._skip_categories: Set[str] = set(config.get("skip_categories") or [])

    async def _classify(self, text: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": text}],
            temperature=0.0,
        )
        return (response.choices[0].message.content or "").strip()

    def _is_blocked(self, verdict: str) -> Optional[str]:
        """Retorna la categoría bloqueante, o None si el mensaje pasa."""
        lines = [line.strip() for line in verdict.splitlines() if line.strip()]
        if not lines or lines[0].lower() != UNSAFE_LABEL:
            return None

        category = lines[1] if len(lines) > 1 else None
        if category and category in self._skip_categories:
            return None
        return category or "unknown_category"

    @hook_config(can_jump_to=["end"])
    async def abefore_agent(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        text = get_latest_human_text(state)
        if not text:
            return None

        try:
            verdict = await asyncio.wait_for(self._classify(text), timeout=self._timeout)
        except Exception as exc:  # noqa: BLE001 - fail-close ante timeout o cualquier error de Groq
            logger.warning(
                "Capa 8: error/timeout consultando Groq (%s). Aplicando fail-close.", exc,
                extra={"guardrail_layer": LAYER_NAME},
            )
            log_block(logger, LAYER_NAME, text, reason="groq_unavailable_fail_close")
            return block_result(BLOCK_MESSAGE)

        blocked_category = self._is_blocked(verdict)
        if blocked_category:
            log_block(logger, LAYER_NAME, text, reason=f"unsafe_category:{blocked_category}")
            return block_result(BLOCK_MESSAGE)

        return None
