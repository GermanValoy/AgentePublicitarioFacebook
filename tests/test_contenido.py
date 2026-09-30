import random

from agente import contenido as txt


def test_spintax_elige_una_opcion():
    resultados = {txt.expandir_spintax("{Hola|Buenas} vecinos", random.Random(i)) for i in range(50)}
    assert resultados == {"Hola vecinos", "Buenas vecinos"}


def test_spintax_anidado_y_llaves_sin_opciones():
    rng = random.Random(1)
    for _ in range(30):
        r = txt.expandir_spintax("{Hola {amigos|vecinos}|Buenas} {sin opciones}", rng)
        assert r in {"Hola amigos {sin opciones}", "Hola vecinos {sin opciones}", "Buenas {sin opciones}"}


def test_llaves_balanceadas():
    assert txt.llaves_balanceadas("{a|b} y {c|{d|e}}")
    assert not txt.llaves_balanceadas("{a|b")
    assert not txt.llaves_balanceadas("a}{b")


def test_conteos():
    assert txt.contar_enlaces("visitá https://x.com y www.y.com o wa.me/549111") == 3
    assert txt.contar_hashtags("#pc #notebook precio#no") == 2
    assert txt.proporcion_mayusculas("HOLA hola") == 0.5


def test_elegir_variante_evita_lo_ya_publicado():
    texto, sim = txt.elegir_variante("{Oferta de limpieza de PC|Formateo de notebooks hoy}",
                                     ["Oferta de limpieza de PC"], random.Random(3))
    assert texto == "Formateo de notebooks hoy"
    assert sim < 0.6
