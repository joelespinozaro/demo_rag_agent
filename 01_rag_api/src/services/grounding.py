"""Grounding y cadena de citas.

1. Cada contexto que entra al prompt recibe un identificador corto: [C1], [C2]... para
   chunks del vector DB y [G1], [G2]... para fichas del grafo.
2. El prompt obliga al modelo a cerrar cada oracion con las citas que la sustentan.
3. Despues de generar, un validador revisa oracion por oracion. Una oracion sin cita,
   o con una cita que no existe, queda marcada como sospechosa.

Asi la cadena queda completa: oracion -> [C2] -> chunk -> archivo de origen.
"""

import re

from src.dto.busqueda_dto import ElementoBusqueda

_CITE = re.compile(r"\[([CG]\d+)\]")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def build_context(contexts: list[ElementoBusqueda]) -> tuple[str, list[dict]]:
    lines: list[str] = []
    sources: list[dict] = []
    c = g = 0
    for ctx in contexts:
        if ctx.document_name == "grafo":
            g += 1
            cid = f"G{g}"
        else:
            c += 1
            cid = f"C{c}"
        lines.append(f"[{cid}] (fuente: {ctx.source_file})\n{ctx.content}")
        sources.append({"id": cid, "tipo": "grafo" if cid.startswith("G") else "chunk",
                        "source_file": ctx.source_file, "content": ctx.content})
    return "\n\n".join(lines), sources


def check_citations(answer: str, valid_ids: set[str]) -> dict:
    sentences = [s.strip() for s in _SENTENCE.split(answer) if len(s.strip()) > 12]
    sin_cita, cita_invalida = [], []
    for s in sentences:
        ids = _CITE.findall(s)
        if not ids:
            sin_cita.append(s)
        elif any(i not in valid_ids for i in ids):
            cita_invalida.append(s)
    total = len(sentences)
    ok = total - len(sin_cita) - len(cita_invalida)
    return {
        "oraciones": total,
        "citadas": ok,
        "ratio": round(ok / total, 2) if total else 1.0,
        "sin_cita": sin_cita,
        "cita_invalida": cita_invalida,
    }
