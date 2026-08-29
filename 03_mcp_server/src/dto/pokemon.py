from pydantic import BaseModel


class Pokemon(BaseModel):
    id: int
    name: str
    height: int
    weight: int
    base_experience: int | None
    types: list[str]
    abilities: list[str]
    stats: dict[str, int]

    @classmethod
    def from_api(cls, data: dict) -> "Pokemon":
        return cls(
            id=data["id"],
            name=data["name"],
            height=data["height"],
            weight=data["weight"],
            base_experience=data.get("base_experience"),
            types=[t["type"]["name"] for t in data.get("types", [])],
            abilities=[a["ability"]["name"] for a in data.get("abilities", [])],
            stats={s["stat"]["name"]: s["base_stat"] for s in data.get("stats", [])},
        )
