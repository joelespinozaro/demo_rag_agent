from mcp.server.fastmcp import FastMCP

from src.routes.documents import register_document_tools
from src.routes.pokemon import register_pokemon_tools
from src.utils.logger import get_logger

logger = get_logger(__name__)

mcp = FastMCP(
    "DemoMCPServer",
    log_level="ERROR",
    dependencies=["httpx", "python-decouple", "python-json-logger"],
)
register_document_tools(mcp)
register_pokemon_tools(mcp)

if __name__ == "__main__":
    logger.info("Iniciando DemoMCPServer (stdio)")
    mcp.run(transport="stdio")
