"""Registro persistente de todo lo que hizo el agente (datos/historial.json)."""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass
from pathlib import Path

from .archivos import guardar_json, leer_json

# Estados que cuentan como actividad real en Facebook para los límites anti-baneo.
ESTADOS_ACTIVIDAD = {"publicada", "fallida", "bloqueada"}
# Estados que dan por terminada una tarea (no se vuelve a intentar).
ESTADOS_FINALES = {"publicada", "vencida", "omitida", "no_confirmada", "bloqueada"}


@dataclass
class Registro:
    clave: str
    publicacion_id: str
    grupo: str
    estado: str
    fecha_hora: str  # ISO 8601 con zona horaria
    texto: str = ""
    detalle: str = ""

    @property
    def momento(self) -> dt.datetime:
        return dt.datetime.fromisoformat(self.fecha_hora)


class Historial:
    def __init__(self, archivo: Path):
        self.archivo = archivo
        self.registros: list[Registro] = []
        datos = leer_json(archivo, [])
        self.registros = [Registro(**r) for r in datos if isinstance(r, dict)] if isinstance(datos, list) else []

    def agregar(self, clave: str, publicacion_id: str, grupo: str, estado: str,
                momento: dt.datetime, texto: str = "", detalle: str = "") -> Registro:
        registro = Registro(clave, publicacion_id, grupo, estado, momento.isoformat(), texto, detalle)
        self.registros.append(registro)
        self._guardar()
        return registro

    def _guardar(self) -> None:
        guardar_json(self.archivo, [asdict(r) for r in self.registros])

    def actividad(self, grupo: str | None = None) -> list[Registro]:
        return [r for r in self.registros
                if r.estado in ESTADOS_ACTIVIDAD and (grupo is None or r.grupo == grupo)]

    def ya_procesada(self, clave: str, max_intentos: int, incluir_simuladas: bool = False) -> bool:
        propios = [r for r in self.registros if r.clave == clave]
        if any(r.estado in ESTADOS_FINALES for r in propios):
            return True
        if incluir_simuladas and any(r.estado == "simulada" for r in propios):
            return True
        return sum(r.estado == "fallida" for r in propios) >= max_intentos

    def textos_publicados(self, grupo: str | None = None, limite: int = 10) -> list[str]:
        """Últimos textos publicados en un grupo (o en cualquier grupo si grupo es None)."""
        textos = [r.texto for r in self.registros
                  if r.estado == "publicada" and r.texto and (grupo is None or r.grupo == grupo)]
        return textos[-limite:]
