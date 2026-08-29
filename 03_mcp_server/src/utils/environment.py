from decouple import config

POKEAPI_BASE_URL: str = config(
    "POKEAPI_BASE_URL", default="https://pokeapi.co/api/v2"
)
HTTP_TIMEOUT_SECONDS: float = config("HTTP_TIMEOUT_SECONDS", default=10, cast=float)
