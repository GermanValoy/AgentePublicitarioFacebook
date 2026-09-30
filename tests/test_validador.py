import datetime as dt

from agente.publicaciones import Publicacion
from agente.validador import validar_publicacion, validar_todas

from .conftest import momento

TEXTO_OK = "{Hola|Buenas}! Hago mantenimiento de computadoras y notebooks. Escribime."


def pub(**cambios):
    datos = dict(id="p1", fecha=dt.date(2026, 10, 5), hora=dt.time(10, 0), grupos=["Grupo A"],
                 texto=TEXTO_OK, imagenes=["buena.png"])
    datos.update(cambios)
    return Publicacion(**datos)


def validar(config, **cambios):
    return validar_publicacion(pub(**cambios), config, momento(config, "2026-10-01 10:00"))


def test_publicacion_correcta(config):
    r = validar(config)
    assert r.ok and not r.advertencias


def test_imagen_inexistente_danada_y_formato(config, tmp_path):
    (config.carpeta_imagenes / "video.gif").write_bytes(b"GIF89a")
    r = validar(config, imagenes=["no-existe.jpg", "rota.png", "video.gif"])
    assert len(r.errores) == 3


def test_imagen_chica_es_advertencia(config):
    r = validar(config, imagenes=["chica.jpg"])
    assert r.ok and any("chica" in a for a in r.advertencias)


def test_demasiadas_imagenes(config):
    assert not validar(config, imagenes=["buena.png"] * 5).ok


def test_grupo_desconocido_e_inactivo(config):
    r = validar(config, grupos=["No existe", "Inactivo"])
    assert any("No existe" in e for e in r.errores)
    assert any("desactivado" in a for a in r.advertencias)


def test_texto_con_problemas(config):
    assert not validar(config, texto="corto").ok
    assert not validar(config, texto=TEXTO_OK + " dinero fácil").ok
    assert not validar(config, texto=TEXTO_OK + " https://a.com https://b.com").ok
    assert not validar(config, texto=TEXTO_OK + " #a #b #c #d #e #f").ok
    assert not validar(config, texto="{Hola|Buenas vecinos, hago mantenimiento de computadoras").ok
    assert not validar(config, texto="x" * 1600).ok


def test_advertencias_utiles(config):
    r = validar(config, texto="HOLA VECINOS HAGO MANTENIMIENTO DE PC", imagenes=[], hora=dt.time(23, 0))
    assert r.ok
    textos = " ".join(r.advertencias)
    for esperado in ("MAYÚSCULAS", "variaciones", "Sin imágenes", "fuera del horario"):
        assert esperado in textos


def test_dia_no_permitido_por_el_grupo(config):
    r = validar(config, grupos=["Solo Sabados"])  # 2026-10-05 es lunes
    assert any("día" in a for a in r.advertencias)


def test_ids_repetidos(config):
    r = validar_todas([pub(), pub()], config, momento(config, "2026-10-01 10:00"))
    assert not r["p1"].ok
