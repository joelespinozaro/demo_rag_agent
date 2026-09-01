# Despliegue en GCP — 03_mcp_server + 02_agent_api + 01_agent-app + API Gateway + Model Armor

Guía paso a paso para desplegar los 3 componentes de este proyecto que sirven al usuario final, con el frontend hablando **solo** con un API Gateway de GCP (nunca directo a la API), `02_agent_api` hablando con `03_mcp_server` por HTTP autenticado con IAM (nunca como subproceso local), y GCP Model Armor como motor de content-safety.

```
                    ┌─────────────────────┐
  Usuario ────────► │  01_agent-app        │  (Next.js, Cloud Run)
                    │  (Firebase Auth)     │
                    └──────────┬───────────┘
                               │ HTTPS + Bearer <Firebase ID token>
                               ▼
                    ┌─────────────────────┐
                    │  GCP API Gateway     │  valida el JWT de Firebase
                    │  (openapi_gateway.yml)│ ANTES de reenviar la petición
                    └──────────┬───────────┘
                               │ solo el Gateway puede invocar
                               │ (Cloud Run --no-allow-unauthenticated)
                               ▼
                    ┌─────────────────────┐      ┌─────────────────────┐
                    │  02_agent_api         │◄────►│  GCP Model Armor    │
                    │  (FastAPI, Cloud Run) │      │  (sanitize_*)       │
                    └──────────┬───────────┘      └─────────────────────┘
                               │ HTTPS + Bearer <ID token de Google>
                               │ (misma SA, roles/run.invoker sobre este servicio)
                               ▼
                    ┌─────────────────────┐
                    │  03_mcp_server        │  (FastMCP streamable-http,
                    │  (Cloud Run, privado) │   Cloud Run --no-allow-unauthenticated)
                    └─────────────────────┘
```

**Por qué `02_agent_api` y `03_mcp_server` son dos Cloud Run separados, no uno bundleado**: `03_mcp_server` corre por transporte **streamable-http** (`mcp.run(transport="streamable-http")`, ver `03_mcp_server/src/main.py`) — un servicio HTTP normal. `02_agent_api` se conecta como cliente (`src/services/tools.py::load_demo_mcp_tools()`, vía `langchain_mcp_adapters.MultiServerMCPClient` con `transport: "streamable_http"`), autenticándose con un **ID token de Google** obtenido dinámicamente (`src/utils/gcp_auth.py::GoogleIDTokenAuth`, refrescado antes de expirar — un ID token dura ~1h y la conexión puede vivir más que eso). Como ambos servicios están en el mismo proyecto GCP, alcanza con IAM: la Service Account compartida (`$SERVICE_SA`) necesita `roles/run.invoker` sobre el Cloud Run de `03_mcp_server` — mismo patrón que ya usa Gateway→agent-api, un nivel más adentro.

**Orden de esta guía**: primero se habilita/crea TODO lo que no depende de que un Cloud Run ya exista (APIs, la Service Account única y sus permisos, el template de Model Armor). Después, `03_mcp_server` se despliega **antes** que `02_agent_api`, porque este último necesita su URL (`DEMO_MCP_SERVER_URL`) en el `.env` antes de desplegarse. La única excepción inevitable en el otorgamiento de permisos: `roles/run.invoker` sobre un Cloud Run específico solo puede otorgarse **después** de que ese Cloud Run exista (IAM no permite un rol sobre un recurso que no existe) — por eso aparece al final de las Fases 2 y 3, no antes.

---

## 0. Variables (definir una sola vez, reusadas en todas las fases)

**Bash:**
```bash
export PROJECT_ID="tu-proyecto-gcp"
export REGION="us-central1"
export AR_REPOSITORY="repo"

# Service Account única — identidad de runtime de 02_agent_api (llama a Model
# Armor y a 03_mcp_server) Y también la que usa el Gateway para invocar
# 02_agent_api (ver Fase 1.2)
export SERVICE_SA_NAME="agent-b-runtime"
export SERVICE_SA="${SERVICE_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Model Armor
export MODEL_ARMOR_TEMPLATE_ID="agent-api-template"

# 03_mcp_server (Cloud Run)
export MCP_SERVER_SERVICE="03-mcp-server-service"

# 02_agent_api (Cloud Run)
export AGENT_API_SERVICE="02-agent-api-service"

# API Gateway
export GATEWAY_API_ID="agent-api-gw"
export GATEWAY_CONFIG_ID="agent-api-gw-config-v1"
export GATEWAY_ID="agent-api-gateway"

# Firebase (mismo proyecto que PROJECT_ID en el caso típico)
export FIREBASE_PROJECT_ID="${PROJECT_ID}"

# 01_agent-app (Cloud Run)
export AGENT_APP_SERVICE="01-agent-app-service"
```

**PowerShell:**
```powershell
$PROJECT_ID = "tu-proyecto-gcp"
$REGION = "us-central1"
$AR_REPOSITORY = "repo"
$SERVICE_SA_NAME = "agent-b-runtime"
$SERVICE_SA = "$SERVICE_SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
$MODEL_ARMOR_TEMPLATE_ID = "agent-api-template"
$MCP_SERVER_SERVICE = "03-mcp-server-service"
$AGENT_API_SERVICE = "02-agent-api-service"
$GATEWAY_API_ID = "agent-api-gw"
$GATEWAY_CONFIG_ID = "agent-api-gw-config-v1"
$GATEWAY_ID = "agent-api-gateway"
$FIREBASE_PROJECT_ID = $PROJECT_ID
$AGENT_APP_SERVICE = "01-agent-app-service"
```

---

## Fase 1 — Habilitar APIs, crear la Service Account y el template de Model Armor

Todo lo de esta fase es independiente de que exista ningún Cloud Run — se hace una sola vez, de entrada.

### 1.1. Habilitar APIs y autenticar Docker

```bash
gcloud config set project "$PROJECT_ID"

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  apigateway.googleapis.com \
  servicemanagement.googleapis.com \
  servicecontrol.googleapis.com \
  modelarmor.googleapis.com \
  iam.googleapis.com

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
```

### 1.2. Crear la Service Account única y darle los permisos que ya se pueden otorgar

Esta SA cumple tres roles: identidad de runtime de `02_agent_api` (para llamar a Model Armor y para autenticarse contra `03_mcp_server`), y la identidad que usa el **Gateway** para invocar `02_agent_api`. Todo lo que no depende de que un Cloud Run exista se le da acá:

```bash
gcloud iam service-accounts create "$SERVICE_SA_NAME" \
  --display-name="Runtime de 02_agent_api + backend-auth del Gateway"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SERVICE_SA}" \
  --role="roles/modelarmor.user"
```

> `roles/run.invoker` (sobre `03_mcp_server` y sobre `02_agent_api`) se agrega en las Fases 2.3 y 3.3, apenas cada servicio exista — no se puede otorgar antes.

### 1.3. Crear el template de Model Armor

```bash
gcloud model-armor templates create "$MODEL_ARMOR_TEMPLATE_ID" \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --rai-settings-filters='[
    {"filterType": "HATE_SPEECH", "confidenceLevel": "MEDIUM_AND_ABOVE"},
    {"filterType": "HARASSMENT", "confidenceLevel": "MEDIUM_AND_ABOVE"},
    {"filterType": "SEXUALLY_EXPLICIT", "confidenceLevel": "MEDIUM_AND_ABOVE"},
    {"filterType": "DANGEROUS", "confidenceLevel": "MEDIUM_AND_ABOVE"}
  ]' \
  --basic-config-filter-enforcement=enabled \
  --pi-and-jailbreak-filter-settings-enforcement=enabled \
  --pi-and-jailbreak-filter-settings-confidence-level=HIGH \
  --malicious-uri-filter-settings-enforcement=enabled
```

Esto habilita: RAI (contenido dañino), prompt injection/jailbreak, URLs maliciosas, y SDP (datos sensibles) en modo **básico** — detecta y bloquea, pero **no enmascara** (no genera `deidentify_result`).

`02_agent_api/src/services/guardrails/layer_model_armor.py` ya sabe leer `deidentify_result` para enmascarar en vez de bloquear (igual criterio que la Capa 5 local de PII) — pero eso requiere el modo **avanzado** de SDP:

<details>
<summary>Opcional/avanzado — SDP con enmascarado real (Cloud DLP)</summary>

El modo básico de arriba solo detecta y bloquea. Para que el filtro `sdp` devuelva texto enmascarado en vez de bloquear, hay que:
1. Crear un **inspect template** y un **deidentify template** en Cloud DLP (Sensitive Data Protection) — fuera del alcance de esta guía, son recursos propios con su propia configuración de info-types y transformaciones.
2. Referenciarlos al crear el template de Model Armor con `--advanced-config-inspect-template=projects/$PROJECT_ID/locations/$REGION/inspectTemplates/TU_INSPECT_TEMPLATE` y `--advanced-config-deidentify-template=projects/$PROJECT_ID/locations/$REGION/deidentifyTemplates/TU_DEIDENTIFY_TEMPLATE`, en vez de `--basic-config-filter-enforcement=enabled`.

Sin esto, el filtro `sdp` en modo básico igual bloquea datos sensibles detectados (vía `_extract_deidentified_text` → sin `deidentify_result` disponible → cae a bloqueo) — solo no los deja pasar enmascarados.
</details>

Con esto termina la Fase 1: ya tenemos la SA, sus permisos de Model Armor, y el template.

---

## Fase 2 — Desplegar 03_mcp_server

Va primero porque `02_agent_api` necesita su URL antes de poder desplegarse.

### 2.1. Completar tu `.env` de `03_mcp_server`

Ver `03_mcp_server/.env.example` (Qdrant, SuperheroAPI, OpenAI para embeddings de `retrieve_documents`). No necesita ninguna variable nueva para el transporte HTTP — Cloud Run inyecta `PORT` automáticamente (`src/utils/environment.py::MCP_SERVER_PORT`).

### 2.2. Build + deploy

Completa el encabezado de `03_mcp_server/scripts/build-deploy.{sh,ps1,bat}` con los mismos valores de `$PROJECT_ID`/`$AR_REPOSITORY`/`$MCP_SERVER_SERVICE` de la Fase 0, y además:
```
RUNTIME_SERVICE_ACCOUNT="<el $SERVICE_SA de la Fase 0>"
```

```bash
cd 03_mcp_server/scripts
./build-deploy.sh   # o build-deploy.ps1 en PowerShell
```

Despliega con `--no-allow-unauthenticated` — nadie fuera de `02_agent_api` (con la SA + `run.invoker` del siguiente paso) puede invocarlo.

### 2.3. Obtener su URL y darle a la SA permiso sobre este Cloud Run

```bash
export MCP_SERVER_URL=$(gcloud run services describe "$MCP_SERVER_SERVICE" \
  --region="$REGION" --format="value(status.url)")
echo "$MCP_SERVER_URL"

gcloud run services add-iam-policy-binding "$MCP_SERVER_SERVICE" \
  --region="$REGION" \
  --member="serviceAccount:${SERVICE_SA}" \
  --role="roles/run.invoker"
```

La URL completa que usará `02_agent_api` es `${MCP_SERVER_URL}/mcp` (el endpoint streamable-http, path por defecto de FastMCP).

---

## Fase 3 — Desplegar 02_agent_api

### 3.1. Completar tu `.env` de `02_agent_api`

```
GUARDRAIL_ENGINE=model_armor
MODEL_ARMOR_PROJECT_ID=<tu PROJECT_ID>
MODEL_ARMOR_LOCATION=<tu REGION>
MODEL_ARMOR_TEMPLATE_ID=<el que creaste en la Fase 1.3>
DEMO_MCP_SERVER_URL=<$MCP_SERVER_URL de la Fase 2.3>/mcp
```
`GOOGLE_APPLICATION_CREDENTIALS` debe quedar **vacío** — el script `build-deploy.{sh,ps1,bat}` ya la excluye del deploy a propósito (la SA de la Fase 1.2 reemplaza esta variable, tanto para Model Armor como para el ID token hacia `03_mcp_server`).

### 3.2. Build + deploy

Completa el encabezado de `02_agent_api/scripts/build-deploy.{sh,ps1,bat}` con los mismos valores de `$PROJECT_ID`/`$AR_REPOSITORY`/`$AGENT_API_SERVICE` de la Fase 0, y además:
```
RUNTIME_SERVICE_ACCOUNT="<el $SERVICE_SA de la Fase 0>"
```

```bash
cd 02_agent_api/scripts
./build-deploy.sh   # o build-deploy.ps1 en PowerShell
```

Despliega con `--no-allow-unauthenticated` y `--service-account "$RUNTIME_SERVICE_ACCOUNT"` — el Cloud Run queda cerrado, solo el Gateway podrá invocarlo.

### 3.3. Ahora sí: darle a la SA permiso sobre este Cloud Run específico

```bash
gcloud run services add-iam-policy-binding "$AGENT_API_SERVICE" \
  --region="$REGION" \
  --member="serviceAccount:${SERVICE_SA}" \
  --role="roles/run.invoker"
```

---

## Fase 4 — Crear el API Gateway

### 4.1. Obtener la URL del Cloud Run recién desplegado

```bash
export CLOUD_RUN_URL=$(gcloud run services describe "$AGENT_API_SERVICE" \
  --region="$REGION" --format="value(status.url)")
echo "$CLOUD_RUN_URL"
```

### 4.2. Renderizar `openapi_gateway.yml` (plantilla parametrizada)

`02_agent_api/openapi_gateway.yml` usa `${CLOUD_RUN_URL}`, `${GATEWAY_HOST}` y `${FIREBASE_PROJECT_ID}` — Google API Gateway sube el YAML tal cual (no soporta variables en runtime), así que hay que resolverlas antes con `envsubst`. `GATEWAY_HOST` recién se conoce después de crear el gateway (paso 4.3) — para esta primera subida usa un placeholder cualquiera (el `servers.url` es informativo, no afecta el ruteo real):

```bash
export GATEWAY_HOST="placeholder.gateway.dev"

cd 02_agent_api
envsubst < openapi_gateway.yml > openapi_gateway.rendered.yml
cd ..
```

### 4.3. Crear API, config y gateway

```bash
gcloud api-gateway apis create "$GATEWAY_API_ID" --project="$PROJECT_ID"

gcloud api-gateway api-configs create "$GATEWAY_CONFIG_ID" \
  --api="$GATEWAY_API_ID" \
  --openapi-spec=02_agent_api/openapi_gateway.rendered.yml \
  --project="$PROJECT_ID" \
  --backend-auth-service-account="$SERVICE_SA"

gcloud api-gateway gateways create "$GATEWAY_ID" \
  --api="$GATEWAY_API_ID" \
  --api-config="$GATEWAY_CONFIG_ID" \
  --location="$REGION" \
  --project="$PROJECT_ID"

export GATEWAY_HOST=$(gcloud api-gateway gateways describe "$GATEWAY_ID" \
  --location="$REGION" --format="value(defaultHostname)")
echo "Gateway listo en: https://$GATEWAY_HOST"
```

Si quieres que `servers.url` del YAML refleje el host real (no el placeholder), vuelve a correr el `envsubst` del paso 4.2 con el `$GATEWAY_HOST` real — no es obligatorio, es solo documentación dentro del propio spec.

**Actualizar el config más adelante** (nuevo deploy de `02_agent_api`, o cambios en `openapi_gateway.yml`): crea un nuevo `GATEWAY_CONFIG_ID` (ej. `agent-api-gw-config-v2`) con `api-configs create` y luego apunta el gateway existente a esa config con `gcloud api-gateway gateways update "$GATEWAY_ID" --api="$GATEWAY_API_ID" --api-config=NUEVO_CONFIG_ID --location="$REGION"` — los configs son inmutables, no se editan in-place.

---

## Fase 5 — Desplegar 01_agent-app (frontend)

Recién acá se despliega el frontend — ya tenemos `$GATEWAY_HOST`, la única variable que le faltaba. Las variables `NEXT_PUBLIC_*` se hornean en build-time (ver comentario en `01_agent-app/Dockerfile`).

```bash
cd 01_agent-app

export IMAGE_TAG=$(date +"%Y%m%d-%H%M%S")
export AGENT_APP_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/01-agent-app:${IMAGE_TAG}"

docker build \
  --build-arg NEXT_PUBLIC_API_BASE="https://${GATEWAY_HOST}" \
  --build-arg NEXT_PUBLIC_FIREBASE_API_KEY="<tu Firebase API key>" \
  --build-arg NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN="${FIREBASE_PROJECT_ID}.firebaseapp.com" \
  --build-arg NEXT_PUBLIC_FIREBASE_PROJECT_ID="${FIREBASE_PROJECT_ID}" \
  -t "$AGENT_APP_IMAGE" .

docker push "$AGENT_APP_IMAGE"

gcloud run deploy "$AGENT_APP_SERVICE" \
  --image "$AGENT_APP_IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --port 3000

cd ..
```

`01_agent-app` sí queda público (`--allow-unauthenticated`) — es la app que ve el usuario final; la protección real está en que `02_agent_api` solo acepta al Gateway (y `03_mcp_server` solo acepta a `02_agent_api`), y el Gateway solo reenvía peticiones con un JWT de Firebase válido.

---

## Verificación

**1. Confirmar que el Gateway responde y valida auth:**
```bash
# Sin token: debe dar 401
curl -i "https://${GATEWAY_HOST}/api/errors"

# Con token de Firebase (reemplaza <ID_TOKEN>, ej. desde el frontend logueado)
curl -i "https://${GATEWAY_HOST}/api/errors" -H "Authorization: Bearer <ID_TOKEN>"
```

**2. Confirmar que Cloud Run rechaza acceso directo** (debe fallar con 403, ya no acepta llamadas sin la identidad del Gateway):
```bash
curl -i "${CLOUD_RUN_URL}/api/errors"
```

**3. Confirmar que Model Armor está activo (no en fallback local)**: revisa los logs de `02_agent_api` en Cloud Logging — al arrancar debe aparecer el pipeline con `ModelArmorMiddleware` y **no** el warning `"No se pudo inicializar ModelArmorMiddleware"` ni `"falta MODEL_ARMOR_PROJECT_ID/MODEL_ARMOR_TEMPLATE_ID"` (ver `guardrails/__init__.py`). Si aparece, revisa que la SA (Fase 1.2) tenga `roles/modelarmor.user`.

**4. Confirmar que 02_agent_api conectó a 03_mcp_server por HTTP**: en los logs, buscar `"Demo MCP server conectado"` (log de `main.py`). Si en cambio aparece `"Error conectando al demo MCP server"`:
   - Revisa que `DEMO_MCP_SERVER_URL` termine en `/mcp` y apunte a la URL real de la Fase 2.3.
   - Si el error menciona 401/403: la SA no tiene `roles/run.invoker` sobre `$MCP_SERVER_SERVICE` (Fase 2.3), o `GoogleIDTokenAuth` no pudo obtener el ID token (revisa que la Cloud Run de `02_agent_api` tenga `--service-account "$SERVICE_SA"` asignado, Fase 3.2) — busca el warning `"No se pudo obtener ID token de Google"` en los logs (`src/utils/gcp_auth.py`). El endpoint se configura con `/mcp`, pero el código usa automáticamente la URL base del servicio como audiencia del token, tal como exige Cloud Run.

**5. Probar el flujo completo**: abrir la URL de `$AGENT_APP_SERVICE`, loguearse con Firebase, mandar un mensaje, y confirmar que llega respuesta (revisando en Network del navegador que la request va a `https://$GATEWAY_HOST/api/chat`, no al Cloud Run directo).
