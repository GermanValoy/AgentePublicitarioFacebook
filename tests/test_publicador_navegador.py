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


@pytest.mark.parametrize("variante", ["selector", "zona"])
def test_adjunta_fotos_en_todas_las_variantes_de_facebook(tmp_path, imagen, variante):
    p = abrir(tmp_path, "automatico")
    try:
        res = p.publicar(f"{PAGINA}?fotos={variante}", "Hola vecinos", [imagen, imagen])
        publicado = p.page.locator("#publicado").inner_text()
    finally:
        p.__exit__(None, None, None)
    assert res.estado == "publicada", res.detalle
    assert publicado.endswith("fotos:2")


def test_avisa_si_la_foto_no_aparece_y_guarda_diagnostico(tmp_path, imagen, monkeypatch):
    import agente.publicador as modulo
    reloj = iter(range(0, 10_000, 10))
    monkeypatch.setattr(modulo.time, "monotonic", lambda: next(reloj))  # no esperar 30 s de verdad
    p = abrir(tmp_path, "simulacion")
    try:
        res = p.publicar(f"{PAGINA}?fotos=nada", "Hola vecinos", [imagen])
    finally:
        p.__exit__(None, None, None)
    assert res.estado == "error_navegador" and "vista previa" in res.detalle  # no se publicó nada
    assert res.captura and res.captura.is_file()
    assert list((tmp_path / "capturas").glob("*error-imagenes.html"))


def test_texto_largo_no_se_corta_por_tiempo(tmp_path):
    """Un texto largo escrito a ritmo humano tarda más que el límite normal de espera de Playwright."""
    p = abrir(tmp_path, "automatico")
    p.velocidad = 0.3
    p.page.set_default_timeout(2_000)  # simula el límite de 30 s con un texto más corto
    texto = "\n".join(f"Línea {i}: reparación y mantenimiento de computadoras ✅" for i in range(8))
    try:
        res = p.publicar(PAGINA, texto, [])
        publicado = p.page.locator("#publicado").inner_text()
    finally:
        p.__exit__(None, None, None)
    assert res.estado == "publicada", res.detalle
    assert "Línea 7" in publicado


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


PAGINA_VENTA = (Path(__file__).parent / "pagina_grupo_venta_falsa.html").as_uri()
TEXTO_VENTA = "✅ REPARACIÓN DE NOTEBOOKS Y PC ✅\n\nHago limpieza y formateo.\n📲 WhatsApp: 381 649-6790"


def abrir_venta(tmp_path, modo, venta=None):
    publicador = PublicadorFacebook(tmp_path / "perfil", tmp_path / "capturas", modo, oculto=True,
                                    verificar_sesion=False, velocidad=0.01,
                                    venta={"precio": "15000", "estado": ""} if venta is None else venta,
                                    carpeta_diagnostico=tmp_path / "reportes")
    try:
        return publicador.__enter__()
    except Exception as e:
        pytest.skip(f"No se pudo abrir Chromium: {e}")


def test_grupo_de_compraventa_publica_articulo_en_venta(tmp_path, imagen):
    p = abrir_venta(tmp_path, "automatico")
    try:
        res = p.publicar(PAGINA_VENTA, TEXTO_VENTA, [imagen])
        publicado = p.page.locator("#publicado").inner_text()
    finally:
        p.__exit__(None, None, None)
    assert res.estado == "publicada", res.detalle
    titulo, precio, estado, descripcion, fotos = publicado.split(" | ")
    assert titulo == "REPARACIÓN DE NOTEBOOKS Y PC"  # primera línea sin emojis
    assert precio == "15000" and estado == "Nuevo" and fotos == "fotos:1"
    assert "Hago limpieza y formateo." in descripcion and "381 649-6790" in descripcion
    lista = (tmp_path / "reportes" / "diagnostico-venta-formulario.txt").read_text(encoding="utf-8")
    assert "Título" in lista and "15000" not in lista  # lista los campos, no lo escrito


def test_compraventa_en_simulacion_no_publica(tmp_path, imagen):
    p = abrir_venta(tmp_path, "simulacion")
    try:
        res = p.publicar(PAGINA_VENTA, TEXTO_VENTA, [imagen])
        publicado = p.page.locator("#publicado").inner_text()
    finally:
        p.__exit__(None, None, None)
    assert res.estado == "simulada", res.detalle
    assert publicado == ""


def test_compraventa_sin_precio_avisa(tmp_path, imagen):
    p = abrir_venta(tmp_path, "automatico", venta={})
    try:
        res = p.publicar(PAGINA_VENTA, TEXTO_VENTA, [imagen])
    finally:
        p.__exit__(None, None, None)
    assert res.estado == "error_navegador" and "precio" in res.detalle


def test_titulo_de_texto():
    assert PublicadorFacebook.titulo_de("\n🔧 {no} \n✅ SERVICIO TÉCNICO ✅\nresto") == "SERVICIO TÉCNICO"
