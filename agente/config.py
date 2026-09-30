"""Carga y validación de config/config.yaml."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

RAIZ = Path(__file__).resolve().parent.parent
MODOS = ("simulacion", "asistido", "aprobacion", "automatico")
NAVEGADORES = ("chromium", "chrome", "msedge")
DIAS = {
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
}


class ErrorConfig(Exception):
    """Error en algún archivo de configuración escrito por el usuario."""


def leer_yaml(archivo: Path) -> dict:
    if not archivo.is_file():
        raise ErrorConfig(f"No existe el archivo {archivo}")
    try:
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ErrorConfig(f"{archivo.name} tiene un error de formato: {e}") from None
    if not isinstance(datos, dict):
        raise ErrorConfig(f"{archivo.name} debe contener claves y valores")
    return datos


def convertir_hora(valor, campo: str) -> dt.time:
    if isinstance(valor, dt.time):
        return valor
    try:
        if isinstance(valor, int):
            # YAML interpreta 10:30 sin comillas como el número 630 (minutos).
            return dt.time(valor // 60, valor % 60)
        return dt.datetime.strptime(str(valor).strip(), "%H:%M").time()
    except ValueError:
        raise ErrorConfig(f"{campo}: hora inválida '{valor}', usá el formato \"HH:MM\"") from None


def convertir_dias(valor, campo: str) -> list[int] | None:
    if valor is None:
        return None
    if isinstance(valor, str):
        valor = [valor]
    dias = []
    for d in valor:
        clave = str(d).strip().lower()
        if clave not in DIAS:
            raise ErrorConfig(f"{campo}: día desconocido '{d}' (usá lunes, martes, ...)")
        dias.append(DIAS[clave])
    return dias


@dataclass
class Grupo:
    nombre: str
    url: str
    activo: bool = True
    dias_permitidos: list[int] | None = None  # 0 = lunes; None = todos los días
    notas: str = ""


@dataclass
class Limites:
    max_publicaciones_por_dia: int = 3
    min_minutos_entre_publicaciones: int = 45
    dias_entre_publicaciones_mismo_grupo: int = 7
    horario_desde: dt.time = dt.time(9, 0)
    horario_hasta: dt.time = dt.time(21, 0)
    demora_aleatoria_min_seg: int = 30
    demora_aleatoria_max_seg: int = 300
    max_horas_retraso: int = 12
    max_intentos: int = 2


@dataclass
class ReglasContenido:
    min_caracteres: int = 30
    max_caracteres: int = 1500
    max_enlaces: int = 1
    max_hashtags: int = 5
    max_imagenes: int = 4
    max_mb_imagen: float = 8
    min_lado_imagen: int = 400
    similitud_maxima: float = 0.85
    palabras_prohibidas: list[str] = field(default_factory=list)


@dataclass
class Config:
    raiz: Path
    zona: ZoneInfo
    modo: str
    navegador: str
    limites: Limites
    contenido: ReglasContenido
    grupos: dict[str, Grupo]

    @property
    def carpeta_imagenes(self) -> Path:
        return self.raiz / "publicaciones" / "imagenes"

    @property
    def archivo_programadas(self) -> Path:
        return self.raiz / "publicaciones" / "programadas.yaml"

    @property
    def carpeta_datos(self) -> Path:
        return self.raiz / "datos"

    def ahora(self) -> dt.datetime:
        return dt.datetime.now(self.zona)


def _numero(seccion: dict, clave: str, defecto, campo: str, minimo=0):
    valor = seccion.get(clave, defecto)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor < minimo:
        raise ErrorConfig(f"{campo}.{clave} debe ser un número mayor o igual a {minimo}")
    return type(defecto)(valor)


def cargar_config(raiz: Path = RAIZ, archivo: Path | None = None) -> Config:
    datos = leer_yaml(archivo or raiz / "config" / "config.yaml")

    try:
        zona = ZoneInfo(str(datos.get("zona_horaria", "America/Argentina/Buenos_Aires")))
    except (ZoneInfoNotFoundError, ValueError):
        raise ErrorConfig(f"zona_horaria desconocida: {datos.get('zona_horaria')}") from None

    modo = str(datos.get("modo", "asistido")).strip().lower()
    if modo not in MODOS:
        raise ErrorConfig(f"modo debe ser uno de: {', '.join(MODOS)}")
    navegador = str(datos.get("navegador", "chromium")).strip().lower()
    if navegador not in NAVEGADORES:
        raise ErrorConfig(f"navegador debe ser uno de: {', '.join(NAVEGADORES)}")

    l = datos.get("limites") or {}
    d = Limites()
    horario = l.get("horario_permitido") or {}
    demora = l.get("demora_aleatoria_segundos") or [d.demora_aleatoria_min_seg, d.demora_aleatoria_max_seg]
    if not (isinstance(demora, list) and len(demora) == 2 and 0 <= demora[0] <= demora[1]):
        raise ErrorConfig("limites.demora_aleatoria_segundos debe ser [mínimo, máximo]")
    limites = Limites(
        max_publicaciones_por_dia=_numero(l, "max_publicaciones_por_dia", d.max_publicaciones_por_dia, "limites", 1),
        min_minutos_entre_publicaciones=_numero(l, "min_minutos_entre_publicaciones", d.min_minutos_entre_publicaciones, "limites"),
        dias_entre_publicaciones_mismo_grupo=_numero(l, "dias_entre_publicaciones_mismo_grupo", d.dias_entre_publicaciones_mismo_grupo, "limites"),
        horario_desde=convertir_hora(horario.get("desde", "09:00"), "limites.horario_permitido.desde"),
        horario_hasta=convertir_hora(horario.get("hasta", "21:00"), "limites.horario_permitido.hasta"),
        demora_aleatoria_min_seg=int(demora[0]),
        demora_aleatoria_max_seg=int(demora[1]),
        max_horas_retraso=_numero(l, "max_horas_retraso", d.max_horas_retraso, "limites", 1),
        max_intentos=_numero(l, "max_intentos", d.max_intentos, "limites", 1),
    )
    if limites.horario_desde >= limites.horario_hasta:
        raise ErrorConfig("limites.horario_permitido: 'desde' debe ser anterior a 'hasta'")

    c = datos.get("contenido") or {}
    r = ReglasContenido()
    prohibidas = c.get("palabras_prohibidas") or []
    if not isinstance(prohibidas, list):
        raise ErrorConfig("contenido.palabras_prohibidas debe ser una lista")
    contenido = ReglasContenido(
        min_caracteres=_numero(c, "min_caracteres", r.min_caracteres, "contenido"),
        max_caracteres=_numero(c, "max_caracteres", r.max_caracteres, "contenido", 1),
        max_enlaces=_numero(c, "max_enlaces", r.max_enlaces, "contenido"),
        max_hashtags=_numero(c, "max_hashtags", r.max_hashtags, "contenido"),
        max_imagenes=_numero(c, "max_imagenes", r.max_imagenes, "contenido"),
        max_mb_imagen=_numero(c, "max_mb_imagen", r.max_mb_imagen, "contenido"),
        min_lado_imagen=_numero(c, "min_lado_imagen", r.min_lado_imagen, "contenido"),
        similitud_maxima=_numero(c, "similitud_maxima", r.similitud_maxima, "contenido"),
        palabras_prohibidas=[str(p).lower() for p in prohibidas],
    )

    grupos: dict[str, Grupo] = {}
    for i, g in enumerate(datos.get("grupos") or [], start=1):
        campo = f"grupos[{i}]"
        if not isinstance(g, dict) or not g.get("nombre") or not g.get("url"):
            raise ErrorConfig(f"{campo}: cada grupo necesita 'nombre' y 'url'")
        nombre, url = str(g["nombre"]).strip(), str(g["url"]).strip()
        if not url.startswith(("https://www.facebook.com/groups/", "https://facebook.com/groups/")):
            raise ErrorConfig(f"{campo} ({nombre}): la url debe empezar con https://www.facebook.com/groups/")
        if nombre in grupos:
            raise ErrorConfig(f"{campo}: el grupo '{nombre}' está repetido")
        grupos[nombre] = Grupo(
            nombre=nombre,
            url=url,
            activo=bool(g.get("activo", True)),
            dias_permitidos=convertir_dias(g.get("dias_permitidos"), f"{campo}.dias_permitidos"),
            notas=str(g.get("notas", "")),
        )

    return Config(raiz=raiz, zona=zona, modo=modo, navegador=navegador, limites=limites, contenido=contenido, grupos=grupos)
