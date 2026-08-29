import asyncio

import pytest

from src.services.guardrails.layer8_llama_guard import LlamaGuardMiddleware
from tests.guardrails.conftest import build_state


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeGroqClient:
    def __init__(self, verdict: str = "safe", delay: float = 0.0, raise_error: bool = False) -> None:
        self._verdict = verdict
        self._delay = delay
        self._raise_error = raise_error
        self.chat = self
        self.completions = self

    async def create(self, **kwargs):
        if self._raise_error:
            raise ConnectionError("Groq no disponible")
        if self._delay:
            await asyncio.sleep(self._delay)
        return _FakeCompletion(self._verdict)


@pytest.mark.asyncio
async def test_passes_safe_message():
    middleware = LlamaGuardMiddleware(client=_FakeGroqClient(verdict="safe"))
    state = build_state("¿Qué certificaciones ofrece la academia?")

    result = await middleware.abefore_agent(state, runtime=None)

    assert result is None


@pytest.mark.asyncio
async def test_blocks_unsafe_message():
    middleware = LlamaGuardMiddleware(client=_FakeGroqClient(verdict="unsafe\nS1"))
    state = build_state("Cómo cometo un crimen violento contra alguien")

    result = await middleware.abefore_agent(state, runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"


@pytest.mark.asyncio
async def test_skip_categories_lets_message_pass():
    middleware = LlamaGuardMiddleware(client=_FakeGroqClient(verdict="unsafe\nS6"))
    middleware._skip_categories = {"S6"}
    state = build_state("Dame un consejo financiero general")

    result = await middleware.abefore_agent(state, runtime=None)

    assert result is None


@pytest.mark.asyncio
async def test_fail_closes_on_groq_error():
    middleware = LlamaGuardMiddleware(client=_FakeGroqClient(raise_error=True))
    state = build_state("Mensaje normal cualquiera")

    result = await middleware.abefore_agent(state, runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"


@pytest.mark.asyncio
async def test_fail_closes_on_timeout():
    middleware = LlamaGuardMiddleware(client=_FakeGroqClient(verdict="safe", delay=5.0))
    middleware._timeout = 0.1
    state = build_state("Mensaje normal cualquiera")

    result = await middleware.abefore_agent(state, runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"
