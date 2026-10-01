import datetime as dt

import pytest

from agente.config import MODOS, ErrorConfig, cargar_config, convertir_hora
from agente.publicaciones import cargar_publicaciones

from .conftest import RAIZ_REPO


def test_config_de_ejemplo_del_repo_es_valida():
    config = cargar_config(RAIZ_REPO)
    assert config.modo in MODOS  # el dueño puede cambiar el modo desde su PC
    assert cargar_publicaciones(config.archivo_programadas)


def test_carga_grupos_y_dias(config):
    assert config.grupos["Solo Sabados"].dias_permitidos == [5]
    assert not config.grupos["Inactivo"].activo


def test_hora_sin_comillas_de_yaml():
    assert convertir_hora(630, "x") == dt.time(10, 30)  # YAML lee 10:30 como 630
    assert convertir_hora("09:05", "x") == dt.time(9, 5)
    with pytest.raises(ErrorConfig):
        convertir_hora("25:00", "x")


def test_url_de_grupo_invalida(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text(
        "grupos:\n  - nombre: X\n    url: https://google.com\n", encoding="utf-8")
    with pytest.raises(ErrorConfig, match="facebook.com/groups"):
        cargar_config(tmp_path)


def test_modo_invalido(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text("modo: turbo\n", encoding="utf-8")
    with pytest.raises(ErrorConfig, match="modo"):
        cargar_config(tmp_path)


def test_publicacion_sin_campos_obligatorios(proyecto):
    config = proyecto(programadas="""
        publicaciones:
          - id: sin-texto
            fecha: 2026-10-05
            hora: "10:00"
            grupos: [Grupo A]
        """)
    with pytest.raises(ErrorConfig, match="texto"):
        cargar_publicaciones(config.archivo_programadas)
