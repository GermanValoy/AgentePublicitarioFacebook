"""Línea de comandos del agente:  python -m agente <comando>"""
from __future__ import annotations

import argparse
import logging
import os
import random
import re
import sys
import time
from contextlib import contextmanager

from . import antiban
from .ciclo import ejecutar_ciclo
from .config import RAIZ, Config, ErrorConfig, cargar_config
from .contenido import elegir_variante
from .historial import Historial
from .planificador import grupos_de, proxima_ocurrencia, tareas_del_momento
from .publicaciones import cargar_publicaciones
from . import telegram
from .sincronizacion import ErrorSincronizacion, conectado, sincronizar
from .validador import validar_todas

log = logging.getLogger("agente")


def _configurar_log(config: Config) -> None:
    config.carpeta_datos.mkdir(parents=True, exist_ok=True)
    formato = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s", "%Y-%m-%d %H:%M:%S")
    log.setLevel(logging.INFO)
    for handler in (logging.StreamHandler(sys.stdout),
                    logging.FileHandler(config.carpeta_datos / "agente.log", encoding="utf-8")):
        handler.setFormatter(formato)
        log.addHandler(handler)


def _historial(config: Config) -> Historial:
    return Historial(config.carpeta_datos / "historial.json")


def _publicador(config: Config, modo: str | None = None, oculto: bool = False):
    from .publicador import PublicadorFacebook
    modo = modo or config.modo
    if modo == "aprobacion":
        modo = "automatico"  # ya lo aprobaste por Telegram: el agente hace el clic en "Publicar"
    return PublicadorFacebook(config.carpeta_datos / "perfil_navegador", config.carpeta_datos / "capturas",
                              modo, oculto=oculto, navegador=config.navegador)


@contextmanager
def _bloqueo(config: Config):
    """Evita que corran dos agentes a la vez (por ejemplo el bucle y el Programador de tareas)."""
    archivo = config.carpeta_datos / "agente.lock"
    archivo.parent.mkdir(parents=True, exist_ok=True)
    if archivo.exists() and time.time() - archivo.stat().st_mtime > 3 * 3600:
        archivo.unlink()  # quedó de una ejecución que se cortó
    try:
        fd = os.open(archivo, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ErrorConfig("Ya hay otro agente trabajando (si no es así, borrá datos/agente.lock)") from None
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        archivo.unlink(missing_ok=True)


def _imprimir_validacion(config: Config, publicaciones) -> bool:
    resultados = validar_todas(publicaciones, config, config.ahora())
    todo_ok = True
    for pub in publicaciones:
        r = resultados[pub.id]
        marca = "OK   " if r.ok else "ERROR"
        extra = "" if pub.activa else " (desactivada)"
        print(f"[{marca}] {pub.id}{extra}")
        for e in r.errores:
            print(f"    ✗ {e}")
        for a in r.advertencias:
            print(f"    ! {a}")
        todo_ok &= r.ok or not pub.activa
    if not publicaciones:
        print("No hay publicaciones en publicaciones/programadas.yaml")
    return todo_ok


# ---- comandos ---------------------------------------------------------------------------------
def cmd_validar(config, args) -> int:
    publicaciones = cargar_publicaciones(config.archivo_programadas)
    print(f"Configuración OK: {len(config.grupos)} grupos, modo '{config.modo}'.\n")
    ok = _imprimir_validacion(config, publicaciones)
    print("\nTodo listo para publicar." if ok else "\nHay errores: corregilos antes de publicar.")
    return 0 if ok else 1


def cmd_vista_previa(config, args) -> int:
    historial = _historial(config)
    for pub in cargar_publicaciones(config.archivo_programadas):
        if args.id and pub.id != args.id:
            continue
        print(f"=============== {pub.id} ===============")
        for grupo in grupos_de(pub, config):
            texto, sim = elegir_variante(pub.texto, historial.textos_publicados(grupo))
            print(f"--- Grupo: {grupo}  (parecido con lo ya publicado: {sim:.0%})")
            print(texto)
            print(f"    Imágenes: {', '.join(pub.imagenes) or 'ninguna'}\n")
    return 0


def resumen_estado(config: Config) -> str:
    historial = _historial(config)
    ahora = config.ahora()
    pausa = antiban.pausa_activa(config)
    lineas = [f"Ahora: {ahora:%d/%m/%Y %H:%M}  |  modo: {config.modo}  |  "
              f"{'PAUSADO: ' + pausa if pausa else 'activo'}"]
    hoy = [r for r in historial.actividad() if r.momento.astimezone(config.zona).date() == ahora.date()]
    lineas.append(f"Publicaciones hoy: {len(hoy)}/{config.limites.max_publicaciones_por_dia}\n")

    publicaciones = cargar_publicaciones(config.archivo_programadas)
    pendientes, _ = tareas_del_momento(publicaciones, config, historial, ahora)
    lineas.append("Pendientes ahora:")
    for t in pendientes:
        d = antiban.evaluar(ahora, t.grupo, config, historial)
        lineas.append(f"  - {t.publicacion.id} -> {t.grupo}: {'se puede publicar' if d.permitido else d.motivo}")
    if not pendientes:
        lineas.append("  (ninguna)")

    lineas.append("\nPróximas programadas:")
    proximas = [(proxima_ocurrencia(p, config, ahora), p) for p in publicaciones if p.activa]
    proximas = sorted((x for x in proximas if x[0]), key=lambda x: x[0])
    for momento, p in proximas[:10]:
        lineas.append(f"  - {momento:%d/%m %H:%M}  {p.id}  ->  {', '.join(grupos_de(p, config))}")
    if not proximas:
        lineas.append("  (ninguna)")

    lineas.append("\nÚltimos movimientos:")
    for r in historial.registros[-8:]:
        lineas.append(f"  - {r.momento:%d/%m %H:%M}  {r.estado:<13} {r.publicacion_id} -> {r.grupo}")
    if not historial.registros:
        lineas.append("  (ninguno)")
    return "\n".join(lineas)


def cmd_estado(config, args) -> int:
    print(resumen_estado(config))
    return 0


def cmd_iniciar_sesion(config, args) -> int:
    print("Se abrirá un navegador. Iniciá sesión en Facebook normalmente (con tu usuario y contraseña).")
    print("El agente NO ve ni guarda tu contraseña: la sesión queda en datos/perfil_navegador.")
    with _publicador(config) as navegador:
        ok = navegador.iniciar_sesion_manual(
            lambda: input("\nCuando veas tu inicio de Facebook, volvé acá y presioná Enter... "))
    print("Sesión guardada correctamente." if ok else "No se detectó la sesión. Probá de nuevo.")
    return 0 if ok else 1


def cmd_verificar_sesion(config, args) -> int:
    with _publicador(config, oculto=args.oculto) as navegador:
        ok = navegador.sesion_activa()
        bloqueo = navegador.detectar_bloqueo() if ok else None
    if bloqueo:
        print(f"Sesión activa, pero Facebook muestra una advertencia: {bloqueo}")
        return 1
    print("Sesión activa." if ok else "No hay sesión. Ejecutá: python -m agente iniciar-sesion")
    return 0 if ok else 1


def cmd_publicar_ahora(config, args) -> int:
    """Publica una publicación del calendario ya mismo en un grupo, respetando las reglas anti-baneo."""
    publicaciones = {p.id: p for p in cargar_publicaciones(config.archivo_programadas)}
    pub = publicaciones.get(args.id)
    if pub is None:
        print(f"No existe la publicación '{args.id}'. Las que hay: {', '.join(publicaciones) or 'ninguna'}")
        return 1
    ahora = config.ahora()
    r = validar_todas([pub], config, ahora)[pub.id]
    if not r.ok:
        print("La publicación no pasa las pruebas:\n  - " + "\n  - ".join(r.errores))
        return 1
    grupos = grupos_de(pub, config)
    grupo = args.grupo or (grupos[0] if grupos else None)
    if grupo not in config.grupos:
        print("Indicá un grupo válido con --grupo \"Nombre del grupo\"")
        return 1
    historial = _historial(config)
    decision = antiban.evaluar(ahora, grupo, config, historial)
    if not decision.permitido:
        print(f"Ahora no se puede publicar en '{grupo}': {decision.motivo}")
        return 1
    texto, _ = elegir_variante(pub.texto, historial.textos_publicados(grupo) + historial.textos_publicados(limite=5))
    # Si lo ejecutás a mano estás frente a la PC: en modo aprobacion se usa asistido (hacés vos el clic).
    modo = "asistido" if config.modo == "aprobacion" else config.modo
    print(f"Publicando '{pub.id}' en '{grupo}' (modo {modo})...")
    with _bloqueo(config), _publicador(config, modo=modo, oculto=args.oculto) as navegador:
        res = navegador.publicar(config.grupos[grupo].url, texto, [config.carpeta_imagenes / n for n in pub.imagenes])
    historial.agregar(f"{pub.id}|{grupo}|manual-{ahora:%Y-%m-%dT%H:%M}", pub.id, grupo, res.estado,
                      config.ahora(), texto, res.detalle + (f" | captura: {res.captura}" if res.captura else ""))
    print(f"Resultado: {res.estado}. {res.detalle}")
    if res.captura:
        print(f"Captura: {res.captura}")
    if res.estado == "bloqueada":
        antiban.pausar(config, res.detalle)
        print("¡Facebook mostró una advertencia! El agente quedó pausado.")
    return 0 if res.estado in ("publicada", "simulada") else 1


def cmd_simular(config, args) -> int:
    """Prueba de punta a punta en Facebook, sin publicar: escribe, adjunta, captura y descarta."""
    publicaciones = {p.id: p for p in cargar_publicaciones(config.archivo_programadas)}
    pub = publicaciones.get(args.id)
    if pub is None:
        print(f"No existe la publicación '{args.id}'")
        return 1
    r = validar_todas([pub], config, config.ahora())[pub.id]
    if not r.ok:
        print("La publicación no pasa las pruebas:\n  - " + "\n  - ".join(r.errores))
        return 1
    grupos = grupos_de(pub, config)
    grupo = args.grupo or (grupos[0] if grupos else None)
    if grupo not in config.grupos:
        print("Indicá un grupo válido con --grupo")
        return 1
    texto, _ = elegir_variante(pub.texto, _historial(config).textos_publicados(grupo))
    with _bloqueo(config), _publicador(config, modo="simulacion", oculto=args.oculto) as navegador:
        res = navegador.publicar(config.grupos[grupo].url, texto, [config.carpeta_imagenes / n for n in pub.imagenes])
    print(f"Resultado: {res.estado}. {res.detalle}")
    if res.captura:
        print(f"Mirá la captura del borrador en: {res.captura}")
    if res.estado == "bloqueada":
        antiban.pausar(config, res.detalle)
    return 0 if res.estado == "simulada" else 1


def _aprobador(config: Config) -> telegram.AprobadorTelegram | None:
    cliente = telegram.cargar(config.carpeta_datos)
    if cliente is None:
        if config.modo == "aprobacion":
            raise ErrorConfig("El modo 'aprobacion' necesita Telegram: ejecutá configurar_telegram.bat")
        return None
    return telegram.AprobadorTelegram(cliente, config.carpeta_datos / "aprobaciones.json")


def _una_pasada(config_inicial: Config, args, aprobador=None) -> str | None:
    config = cargar_config(config_inicial.raiz)  # se relee para tomar cambios sin reiniciar
    publicaciones = cargar_publicaciones(config.archivo_programadas)
    if aprobador is None:
        aprobador = _aprobador(config)
        if aprobador:
            aprobador.procesar(comandos=_comandos_telegram(config))  # tomar botones tocados desde la última vez
    with _bloqueo(config):
        return ejecutar_ciclo(config, publicaciones, _historial(config),
                              lambda: _publicador(config, oculto=args.oculto),
                              esperar=(lambda s: None) if args.sin_demora else time.sleep,
                              aprobador=aprobador)


def _comandos_telegram(config: Config):
    def responder(texto: str) -> str:
        if texto.startswith("/estado"):
            return resumen_estado(config)
        if texto.startswith("/pausar"):
            antiban.pausar(config, "Pausado desde Telegram")
            return "⏸️ Agente pausado. No se publica nada hasta que mandes /reanudar."
        if texto.startswith("/reanudar"):
            antiban.reanudar(config)
            return "▶️ Agente reanudado."
        return ("Comandos:\n/estado - qué se publicó y qué viene\n/pausar - frenar todo\n"
                "/reanudar - volver a publicar\n\nCuando toque publicar te mando la foto y el texto "
                "con los botones ✅ Publicar / ❌ No publicar.")
    return responder


def _sincronizar(config: Config, aprobador=None) -> bool:
    if not conectado(config.raiz):
        return False
    try:
        resumen = sincronizar(config.raiz)
        log.info("GitHub: %s", resumen)
        if aprobador and "bajaron" in resumen:
            aprobador.avisar(f"🔄 Llegaron novedades desde GitHub: {resumen}")
        return True
    except ErrorSincronizacion as e:
        log.warning("GitHub: no se pudo sincronizar. %s", e)
        return False


def cmd_sincronizar(config, args) -> int:
    if not conectado(config.raiz):
        print("La carpeta no está conectada a GitHub. Ejecutá conectar_github.bat")
        return 1
    return 0 if _sincronizar(config) else 1


def cmd_publicar_pendientes(config, args) -> int:
    _sincronizar(config)
    _una_pasada(config, args)
    return 0


def cmd_ejecutar(config, args) -> int:
    aprobador = _aprobador(config)
    log.info("Agente en marcha (modo %s). Revisa el calendario cada ~%d minutos. %s Ctrl+C para salir.",
             config.modo, args.intervalo,
             "Telegram conectado: respondé desde el celular." if aprobador else "")
    if aprobador:
        aprobador.avisar(f"🤖 Agente en marcha (modo {config.modo}). Mandá /estado para ver qué viene.")
    comandos = _comandos_telegram(config)
    ultima_sincronizacion = ultima_pasada = 0.0
    while True:
        try:
            if args.sincronizar_cada and time.time() - ultima_sincronizacion >= args.sincronizar_cada * 60:
                _sincronizar(config, aprobador)
                ultima_sincronizacion = time.time()
            if time.time() - ultima_pasada >= args.intervalo * 60:
                _una_pasada(config, args, aprobador)
                ultima_pasada = time.time()
            if aprobador:
                # Espera escuchando a Telegram: si tocás un botón, se actúa enseguida.
                if aprobador.procesar(espera=25, comandos=comandos):
                    ultima_pasada = 0.0
            else:
                time.sleep(30)
        except KeyboardInterrupt:
            raise
        except telegram.ErrorTelegram as e:
            log.warning("Telegram: %s", e)
            time.sleep(30)
        except Exception:
            log.exception("Error en la pasada; se reintenta en la próxima")
            time.sleep(60)


def cmd_configurar_telegram(config, args) -> int:
    print("""
=== CONECTAR TELEGRAM (gratis) ===
1. En tu celular abrí Telegram y buscá  @BotFather  (tiene tilde azul).
2. Mandale  /newbot
3. Te pide un nombre: por ejemplo  Agente Servicio Tecnico
4. Te pide un usuario que termine en "bot": por ejemplo  servicio_tafi_bot
5. BotFather te responde con un TOKEN largo, parecido a  123456789:AAH...xyz
""")
    token = input("Pegá acá el token y presioná Enter: ").strip()
    cliente = telegram.Telegram(token)
    try:
        bot = cliente.llamar("getMe")
    except telegram.ErrorTelegram as e:
        print(f"El token no funciona: {e}")
        return 1
    print(f"\nPerfecto. Ahora abrí este link en el celular y tocá INICIAR (o mandale /start):")
    print(f"    https://t.me/{bot['username']}\n")
    print("Esperando tu mensaje (hasta 5 minutos)...")
    desde, limite = 0, time.time() + 300
    while time.time() < limite:
        for u in cliente.actualizaciones(desde, espera=25):
            desde = u["update_id"] + 1
            chat = (u.get("message") or {}).get("chat", {})
            if chat.get("type") == "private":
                telegram.guardar(config.carpeta_datos, token, chat["id"])
                cliente.chat_id = chat["id"]
                cliente.llamar("getUpdates", {"offset": desde})  # marcar como leídos
                cliente.mensaje("✅ ¡Conectado! Desde acá vas a aprobar las publicaciones.\n"
                                "Mandá /estado para ver qué viene.")
                print("¡Listo! Telegram conectado. Te llegó un mensaje de prueba.")
                return _activar_modo_aprobacion(config)
    print("No llegó ningún mensaje. Volvé a intentarlo.")
    return 1


def _activar_modo_aprobacion(config: Config) -> int:
    archivo = config.raiz / "config" / "config.yaml"
    contenido = archivo.read_text(encoding="utf-8")
    if "\nmodo: aprobacion" in contenido:
        return 0
    nuevo, cambios = re.subn(r"(?m)^modo:\s*\w+", "modo: aprobacion", contenido, count=1)
    if cambios:
        archivo.write_text(nuevo, encoding="utf-8")
        print("Modo cambiado a 'aprobacion': de ahora en más aprobás desde Telegram.")
    else:
        print("Poné  modo: aprobacion  en config/config.yaml para aprobar desde Telegram.")
    return 0


def cmd_reanudar(config, args) -> int:
    antiban.reanudar(config)
    print("Agente reanudado. Antes de seguir, entrá a Facebook y verificá que tu cuenta no tenga avisos.")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m agente",
                                     description="Asistente para publicar en grupos de Facebook.")
    parser.add_argument("--oculto", action="store_true", help="navegador sin ventana (solo modo automatico)")
    sub = parser.add_subparsers(dest="comando", required=True, metavar="comando")

    sub.add_parser("iniciar-sesion", help="abre el navegador para que inicies sesión en Facebook (una vez)")
    sub.add_parser("verificar-sesion", help="comprueba que la sesión siga activa y sin advertencias")
    sub.add_parser("validar", help="prueba todas las publicaciones sin abrir Facebook")
    p = sub.add_parser("vista-previa", help="muestra el texto que saldría en cada grupo")
    p.add_argument("--id")
    sub.add_parser("estado", help="límites de hoy, pendientes, próximas y últimos movimientos")
    p = sub.add_parser("simular", help="prueba real en Facebook SIN publicar (captura y descarta)")
    p.add_argument("--id", required=True)
    p.add_argument("--grupo")
    p = sub.add_parser("publicar-ahora", help="publica YA una publicación del calendario (respeta anti-baneo)")
    p.add_argument("--id", required=True)
    p.add_argument("--grupo")
    p = sub.add_parser("publicar-pendientes", help="una pasada: publica como máximo una tarea pendiente")
    p.add_argument("--sin-demora", action="store_true")
    p = sub.add_parser("ejecutar", help="deja el agente corriendo y publica según el calendario")
    p.add_argument("--intervalo", type=int, default=5, help="minutos entre revisiones (por defecto 5)")
    p.add_argument("--sin-demora", action="store_true")
    p.add_argument("--sincronizar-cada", type=int, default=30,
                   help="minutos entre sincronizaciones con GitHub (0 = nunca; por defecto 30)")
    sub.add_parser("sincronizar", help="sube tus fotos/ideas y baja lo nuevo desde GitHub")
    sub.add_parser("configurar-telegram", help="conecta un bot de Telegram para aprobar desde el celular")
    sub.add_parser("reanudar", help="quita la pausa de emergencia")
    return parser


COMANDOS = {
    "iniciar-sesion": cmd_iniciar_sesion, "verificar-sesion": cmd_verificar_sesion,
    "validar": cmd_validar, "vista-previa": cmd_vista_previa, "estado": cmd_estado,
    "simular": cmd_simular, "publicar-ahora": cmd_publicar_ahora, "publicar-pendientes": cmd_publicar_pendientes,
    "ejecutar": cmd_ejecutar, "sincronizar": cmd_sincronizar,
    "configurar-telegram": cmd_configurar_telegram, "reanudar": cmd_reanudar,
}


def _usar_certificados_del_sistema() -> None:
    """Usa los certificados de Windows/Mac/Linux para las conexiones seguras (Telegram).
    Sin esto falla con antivirus que analizan HTTPS (error CERTIFICATE_VERIFY_FAILED)."""
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass


def main(argv: list[str] | None = None) -> int:
    _usar_certificados_del_sistema()
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")  # consola de Windows
    args = construir_parser().parse_args(argv)
    try:
        config = cargar_config(RAIZ)
        _configurar_log(config)
        return COMANDOS[args.comando](config, args)
    except ErrorConfig as e:
        print(f"Error: {e}")
        return 2
    except KeyboardInterrupt:
        print("\nAgente detenido.")
        return 0
