"""El agente tiene que arrancar aunque un archivo de memoria quede vacío o dañado."""
import json

from agente import archivos, telegram
from agente.historial import Historial


def test_historial_vacio_no_impide_arrancar(tmp_path):
    archivo = tmp_path / "historial.json"
    archivo.write_text("", encoding="utf-8")  # lo que causaba el JSONDecodeError
    h = Historial(archivo)
    assert h.registros == []
    assert list(tmp_path.glob("historial.danado-*.json"))  # se guarda una copia del dañado
    assert "historial.json" in archivos.RECUPERADOS
    archivos.RECUPERADOS.clear()


def test_aprobaciones_danadas_no_impiden_arrancar(tmp_path):
    archivo = tmp_path / "aprobaciones.json"
    archivo.write_text('{"desde": 5, "pedidos": {', encoding="utf-8")
    a = telegram.AprobadorTelegram(telegram.Telegram("t", 1), archivo)
    assert a.datos == {"desde": 0, "pedidos": {}}
    archivos.RECUPERADOS.clear()


def test_telegram_json_danado_se_trata_como_no_configurado(tmp_path):
    (tmp_path / "telegram.json").write_text("{", encoding="utf-8")
    assert telegram.cargar(tmp_path) is None
    archivos.RECUPERADOS.clear()


def test_guardar_es_atomico_y_legible(tmp_path):
    archivo = tmp_path / "x.json"
    archivos.guardar_json(archivo, {"a": "ñ"})
    assert json.loads(archivo.read_text(encoding="utf-8")) == {"a": "ñ"}
    assert not list(tmp_path.glob("*.tmp"))


def test_reclasifica_intentos_viejos_que_no_publicaron(tmp_path):
    """El 05/10 la versión vieja marcó como 'fallida' (bloqueando el grupo 7 días) un intento sin publicar."""
    archivo = tmp_path / "historial.json"
    base = {"clave": "x", "publicacion_id": "celulares", "grupo": "Venta de Garage", "fecha_hora": "2026-10-05T11:53:51-03:00"}
    archivo.write_text(json.dumps([
        {**base, "estado": "fallida", "detalle": "No se encontró el cuadro 'Escribe algo...'. ¿Sos miembro?"},
        {**base, "estado": "fallida", "detalle": "Facebook mostró un error al publicar"},
    ]), encoding="utf-8")
    h = Historial(archivo)
    assert [r.estado for r in h.registros] == ["error_navegador", "fallida"]
    assert len(h.actividad("Venta de Garage")) == 1


def test_reclasifica_el_intento_del_13_10(tmp_path):
    archivo = tmp_path / "historial.json"
    archivo.write_text(json.dumps([{
        "clave": "x", "publicacion_id": "netbook-2026-10-13", "grupo": "Alguien sabe Yo se? Por un Tafi mejor",
        "fecha_hora": "2026-10-13T11:36:00-03:00", "estado": "fallida",
        "detalle": 'Error inesperado: Locator.wait_for: Timeout 15000ms exceeded. Call log:   - waiting for '
                   'get_by_role("dialog").filter(has=get_by_role("textbox")).last to be visible'}]), encoding="utf-8")
    h = Historial(archivo)
    assert h.registros[0].estado == "error_navegador" and h.actividad() == []
