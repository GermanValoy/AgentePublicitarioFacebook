"""Prueba de los comandos que abren Facebook, con un navegador falso."""
import argparse
import datetime as dt

from agente import antiban, cli
from agente.historial import Historial
from agente.publicador import ResultadoPublicacion

CALENDARIO = """
publicaciones:
  - id: promo
    fecha: 2026-10-05
    hora: "10:00"
    grupos: [Grupo A]
    imagenes: [buena.png]
    texto: "{Hola|Buenas} vecinos, hago mantenimiento de PC y notebooks. Escribime por privado."
"""


class NavegadorFalso:
    def __init__(self, estado):
        self.estado = estado
        self.urls = []

    def __call__(self, config, modo=None, oculto=False):
        self.modo = modo
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def publicar(self, url, texto, imagenes):
        self.urls.append(url)
        return ResultadoPublicacion(self.estado, "ok")


def preparar(proyecto, monkeypatch, estado="publicada", hora=dt.time(11, 0)):
    config = proyecto(programadas=CALENDARIO)
    ahora = dt.datetime.combine(dt.date(2026, 10, 1), hora, tzinfo=config.zona)
    monkeypatch.setattr(type(config), "ahora", lambda self: ahora)
    falso = NavegadorFalso(estado)
    monkeypatch.setattr(cli, "_publicador", falso)
    return config, falso


def args(**kw):
    return argparse.Namespace(oculto=False, grupo=None, **kw)


def test_publicar_ahora(proyecto, monkeypatch):
    config, falso = preparar(proyecto, monkeypatch)
    assert cli.cmd_publicar_ahora(config, args(id="promo")) == 0
    assert falso.urls == ["https://www.facebook.com/groups/aaa"]
    hist = Historial(config.carpeta_datos / "historial.json")
    assert hist.registros[-1].estado == "publicada"
    # Respeta el anti-baneo: no deja repetir en el mismo grupo.
    assert cli.cmd_publicar_ahora(config, args(id="promo")) == 1
    assert len(falso.urls) == 1


def test_publicar_ahora_fuera_de_horario(proyecto, monkeypatch):
    config, falso = preparar(proyecto, monkeypatch, hora=dt.time(23, 30))
    assert cli.cmd_publicar_ahora(config, args(id="promo")) == 1
    assert falso.urls == []


def test_publicar_ahora_id_inexistente(proyecto, monkeypatch):
    config, falso = preparar(proyecto, monkeypatch)
    assert cli.cmd_publicar_ahora(config, args(id="no-existe")) == 1


def test_publicar_ahora_bloqueo_pausa(proyecto, monkeypatch):
    config, _ = preparar(proyecto, monkeypatch, estado="bloqueada")
    assert cli.cmd_publicar_ahora(config, args(id="promo")) == 1
    assert antiban.pausa_activa(config)


def test_simular_no_toca_el_historial(proyecto, monkeypatch):
    config, falso = preparar(proyecto, monkeypatch, estado="simulada", hora=dt.time(23, 30))
    assert cli.cmd_simular(config, args(id="promo")) == 0
    assert falso.urls and not (config.carpeta_datos / "historial.json").exists()


def test_publicar_ahora_en_modo_aprobacion_pide_tu_clic(proyecto, monkeypatch):
    config, falso = preparar(proyecto, monkeypatch)
    config.modo = "aprobacion"
    assert cli.cmd_publicar_ahora(config, args(id="promo")) == 0
    assert falso.modo == "asistido"
