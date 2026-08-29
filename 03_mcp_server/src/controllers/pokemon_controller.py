from src.dto.pokemon import Pokemon
from src.services import pokemon_service


def _format_pokemon(pokemon: Pokemon) -> str:
    types = ", ".join(pokemon.types)
    abilities = ", ".join(pokemon.abilities)
    stats = ", ".join(f"{name}: {value}" for name, value in pokemon.stats.items())
    return (
        f"#{pokemon.id} {pokemon.name} — tipo(s): {types} — habilidades: {abilities} — "
        f"altura: {pokemon.height} — peso: {pokemon.weight} — "
        f"experiencia base: {pokemon.base_experience} — stats: {stats}"
    )


async def handle_get_pokemon(name_or_id: str) -> str:
    pokemon = await pokemon_service.get_pokemon(name_or_id)
    return _format_pokemon(pokemon)


async def handle_list_pokemons(limit: int, offset: int) -> str:
    names = await pokemon_service.list_pokemons(limit, offset)
    return "\n".join(names)
