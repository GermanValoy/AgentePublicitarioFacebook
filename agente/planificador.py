"""Convierte el calendario en tareas concretas (una publicación en un grupo)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .config import Config
from .historial import Historial
from .publicaciones import Publicacion


@dataclass(frozen=True)
class Tarea:
    publicacion: Publicacion
    grupo: str
    programada_para: dt.datetime

    @property
    def clave(self) -> str:
        return f"{self.publicacion.id}|{self.grupo}|{self.programada_para.date().isoformat()}"


def grupos_de(pub: Publicacion, config: Config) -> list[str]:
    if [g.lower() for g in pub.grupos] == ["todos"]:
        return [n for n, g in config.grupos.items() if g.activo]
    return [g for g in pub.grupos if g in config.grupos and config.grupos[g].activo]


def _primera(pub: Publicacion, config: Config) -> dt.datetime:
    return dt.datetime.combine(pub.fecha, pub.hora, tzinfo=config.zona)


def ocurrencia_vigente(pub: Publicacion, config: Config, ahora: dt.datetime) -> dt.datetime | None:
    """La última fecha programada que ya llegó (o None si todavía no llegó ninguna)."""
    primera = _primera(pub, config)
    if ahora < primera:
        return None
    if not pub.repetir_cada_dias:
        return primera
    paso = dt.timedelta(days=pub.repetir_cada_dias)
    ocurrencia = primera + paso * ((ahora - primera) // paso)
    return ocurrencia - paso if ocurrencia > ahora else ocurrencia


def proxima_ocurrencia(pub: Publicacion, config: Config, ahora: dt.datetime) -> dt.datetime | None:
    primera = _primera(pub, config)
    if ahora < primera:
        return primera
    if not pub.repetir_cada_dias:
        return None
    return ocurrencia_vigente(pub, config, ahora) + dt.timedelta(days=pub.repetir_cada_dias)


def tareas_del_momento(publicaciones: list[Publicacion], config: Config, historial: Historial,
                       ahora: dt.datetime) -> tuple[list[Tarea], list[Tarea]]:
    """Devuelve (pendientes, vencidas). Vencida = se pasó el retraso máximo sin poder publicarse."""
    limite_retraso = dt.timedelta(hours=config.limites.max_horas_retraso)
    incluir_simuladas = config.modo == "simulacion"
    pendientes, vencidas = [], []
    for pub in publicaciones:
        if not pub.activa:
            continue
        ocurrencia = ocurrencia_vigente(pub, config, ahora)
        if ocurrencia is None:
            continue
        for grupo in grupos_de(pub, config):
            tarea = Tarea(pub, grupo, ocurrencia)
            if historial.ya_procesada(tarea.clave, config.limites.max_intentos, incluir_simuladas):
                continue
            (vencidas if ahora - ocurrencia > limite_retraso else pendientes).append(tarea)
    pendientes.sort(key=lambda t: (t.programada_para, t.grupo))
    return pendientes, vencidas
