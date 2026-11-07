"""Verifica la conexion con Neo4j (Aura Free) antes de construir el grafo.

Uso (desde 01_rag_api):
    python -m scripts.check_neo4j
"""

import sys

from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable

from src.utils.environment import NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USERNAME


def main() -> None:
    if not NEO4J_URI or not NEO4J_PASSWORD:
        sys.exit("Falta NEO4J_URI o NEO4J_PASSWORD en tu .env. Copialos del archivo de credenciales de Aura.")
    if not NEO4J_URI.startswith("neo4j+s://"):
        print(f"Aviso: Aura usa URIs que empiezan con neo4j+s://. La tuya es {NEO4J_URI}")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
        info = driver.get_server_info()
        print(f"[1/2] Conexion OK con {info.agent} en {NEO4J_URI}")
        records, _, _ = driver.execute_query(
            "SHOW VECTOR INDEXES YIELD name, state RETURN name, state", database_=NEO4J_DATABASE
        )
        if records:
            for r in records:
                print(f"[2/2] Indice vectorial '{r['name']}': {r['state']}")
        else:
            print("[2/2] Aun no hay indices vectoriales. Es normal antes de correr scripts.build_graph.")
    except AuthError:
        sys.exit("Usuario o contrasena incorrectos. Revisa NEO4J_USERNAME y NEO4J_PASSWORD.")
    except ServiceUnavailable:
        sys.exit(
            "No se pudo conectar. Revisa que la instancia este en estado Running en console.neo4j.io "
            "(las instancias Free se pausan tras 3 dias sin uso) y que la URI sea correcta."
        )
    finally:
        driver.close()


if __name__ == "__main__":
    main()
