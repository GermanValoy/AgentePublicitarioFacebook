"""Prueba del ciclo completo con un publicador falso (no abre Facebook)."""
import random
from contextlib import contextmanager

from agente import antiban
from agente.ciclo import ejecutar_ciclo
from agente.historial import Historial
from agente.publicaciones import cargar_publicaciones
from agente.publicador import ResultadoPublicacion

from .conftest import momento

CALENDARIO = """
publicaciones:
  - id: promo
    fecha: 2026-10-05
    hora: "10:00"
    grupos: [Grupo A, Grupo B]
    imagenes: [buena.png]
    texto: "{Hola|Buenas|Qué tal} vecinos, hago {limpieza|mantenimiento} de PC y notebooks. {Escribime|Consultame}."
  - id: rota
    fecha: 2026-10-05
    hora: "09:00"
    grupos: [Grupo A]
    imagenes: [no-existe.png]
    texto: "Esta publicación tiene una imagen que no existe en la carpeta."
"""


class PublicadorFalso:
    def __init__(self, estado="publicada"):
        self.estado = estado
        self.llamadas = []

    @contextmanager
    def fabrica(self):
        yield self

    def publicar(self, url, texto, imagenes):
        self.llamadas.append((url, texto, imagenes))
        return ResultadoPublicacion(self.estado, "ok")


def preparar(proyecto, modo="asistido"):
    config = proyecto(modo=modo, programadas=CALENDARIO)
    return config, cargar_publicaciones(config.archivo_programadas), Historial(config.carpeta_datos / "historial.json")


def ciclo(config, pubs, hist, falso, cuando):
    return ejecutar_ciclo(config, pubs, hist, falso.fabrica, momento(config, cuando), random.Random(0),
                          esperar=lambda s: None)


def test_publica_de_a_una_y_espacia(proyecto):
    config, pubs, hist = preparar(proyecto)
    falso = PublicadorFalso()

    assert ciclo(config, pubs, hist, falso, "2026-10-05 10:00") == "publicada"
    url, texto, imagenes = falso.llamadas[0]
    assert url == "https://www.facebook.com/groups/aaa"
    assert "{" not in texto and imagenes[0].name == "buena.png"

    assert ciclo(config, pubs, hist, falso, "2026-10-05 10:20") is None   # respeta los 45 minutos
    assert ciclo(config, pubs, hist, falso, "2026-10-05 10:50") == "publicada"
    assert falso.llamadas[1][0] == "https://www.facebook.com/groups/bbb"
    assert ciclo(config, pubs, hist, falso, "2026-10-05 12:00") is None   # ya no queda nada
    assert len(falso.llamadas) == 2


def test_no_publica_si_no_pasa_las_pruebas(proyecto):
    config, pubs, hist = preparar(proyecto)
    falso = PublicadorFalso()
    ciclo(config, pubs, hist, falso, "2026-10-05 09:30")
    assert falso.llamadas == []


def test_bloqueo_pausa_el_agente(proyecto):
    config, pubs, hist = preparar(proyecto)
    falso = PublicadorFalso("bloqueada")
    assert ciclo(config, pubs, hist, falso, "2026-10-05 10:00") == "bloqueada"
    assert antiban.pausa_activa(config)
    assert ciclo(config, pubs, hist, falso, "2026-10-12 10:00") is None
    assert len(falso.llamadas) == 1


def test_modo_simulacion_no_repite_la_simulacion(proyecto):
    config, pubs, hist = preparar(proyecto, modo="simulacion")
    falso = PublicadorFalso("simulada")
    assert ciclo(config, pubs, hist, falso, "2026-10-05 10:00") == "simulada"
    assert ciclo(config, pubs, hist, falso, "2026-10-05 10:05") == "simulada"  # la simulación no cuenta como actividad
    assert ciclo(config, pubs, hist, falso, "2026-10-05 10:10") is None


def test_marca_vencidas(proyecto):
    config, pubs, hist = preparar(proyecto)
    ciclo(config, pubs, hist, PublicadorFalso(), "2026-10-06 10:00")
    assert {r.estado for r in hist.registros} == {"vencida"}


def test_omite_texto_repetido_en_el_mismo_grupo(proyecto):
    config = proyecto(programadas="""
        publicaciones:
          - id: fija
            fecha: 2026-10-05
            hora: "10:00"
            repetir_cada_dias: 7
            grupos: [Grupo A]
            texto: "Hago mantenimiento de computadoras, siempre el mismo texto sin variar."
        """)
    pubs = cargar_publicaciones(config.archivo_programadas)
    hist = Historial(config.carpeta_datos / "historial.json")
    falso = PublicadorFalso()
    assert ciclo(config, pubs, hist, falso, "2026-10-05 10:00") == "publicada"
    assert ciclo(config, pubs, hist, falso, "2026-10-12 10:00") is None
    assert hist.registros[-1].estado == "omitida"
