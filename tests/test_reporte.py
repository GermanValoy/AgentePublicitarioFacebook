from agente import antiban, reporte
from agente.publicaciones import cargar_publicaciones

from .conftest import momento

CALENDARIO = """
publicaciones:
  - id: promo
    fecha: 2026-10-05
    hora: "10:00"
    grupos: [Grupo A]
    texto: "Hola vecinos, hago mantenimiento de PC y notebooks. Escribime por privado."
"""


def test_reporte_con_movimientos_sin_datos_privados(proyecto, historial):
    config = proyecto(programadas=CALENDARIO)
    ahora = momento(config, "2026-10-03 12:00")
    historial.agregar("promo|Grupo A|x", "promo", "Grupo A", "publicada", momento(config, "2026-10-03 10:05"),
                      detalle=r"Publicada | captura: C:\Users\German\Agente\datos\capturas\20261003-publicada.png")
    historial.agregar("promo|Grupo B|x", "promo", "Grupo B", "fallida", momento(config, "2026-10-03 11:00"),
                      detalle="Error en /home/german/agente/datos/x.png")
    config.carpeta_datos.mkdir(exist_ok=True)
    (config.carpeta_datos / "agente.log").write_text(
        "2026-10-03 11:00:00 INFO     Abriendo el grupo https://www.facebook.com/groups/aaa\n"
        "2026-10-03 11:00:05 WARNING  Telegram: fallo con bot123456789:AAG0aEgI8wISyT2QhvAyMlNSm6441bPIUo0\n",
        encoding="utf-8")
    texto = reporte.generar(config, historial, cargar_publicaciones(config.archivo_programadas),
                            telegram_conectado=True, aprobaciones_pendientes=1, ahora=ahora)
    assert "✅ funcionando" in texto and "conectado · 1 aprobación" in texto
    assert "| 03/10 10:05 | publicada | promo | Grupo A |" in texto
    assert "20261003-publicada.png" in texto
    assert "German" not in texto and "/home/" not in texto
    assert "AAG0aEgI8" not in texto and "[TOKEN]" in texto
    assert "05/10 10:00 | promo | Grupo A" in texto
    assert "1 fallida, 1 publicada" in texto


def test_reporte_muestra_pausa(config, historial):
    antiban.pausar(config, "Facebook mostró: bloqueado temporalmente")
    assert "PAUSADO" in reporte.generar(config, historial)


def test_escribir_crea_el_archivo(config, historial):
    ruta = reporte.escribir(config, historial)
    assert ruta == config.raiz / "reportes" / "estado.md" and ruta.read_text(encoding="utf-8").startswith("# Estado")
