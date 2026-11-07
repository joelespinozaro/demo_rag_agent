# RAG API · Laboratorio Sesión 2 (Advanced RAG, GraphRAG y evaluación)

API en FastAPI que responde preguntas sobre un instituto de formación en datos (programas, cursos, docentes, egresados, reglamento). La rama `rag_agent_v1` trae el laboratorio completo:

| Capa | Qué agrega | Dónde vive |
|---|---|---|
| Base | Embeddings, Qdrant, LLM e historial en PostgreSQL | `src/` |
| Query expansion y reranking | 1 pregunta se convierte en 4 búsquedas y un LLM reordena | `src/integrations/impl/openai_*` |
| Lab 1 · Búsqueda híbrida | Vector denso + BM25 fusionados con RRF en Qdrant | `scripts/build_hybrid_index.py`, `qdrant_hybrid_integration.py` |
| Lab 2 · GraphRAG | Grafo de entidades en Neo4j y respuestas con citas `[C#]` y `[G#]` | `scripts/build_graph.py`, `neo4j_graph_integration.py`, `src/services/grounding.py` |
| Lab 3 · Evaluación | RAGAS sobre un golden dataset de 12 preguntas, y DeepEval como tests | `eval/` |

Las ramas `rag_agents_hybrid`, `rag_agents_graphrag` y `rag_agents_eval` muestran cada capa por separado. Ejemplo: `git diff origin/rag_agents_reranking origin/rag_agents_hybrid`.

## Servicios que necesitas

| Servicio | Para qué | Plan |
|---|---|---|
| OpenAI | `gpt-4o-mini` (respuestas, extracción, juez) y `text-embedding-3-small` | De pago, cuesta centavos |
| Qdrant Cloud | Base vectorial: colección `data-academy` (densa) y `data-academy-hybrid` (Lab 1) | Free |
| PostgreSQL (Neon) | Tabla `history` con las conversaciones | Free |
| Neo4j AuraDB Free | Base de grafos para el Lab 2 | Free, sin tarjeta |

## Instalación

```bash
git clone https://github.com/joelespinozaro/demo_rag_agent.git
cd demo_rag_agent/01_rag_api
git checkout rag_agent_v1
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env              # Windows: copy .env.example .env
```

Completa `.env`. Si nunca cargaste la colección `data-academy`, abre `setup/qdrant-db.ipynb` desde la carpeta `setup/` (usa su propio `setup/.env`) y córrelo completo y si tu base no tiene la tabla `history`, ejecuta `setup/database.sql`.

## Comandos por laboratorio

```bash
# Lab 1 · búsqueda híbrida
python -m scripts.build_hybrid_index
python -m scripts.compare_search "¿Qué docente es experto en TOGAF?"
python -m src.main                       # API en http://localhost:8080/api/chat

# Lab 2 · GraphRAG (pon GRAPH_ENABLED=true y tus credenciales de Aura en .env)
python -m scripts.check_neo4j
python -m scripts.build_graph --limit 10
python -m scripts.build_graph --reset
python -m scripts.ask_graph "¿Qué docentes y egresados trabajan en Yape?"

# Lab 3 · evaluación (con el API corriendo en otra terminal)
python -m eval.run_eval --label baseline
python -m eval.run_eval --label hybrid_graph --min-faithfulness 0.7
pip install -r eval/requirements-deepeval.txt
pytest eval/test_rag_deepeval.py -v
```

## Problemas comunes

- `ServiceUnavailable` con Neo4j: la instancia Free se pausa tras 3 días sin uso. Reanúdala en console.neo4j.io. Si sigue pausada 30 días, Aura la borra.
- Aviso `db.index.vector.queryNodes is deprecated`: es solo un aviso de Neo4j, la consulta funciona.
- `NEO4J_DATABASE`: déjalo vacío salvo que tu archivo de credenciales traiga otro valor.
- La evaluación tarda: es el LLM juez. Para probar, usa `--dataset` con un JSON de 3 o 4 preguntas.
