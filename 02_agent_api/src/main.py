import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes.chat import chat_router
from src.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: conectar al MCP de Neon y reinicializar el agente con todas las tools."""
    from src.services.tools import load_neon_tools, get_all_tools
    from src.services.agent_service import init_agent

    mcp_tools = []
    try:
        mcp_tools, _ = await load_neon_tools()
        if mcp_tools:
            logger.info("Neon MCP conectado — %d tool(s) disponibles", len(mcp_tools))
    except Exception as exc:
        logger.warning("Error conectando a Neon MCP: %s. Continuando sin tools MCP.", exc)

    all_tools = get_all_tools(mcp_tools or None)
    init_agent(all_tools)
    logger.info("Registro de tools listo: %s", [t.name for t in all_tools])

    yield


app = FastAPI(
    title="Agente Simple",
    description="Asistente simple",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)

if __name__ == "__main__":
    logger.info("Iniciando servidor en puerto 8080")
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=False)