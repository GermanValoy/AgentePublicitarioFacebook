"""Reglas anti-baneo: decide si en este momento se puede publicar en un grupo."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .config import Config
from .historial import Historial

NOMBRES_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


@dataclass
class Decision:
    permitido: bool
    motivo: str = ""


def _archivo_pausa(config: Config):
    return config.carpeta_datos / "PAUSADO"


def pausar(config: Config, motivo: str) -> None:
    """Freno de emergencia: nada se publica hasta ejecutar `python -m agente reanudar`."""
    archivo = _archivo_pausa(config)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(f"{config.ahora():%Y-%m-%d %H:%M} - {motivo}\n", encoding="utf-8")


def pausa_activa(config: Config) -> str | None:
    archivo = _archivo_pausa(config)
    return archivo.read_text(encoding="utf-8").strip() if archivo.is_file() else None


def reanudar(config: Config) -> None:
    _archivo_pausa(config).unlink(missing_ok=True)


def evaluar(ahora: dt.datetime, grupo: str, config: Config, historial: Historial) -> Decision:
    lim = config.limites
    ahora = ahora.astimezone(config.zona)

    motivo_pausa = pausa_activa(config)
    if motivo_pausa:
        return Decision(False, f"Agente pausado ({motivo_pausa}). Revisá tu cuenta y ejecutá: python -m agente reanudar")

    if not lim.horario_desde <= ahora.time() <= lim.horario_hasta:
        return Decision(False, f"Fuera del horario permitido ({lim.horario_desde:%H:%M}-{lim.horario_hasta:%H:%M})")

    g = config.grupos.get(grupo)
    if g is None or not g.activo:
        return Decision(False, f"El grupo '{grupo}' no existe o está desactivado")
    if g.dias_permitidos is not None and ahora.weekday() not in g.dias_permitidos:
        dias = ", ".join(NOMBRES_DIAS[d] for d in g.dias_permitidos)
        return Decision(False, f"'{grupo}' solo permite publicar: {dias}")

    actividad = historial.actividad()
    hoy = [r for r in actividad if r.momento.astimezone(config.zona).date() == ahora.date()]
    if len(hoy) >= lim.max_publicaciones_por_dia:
        return Decision(False, f"Ya se hicieron {len(hoy)} publicaciones hoy (máximo {lim.max_publicaciones_por_dia})")

    if actividad:
        ultima = max(r.momento for r in actividad)
        proxima = ultima + dt.timedelta(minutes=lim.min_minutos_entre_publicaciones)
        if ahora < proxima:
            return Decision(False, f"Hay que esperar entre publicaciones; se puede de nuevo a las "
                                   f"{proxima.astimezone(config.zona):%H:%M}")

    en_grupo = historial.actividad(grupo)
    if en_grupo:
        ultima = max(r.momento for r in en_grupo)
        proxima = ultima + dt.timedelta(days=lim.dias_entre_publicaciones_mismo_grupo)
        if ahora < proxima:
            return Decision(False, f"Ya se publicó en '{grupo}' hace poco; se puede de nuevo desde el "
                                   f"{proxima.astimezone(config.zona):%d/%m %H:%M}")

    return Decision(True)
