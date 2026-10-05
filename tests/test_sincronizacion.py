"""Simula la PC y GitHub con repositorios locales (no usa internet)."""
import shutil
import subprocess

import pytest

from agente.sincronizacion import sincronizar

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git no instalado")

IDENTIDAD = ["-c", "user.name=Prueba", "-c", "user.email=prueba@example.com"]


def git(carpeta, *args):
    return subprocess.run(["git", *IDENTIDAD, *args], cwd=carpeta, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repos(tmp_path):
    github = tmp_path / "github.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(github))
    claude = tmp_path / "claude"
    git(tmp_path, "clone", "-q", str(github), str(claude))
    (claude / "publicaciones" / "imagenes").mkdir(parents=True)
    (claude / "publicaciones" / "programadas.yaml").write_text("publicaciones: []\n")
    (claude / "publicaciones" / "imagenes" / ".gitkeep").write_text("")
    (claude / ".gitignore").write_text("datos/\n")
    git(claude, "add", "-A")
    git(claude, "commit", "-q", "-m", "inicio")
    git(claude, "push", "-q", "-u", "origin", "main")
    pc = tmp_path / "pc"
    git(tmp_path, "clone", "-q", str(github), str(pc))
    return claude, pc


def test_sin_cambios(repos):
    _, pc = repos
    assert sincronizar(pc) == "todo al día"


def test_sube_fotos_de_la_pc_pero_nunca_datos(repos):
    claude, pc = repos
    (pc / "publicaciones" / "imagenes" / "foto-local.jpg").write_bytes(b"foto")
    (pc / "datos").mkdir()
    (pc / "datos" / "sesion.txt").write_text("secreto")
    assert "subieron" in sincronizar(pc)
    git(claude, "pull", "-q")
    assert (claude / "publicaciones" / "imagenes" / "foto-local.jpg").exists()
    assert not (claude / "datos").exists()


def test_baja_lo_nuevo_y_avisa_si_cambio_el_agente(repos):
    claude, pc = repos
    (claude / "publicaciones" / "programadas.yaml").write_text("publicaciones: [nueva]\n")
    (claude / "agente").mkdir()
    (claude / "agente" / "mejora.py").write_text("x = 1\n")
    git(claude, "add", "-A")
    git(claude, "commit", "-q", "-m", "nuevas publicaciones")
    git(claude, "push", "-q")
    resumen = sincronizar(pc)
    assert "2 archivos" in resumen and "versión nueva" in resumen
    assert "nueva" in (pc / "publicaciones" / "programadas.yaml").read_text()


def test_cambios_en_ambos_lados_sin_choque(repos):
    claude, pc = repos
    (claude / "publicaciones" / "programadas.yaml").write_text("publicaciones: [semana]\n")
    git(claude, "commit", "-qam", "semana")
    git(claude, "push", "-q")
    (pc / "publicaciones" / "imagenes" / "local.jpg").write_bytes(b"x")
    resumen = sincronizar(pc)
    assert "subieron" in resumen and "bajaron" in resumen


def test_quita_candados_viejos_de_git(repos):
    import os
    import time
    _, pc = repos
    candado = pc / ".git" / "HEAD.lock"
    candado.write_text("")
    viejo = time.time() - 3600
    os.utime(candado, (viejo, viejo))
    (pc / "publicaciones" / "imagenes" / "nueva.jpg").write_bytes(b"x")
    assert "subieron" in sincronizar(pc)
    assert not candado.exists()
