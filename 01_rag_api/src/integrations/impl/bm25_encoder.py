"""Codificador BM25 para vectores dispersos (sparse) en Qdrant.

BM25 puntua un documento con dos ingredientes:
  1. Cuantas veces aparece cada termino de la pregunta en el documento (TF),
     con saturacion: la quinta aparicion suma mucho menos que la primera.
  2. Que tan raro es ese termino en toda la coleccion (IDF).

Aqui calculamos solo la parte de TF. La parte de IDF la calcula Qdrant del
lado del servidor porque la coleccion se crea con `modifier=IDF`. Asi el IDF
siempre refleja los documentos que realmente estan indexados.

Cada palabra se convierte en un indice numerico con un hash estable. No hace
falta vocabulario ni descargar modelos.
"""

import hashlib
import re
import unicodedata
from collections import Counter

K1 = 1.2  # saturacion de la frecuencia del termino
B = 0.75  # cuanto penaliza la longitud del documento

STOPWORDS = {
    "a", "al", "algo", "como", "con", "cual", "cuales", "cuando", "de", "del",
    "desde", "donde", "el", "ella", "en", "entre", "es", "esa", "ese", "esta",
    "este", "esto", "fue", "ha", "hay", "la", "las", "le", "les", "lo", "los",
    "mas", "me", "mi", "muy", "no", "nos", "o", "para", "pero", "por", "que",
    "quien", "se", "si", "sin", "sobre", "son", "su", "sus", "te", "tiene",
    "un", "una", "uno", "unos", "unas", "y", "ya", "yo", "documento", "titulo",
    "subtitulo",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _stem(token: str) -> str:
    """Stemming minimo: plural a singular (docentes -> docente). No toca codigos."""
    if len(token) > 4 and token.endswith("s") and token.isalpha():
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    """Minusculas, sin tildes, sin stopwords, singular. Conserva codigos como d3.js o sl-90."""
    tokens = _TOKEN_RE.findall(_normalize(text))
    return [_stem(t) for t in tokens if t not in STOPWORDS and len(t) > 1]


def token_index(token: str) -> int:
    """Hash estable (no depende de la ejecucion) en el rango de 31 bits."""
    digest = hashlib.md5(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "little") & 0x7FFFFFFF


def encode_document(text: str, avg_doc_len: float) -> tuple[list[int], list[float]]:
    """Pesos BM25 de TF para un documento. Devuelve (indices, valores)."""
    tokens = tokenize(text)
    if not tokens:
        return [], []
    doc_len = len(tokens)
    counts = Counter(tokens)
    weights: dict[int, float] = {}
    for token, tf in counts.items():
        norm = K1 * (1 - B + B * doc_len / max(avg_doc_len, 1.0))
        idx = token_index(token)
        weights[idx] = weights.get(idx, 0.0) + tf * (K1 + 1) / (tf + norm)
    return list(weights.keys()), list(weights.values())


def encode_query(text: str) -> tuple[list[int], list[float]]:
    """La pregunta solo marca que terminos busca: peso 1 por termino unico."""
    indices = sorted({token_index(t) for t in tokenize(text)})
    return indices, [1.0] * len(indices)
