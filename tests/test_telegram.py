"""Aprobación por Telegram con un Telegram falso (no usa internet)."""
import json
import random
from contextlib import contextmanager

import pytest

from agente import telegram
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
"""
MI_CHAT = 555


class TelegramFalso(telegram.Telegram):
    def __init__(self):
        super().__init__("token", MI_CHAT)
        self.enviados, self.fotos_enviadas, self.editados, self.cola = [], [], [], []
        self.siguiente_id = 1

    def mensaje(self, texto, botones=None):
        self.enviados.append((texto, botones))
        self.siguiente_id += 1
        return self.siguiente_id

    def fotos(self, rutas, leyenda=""):
        self.fotos_enviadas.append(([r.name for r in rutas], leyenda))

    def editar(self, message_id, texto):
        self.editados.append(texto)

    def responder_boton(self, callback_id, texto):
        pass

    def actualizaciones(self, desde, espera=0):
        nuevas = [u for u in self.cola if u["update_id"] >= desde]
        self.cola = []
        return nuevas

    def tocar(self, accion, chat=MI_CHAT):
        _, botones = next(e for e in reversed(self.enviados) if e[1])
        dato = botones[0][0 if accion == "si" else 1]["callback_data"]
        self.cola.append({"update_id": len(self.enviados) + 100, "callback_query": {
            "id": "x", "data": dato, "message": {"chat": {"id": chat}}}})

    def escribir(self, texto):
        self.cola.append({"update_id": len(self.enviados) + 200,
                          "message": {"chat": {"id": MI_CHAT}, "text": texto}})


class Navegador:
    def __init__(self, estado="publicada"):
        self.estado, self.textos = estado, []

    @contextmanager
    def fabrica(self):
        yield self

    def publicar(self, url, texto, imagenes):
        self.textos.append(texto)
        return ResultadoPublicacion(self.estado, "ok")


@pytest.fixture
def entorno(proyecto):
    config = proyecto(modo="aprobacion", programadas=CALENDARIO)
    tg = TelegramFalso()
    aprobador = telegram.AprobadorTelegram(tg, config.carpeta_datos / "aprobaciones.json")
    return config, cargar_publicaciones(config.archivo_programadas), \
        Historial(config.carpeta_datos / "historial.json"), tg, aprobador


def ciclo(config, pubs, hist, nav, aprobador, cuando="2026-10-05 10:00"):
    return ejecutar_ciclo(config, pubs, hist, nav.fabrica, momento(config, cuando), random.Random(0),
                          esperar=lambda s: None, aprobador=aprobador)


def test_pide_aprobacion_y_publica_cuando_aprobas(entorno):
    config, pubs, hist, tg, aprobador = entorno
    nav = Navegador()
    assert ciclo(config, pubs, hist, nav, aprobador) == "esperando_aprobacion"
    assert nav.textos == []
    assert tg.fotos_enviadas[0][0] == ["buena.png"]
    texto_pedido = tg.enviados[-1][0]
    assert "Grupo A" in texto_pedido

    # Mientras no respondas, no publica nada (ni en otros grupos).
    assert ciclo(config, pubs, hist, nav, aprobador) == "esperando_aprobacion"
    assert nav.textos == []

    tg.tocar("si")
    assert aprobador.procesar() is True
    assert ciclo(config, pubs, hist, nav, aprobador) == "publicada"
    assert nav.textos and nav.textos[0] in texto_pedido  # publica exactamente el texto que aprobaste
    assert any("Publicado" in e[0] for e in tg.enviados)
    assert hist.registros[-1].estado == "publicada"


def test_rechazar_no_publica(entorno):
    config, pubs, hist, tg, aprobador = entorno
    nav = Navegador()
    ciclo(config, pubs, hist, nav, aprobador)
    tg.tocar("no")
    aprobador.procesar()
    # Rechazada la de Grupo A, pasa a pedir la de Grupo B.
    assert ciclo(config, pubs, hist, nav, aprobador) == "esperando_aprobacion"
    assert nav.textos == []
    assert hist.registros[-1].estado == "no_confirmada"
    assert "Grupo B" in tg.enviados[-1][0]


def test_ignora_botones_de_otros_chats(entorno):
    config, pubs, hist, tg, aprobador = entorno
    ciclo(config, pubs, hist, Navegador(), aprobador)
    tg.tocar("si", chat=999)
    assert aprobador.procesar() is False
    assert aprobador.estado(aprobador.pendientes()[0]) == "pendiente"


def test_vence_sin_respuesta(entorno):
    config, pubs, hist, tg, aprobador = entorno
    ciclo(config, pubs, hist, Navegador(), aprobador)
    ciclo(config, pubs, hist, Navegador(), aprobador, "2026-10-06 10:00")
    assert not aprobador.pendientes()
    assert any("Venció" in e for e in tg.editados)


def test_bloqueo_avisa_por_telegram(entorno):
    config, pubs, hist, tg, aprobador = entorno
    ciclo(config, pubs, hist, Navegador("bloqueada"), aprobador)
    tg.tocar("si")
    aprobador.procesar()
    assert ciclo(config, pubs, hist, Navegador("bloqueada"), aprobador) == "bloqueada"
    assert any("PAUSADO" in e[0] for e in tg.enviados)


def test_estado_persistente_entre_reinicios(entorno):
    config, pubs, hist, tg, aprobador = entorno
    ciclo(config, pubs, hist, Navegador(), aprobador)
    otro = telegram.AprobadorTelegram(tg, config.carpeta_datos / "aprobaciones.json")
    assert otro.pendientes() == aprobador.pendientes()


def test_comandos(entorno):
    _, _, _, tg, aprobador = entorno
    tg.escribir("/estado")
    aprobador.procesar(comandos=lambda t: f"respuesta a {t}")
    assert tg.enviados[-1][0] == "respuesta a /estado"


def test_modo_aprobacion_sin_telegram_falla(entorno):
    config, pubs, hist, _, _ = entorno
    with pytest.raises(ValueError):
        ejecutar_ciclo(config, pubs, hist, Navegador().fabrica, momento(config, "2026-10-05 10:00"))


def test_multipart_de_fotos(tmp_path, monkeypatch):
    foto = tmp_path / "a.png"
    foto.write_bytes(b"PNGDATA")
    capturado = {}

    class Respuesta:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def read(self):
            return json.dumps({"ok": True, "result": {"message_id": 1}}).encode()

    def falso_urlopen(pedido, timeout):
        capturado["url"], capturado["cuerpo"] = pedido.full_url, pedido.data
        capturado["tipo"] = pedido.headers["Content-type"]
        return Respuesta()

    monkeypatch.setattr(telegram.urllib.request, "urlopen", falso_urlopen)
    telegram.Telegram("T", 1).fotos([foto], "hola")
    assert capturado["url"].endswith("/botT/sendPhoto")
    assert "multipart/form-data" in capturado["tipo"]
    assert b"PNGDATA" in capturado["cuerpo"] and b"hola" in capturado["cuerpo"]
