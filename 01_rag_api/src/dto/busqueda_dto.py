from pydantic import BaseModel


class ElementoBusqueda(BaseModel):
    id: str
    source_file: str
    document_name: str
    content: str
    score: float

class BusquedaRequest(BaseModel):
    input: str
    limit: int = 5


class BusquedaResponse(BaseModel):
    input: str
    results: list[ElementoBusqueda]
    