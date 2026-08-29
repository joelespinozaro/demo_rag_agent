from io import BytesIO

from pptx import Presentation

from src.dto.pptx import SlideInput


def build_pptx(title: str, slides: list[SlideInput]) -> bytes:
    presentation = Presentation()

    title_slide = presentation.slides.add_slide(presentation.slide_layouts[0])
    title_slide.shapes.title.text = title
    if len(title_slide.placeholders) > 1:
        title_slide.placeholders[1].text = "Generado por el asistente"

    content_layout = presentation.slide_layouts[1]
    for slide_input in slides:
        slide = presentation.slides.add_slide(content_layout)
        slide.shapes.title.text = slide_input.title

        body = slide.placeholders[1].text_frame
        body.clear()
        for i, bullet in enumerate(slide_input.bullets):
            paragraph = body.paragraphs[0] if i == 0 else body.add_paragraph()
            paragraph.text = bullet

    buffer = BytesIO()
    presentation.save(buffer)
    return buffer.getvalue()
