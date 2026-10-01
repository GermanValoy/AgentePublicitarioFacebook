"""Reporte diario del agente (reportes/estado.md), que se sube a GitHub para revisarlo a distancia.

No incluye datos privados: ni el token de Telegram, ni la sesión de Facebook, ni rutas de la PC.
"""
from __future__ import annotations

import datetime as dt
import re
import subprocess
from pathlib import Path

from . import antiban
from .config import Config
from .historial import Historial
from .planificador import grupos_de, proxima_ocurrencia

TOKEN = re.compile(r"\d{6,12}:[A-Za-z0-9_-]{25,}")
RUTA = re.compile(r"[A-Za-z]:\\(?:[^\s|\\]+\\)+|(?<![\w:/.])/(?:[^\s|/]+/)+")
NIVELES = re.compile(r"\b(WARNING|ERROR|CRITICAL)\b")


def archivo(config: Config) -> Path:
    return config.raiz / "reportes" / "estado.md"


def _limpiar(texto: str) -> str:
    """Quita tokens y rutas de carpetas de la PC (deja solo el nombre del archivo)."""
    return RUTA.sub("", TOKEN.sub("[TOKEN]", texto)).replace("\n", " ").strip()


def _version(config: Config) -> str:
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%h (%cd)", "--date=format:%d/%m %H:%M"],
                           cwd=config.raiz, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or "desconocida"
    except Exception:
        return "desconocida"


def _errores_recientes(config: Config, cantidad: int = 10) -> list[str]:
    log = config.carpeta_datos / "agente.log"
    if not log.is_file():
        return []
    lineas = log.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:]
    return [_limpiar(l)[:220] for l in lineas if NIVELES.search(l)][-cantidad:]


def generar(config: Config, historial: Historial, publicaciones=(), telegram_conectado: bool = False,
            aprobaciones_pendientes: int = 0, ahora: dt.datetime | None = None) -> str:
    ahora = ahora or config.ahora()
    pausa = antiban.pausa_activa(config)
    actividad = historial.actividad()
    hace_7 = ahora - dt.timedelta(days=7)
    semana = [r for r in historial.registros if r.momento >= hace_7]
    conteo = {}
    for r in semana:
        conteo[r.estado] = conteo.get(r.estado, 0) + 1
    hoy = [r for r in actividad if r.momento.astimezone(config.zona).date() == ahora.date()]

    l = [
        "# Estado del agente",
        "",
        f"_Actualizado: {ahora:%d/%m/%Y %H:%M} ({config.zona.key}). "
        "Si esta fecha tiene más de un día, el agente probablemente no está funcionando._",
        "",
        f"- **Estado:** {'⏸️ PAUSADO — ' + _limpiar(pausa) if pausa else '✅ funcionando'}",
        f"- **Modo:** {config.modo}",
        f"- **Telegram:** {'conectado' if telegram_conectado else 'no configurado'}"
        + (f" · {aprobaciones_pendientes} aprobación(es) esperando respuesta" if aprobaciones_pendientes else ""),
        f"- **Versión del agente:** {_version(config)}",
        f"- **Publicaciones hoy:** {len(hoy)}/{config.limites.max_publicaciones_por_dia}",
        "- **Últimos 7 días:** " + (", ".join(f"{v} {k}" for k, v in sorted(conteo.items())) or "sin movimientos"),
        "",
        "## Próximas programadas",
        "",
    ]
    proximas = sorted(((proxima_ocurrencia(p, config, ahora), p) for p in publicaciones if p.activa),
                      key=lambda x: (x[0] is None, x[0] or ahora))
    filas = [f"| {m:%d/%m %H:%M} | {p.id} | {', '.join(grupos_de(p, config))} |" for m, p in proximas if m][:10]
    l += (["| Cuándo | Publicación | Grupos |", "|---|---|---|", *filas] if filas else ["(ninguna)"])

    l += ["", "## Últimos movimientos", ""]
    ultimos = historial.registros[-15:]
    if ultimos:
        l += ["| Fecha | Estado | Publicación | Grupo | Detalle |", "|---|---|---|---|---|"]
        for r in reversed(ultimos):
            detalle = _limpiar(r.detalle)[:120].replace("|", "/")
            l.append(f"| {r.momento.astimezone(config.zona):%d/%m %H:%M} | {r.estado} | {r.publicacion_id} | "
                     f"{r.grupo} | {detalle} |")
    else:
        l.append("(ninguno)")

    l += ["", "## Avisos y errores recientes del registro", ""]
    errores = _errores_recientes(config)
    l += [f"- `{e}`" for e in errores] if errores else ["(ninguno)"]
    return "\n".join(l) + "\n"


def escribir(config: Config, historial: Historial, **kwargs) -> Path:
    destino = archivo(config)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(generar(config, historial, **kwargs), encoding="utf-8")
    return destino
