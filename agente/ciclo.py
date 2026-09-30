"""Una pasada del agente: valida, elige la próxima tarea permitida y la publica (máximo una)."""
from __future__ import annotations

import datetime as dt
import logging
import random
import time
from contextlib import AbstractContextManager
from typing import Callable

from . import antiban
from .config import Config
from .contenido import elegir_variante, similitud
from .historial import Historial
from .planificador import tareas_del_momento
from .publicaciones import Publicacion
from .validador import validar_todas

log = logging.getLogger("agente")

FabricaPublicador = Callable[[], AbstractContextManager]


def ejecutar_ciclo(config: Config, publicaciones: list[Publicacion], historial: Historial,
                   fabrica_publicador: FabricaPublicador, ahora: dt.datetime | None = None,
                   rng: random.Random | None = None,
                   esperar: Callable[[float], None] = time.sleep) -> str | None:
    """Devuelve el estado de la publicación realizada, o None si no se hizo nada."""
    hora_fija = ahora is not None
    ahora = ahora or config.ahora()
    rng = rng or random.Random()

    motivo = antiban.pausa_activa(config)
    if motivo:
        log.warning("Agente pausado: %s. Ejecutá 'python -m agente reanudar' cuando revises tu cuenta.", motivo)
        return None

    resultados = validar_todas(publicaciones, config, ahora)
    pendientes, vencidas = tareas_del_momento(publicaciones, config, historial, ahora)

    for t in vencidas:
        historial.agregar(t.clave, t.publicacion.id, t.grupo, "vencida", ahora,
                          detalle="Pasó el retraso máximo sin poder publicarse (se evita publicar en ráfaga)")
        log.info("Vencida: '%s' en '%s'", t.publicacion.id, t.grupo)

    for t in pendientes:
        pub = t.publicacion
        resultado = resultados[pub.id]
        if not resultado.ok:
            log.error("'%s' no pasó las pruebas y no se publica: %s", pub.id, "; ".join(resultado.errores))
            continue

        decision = antiban.evaluar(ahora, t.grupo, config, historial)
        if not decision.permitido:
            log.info("En espera '%s' -> '%s': %s", pub.id, t.grupo, decision.motivo)
            continue

        # Se elige la variante más distinta a lo publicado recientemente en TODOS los grupos,
        # pero solo se descarta si se parece demasiado a algo ya publicado en ESTE grupo.
        previos_grupo = historial.textos_publicados(t.grupo)
        texto, _ = elegir_variante(pub.texto, previos_grupo + historial.textos_publicados(limite=5), rng)
        sim = max((similitud(texto, p) for p in previos_grupo), default=0.0)
        if sim > config.contenido.similitud_maxima:
            historial.agregar(t.clave, pub.id, t.grupo, "omitida", ahora, texto,
                              f"Texto {sim:.0%} igual a uno ya publicado en el grupo. Agregá variaciones {{a|b}}")
            log.warning("Omitida '%s' en '%s': texto demasiado parecido a uno anterior (%.0f%%)",
                        pub.id, t.grupo, sim * 100)
            continue

        demora = rng.uniform(config.limites.demora_aleatoria_min_seg, config.limites.demora_aleatoria_max_seg)
        log.info("Publicando '%s' en '%s' (modo %s) en %.0f segundos...", pub.id, t.grupo, config.modo, demora)
        esperar(demora)

        imagenes = [config.carpeta_imagenes / n for n in pub.imagenes]
        with fabrica_publicador() as publicador:
            res = publicador.publicar(config.grupos[t.grupo].url, texto, imagenes)

        momento = ahora if hora_fija else config.ahora()
        historial.agregar(t.clave, pub.id, t.grupo, res.estado, momento, texto,
                          res.detalle + (f" | captura: {res.captura}" if res.captura else ""))
        log.info("Resultado '%s' en '%s': %s. %s", pub.id, t.grupo, res.estado, res.detalle)
        if res.estado == "bloqueada":
            antiban.pausar(config, res.detalle)
            log.critical("¡Facebook mostró una advertencia! El agente quedó PAUSADO. Detalle: %s", res.detalle)
        return res.estado

    return None
