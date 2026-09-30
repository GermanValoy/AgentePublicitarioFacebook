import datetime as dt
import shutil
import textwrap
from pathlib import Path

import pytest
from PIL import Image

from agente.config import cargar_config
from agente.historial import Historial

RAIZ_REPO = Path(__file__).resolve().parent.parent

CONFIG = """
zona_horaria: America/Argentina/Buenos_Aires
modo: {modo}
limites:
  max_publicaciones_por_dia: 3
  min_minutos_entre_publicaciones: 45
  dias_entre_publicaciones_mismo_grupo: 7
  horario_permitido: {{desde: "09:00", hasta: "21:00"}}
  demora_aleatoria_segundos: [0, 0]
  max_horas_retraso: 12
  max_intentos: 2
contenido:
  palabras_prohibidas: [dinero fácil]
grupos:
  - nombre: Grupo A
    url: https://www.facebook.com/groups/aaa
  - nombre: Grupo B
    url: https://www.facebook.com/groups/bbb
  - nombre: Solo Sabados
    url: https://www.facebook.com/groups/ccc
    dias_permitidos: [sabado]
  - nombre: Inactivo
    url: https://www.facebook.com/groups/ddd
    activo: false
"""


@pytest.fixture
def proyecto(tmp_path):
    """Crea una copia mínima del proyecto en una carpeta temporal."""
    def crear(modo="asistido", programadas=""):
        (tmp_path / "config").mkdir(exist_ok=True)
        (tmp_path / "config" / "config.yaml").write_text(CONFIG.format(modo=modo), encoding="utf-8")
        imagenes = tmp_path / "publicaciones" / "imagenes"
        imagenes.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1080, 1080), "blue").save(imagenes / "buena.png")
        Image.new("RGB", (200, 200), "red").save(imagenes / "chica.jpg")
        (imagenes / "rota.png").write_bytes(b"esto no es una imagen")
        (tmp_path / "publicaciones" / "programadas.yaml").write_text(textwrap.dedent(programadas), encoding="utf-8")
        return cargar_config(tmp_path)
    return crear


@pytest.fixture
def config(proyecto):
    return proyecto()


@pytest.fixture
def historial(config):
    return Historial(config.carpeta_datos / "historial.json")


def momento(config, texto):
    """'2026-10-05 10:00' -> datetime en la zona horaria del agente."""
    return dt.datetime.strptime(texto, "%Y-%m-%d %H:%M").replace(tzinfo=config.zona)
