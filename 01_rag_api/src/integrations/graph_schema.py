"""Esquema del grafo de conocimiento: que entidades y que relaciones existen.

Un esquema cerrado es la diferencia entre un grafo util y una sopa de nodos.
El LLM solo puede extraer estos tipos, y cada relacion solo puede unir los
tipos que tienen sentido (un Curso no "trabaja en" una Empresa).
"""

import re
import unicodedata

ENTITY_TYPES = ["Programa", "Curso", "Docente", "Egresado", "Empresa", "Sede", "Herramienta"]

# relacion -> (tipos de origen permitidos, tipos de destino permitidos, verbo legible)
RELATIONS: dict[str, tuple[set[str], set[str], str]] = {
    "PERTENECE_A": ({"Curso"}, {"Programa"}, "pertenece al programa"),
    "ENSENA_EN": ({"Docente"}, {"Programa"}, "enseña en el programa"),
    "EGRESO_DE": ({"Egresado"}, {"Programa"}, "egresó del programa"),
    "TRABAJA_EN": ({"Docente", "Egresado"}, {"Empresa"}, "trabaja actualmente en"),
    "TRABAJO_EN": ({"Docente", "Egresado"}, {"Empresa"}, "trabajó antes en"),
    "DOMINA": ({"Docente"}, {"Herramienta"}, "domina"),
    "RECLUTA_DE": ({"Empresa"}, {"Programa"}, "recluta egresados del programa"),
    "SE_ESPECIALIZA_EN": ({"Sede"}, {"Programa"}, "se especializa en el programa"),
}

# Los programas son una lista cerrada. El texto los nombra de varias formas
# ("Data Engineering", "Data Engineer", "programa de DE"): todas apuntan al mismo nodo.
CANONICAL_PROGRAMS = ["Data Engineer", "Data Architect", "ML Engineer", "Data Visualization", "Marketing Analytics"]

_TITLES = re.compile(r"^(dr|dra|ing|lic|mg|msc|phd)\.?\s+", re.IGNORECASE)


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = _TITLES.sub("", text)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def canonical_program(name: str) -> str | None:
    s = slug(name)
    if "marketing" in s:
        return "Marketing Analytics"
    if "visual" in s:
        return "Data Visualization"
    if "architect" in s or "arquitect" in s:
        return "Data Architect"
    if s.startswith("ml") or "machine-learning" in s:
        return "ML Engineer"
    if "data-engineer" in s or "ingenieria-de-datos" in s:
        return "Data Engineer"
    return None


_COMPANY_SUFFIXES = {"peru", "sa", "sac", "saa", "corp", "inc", "latam"}


def entity_key(tipo: str, nombre: str) -> str:
    """Clave unica del nodo. Incluye el tipo a proposito: el docente Carlos Mendoza
    y el egresado Carlos Mendoza son dos personas distintas y no deben fusionarse."""
    if tipo == "Programa":
        nombre = canonical_program(nombre) or nombre
    key = slug(nombre)
    if tipo == "Empresa":
        # "Rappi Peru" y "Rappi" son la misma empresa.
        parts = key.split("-")
        while len(parts) > 1 and parts[-1] in _COMPANY_SUFFIXES:
            parts.pop()
        key = "-".join(parts)
    return f"{tipo.lower()}:{key}"


def relation_allowed(rel: str, src_type: str, dst_type: str) -> bool:
    spec = RELATIONS.get(rel)
    return bool(spec) and src_type in spec[0] and dst_type in spec[1]


def verb(rel: str) -> str:
    return RELATIONS.get(rel, (set(), set(), rel.lower()))[2]
