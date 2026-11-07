"""El mismo RAG evaluado con DeepEval, en formato de pruebas unitarias (pytest).

RAGAS sirve para medir y comparar configuraciones. DeepEval sirve para que una
regresion de calidad rompa el build, igual que un test que falla.

Instalacion (opcional, aparte de requirements.txt):
    pip install -r eval/requirements-deepeval.txt

Uso (desde 01_rag_api, con el API corriendo):
    deepeval test run eval/test_rag_deepeval.py
    # o simplemente:  pytest eval/test_rag_deepeval.py -v
"""

import json
import os
from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from eval.run_eval import collect

API = os.getenv("EVAL_API", "http://localhost:8080")
EVAL_MODEL = os.getenv("EVAL_MODEL", "gpt-4o-mini")
GOLDEN = json.loads((Path(__file__).parent / "golden_dataset.json").read_text(encoding="utf-8"))
# Un caso por tipo de pregunta para que la suite corra rapido en CI.
CASES = list({item["tipo"]: item for item in GOLDEN}.values())


def build_metrics(model=EVAL_MODEL):
    return [
        FaithfulnessMetric(threshold=0.7, model=model),
        AnswerRelevancyMetric(threshold=0.7, model=model),
        # Metrica propia escrita en lenguaje natural: el criterio de negocio que RAGAS no trae.
        GEval(
            name="Responde como la referencia",
            criteria=(
                "Evalua si la respuesta real contiene los mismos hechos clave que la respuesta esperada "
                "(nombres, cifras, empresas, programas) sin contradecirla. Si la esperada dice que no hay "
                "informacion, la real debe reconocerlo en vez de inventar."
            ),
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.EXPECTED_OUTPUT],
            threshold=0.6,
            model=model,
        ),
    ]


@pytest.fixture(scope="module")
def rows():
    return {r["id"]: r for r in collect(API, CASES)}


@pytest.mark.parametrize("case_id", [c["id"] for c in CASES])
def test_rag_quality(rows, case_id):
    row = rows[case_id]
    test_case = LLMTestCase(
        input=row["user_input"],
        actual_output=row["response"],
        expected_output=row["reference"],
        retrieval_context=row["retrieved_contexts"],
    )
    assert_test(test_case, build_metrics())
