"""Pruebas automáticas que se corren ANTES de publicar cualquier cosa."""
from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from . import contenido as txt
from .config import Config, ReglasContenido
from .publicaciones import Publicacion

EXTENSIONES = {".jpg", ".jpeg", ".png"}
MUESTRAS_SPINTAX = 30


@dataclass
class Resultado:
    errores: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errores


def validar_imagen(ruta: Path, reglas: ReglasContenido, res: Resultado) -> None:
    nombre = ruta.name
    if not ruta.is_file():
        res.errores.append(f"No existe la imagen '{nombre}' en publicaciones/imagenes/")
        return
    if ruta.suffix.lower() not in EXTENSIONES:
        res.errores.append(f"'{nombre}': formato no admitido (usá .jpg o .png)")
        return
    mb = ruta.stat().st_size / 1_048_576
    if mb > reglas.max_mb_imagen:
        res.errores.append(f"'{nombre}' pesa {mb:.1f} MB (máximo {reglas.max_mb_imagen} MB)")
    try:
        with Image.open(ruta) as im:
            im.verify()
        with Image.open(ruta) as im:
            ancho, alto = im.size
    except Exception:
        res.errores.append(f"'{nombre}' está dañada o no es una imagen válida")
        return
    if min(ancho, alto) < reglas.min_lado_imagen:
        res.advertencias.append(f"'{nombre}' es chica ({ancho}x{alto}); se verá pixelada. "
                                f"Recomendado: 1080x1080")
    if max(ancho, alto) / min(ancho, alto) > 3:
        res.advertencias.append(f"'{nombre}' es muy alargada ({ancho}x{alto}); Facebook la recortará")


def validar_texto(plantilla: str, reglas: ReglasContenido, res: Resultado) -> None:
    if not txt.llaves_balanceadas(plantilla):
        res.errores.append("El texto tiene llaves { } sin cerrar (revisá las variaciones {a|b})")
        return
    minusculas = plantilla.lower()
    for palabra in reglas.palabras_prohibidas:
        if palabra in minusculas:
            res.errores.append(f"El texto contiene la palabra prohibida '{palabra}'")

    rng = random.Random(0)
    muestras = {txt.expandir_spintax(plantilla, rng) for _ in range(MUESTRAS_SPINTAX)}
    largos = [len(m) for m in muestras]
    if max(largos) > reglas.max_caracteres:
        res.errores.append(f"El texto puede llegar a {max(largos)} caracteres (máximo {reglas.max_caracteres})")
    if min(largos) < reglas.min_caracteres:
        res.errores.append(f"El texto es muy corto ({min(largos)} caracteres, mínimo {reglas.min_caracteres})")
    enlaces = max(txt.contar_enlaces(m) for m in muestras)
    if enlaces > reglas.max_enlaces:
        res.errores.append(f"El texto tiene {enlaces} enlaces (máximo {reglas.max_enlaces}); "
                           f"muchos enlaces activan el filtro de spam")
    hashtags = max(txt.contar_hashtags(m) for m in muestras)
    if hashtags > reglas.max_hashtags:
        res.errores.append(f"El texto tiene {hashtags} hashtags (máximo {reglas.max_hashtags})")
    if max(txt.proporcion_mayusculas(m) for m in muestras) > 0.5:
        res.advertencias.append("Más de la mitad del texto está en MAYÚSCULAS; parece spam")
    if len(muestras) == 1:
        res.advertencias.append("El texto no tiene variaciones {opción1|opción2}: se publicará idéntico "
                                "en todos los grupos (Facebook detecta textos repetidos)")


def validar_publicacion(pub: Publicacion, config: Config, ahora: dt.datetime) -> Resultado:
    res = Resultado()
    reglas = config.contenido

    if [g.lower() for g in pub.grupos] != ["todos"]:
        for grupo in pub.grupos:
            g = config.grupos.get(grupo)
            if g is None:
                res.errores.append(f"El grupo '{grupo}' no está en config/config.yaml")
            elif not g.activo:
                res.advertencias.append(f"El grupo '{grupo}' está desactivado; se ignorará")
            elif g.dias_permitidos is not None and not pub.repetir_cada_dias \
                    and pub.fecha.weekday() not in g.dias_permitidos:
                res.advertencias.append(f"El grupo '{grupo}' no permite publicar ese día de la semana")

    if not pub.imagenes:
        res.advertencias.append("Sin imágenes: las publicaciones con foto reciben mucha más atención")
    if len(pub.imagenes) > reglas.max_imagenes:
        res.errores.append(f"Tiene {len(pub.imagenes)} imágenes (máximo {reglas.max_imagenes})")
    for nombre in pub.imagenes:
        validar_imagen(config.carpeta_imagenes / nombre, reglas, res)

    validar_texto(pub.texto, reglas, res)

    lim = config.limites
    if not lim.horario_desde <= pub.hora <= lim.horario_hasta:
        res.advertencias.append(f"La hora {pub.hora:%H:%M} está fuera del horario permitido "
                                f"({lim.horario_desde:%H:%M}-{lim.horario_hasta:%H:%M})")
    momento = dt.datetime.combine(pub.fecha, pub.hora, tzinfo=config.zona)
    if not pub.repetir_cada_dias and ahora - momento > dt.timedelta(hours=lim.max_horas_retraso):
        res.advertencias.append("La fecha ya pasó hace rato: esta publicación no se va a publicar")
    return res


def validar_todas(publicaciones: list[Publicacion], config: Config, ahora: dt.datetime) -> dict[str, Resultado]:
    resultados = {}
    for pub in publicaciones:
        if pub.id in resultados:
            resultados[pub.id].errores.append(f"El id '{pub.id}' está repetido")
            continue
        resultados[pub.id] = validar_publicacion(pub, config, ahora)
    return resultados
