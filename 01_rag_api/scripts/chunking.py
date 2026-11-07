"""Mismo chunking que setup/qdrant-db.ipynb, empaquetado para usarlo desde scripts.

Cada chunk es una seccion del markdown (corte por encabezados) enriquecida con
el nombre del documento y sus titulos, para que el embedding sepa de que habla.
"""

from pathlib import Path
from typing import Any

from langchain_text_splitters import MarkdownHeaderTextSplitter

DATA_DIR = Path(__file__).resolve().parent.parent / "setup" / "data"

HEADERS = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
    ("####", "Header 4"),
    ("#####", "Header 5"),
]


def build_enriched_content(content: str, metadata: dict, document_name: str) -> str:
    parts = [f"[Documento: {document_name}]"]
    for i in range(1, 6):
        key = f"Header {i}"
        if key in metadata:
            label = "Titulo" if i == 1 else "Subtitulo"
            parts.append(f"[{label}: {metadata[key]}]")
    return "".join(parts) + " " + content


def load_chunks(data_dir: Path = DATA_DIR) -> list[dict[str, Any]]:
    splitter = MarkdownHeaderTextSplitter(HEADERS)
    chunks: list[dict[str, Any]] = []
    for md_file in sorted(data_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        sections = splitter.split_text(text)
        for i, section in enumerate(sections):
            chunks.append(
                {
                    "chunk_id": f"{md_file.stem}#{i}",
                    "content": build_enriched_content(section.page_content, section.metadata, md_file.stem),
                    "original_content": section.page_content,
                    "metadata": {
                        **section.metadata,
                        "source_file": md_file.name,
                        "document_name": md_file.stem,
                        "chunk_index": i,
                    },
                }
            )
    return chunks


if __name__ == "__main__":
    data = load_chunks()
    print(f"{len(data)} chunks")
    for c in data[:3]:
        print(c["chunk_id"], "->", c["content"][:120])
