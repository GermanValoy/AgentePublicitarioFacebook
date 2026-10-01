"""Lectura y escritura segura de los archivos JSON del agente (historial, aprobaciones)."""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
from pathlib import Path

log = logging.getLogger("agente")

# Archivos dañados que se reemplazaron en esta ejecución (para avisar por Telegram).
RECUPERADOS: list[str] = []


def leer_json(archivo: Path, defecto):
    """Lee un JSON. Si está vacío o dañado (p. ej. la PC se apagó mientras se guardaba),
    lo guarda aparte como copia y devuelve `defecto` para que el agente pueda seguir."""
    if not archivo.is_file():
        return defecto
    try:
        return json.loads(archivo.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        copia = archivo.with_name(f"{archivo.stem}.danado-{dt.datetime.now():%Y%m%d-%H%M%S}{archivo.suffix}")
        try:
            os.replace(archivo, copia)
        except OSError:
            copia = archivo
        log.warning("El archivo %s estaba dañado (%s). Se guardó una copia como %s y se empezó uno nuevo.",
                    archivo.name, e, copia.name)
        RECUPERADOS.append(archivo.name)
        return defecto


def guardar_json(archivo: Path, datos) -> None:
    """Guarda de forma atómica: nunca deja el archivo a medio escribir."""
    archivo.parent.mkdir(parents=True, exist_ok=True)
    temporal = archivo.with_suffix(archivo.suffix + ".tmp")
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporal, archivo)
