"""Lectura del calendario de publicaciones (publicaciones/programadas.yaml)."""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import ErrorConfig, convertir_hora, leer_yaml

ID_VALIDO = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass
class Publicacion:
    id: str
    fecha: dt.date
    hora: dt.time
    grupos: list[str]
    texto: str
    imagenes: list[str] = field(default_factory=list)
    activa: bool = True
    repetir_cada_dias: int | None = None


def _fecha(valor, campo: str) -> dt.date:
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor
    try:
        return dt.date.fromisoformat(str(valor).strip())
    except ValueError:
        raise ErrorConfig(f"{campo}: fecha inválida '{valor}', usá el formato AAAA-MM-DD") from None


def _lista(valor) -> list[str]:
    if valor is None:
        return []
    if isinstance(valor, str):
        return [valor]
    return [str(v) for v in valor]


def cargar_publicaciones(archivo: Path) -> list[Publicacion]:
    datos = leer_yaml(archivo)
    publicaciones = []
    for i, p in enumerate(datos.get("publicaciones") or [], start=1):
        campo = f"publicaciones[{i}]"
        if not isinstance(p, dict):
            raise ErrorConfig(f"{campo}: formato inválido")
        pid = str(p.get("id", "")).strip()
        if not ID_VALIDO.match(pid):
            raise ErrorConfig(f"{campo}: 'id' obligatorio, solo letras, números, - y _")
        campo = f"publicación '{pid}'"
        for obligatorio in ("fecha", "hora", "grupos", "texto"):
            if p.get(obligatorio) in (None, "", []):
                raise ErrorConfig(f"{campo}: falta '{obligatorio}'")
        repetir = p.get("repetir_cada_dias")
        if repetir is not None and (not isinstance(repetir, int) or isinstance(repetir, bool) or repetir < 1):
            raise ErrorConfig(f"{campo}: repetir_cada_dias debe ser un número entero mayor a 0")
        publicaciones.append(Publicacion(
            id=pid,
            fecha=_fecha(p["fecha"], f"{campo}.fecha"),
            hora=convertir_hora(p["hora"], f"{campo}.hora"),
            grupos=_lista(p["grupos"]),
            texto=str(p["texto"]).strip(),
            imagenes=_lista(p.get("imagenes")),
            activa=bool(p.get("activa", True)),
            repetir_cada_dias=repetir,
        ))
    return publicaciones
