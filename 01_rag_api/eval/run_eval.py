"""Pipeline de evaluacion automatizada del RAG con RAGAS.

Le hace al API las preguntas del dataset dorado, recupera lo que el sistema
leyo (retrieved_contexts del historial) y mide cuatro metricas:

  Generacion  faithfulness          ¿la respuesta esta sustentada por el contexto?
              answer_relevancy      ¿la respuesta atiende la pregunta?
  Retrieval   context_precision     ¿los chunks utiles quedaron arriba?
              context_recall        ¿el contexto trae todo lo que pide la referencia?

Uso (desde 01_rag_api, con el API corriendo en otra terminal):
    python -m eval.run_eval --label baseline
    python -m eval.run_eval --label hibrido_grafo --min-faithfulness 0.8

Cada corrida deja el detalle en eval/results/<label>_detalle.csv y agrega una
fila a eval/results/resumen.csv para comparar configuraciones.
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import EvaluationDataset, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    Faithfulness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
    ResponseRelevancy,
)

from src.utils.environment import OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
CITES = re.compile(r"\s*\[[CG]\d+\]")
INPUT_COLUMNS = {"user_input", "retrieved_contexts", "response", "reference"}


def parse_contexts(raw: str | None) -> list[str]:
    """retrieved_contexts se guarda como JSON (rama graphrag) o como lista con guiones (ramas previas)."""
    if not raw:
        return []
    try:
        return [c["content"] for c in json.loads(raw)]
    except (json.JSONDecodeError, TypeError, KeyError):
        return [p.strip().removeprefix("- ") for p in raw.split("\n- ") if p.strip()]


def collect(api: str, dataset: list[dict], transport: httpx.BaseTransport | None = None) -> list[dict]:
    """Paso 1: preguntarle al sistema real, como lo haria un usuario."""
    rows = []
    with httpx.Client(base_url=api, timeout=120, transport=transport) as client:
        for item in dataset:
            t0 = time.perf_counter()
            resp = client.post("/api/chat", json={"question": item["question"], "user": "eval"})
            resp.raise_for_status()
            chat = resp.json()
            latency = time.perf_counter() - t0
            resp = client.get(f"/api/history/{chat['session_id']}")
            resp.raise_for_status()
            history = resp.json()
            contexts = parse_contexts(history[-1].get("retrieved_contexts")) if history else []
            grounding = chat.get("grounding") or {}
            rows.append(
                {
                    "id": item["id"],
                    "tipo": item["tipo"],
                    "user_input": item["question"],
                    "response": CITES.sub("", chat["answer"]),
                    "retrieved_contexts": contexts,
                    "reference": item["reference"],
                    "latencia_s": round(latency, 2),
                    "grounding_ratio": grounding.get("ratio"),
                    "trace_id": chat["trace_id"],
                }
            )
            print(f"  {item['id']:<3} {latency:5.1f}s  {len(contexts)} contextos  {item['question'][:60]}")
    return rows


def score(rows: list[dict], eval_model: str, llm=None, embeddings=None) -> pd.DataFrame:
    """Paso 2: un LLM juez puntua cada fila. Temperatura 0 para que sea repetible."""
    llm = llm or LangchainLLMWrapper(ChatOpenAI(api_key=OPENAI_API_KEY, model=eval_model, temperature=0))
    embeddings = embeddings or LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(api_key=OPENAI_API_KEY, model=OPENAI_EMBEDDING_MODEL)
    )
    dataset = EvaluationDataset.from_list([{k: r[k] for k in INPUT_COLUMNS} for r in rows])
    result = evaluate(
        dataset,
        metrics=[Faithfulness(), ResponseRelevancy(), LLMContextPrecisionWithReference(), LLMContextRecall()],
        llm=llm,
        embeddings=embeddings,
        show_progress=True,
    )
    scores = result.to_pandas().rename(columns={"llm_context_precision_with_reference": "context_precision"})
    metric_cols = [c for c in scores.columns if c not in INPUT_COLUMNS]
    extra = pd.DataFrame(rows)[["id", "tipo", "latencia_s", "grounding_ratio", "trace_id"]]
    return pd.concat([extra, scores[["user_input"] + metric_cols]], axis=1)


def report(df: pd.DataFrame, label: str) -> dict:
    """Paso 3: resumir, guardar y comparar."""
    metric_cols = [c for c in df.columns if df[c].dtype.kind == "f" and c not in {"latencia_s", "grounding_ratio"}]
    RESULTS.mkdir(exist_ok=True)
    df.to_csv(RESULTS / f"{label}_detalle.csv", index=False)

    print(f"\nPromedio por tipo de pregunta ({label}):")
    print(df.groupby("tipo")[metric_cols].mean().round(2).to_string())

    summary = {"label": label, "fecha": datetime.now().isoformat(timespec="seconds"), "preguntas": len(df)}
    summary.update({m: round(float(df[m].mean()), 3) for m in metric_cols})
    summary["latencia_s"] = round(float(df["latencia_s"].mean()), 2)
    resumen_path = RESULTS / "resumen.csv"
    resumen = pd.read_csv(resumen_path) if resumen_path.exists() else pd.DataFrame()
    resumen = pd.concat([resumen, pd.DataFrame([summary])], ignore_index=True)
    resumen.to_csv(resumen_path, index=False)

    print("\nComparativa de corridas (eval/results/resumen.csv):")
    print(resumen.drop(columns=["fecha"]).to_string(index=False))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, help="nombre de la configuracion evaluada, ej. baseline")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--dataset", default=str(HERE / "golden_dataset.json"))
    parser.add_argument("--eval-model", default="gpt-4o-mini")
    parser.add_argument("--min-faithfulness", type=float, default=None, help="compuerta de calidad para CI")
    args = parser.parse_args()

    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    print(f"[1/3] Preguntando al API ({len(dataset)} preguntas)...")
    rows = collect(args.api, dataset)
    print("[2/3] Evaluando con RAGAS...")
    df = score(rows, args.eval_model)
    print("[3/3] Resultados")
    summary = report(df, args.label)

    if args.min_faithfulness is not None and summary.get("faithfulness", 0) < args.min_faithfulness:
        print(f"\nCOMPUERTA FALLIDA: faithfulness {summary.get('faithfulness')} < {args.min_faithfulness}")
        sys.exit(1)


if __name__ == "__main__":
    main()
