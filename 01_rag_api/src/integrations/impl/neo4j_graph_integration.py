from neo4j import GraphDatabase

from src.dto.busqueda_dto import ElementoBusqueda
from src.integrations.graph_integration import GraphIntegration
from src.integrations.graph_schema import verb
from src.utils.environment import (
    GRAPH_MAX_RELATIONS,
    NEO4J_DATABASE,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USERNAME,
)

# Local search de GraphRAG en una sola consulta:
#   1. El indice vectorial encuentra las entidades semilla mas parecidas a la pregunta.
#   2. Cypher recorre un salto desde cada semilla y trae sus vecinos.
LOCAL_SEARCH = """
CALL db.index.vector.queryNodes('entidad_embedding', $k, $vector) YIELD node, score
OPTIONAL MATCH (node)-[r]-(vecino:Entidad)
WITH node, score, r, vecino
ORDER BY score DESC
WITH node, score,
     collect(CASE WHEN r IS NULL THEN NULL ELSE {
        rel: type(r),
        saliente: startNode(r) = node,
        nombre: vecino.nombre,
        tipo: vecino.tipo,
        fuentes: r.fuentes
     } END)[..$max_rel] AS relaciones
RETURN node.key AS key, node.nombre AS nombre, node.tipo AS tipo,
       node.descripcion AS descripcion, node.fuentes AS fuentes, score, relaciones
ORDER BY score DESC
"""


class Neo4jGraphIntegration(GraphIntegration):
    def __init__(self, driver=None):
        self._driver = driver or GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    def search(self, vector: list[float], k: int = 4) -> list[ElementoBusqueda]:
        records, _, _ = self._driver.execute_query(
            LOCAL_SEARCH, k=k, vector=vector, max_rel=GRAPH_MAX_RELATIONS, database_=NEO4J_DATABASE
        )
        return [build_ficha(dict(r)) for r in records]


def build_ficha(rec: dict) -> ElementoBusqueda:
    """Convierte una entidad y su vecindario en un texto que el LLM puede leer y citar."""
    nombre, tipo = rec["nombre"], rec["tipo"]
    lineas = [f"[Grafo: {nombre} ({tipo})] {rec.get('descripcion') or ''}".strip()]
    fuentes: list[str] = list(rec.get("fuentes") or [])
    for rel in rec.get("relaciones") or []:
        vecino = f"{rel['nombre']} ({rel['tipo']})"
        if rel["saliente"]:
            lineas.append(f"- {nombre} {verb(rel['rel'])} {vecino}.")
        else:
            lineas.append(f"- {vecino} {verb(rel['rel'])} {nombre}.")
        for f in rel.get("fuentes") or []:
            if f not in fuentes:
                fuentes.append(f)
    archivos = sorted({f.split("#")[0] + ".md" for f in fuentes})
    return ElementoBusqueda(
        id=f"grafo:{rec['key']}",
        source_file=", ".join(archivos),
        document_name="grafo",
        content="\n".join(lineas),
        score=float(rec["score"]),
    )
