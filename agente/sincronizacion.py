"""Sincronización de la carpeta del proyecto con GitHub.

- Sube lo que dejás en la PC (fotos nuevas en publicaciones/imagenes/, ideas en publicaciones/ideas.txt).
- Baja lo que prepara Claude (publicaciones nuevas, imágenes, mejoras del agente).

Nunca sube la carpeta datos/ (tu sesión de Facebook): está en .gitignore y además no se agrega.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger("agente")

RUTAS_A_SUBIR = ["publicaciones", "config", "reportes"]
IDENTIDAD = ["-c", "user.name=Agente (PC)", "-c", "user.email=agente-pc@users.noreply.github.com"]


class ErrorSincronizacion(Exception):
    pass


def _git(raiz: Path, *args: str, revisar: bool = True) -> subprocess.CompletedProcess:
    try:
        resultado = subprocess.run(["git", *args], cwd=raiz, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=180)
    except FileNotFoundError:
        raise ErrorSincronizacion("Git no está instalado (descargalo de https://git-scm.com)") from None
    except subprocess.TimeoutExpired:
        raise ErrorSincronizacion(f"git {args[0]} tardó demasiado (¿hay internet?)") from None
    if revisar and resultado.returncode != 0:
        raise ErrorSincronizacion(f"git {args[0]} falló: {(resultado.stderr or resultado.stdout).strip()}")
    return resultado


def conectado(raiz: Path) -> bool:
    return (raiz / ".git").exists()


def sincronizar(raiz: Path) -> str:
    """Sube los cambios locales y baja los remotos. Devuelve un resumen de lo que pasó."""
    if not conectado(raiz):
        return "La carpeta no está conectada a GitHub (ejecutá conectar_github.bat)"

    rutas = [r for r in RUTAS_A_SUBIR if (raiz / r).exists()]
    _git(raiz, "add", "--", *rutas)
    hay_locales = _git(raiz, "diff", "--cached", "--quiet", revisar=False).returncode == 1
    if hay_locales:
        _git(raiz, *IDENTIDAD, "commit", "-q", "-m", "Cambios desde la PC (fotos, ideas y reporte)")

    antes = _git(raiz, "rev-parse", "HEAD").stdout.strip()
    bajada = _git(raiz, *IDENTIDAD, "pull", "--rebase", "--autostash", "-q", revisar=False)
    if bajada.returncode != 0:
        _git(raiz, "rebase", "--abort", revisar=False)
        raise ErrorSincronizacion("Tus cambios y los de GitHub chocan en el mismo archivo. Se siguen usando "
                                  "los archivos de la PC; pedile a Claude que lo resuelva. Detalle: "
                                  + (bajada.stderr or bajada.stdout).strip())
    despues = _git(raiz, "rev-parse", "HEAD").stdout.strip()

    partes = []
    pendientes = _git(raiz, "rev-list", "--count", "@{u}..HEAD", revisar=False).stdout.strip()
    if pendientes not in ("", "0"):
        _git(raiz, "push", "-q")
        partes.append("se subieron tus fotos/ideas a GitHub")
    if antes != despues:
        cambios = _git(raiz, "diff", "--name-only", antes, despues).stdout.split()
        partes.append(f"se bajaron {len(cambios)} archivos nuevos o actualizados")
        if any(c.startswith("agente/") or c == "requirements.txt" for c in cambios):
            partes.append("hay una versión nueva del agente: cerralo y abrilo de nuevo para usarla")
    return "; ".join(partes) or "todo al día"
