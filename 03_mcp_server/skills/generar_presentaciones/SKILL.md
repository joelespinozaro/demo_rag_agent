---
name: generar_presentaciones
description: Cómo estructurar y generar una presentación PowerPoint (.pptx) a partir de una conversación o un tema. Usar cuando el usuario pida explícitamente una presentación, PPT, PowerPoint o slides.
---

# Generar presentaciones PowerPoint

## Cuándo usar esta skill

Solo cuando el usuario pida explícitamente una presentación, PPT, PowerPoint o
"slides". No la uses para resumir texto dentro del chat — para eso alcanza con
una respuesta normal.

## De dónde sale el contenido

- Si el usuario pide resumir o presentar algo que ya se conversó, arma las
  slides en base a esa conversación.
- Si el tema es institucional (programas, cursos, temarios, precios, duración,
  requisitos, certificaciones), consulta primero `retrieve_documents` y basa
  las slides en esa información real — no inventes datos de la academia.
- Si el tema es genérico y no relacionado con la academia, improvisa el
  contenido con tu propio conocimiento.

## Cómo estructurar las slides

- Entre 3 y 8 slides de contenido según la complejidad del tema: ni una sola
  slide con todo, ni veinte triviales.
- Cada slide: un título corto y claro, más 3 a 5 viñetas concisas (frases
  cortas, no párrafos).
- No repitas el título general como título de la primera slide de contenido:
  la portada se genera sola con ese título.

## Cómo generarla

Una vez decidido el título general y la lista de slides (cada una con su
`title` y sus `bullets`), llama a la tool `generate_pptx(title, slides)`. La
tool arma el archivo .pptx real y lo entrega directamente en la interfaz del
chat como adjunto descargable — vos no generás el archivo, solo decidís el
contenido y llamás a la tool con esa estructura.

## Qué NO hacer

- No inventes un enlace de descarga, ruta `sandbox:` ni markdown tipo
  `[Descargar](...)` en tu respuesta de texto: el archivo llega aparte, como
  adjunto en la interfaz, no como link en el mensaje.
- Después de llamar a `generate_pptx`, en tu respuesta de texto solo confirma
  el título y la cantidad de slides generadas — no repitas el contenido
  completo de cada slide.
