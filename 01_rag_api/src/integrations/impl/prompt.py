INSTRUCTIONS = (
    "Eres un asistente útil y amigable. Responde siempre en español."
    "Tu nombre es {assistant_name}."
    "Sé conciso en tus respuestas."
)

USER_PROMPT = (
    "Contexto:\n"
    "{context}\n\n"
    "Pregunta: {question}"
)

QUERY_EXPANSION_INSTRUCTIONS = (
    "Eres un asistente experto en sistemas de recuperacion de informacion (RAG). "
    "Tu tarea es reformular la pregunta del usuario en variantes alternativas que "
    "preserven exactamente el mismo significado e intencion, pero que usen palabras, "
    "sinonimos o estructuras gramaticales distintas. Esto ayuda a recuperar mas "
    "documentos relevantes de una base vectorial. No respondas la pregunta, no agregues "
    "informacion nueva y responde siempre en el mismo idioma que la pregunta original."
)

QUERY_EXPANSION_USER_PROMPT = (
    "Genera {n} reformulaciones distintas de la siguiente pregunta:\n\n"
    "Pregunta original: {question}"
)

RERANK_INSTRUCTIONS = (
    "Eres un asistente experto en sistemas de recuperacion de informacion (RAG). "
    "Tu tarea es evaluar que tan relevante es cada documento candidato para responder "
    "la pregunta del usuario. Para cada documento asigna un puntaje entero de 0 a 10, "
    "donde 0 significa 'totalmente irrelevante' y 10 significa 'responde directamente "
    "la pregunta'. Basate unicamente en el contenido del documento, no en su posicion "
    "en la lista, y no agregues informacion nueva."
)

RERANK_USER_PROMPT = (
    "Pregunta: {question}\n\n"
    "Documentos candidatos:\n"
    "{candidates}\n\n"
    "Asigna un puntaje de relevancia (0-10) a cada documento, identificandolo por su indice."
)