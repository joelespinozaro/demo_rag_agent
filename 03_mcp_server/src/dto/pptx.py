from pydantic import BaseModel


class SlideInput(BaseModel):
    title: str
    bullets: list[str] = []
