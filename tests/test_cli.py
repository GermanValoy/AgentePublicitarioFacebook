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
    kw.setdefault("espera_aprobacion", 15)
    kw.setdefault("espera_telegram", 0)
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


def test_publicar_ahora_en_modo_aprobacion_pregunta_por_telegram(proyecto, monkeypatch):
    from agente import telegram
    from .test_telegram import TelegramFalso
    config, falso = preparar(proyecto, monkeypatch)
    config.modo = "aprobacion"
    tg = TelegramFalso()
    monkeypatch.setattr(telegram, "cargar", lambda carpeta: tg)
    original = telegram.AprobadorTelegram.procesar

    def procesar_y_aprobar(self, espera=0, comandos=None):
        if self.pendientes():
            tg.tocar("si")
        return original(self, 0, comandos)

    monkeypatch.setattr(telegram.AprobadorTelegram, "procesar", procesar_y_aprobar)
    assert cli.cmd_publicar_ahora(config, args(id="promo", espera_aprobacion=1, espera_telegram=0)) == 0
    assert falso.modo == "automatico" and falso.urls
    assert any("Publicado" in e[0] for e in tg.enviados)


def test_publicar_ahora_rechazada_por_telegram(proyecto, monkeypatch):
    from agente import telegram
    from .test_telegram import TelegramFalso
    config, falso = preparar(proyecto, monkeypatch)
    config.modo = "aprobacion"
    tg = TelegramFalso()
    monkeypatch.setattr(telegram, "cargar", lambda carpeta: tg)
    original = telegram.AprobadorTelegram.procesar

    def procesar_y_rechazar(self, espera=0, comandos=None):
        if self.pendientes():
            tg.tocar("no")
        return original(self, 0, comandos)

    monkeypatch.setattr(telegram.AprobadorTelegram, "procesar", procesar_y_rechazar)
    assert cli.cmd_publicar_ahora(config, args(id="promo", espera_aprobacion=1, espera_telegram=0)) == 1
    assert falso.urls == []


def test_no_permite_dos_agentes_a_la_vez(config):
    import pytest
    from agente.config import ErrorConfig
    with cli._unica_instancia(config):
        assert (config.carpeta_datos / "agente.pid").read_text().isdigit()
        with pytest.raises(ErrorConfig, match="ya está funcionando"):
            with cli._unica_instancia(config):
                pass
    assert not (config.carpeta_datos / "agente.pid").exists()
    with cli._unica_instancia(config):  # liberado: se puede volver a abrir
        pass


def test_publicar_ahora_avisa_si_el_agente_esta_andando(proyecto, monkeypatch, capsys):
    config, falso = preparar(proyecto, monkeypatch)
    with cli._unica_instancia(config):
        assert cli.cmd_publicar_ahora(config, args(id="promo")) == 1
    assert falso.urls == []
    assert "detener_agente.bat" in capsys.readouterr().out


def test_se_reinicia_solo_con_version_nueva(config, monkeypatch):
    llamadas = []
    monkeypatch.setattr(cli, "_aprobador", lambda c: None)
    monkeypatch.setattr(cli, "_escribir_reporte", lambda c, a=None: llamadas.append("reporte"))
    monkeypatch.setattr(cli, "_sincronizar", lambda c, a=None: "se bajaron 3 archivos; hay una versión nueva del agente")
    monkeypatch.setattr(cli, "_una_pasada", lambda *a: llamadas.append("pasada"))
    monkeypatch.setattr(cli, "_reiniciar", lambda c: llamadas.append("reinicio"))
    a = argparse.Namespace(esperar_inicio=0, reiniciar_solo=True, sincronizar_cada=30, intervalo=5,
                           oculto=False, sin_demora=True)
    assert cli.cmd_ejecutar(config, a) == 0
    assert llamadas == ["reporte", "reinicio"]  # no publica con la versión vieja
    assert not (config.carpeta_datos / "agente.pid").exists()  # libera el candado para la versión nueva


def test_funciona_oculto_sin_consola(config, monkeypatch):
    """Con pythonw no hay consola (sys.stdout es None): el registro igual tiene que andar."""
    import logging
    monkeypatch.setattr(cli.sys, "stdout", None)
    monkeypatch.setattr(cli.log, "handlers", [])
    cli._configurar_log(config)
    cli.log.info("prueba oculta")
    for h in cli.log.handlers:
        h.flush()
    assert "prueba oculta" in (config.carpeta_datos / "agente.log").read_text(encoding="utf-8")
    assert all(not isinstance(h, logging.StreamHandler) or isinstance(h, logging.FileHandler)
               for h in cli.log.handlers)


def test_si_no_arranca_lo_anota_y_avisa(tmp_path, monkeypatch):
    from agente import telegram
    from .test_telegram import TelegramFalso
    tg = TelegramFalso()
    monkeypatch.setattr(cli, "RAIZ", tmp_path)
    monkeypatch.setattr(telegram, "cargar", lambda carpeta: tg)
    cli._avisar_fallo_de_arranque(argparse.Namespace(comando="ejecutar"), "El agente ya está funcionando")
    assert "ya está funcionando" in (tmp_path / "datos" / "arranque.log").read_text(encoding="utf-8")
    assert "no pudo arrancar" in tg.enviados[-1][0]
