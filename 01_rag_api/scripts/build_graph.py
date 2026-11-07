"""Construye el grafo de conocimiento en Neo4j a partir de los mismos documentos del RAG.

Pipeline:
  1. Chunking (el mismo del RAG).
  2. Extraccion de entidades y relaciones con un LLM y salida estructurada.
  3. Validacion contra el esquema y resolucion de entidades (mismo programa, varios nombres).
  4. Carga en Neo4j con MERGE (idempotente) guardando de que chunk salio cada relacion.
  5. Embedding de cada entidad + indice vectorial, para encontrar nodos semilla por significado.

Uso (desde 01_rag_api):
    python -m scripts.build_graph               # extrae con el LLM y carga
    python -m scripts.build_graph --limit 10    # prueba barata con 10 chunks
    python -m scripts.build_graph --from-cache  # recarga sin volver a llamar al LLM
    python -m scripts.build_graph --reset       # borra el grafo antes de cargar
"""

import argparse
import json
from pathlib import Path
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from neo4j import GraphDatabase
from pydantic import BaseModel, Field

from scripts.chunking import load_chunks
from src.integrations.graph_schema import (
    CANONICAL_PROGRAMS,
    ENTITY_TYPES,
    RELATIONS,
    canonical_program,
    entity_key,
    relation_allowed,
)
from src.utils.environment import (
    NEO4J_DATABASE,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USERNAME,
    OPENAI_API_KEY,
    OPENAI_EMBEDDING_MODEL,
    OPENAI_MODEL,
)

# Documentos con entidades. reglamento, faq u horarios casi no tienen relaciones entre entidades.
GRAPH_FILES = {"docentes.md", "graduados.md", "cursos.md", "programas.md", "empresas_aliadas.md", "sedes.md"}
CACHE = Path(__file__).resolve().parent / "out" / "extraccion.json"
INDEX_NAME = "entidad_embedding"

TipoEntidad = Literal["Programa", "Curso", "Docente", "Egresado", "Empresa", "Sede", "Herramienta"]
TipoRelacion = Literal[
    "PERTENECE_A", "ENSENA_EN", "EGRESO_DE", "TRABAJA_EN", "TRABAJO_EN", "DOMINA", "RECLUTA_DE", "SE_ESPECIALIZA_EN"
]


class Entidad(BaseModel):
    nombre: str = Field(description="Nombre propio tal como aparece, sin cargo. Ej: 'Sofia Chen', 'Yape', 'Apache Airflow'")
    tipo: TipoEntidad
    descripcion: str = Field(description="Una frase que describa la entidad segun el texto")


class Relacion(BaseModel):
    origen: str = Field(description="Nombre de la entidad de origen, igual que en la lista de entidades")
    relacion: TipoRelacion
    destino: str = Field(description="Nombre de la entidad de destino, igual que en la lista de entidades")


class Extraccion(BaseModel):
    entidades: list[Entidad]
    relaciones: list[Relacion]


SYSTEM = (
    "Eres un extractor de grafos de conocimiento para un instituto de formacion en datos. "
    "Lee el fragmento y devuelve solo entidades y relaciones explicitas en el texto.\n\n"
    "Tipos de entidad: {tipos}.\n"
    "Relaciones permitidas (origen -> destino):\n{relaciones}\n\n"
    "Reglas:\n"
    "- Los programas son exactamente: {programas}. Usa siempre esos nombres.\n"
    "- En el documento 'docentes', el Titulo de la seccion es el programa donde ensena la persona.\n"
    "- En el documento 'graduados', el Titulo de la seccion es el programa del que egreso la persona.\n"
    "- En el documento 'cursos', el Titulo es el programa al que pertenece cada curso.\n"
    "- TRABAJA_EN es el empleo actual. Si el texto dice 'anteriormente' o 'trabajo en', usa TRABAJO_EN.\n"
    "- Herramienta es una tecnologia concreta (Airflow, Tableau, TOGAF, Kubeflow). No extraigas conceptos genericos.\n"
    "- No inventes. Si una relacion no esta en el texto, no la incluyas."
)


def build_prompt() -> ChatPromptTemplate:
    rel_lines = "\n".join(
        f"- {name}: {'/'.join(sorted(src))} -> {'/'.join(sorted(dst))} ({verbo})" for name, (src, dst, verbo) in RELATIONS.items()
    )
    system = SYSTEM.format(tipos=", ".join(ENTITY_TYPES), relaciones=rel_lines, programas=", ".join(CANONICAL_PROGRAMS))
    # Las llaves del texto ya se resolvieron: se escapan para que LangChain no las lea como variables.
    system = system.replace("{", "{{").replace("}", "}}")
    return ChatPromptTemplate.from_messages([("system", system), ("human", "Fragmento:\n{chunk}")])


def extract(chunks: list[dict]) -> list[dict]:
    llm = ChatOpenAI(api_key=OPENAI_API_KEY, model=OPENAI_MODEL, temperature=0).with_structured_output(Extraccion)
    chain = build_prompt() | llm
    results = chain.batch([{"chunk": c["content"]} for c in chunks], config={"max_concurrency": 8})
    return [
        {"chunk_id": c["chunk_id"], "source_file": c["metadata"]["source_file"], **r.model_dump()}
        for c, r in zip(chunks, results)
    ]


def resolve(extractions: list[dict]) -> tuple[dict[str, dict], list[dict], dict[str, int]]:
    """Valida contra el esquema y fusiona entidades duplicadas. Devuelve nodos, aristas y estadisticas."""
    nodes: dict[str, dict] = {}
    edges: dict[tuple[str, str, str], dict] = {}
    stats = {"entidades_crudas": 0, "relaciones_crudas": 0, "descartadas_esquema": 0, "descartadas_huerfanas": 0}

    for ex in extractions:
        local: dict[str, str] = {}  # nombre en este chunk -> key global
        for ent in ex["entidades"]:
            stats["entidades_crudas"] += 1
            nombre = ent["nombre"].strip()
            if ent["tipo"] == "Programa":
                canon = canonical_program(nombre)
                if canon is None:
                    continue
                nombre = canon
            key = entity_key(ent["tipo"], nombre)
            local[ent["nombre"].strip().lower()] = key
            node = nodes.setdefault(key, {"key": key, "nombre": nombre, "tipo": ent["tipo"], "descripcion": "", "fuentes": []})
            if len(ent["descripcion"]) > len(node["descripcion"]):
                node["descripcion"] = ent["descripcion"]
            if ex["chunk_id"] not in node["fuentes"]:
                node["fuentes"].append(ex["chunk_id"])

        def lookup(name: str) -> str | None:
            key = local.get(name.strip().lower())
            if key is None and canonical_program(name):
                # El LLM nombro el programa distinto en la relacion que en la lista de entidades.
                key = entity_key("Programa", canonical_program(name))
                nodes.setdefault(key, {"key": key, "nombre": canonical_program(name), "tipo": "Programa", "descripcion": "", "fuentes": []})
            return key

        for rel in ex["relaciones"]:
            stats["relaciones_crudas"] += 1
            a = lookup(rel["origen"])
            b = lookup(rel["destino"])
            if not a or not b:
                stats["descartadas_huerfanas"] += 1
                continue
            if not relation_allowed(rel["relacion"], nodes[a]["tipo"], nodes[b]["tipo"]):
                stats["descartadas_esquema"] += 1
                continue
            edge = edges.setdefault((a, rel["relacion"], b), {"a": a, "rel": rel["relacion"], "b": b, "fuentes": []})
            if ex["chunk_id"] not in edge["fuentes"]:
                edge["fuentes"].append(ex["chunk_id"])

    stats["nodos"] = len(nodes)
    stats["aristas"] = len(edges)
    return nodes, list(edges.values()), stats


def load_into_neo4j(nodes: dict[str, dict], edges: list[dict], reset: bool) -> None:
    embedder = OpenAIEmbeddings(api_key=OPENAI_API_KEY, model=OPENAI_EMBEDDING_MODEL)
    rows = list(nodes.values())
    texts = [f"{n['nombre']} ({n['tipo']}): {n['descripcion']}" for n in rows]
    vectors = embedder.embed_documents(texts)
    for row, vec in zip(rows, vectors):
        row["embedding"] = vec
    dim = len(vectors[0])

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    with driver.session(database=NEO4J_DATABASE) as session:
        if reset:
            session.run("MATCH (n:Entidad) DETACH DELETE n")
        session.run("CREATE CONSTRAINT entidad_key IF NOT EXISTS FOR (e:Entidad) REQUIRE e.key IS UNIQUE")

        # Una etiqueta por tipo (:Docente, :Empresa...). Las etiquetas no se pueden pasar como
        # parametro en Cypher, por eso se agrupa por tipo y el tipo sale de una lista cerrada.
        for tipo in ENTITY_TYPES:
            batch = [r for r in rows if r["tipo"] == tipo]
            if not batch:
                continue
            session.run(
                f"""
                UNWIND $rows AS row
                MERGE (e:Entidad {{key: row.key}})
                SET e:{tipo}, e.nombre = row.nombre, e.tipo = row.tipo,
                    e.descripcion = row.descripcion, e.fuentes = row.fuentes, e.embedding = row.embedding
                """,
                rows=batch,
            )

        for rel in RELATIONS:
            batch = [e for e in edges if e["rel"] == rel]
            if not batch:
                continue
            session.run(
                f"""
                UNWIND $rows AS row
                MATCH (a:Entidad {{key: row.a}}), (b:Entidad {{key: row.b}})
                MERGE (a)-[r:{rel}]->(b)
                SET r.fuentes = row.fuentes
                """,
                rows=batch,
            )

        session.run(
            f"""
            CREATE VECTOR INDEX {INDEX_NAME} IF NOT EXISTS
            FOR (e:Entidad) ON (e.embedding)
            OPTIONS {{indexConfig: {{`vector.dimensions`: {dim}, `vector.similarity_function`: 'cosine'}}}}
            """
        )
        session.run("CALL db.awaitIndexes(300)")
    driver.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="procesar solo N chunks (prueba barata)")
    parser.add_argument("--from-cache", action="store_true", help="usar scripts/out/extraccion.json")
    parser.add_argument("--reset", action="store_true", help="borrar el grafo antes de cargar")
    args = parser.parse_args()

    if args.from_cache:
        extractions = json.loads(CACHE.read_text(encoding="utf-8"))
        print(f"[1/3] {len(extractions)} extracciones leidas de {CACHE.name}")
    else:
        chunks = [c for c in load_chunks() if c["metadata"]["source_file"] in GRAPH_FILES]
        if args.limit:
            chunks = chunks[: args.limit]
        print(f"[1/3] Extrayendo entidades de {len(chunks)} chunks con {OPENAI_MODEL}...")
        extractions = extract(chunks)
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(extractions, ensure_ascii=False, indent=2), encoding="utf-8")

    nodes, edges, stats = resolve(extractions)
    print(f"[2/3] Resolucion de entidades: {json.dumps(stats, ensure_ascii=False)}")

    load_into_neo4j(nodes, edges, reset=args.reset)
    print(f"[3/3] Grafo cargado en Neo4j: {len(nodes)} nodos, {len(edges)} relaciones, indice '{INDEX_NAME}' listo")
    print("Pruebalo en Neo4j Browser:  MATCH (e:Empresa {nombre:'Yape'})-[r]-(x) RETURN e, r, x")


if __name__ == "__main__":
    main()
