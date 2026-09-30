"""Aprobación de publicaciones desde el celular (o la PC) con un bot de Telegram. Gratis.

El token del bot y tu chat quedan en datos/telegram.json (en tu PC, nunca se sube a GitHub).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

log = logging.getLogger("agente")

API = "https://api.telegram.org/bot{token}/{metodo}"


class ErrorTelegram(Exception):
    pass


class Telegram:
    """Cliente mínimo de la API de bots de Telegram (solo usa la biblioteca estándar)."""

    def __init__(self, token: str, chat_id: int | None = None):
        self.token = token
        self.chat_id = chat_id

    def llamar(self, metodo: str, datos: dict | None = None, archivos: dict[str, Path] | None = None,
               espera: int = 30):
        url = API.format(token=self.token, metodo=metodo)
        datos = {k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v))
                 for k, v in (datos or {}).items() if v is not None}
        if archivos:
            limite = uuid.uuid4().hex
            partes = []
            for k, v in datos.items():
                partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
            for k, ruta in archivos.items():
                partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{k}"; filename="{ruta.name}"\r\n'
                              f'Content-Type: application/octet-stream\r\n\r\n'.encode() + ruta.read_bytes() + b"\r\n")
            cuerpo = b"".join(partes) + f"--{limite}--\r\n".encode()
            pedido = urllib.request.Request(url, cuerpo, {"Content-Type": f"multipart/form-data; boundary={limite}"})
        else:
            pedido = urllib.request.Request(url, urllib.parse.urlencode(datos).encode())
        try:
            with urllib.request.urlopen(pedido, timeout=espera + 15) as r:
                respuesta = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            try:
                respuesta = json.loads(e.read().decode())
            except Exception:
                raise ErrorTelegram(f"Telegram respondió {e.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                raise ErrorTelegram("un antivirus o proxy está interceptando la conexión segura. Actualizá con "
                                    "sincronizar.bat y volvé a abrir este archivo (se instala 'truststore')") from None
            raise ErrorTelegram(f"Sin conexión con Telegram: {e}") from None
        if not respuesta.get("ok"):
            raise ErrorTelegram(respuesta.get("description", "error desconocido"))
        return respuesta["result"]

    def mensaje(self, texto: str, botones: list[list[dict]] | None = None) -> int:
        datos = {"chat_id": self.chat_id, "text": texto[:4000]}
        if botones:
            datos["reply_markup"] = {"inline_keyboard": botones}
        return self.llamar("sendMessage", datos)["message_id"]

    def fotos(self, rutas: list[Path], leyenda: str = "") -> None:
        rutas = [r for r in rutas if r.is_file()]
        if len(rutas) == 1:
            self.llamar("sendPhoto", {"chat_id": self.chat_id, "caption": leyenda[:1000]}, {"photo": rutas[0]})
        elif rutas:
            media = [{"type": "photo", "media": f"attach://f{i}"} for i in range(len(rutas[:10]))]
            if leyenda:
                media[0]["caption"] = leyenda[:1000]
            self.llamar("sendMediaGroup", {"chat_id": self.chat_id, "media": media},
                        {f"f{i}": r for i, r in enumerate(rutas[:10])})

    def editar(self, message_id: int, texto: str) -> None:
        try:
            self.llamar("editMessageText", {"chat_id": self.chat_id, "message_id": message_id, "text": texto[:4000]})
        except ErrorTelegram as e:
            log.debug("No se pudo editar el mensaje: %s", e)

    def actualizaciones(self, desde: int, espera: int = 0) -> list[dict]:
        return self.llamar("getUpdates", {"offset": desde, "timeout": espera,
                                          "allowed_updates": ["message", "callback_query"]}, espera=espera)

    def responder_boton(self, callback_id: str, texto: str) -> None:
        try:
            self.llamar("answerCallbackQuery", {"callback_query_id": callback_id, "text": texto})
        except ErrorTelegram:
            pass


def _corto(clave: str) -> str:
    return hashlib.sha1(clave.encode()).hexdigest()[:12]


class AprobadorTelegram:
    """Pide aprobación por Telegram y recuerda las respuestas en datos/aprobaciones.json."""

    def __init__(self, telegram: Telegram, archivo: Path):
        self.tg = telegram
        self.archivo = archivo
        self.datos = {"desde": 0, "pedidos": {}}
        if archivo.is_file():
            self.datos = json.loads(archivo.read_text(encoding="utf-8"))

    def _guardar(self) -> None:
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.archivo.with_suffix(".tmp")
        temporal.write_text(json.dumps(self.datos, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporal, self.archivo)

    # ---- lo que usa el ciclo -----------------------------------------------------------------
    def estado(self, clave: str) -> str | None:
        pedido = self.datos["pedidos"].get(clave)
        return pedido["estado"] if pedido else None

    def texto(self, clave: str) -> str:
        return self.datos["pedidos"][clave]["texto"]

    def pendientes(self) -> list[str]:
        return [c for c, p in self.datos["pedidos"].items() if p["estado"] == "pendiente"]

    def solicitar(self, clave: str, publicacion_id: str, grupo: str, texto: str, imagenes: list[Path]) -> None:
        self.tg.fotos(imagenes)
        corto = _corto(clave)
        mensaje_id = self.tg.mensaje(
            f"📢 ¿Publico esto en «{grupo}»?\n\n{texto}",
            [[{"text": "✅ Publicar", "callback_data": f"si:{corto}"},
              {"text": "❌ No publicar", "callback_data": f"no:{corto}"}]])
        self.datos["pedidos"][clave] = {"estado": "pendiente", "corto": corto, "texto": texto, "grupo": grupo,
                                        "publicacion_id": publicacion_id, "mensaje_id": mensaje_id,
                                        "pedido": dt.datetime.now().isoformat(timespec="seconds")}
        self._guardar()

    def cerrar(self, clave: str, aviso: str | None = None) -> None:
        pedido = self.datos["pedidos"].pop(clave, None)
        self._guardar()
        if pedido and aviso:
            self.tg.editar(pedido["mensaje_id"], f"{aviso}\n\n{pedido['texto']}")

    def avisar(self, texto: str, imagen: Path | None = None) -> None:
        try:
            if imagen and imagen.is_file():
                self.tg.fotos([imagen], texto)
            else:
                self.tg.mensaje(texto)
        except ErrorTelegram as e:
            log.warning("No se pudo avisar por Telegram: %s", e)

    # ---- lectura de respuestas -------------------------------------------------------------
    def procesar(self, espera: int = 0, comandos=None) -> bool:
        """Lee botones tocados y comandos (/estado, /pausar...). Devuelve True si llegó una decisión."""
        decidido = False
        for u in self.tg.actualizaciones(self.datos["desde"], espera):
            self.datos["desde"] = u["update_id"] + 1
            boton = u.get("callback_query")
            if boton:
                if boton.get("message", {}).get("chat", {}).get("id") != self.tg.chat_id:
                    continue  # solo obedece a tu chat
                accion, _, corto = boton.get("data", "").partition(":")
                pedido = next((p for p in self.datos["pedidos"].values() if p["corto"] == corto), None)
                if pedido is None or pedido["estado"] != "pendiente":
                    self.tg.responder_boton(boton["id"], "Esta publicación ya no está pendiente")
                    continue
                pedido["estado"] = "aprobada" if accion == "si" else "rechazada"
                self.tg.responder_boton(boton["id"], "¡Publicando!" if accion == "si" else "No se publica")
                self.tg.editar(pedido["mensaje_id"], ("✅ Aprobada, publicando en unos minutos..."
                                                      if accion == "si" else "❌ No se publica") +
                               f" — «{pedido['grupo']}»\n\n{pedido['texto']}")
                decidido = True
            mensaje = u.get("message")
            if mensaje and mensaje.get("chat", {}).get("id") == self.tg.chat_id and comandos:
                texto = (mensaje.get("text") or "").strip().split("@")[0].lower()
                if texto.startswith("/"):
                    try:
                        self.tg.mensaje(comandos(texto))
                    except ErrorTelegram as e:
                        log.warning("No se pudo responder el comando: %s", e)
        self._guardar()
        return decidido


# ---- configuración --------------------------------------------------------------------------
def archivo_config(carpeta_datos: Path) -> Path:
    return carpeta_datos / "telegram.json"


def cargar(carpeta_datos: Path) -> Telegram | None:
    archivo = archivo_config(carpeta_datos)
    if not archivo.is_file():
        return None
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    return Telegram(datos["token"], int(datos["chat_id"]))


def guardar(carpeta_datos: Path, token: str, chat_id: int) -> None:
    archivo = archivo_config(carpeta_datos)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps({"token": token, "chat_id": chat_id}), encoding="utf-8")
