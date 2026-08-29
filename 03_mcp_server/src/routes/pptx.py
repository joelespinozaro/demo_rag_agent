from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult
from pydantic import Field

from src.controllers import pptx_controller
from src.dto.pptx import SlideInput


def register_pptx_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="generate_pptx",
        description=(
            "Genera un archivo .pptx (PowerPoint) descargable a partir de un título y "
            "una lista de slides ya decididas (cada una con su propio título y "
            "viñetas/bullets), y lo entrega como adjunto en la interfaz del chat. "
            "Antes de llamarla, cargá la skill 'generar_presentaciones' (vía "
            "load_skill) para saber de dónde sacar el contenido y cómo estructurar "
            "las slides."
        ),
    )
    async def generate_pptx(
        title: str = Field(description="Título de la presentación"),
        slides: list[SlideInput] = Field(
            description="Lista de slides; cada una con 'title' (string) y 'bullets' (lista de viñetas en string)"
        ),
    ) -> CallToolResult:
        return await pptx_controller.handle_generate_pptx(title, slides)
