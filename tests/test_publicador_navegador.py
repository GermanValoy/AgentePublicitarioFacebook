"""Prueba el flujo del navegador contra una página local que imita un grupo de Facebook.

No se conecta a Facebook: verifica que el agente sepa abrir el cuadro, escribir, adjuntar
fotos, sacar la captura y publicar/descartar. Se saltea si Playwright/Chromium no están.
"""
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from agente.publicador import PublicadorFacebook  # noqa: E402

PAGINA = (Path(__file__).parent / "pagina_grupo_falsa.html").as_uri()


def abrir(tmp_path, modo, confirmar=lambda m: True):
    publicador = PublicadorFacebook(tmp_path / "perfil", tmp_path / "capturas", modo, oculto=True,
                                    confirmar=confirmar, verificar_sesion=False, velocidad=0.01)
    try:
        return publicador.__enter__()
    except Exception as e:  # Chromium no instalado
        pytest.skip(f"No se pudo abrir Chromium: {e}")


@pytest.fixture
def imagen(tmp_path):
    from PIL import Image
    ruta = tmp_path / "foto.png"
    Image.new("RGB", (800, 800), "green").save(ruta)
    return ruta


def test_modo_automatico_publica(tmp_path, imagen):
    p = abrir(tmp_path, "automatico")
    try:
        res = p.publicar(PAGINA, "Hola vecinos\nHago service de PC", [imagen])
        publicado = p.page.locator("#publicado").inner_text()
    finally:
        p.__exit__(None, None, None)
    assert res.estado == "publicada", res.detalle
    assert "Hola vecinos" in publicado and "Hago service de PC" in publicado
    assert publicado.endswith("fotos:1")
    assert res.captura.is_file()


def test_modo_simulacion_no_publica(tmp_path, imagen):
    p = abrir(tmp_path, "simulacion")
    try:
        res = p.publicar(PAGINA, "Texto de prueba", [imagen])
        publicado = p.page.locator("#publicado").inner_text()
    finally:
        p.__exit__(None, None, None)
    assert res.estado == "simulada"
    assert publicado == ""
    assert res.captura.is_file()


def test_modo_asistido_respeta_la_decision_del_usuario(tmp_path):
    p = abrir(tmp_path, "asistido", confirmar=lambda m: False)
    try:
        res = p.publicar(PAGINA, "Texto de prueba", [])
    finally:
        p.__exit__(None, None, None)
    assert res.estado == "no_confirmada"


def test_detecta_bloqueo(tmp_path):
    pagina = tmp_path / "bloqueo.html"
    pagina.write_text("<html><body>Estás bloqueado temporalmente</body></html>", encoding="utf-8")
    p = abrir(tmp_path, "automatico")
    try:
        res = p.publicar(pagina.as_uri(), "x", [])
    finally:
        p.__exit__(None, None, None)
    assert res.estado == "bloqueada"
