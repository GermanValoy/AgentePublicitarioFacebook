"""Control del navegador (Playwright) para publicar en grupos de Facebook.

Se usa un perfil de Chromium propio (datos/perfil_navegador) donde vos iniciás sesión
a mano una sola vez. El agente NUNCA guarda ni pide tu contraseña.

Modos:
  simulacion -> abre el grupo, escribe el texto, adjunta las fotos, saca una captura y DESCARTA.
  asistido   -> igual, pero deja el borrador listo y vos hacés clic en "Publicar".
  automatico -> hace clic en "Publicar" solo.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

log = logging.getLogger("agente")

URL_FACEBOOK = "https://www.facebook.com/"

PATRONES_BLOQUEO = re.compile(
    r"bloquead[oa] temporalmente|temporarily blocked|limitamos la frecuencia|we limit how often"
    r"|tu cuenta (está|fue|se) (restringida|suspendida)|your account (is|has been) (restricted|suspended)"
    r"|confirm[aá] tu identidad|confirm your identity|va en contra de nuestras normas"
    r"|goes against our community standards",
    re.I,
)
TEXTO_COMPOSITOR = re.compile(
    r"escrib[eí] algo|write something|crea una publicaci[oó]n|create a public post|crear publicaci[oó]n", re.I)
BOTON_FOTO = re.compile(r"foto\/v[ií]deo|photo\/video", re.I)  # "/" escapada: Playwright la exige
BOTON_AGREGAR_FOTOS = re.compile(r"agrega(r)? fotos|add photos|arrastra|drag and drop", re.I)
BOTON_PUBLICAR = re.compile(r"^\s*(publicar|post)\s*$", re.I)
# Grupos de compra-venta: "Vender algo" → "Artículo en venta" → formulario (fotos, título, precio, descripción).
BOTON_VENDER = re.compile(r"vender algo|vende algo|sell something|qu[eé] vas a vender", re.I)
OPCION_ARTICULO = re.compile(r"art[ií]culo en venta|item for sale", re.I)
CAMPO_TITULO = re.compile(r"^\s*(t[ií]tulo|title)", re.I)
CAMPO_PRECIO = re.compile(r"^\s*(precio|price)", re.I)
CAMPO_DESCRIPCION = re.compile(r"descripci[oó]n|description|describ", re.I)
CAMPO_ESTADO = re.compile(r"^\s*(estado|condici[oó]n|condition)", re.I)
OPCION_NUEVO = re.compile(r"^\s*(nuevo|new)\b", re.I)
CONTADOR_FOTOS = re.compile(r"(?:fotos|photos)\s*[·•:-]\s*(\d+)\s*/\s*\d+", re.I)
BOTON_MAS_DETALLES = re.compile(r"m[aá]s detalles|more details", re.I)
BOTON_SIGUIENTE = re.compile(r"^\s*(siguiente|next)\s*$", re.I)
EMOJIS = re.compile(r"[^\w\s.,:;!¡?¿()%$/+&'\"-]", re.UNICODE)

JS_CONTROLES = """(raiz) => Array.from(raiz.querySelectorAll(
  'input,textarea,select,[role=button],[role=combobox],[role=textbox],[role=radio],label'))
  .slice(0, 200).map(e => {
    const rol = e.getAttribute('role') || '';
    const texto = (e.tagName === 'LABEL' || rol === 'button') ? (e.innerText || '').replace(/\\s+/g, ' ') : '';
    return [e.tagName.toLowerCase(), rol, e.getAttribute('type') || '', (e.getAttribute('aria-label') || ''),
            e.getAttribute('placeholder') || '', texto].map(x => x.slice(0, 60)).join(' | ');
  }).join('\\n')"""
BOTON_DESCARTAR = re.compile(r"^\s*(descartar|discard|salir|leave)\s*$", re.I)


@dataclass
class ResultadoPublicacion:
    estado: str  # publicada | simulada | fallida | no_confirmada | bloqueada
    detalle: str = ""
    captura: Path | None = None


def confirmar_por_consola(mensaje: str) -> bool:
    print("\a" + mensaje)
    return input("¿Se publicó? [s/n]: ").strip().lower().startswith("s")


class PublicadorFacebook:
    def __init__(self, carpeta_perfil: Path, carpeta_capturas: Path, modo: str, oculto: bool = False,
                 confirmar: Callable[[str], bool] = confirmar_por_consola, verificar_sesion: bool = True,
                 velocidad: float = 1.0, navegador: str = "chromium", venta: dict | None = None,
                 carpeta_diagnostico: Path | None = None):
        self.carpeta_perfil = carpeta_perfil
        self.carpeta_capturas = carpeta_capturas
        self.modo = modo
        self.oculto = oculto
        self.confirmar = confirmar
        self.verificar_sesion = verificar_sesion
        self.velocidad = velocidad  # 1.0 = ritmo humano; los tests usan valores bajos
        self.navegador = navegador  # chromium (de Playwright), chrome o msedge (instalados en la PC)
        self.venta = venta or {}  # precio (y opcionalmente estado) para grupos de compra-venta
        self.carpeta_diagnostico = carpeta_diagnostico  # reportes/: lista de campos (sin datos) para ajustar

    # ---- ciclo de vida -------------------------------------------------------------------
    def __enter__(self) -> "PublicadorFacebook":
        from playwright.sync_api import sync_playwright

        self.carpeta_perfil.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        opciones = {}
        if os.environ.get("AGENTE_NAVEGADOR_RUTA"):
            opciones["executable_path"] = os.environ["AGENTE_NAVEGADOR_RUTA"]
        elif self.navegador != "chromium":
            opciones["channel"] = self.navegador
        try:
            self._ctx = self._pw.chromium.launch_persistent_context(
                str(self.carpeta_perfil),
                headless=self.oculto,
                **opciones,
                locale="es-ES",
                viewport={"width": 1280, "height": 900},
                args=["--disable-notifications"],
            )
        except Exception:
            self._pw.stop()
            raise
        self.page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        return self

    def __exit__(self, *exc) -> None:
        self._ctx.close()
        self._pw.stop()

    # ---- utilidades ----------------------------------------------------------------------
    def _pausa(self, desde: float = 1.0, hasta: float = 3.0) -> None:
        self.page.wait_for_timeout(random.uniform(desde, hasta) * 1000 * self.velocidad)

    def _captura(self, etiqueta: str) -> Path | None:
        """Guarda una captura. Si falla (Facebook a veces tarda en cargar fuentes) no corta el proceso."""
        try:
            self.carpeta_capturas.mkdir(parents=True, exist_ok=True)
            ruta = self.carpeta_capturas / f"{dt.datetime.now():%Y%m%d-%H%M%S}-{etiqueta}.png"
            self.page.screenshot(path=str(ruta), timeout=20_000, animations="disabled", caret="hide")
            log.info("Captura guardada: %s", ruta)
            return ruta
        except Exception as e:
            log.warning("No se pudo sacar la captura (%s): %s", etiqueta, e)
            return None

    def _guardar_controles(self, contenedor, etiqueta: str) -> None:
        """Guarda en reportes/ la lista de campos y botones del formulario (sin lo escrito en ellos),
        para poder ajustar el agente a distancia si Facebook cambia el formulario."""
        if not self.carpeta_diagnostico:
            return
        try:
            self.carpeta_diagnostico.mkdir(parents=True, exist_ok=True)
            lista = contenedor.evaluate(JS_CONTROLES)
            (self.carpeta_diagnostico / f"diagnostico-{etiqueta}.txt").write_text(
                f"# {dt.datetime.now():%d/%m/%Y %H:%M} · etiqueta | rol | tipo | aria-label | placeholder | texto\n"
                + lista + "\n", encoding="utf-8")
        except Exception as e:
            log.warning("No se pudo guardar la lista de campos: %s", e)

    def _guardar_diagnostico(self, dialogo, etiqueta: str) -> None:
        """Guarda el HTML del cuadro de publicación para poder ajustar el agente si Facebook cambia."""
        try:
            self.carpeta_capturas.mkdir(parents=True, exist_ok=True)
            ruta = self.carpeta_capturas / f"{dt.datetime.now():%Y%m%d-%H%M%S}-{etiqueta}.html"
            ruta.write_text(dialogo.evaluate("e => e.outerHTML"), encoding="utf-8")
            log.info("Diagnóstico guardado: %s", ruta)
        except Exception as e:
            log.warning("No se pudo guardar el diagnóstico: %s", e)

    def sesion_activa(self) -> bool:
        self.page.goto(URL_FACEBOOK, wait_until="domcontentloaded")
        self._pausa(2, 4)
        return any(c["name"] == "c_user" for c in self._ctx.cookies(URL_FACEBOOK))

    def iniciar_sesion_manual(self, esperar: Callable[[], None]) -> bool:
        self.page.goto(URL_FACEBOOK + "login", wait_until="domcontentloaded")
        esperar()
        return self.sesion_activa()

    def detectar_bloqueo(self) -> str | None:
        if "/checkpoint" in self.page.url:
            return "Facebook pidió una verificación de seguridad (checkpoint)"
        try:
            texto = self.page.locator("body").inner_text(timeout=5000)
        except Exception:
            return None
        m = PATRONES_BLOQUEO.search(texto)
        return f"Facebook mostró: '{m.group(0)}'" if m else None

    def _buscar_compositor(self):
        for candidato in (
            self.page.get_by_role("button", name=TEXTO_COMPOSITOR),
            self.page.get_by_text(TEXTO_COMPOSITOR),
        ):
            if candidato.count() and candidato.first.is_visible():
                return candidato.first
        return None

    def _subir_por_entrada(self, dialogo, archivos: list[str]) -> bool:
        entrada = dialogo.locator("input[type=file]")
        if entrada.count():
            entrada.last.set_input_files(archivos)
            return True
        return False

    def _subir_con_selector(self, boton, archivos: list[str]) -> bool:
        """Hace clic en el botón y, si se abre la ventana de elegir archivos, carga las fotos ahí."""
        from playwright.sync_api import TimeoutError as TiempoAgotado
        try:
            with self.page.expect_file_chooser(timeout=6_000) as selector:
                boton.click()
            selector.value.set_files(archivos)
            return True
        except TiempoAgotado:
            return False

    def _boton(self, dialogo, patron):
        for candidato in (dialogo.get_by_role("button", name=patron), dialogo.get_by_label(patron),
                          dialogo.get_by_text(patron)):
            if candidato.count() and candidato.first.is_visible():
                return candidato.first
        return None

    @staticmethod
    def _contador_fotos(contenedor) -> int:
        """Lee el contador del formulario de venta ("Fotos · 1/42"). 0 si no hay contador."""
        try:
            m = CONTADOR_FOTOS.search(contenedor.inner_text(timeout=2_000))
            return int(m.group(1)) if m else 0
        except Exception:
            return 0

    def _adjuntar_imagenes(self, dialogo, imagenes: list[Path]) -> None:
        archivos = [str(i) for i in imagenes]
        miniaturas_antes = dialogo.locator("img").count()
        fotos_antes = self._contador_fotos(dialogo)

        subido = self._subir_por_entrada(dialogo, archivos)
        if not subido:
            boton = self._boton(dialogo, BOTON_FOTO)
            if boton is None:
                raise RuntimeError("no se encontró el botón 'Foto/video' en el cuadro de publicación")
            log.info("Clic en 'Foto/video'")
            subido = self._subir_con_selector(boton, archivos)
            if not subido:  # el clic mostró la zona "Agregar fotos/videos" en lugar del selector
                self._pausa(1, 2)
                subido = self._subir_por_entrada(dialogo, archivos)
            if not subido:
                zona = self._boton(dialogo, BOTON_AGREGAR_FOTOS)
                subido = zona is not None and self._subir_con_selector(zona, archivos)
        if not subido:
            raise RuntimeError("no se encontró dónde cargar las fotos")

        # Confirmar que Facebook tomó la foto: aparece la miniatura o sube el contador "Fotos · N/42".
        limite = time.monotonic() + 45
        while not (dialogo.locator("img").count() > miniaturas_antes or self._contador_fotos(dialogo) > fotos_antes):
            if time.monotonic() > limite:
                raise RuntimeError("se cargó el archivo pero Facebook no mostró la vista previa de la foto")
            self.page.wait_for_timeout(500)
        log.info("Foto(s) adjuntada(s): %d", len(archivos))
        self._pausa(3 + 2 * len(imagenes), 5 + 2 * len(imagenes))  # tiempo de subida

    def _buscar_en(self, contenedor, patron, solo_botones: bool = False):
        candidatos = [contenedor.get_by_role("button", name=patron)]
        if not solo_botones:
            candidatos += [contenedor.get_by_role("menuitem", name=patron), contenedor.get_by_role("radio", name=patron),
                           contenedor.get_by_role("option", name=patron), contenedor.get_by_text(patron)]
        for c in candidatos:
            try:
                for i in range(min(c.count(), 5)):
                    if c.nth(i).is_visible():
                        return c.nth(i)
            except Exception:
                continue
        return None

    def _campo(self, contenedor, patron):
        for c in (contenedor.get_by_label(patron), contenedor.get_by_placeholder(patron),
                  contenedor.get_by_role("textbox", name=patron)):
            try:
                if c.count() and c.first.is_visible():
                    return c.first
            except Exception:
                continue
        return None

    @staticmethod
    def titulo_de(texto: str) -> str:
        """Primera línea del texto, sin emojis, como título del artículo (máx. 90 caracteres)."""
        for linea in texto.splitlines():
            limpia = " ".join(EMOJIS.sub(" ", linea).split())
            if len(limpia) >= 5:
                return limpia[:90]
        return "Servicio técnico"

    def _publicar_venta(self, vender, texto: str, imagenes: list[Path]) -> ResultadoPublicacion:
        """Grupos de compra-venta: «Vender algo» → «Artículo en venta» → fotos, título, precio y descripción."""
        page = self.page
        precio = str(self.venta.get("precio", "")).strip()
        if not precio:
            return ResultadoPublicacion("error_navegador", "Es un grupo de compra-venta y falta el precio: "
                                        "poné venta → precio en config/config.yaml", self._captura("venta-sin-precio"))
        log.info("Grupo de compra-venta: «Vender algo»")
        vender.click()
        self._pausa(2, 4)
        elegir = page.get_by_role("dialog")
        articulo = self._buscar_en(elegir.last if elegir.count() else page, OPCION_ARTICULO)
        if articulo is not None:
            log.info("«Artículo en venta»")
            articulo.click()
            self._pausa(2, 4)
        dialogos = page.get_by_role("dialog")
        formulario = dialogos.last if dialogos.count() else page.locator("body")
        self._guardar_controles(formulario, "venta-formulario")

        try:
            if imagenes:
                log.info("Adjuntando %d imagen(es)", len(imagenes))
                self._adjuntar_imagenes(formulario, imagenes)
            faltan = []
            for nombre, patron, valor in (("título", CAMPO_TITULO, self.titulo_de(texto)),
                                          ("precio", CAMPO_PRECIO, precio)):
                campo = self._campo(formulario, patron)
                if campo is None:
                    faltan.append(nombre)
                    continue
                campo.click()
                self._escribir(campo, valor)
                self._pausa(1, 2)
            estado = self._campo(formulario, CAMPO_ESTADO) or self._buscar_en(formulario, CAMPO_ESTADO)
            if estado is not None:
                try:
                    estado.click()
                    self._pausa(1, 2)
                    opcion = self._buscar_en(page, re.compile(self.venta.get("estado", "") or OPCION_NUEVO.pattern,
                                                              re.I))
                    if opcion is not None:
                        opcion.click()
                except Exception as e:
                    log.info("No se pudo elegir el estado del artículo (se sigue igual): %s", e)
            descripcion = self._campo(formulario, CAMPO_DESCRIPCION)
            if descripcion is None:  # suele estar dentro de "Más detalles", que viene cerrado
                mas = self._buscar_en(formulario, BOTON_MAS_DETALLES)
                if mas is not None:
                    mas.click()
                    self._pausa(1, 2)
                    descripcion = self._campo(formulario, CAMPO_DESCRIPCION)
            if descripcion is None:
                faltan.append("descripción")
            else:
                descripcion.click()
                log.info("Escribiendo la descripción")
                self._escribir(descripcion, texto)
            if faltan:
                raise RuntimeError(f"no se encontraron los campos: {', '.join(faltan)}")
        except Exception as e:
            log.warning("Formulario de venta: %s", e)
            self._guardar_controles(formulario, "venta-error")
            captura = self._captura("venta-error")
            self._descartar(formulario)
            return ResultadoPublicacion("error_navegador", f"Formulario de venta: {e}", captura)

        self._pausa(1, 3)
        return self._terminar(formulario, pasos_siguiente=True)

    def _escribir(self, caja, texto: str) -> None:
        """Escribe letra por letra, de a una línea, dándole a cada línea el tiempo que necesita
        (un texto largo escrito a ritmo humano tarda más que el límite normal de 30 segundos)."""
        demora = random.uniform(35, 90) * self.velocidad
        for i, linea in enumerate(texto.split("\n")):
            if i:
                caja.press("Enter")
            if linea:
                caja.press_sequentially(linea, delay=demora, timeout=len(linea) * (demora + 50) + 15_000)

    def _descartar(self, dialogo) -> None:
        try:
            self.page.keyboard.press("Escape")
            self._pausa(1, 2)
            boton = self.page.get_by_role("button", name=BOTON_DESCARTAR)
            if boton.count() and boton.first.is_visible():
                boton.first.click()
            dialogo.wait_for(state="hidden", timeout=10_000)
            log.info("Borrador descartado")
        except Exception as e:
            log.warning("No se pudo cerrar el borrador: %s", e)

    # ---- publicación ---------------------------------------------------------------------
    def publicar(self, url_grupo: str, texto: str, imagenes: list[Path]) -> ResultadoPublicacion:
        try:
            return self._publicar(url_grupo, texto, imagenes)
        except Exception as e:
            log.exception("Error inesperado al publicar")
            return ResultadoPublicacion("fallida", f"Error inesperado: {e}", self._captura("error"))

    def _publicar(self, url_grupo: str, texto: str, imagenes: list[Path]) -> ResultadoPublicacion:
        page = self.page
        if self.verificar_sesion and not self.sesion_activa():
            return ResultadoPublicacion("fallida", "No hay sesión de Facebook. Ejecutá: python -m agente iniciar-sesion")

        log.info("Abriendo el grupo %s", url_grupo)
        page.goto(url_grupo, wait_until="domcontentloaded")
        self._pausa(3, 6)
        bloqueo = self.detectar_bloqueo()
        if bloqueo:
            return ResultadoPublicacion("bloqueada", bloqueo, self._captura("bloqueo"))

        # Moverse un poco por el grupo como haría una persona.
        page.mouse.wheel(0, random.randint(300, 700))
        self._pausa(2, 5)
        page.mouse.wheel(0, -2000)
        self._pausa(1, 2)

        compositor = self._buscar_compositor()
        if compositor is None:
            vender = self._buscar_en(page, BOTON_VENDER)
            if vender is not None:
                return self._publicar_venta(vender, texto, imagenes)
            # No llegó a escribir nada: no cuenta como actividad en el grupo (se puede reintentar).
            return ResultadoPublicacion("error_navegador", "No se encontró el cuadro 'Escribe algo...'. "
                                        "¿Sos miembro del grupo y permite publicar?", self._captura("sin-compositor"))
        compositor.click()
        dialogo = page.get_by_role("dialog").filter(has=page.get_by_role("textbox")).last
        dialogo.wait_for(state="visible", timeout=15_000)
        self._pausa(1, 3)

        log.info("Escribiendo el texto")
        caja = dialogo.get_by_role("textbox").first
        caja.click()
        self._escribir(caja, texto)
        self._pausa(1, 3)

        if imagenes:
            log.info("Adjuntando %d imagen(es)", len(imagenes))
            try:
                self._adjuntar_imagenes(dialogo, imagenes)
            except Exception as e:
                log.warning("No se pudieron adjuntar las imágenes: %s", e)
                captura = self._captura("error-imagenes")
                self._guardar_diagnostico(dialogo, "error-imagenes")
                self._descartar(dialogo)
                return ResultadoPublicacion("error_navegador", f"No se pudieron adjuntar las imágenes: {e}", captura)

        return self._terminar(dialogo)

    def _terminar(self, dialogo, pasos_siguiente: bool = False) -> ResultadoPublicacion:
        captura = self._captura(f"borrador-{self.modo}")

        if self.modo == "simulacion":
            self._descartar(dialogo)
            return ResultadoPublicacion("simulada", "Borrador completo y descartado (no se publicó)", captura)

        if self.modo == "asistido":
            publicada = self.confirmar(
                "\n>>> El borrador está listo en el navegador. Revisalo y hacé clic en «Publicar»"
                + (" (o «Siguiente» y después «Publicar»)" if pasos_siguiente else "") + ".\n"
                "    Si no querés publicarlo, cerralo y respondé 'n'.")
            if not publicada:
                if dialogo.is_visible():
                    self._descartar(dialogo)
                return ResultadoPublicacion("no_confirmada", "El usuario decidió no publicar", captura)
            return ResultadoPublicacion("publicada", "Publicada por el usuario (modo asistido)", captura)

        if pasos_siguiente:  # el formulario de venta tiene "Siguiente" antes de "Publicar"
            for _ in range(3):
                siguiente = self._buscar_en(self.page, BOTON_SIGUIENTE, solo_botones=True)
                if siguiente is None or self._buscar_en(self.page, BOTON_PUBLICAR, solo_botones=True):
                    break
                siguiente.click()
                self._pausa(2, 4)
            boton = self._buscar_en(self.page, BOTON_PUBLICAR, solo_botones=True)
            if boton is None:
                self._guardar_controles(self.page.locator("body"), "venta-publicar")
                raise RuntimeError("no se encontró el botón «Publicar» del formulario de venta")
            boton.click()
        else:
            dialogo.get_by_role("button", name=BOTON_PUBLICAR).last.click()
        try:
            dialogo.wait_for(state="hidden", timeout=60_000)
        except Exception:
            if not pasos_siguiente:
                raise
            self._pausa(5, 8)  # el formulario de venta a veces es una página entera, no una ventana
        self._pausa(3, 6)
        bloqueo = self.detectar_bloqueo()
        if bloqueo:
            return ResultadoPublicacion("bloqueada", bloqueo, self._captura("bloqueo"))
        return ResultadoPublicacion("publicada", "Publicada automáticamente", self._captura("publicada"))
