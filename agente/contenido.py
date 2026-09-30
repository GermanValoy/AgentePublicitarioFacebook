"""Utilidades de texto: variaciones (spintax), conteos y similitud."""
from __future__ import annotations

import difflib
import random
import re

_SPIN = re.compile(r"\{([^{}]*\|[^{}]*)\}")
ENLACE = re.compile(r"(https?://|www\.|wa\.me/)\S+", re.I)
HASHTAG = re.compile(r"(?<!\w)#\w+")


def expandir_spintax(texto: str, rng: random.Random | None = None) -> str:
    """Convierte "{Hola|Buenas} vecinos" en "Hola vecinos" o "Buenas vecinos". Admite anidado."""
    rng = rng or random.Random()
    anterior = None
    while anterior != texto:
        anterior = texto
        texto = _SPIN.sub(lambda m: rng.choice(m.group(1).split("|")), texto)
    return texto


def llaves_balanceadas(texto: str) -> bool:
    nivel = 0
    for c in texto:
        nivel += (c == "{") - (c == "}")
        if nivel < 0:
            return False
    return nivel == 0


def contar_enlaces(texto: str) -> int:
    return len(ENLACE.findall(texto))


def contar_hashtags(texto: str) -> int:
    return len(HASHTAG.findall(texto))


def proporcion_mayusculas(texto: str) -> float:
    letras = [c for c in texto if c.isalpha()]
    return sum(c.isupper() for c in letras) / len(letras) if letras else 0.0


def similitud(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def elegir_variante(plantilla: str, previos: list[str], rng: random.Random | None = None,
                    intentos: int = 20) -> tuple[str, float]:
    """Genera la variante del texto que menos se parece a lo ya publicado en el grupo."""
    rng = rng or random.Random()
    mejor, mejor_sim = "", 2.0
    for _ in range(intentos):
        candidato = expandir_spintax(plantilla, rng)
        sim = max((similitud(candidato, p) for p in previos), default=0.0)
        if sim < mejor_sim:
            mejor, mejor_sim = candidato, sim
    return mejor, mejor_sim
