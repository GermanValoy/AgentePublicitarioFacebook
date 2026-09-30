import datetime as dt

from agente.planificador import ocurrencia_vigente, proxima_ocurrencia, tareas_del_momento
from agente.publicaciones import Publicacion

from .conftest import momento


def pub(**cambios):
    datos = dict(id="p1", fecha=dt.date(2026, 10, 5), hora=dt.time(10, 0), grupos=["Grupo A", "Grupo B"],
                 texto="texto")
    datos.update(cambios)
    return Publicacion(**datos)


def test_todavia_no_llega(config, historial):
    pendientes, vencidas = tareas_del_momento([pub()], config, historial, momento(config, "2026-10-05 09:59"))
    assert pendientes == vencidas == []


def test_una_tarea_por_grupo(config, historial):
    pendientes, _ = tareas_del_momento([pub()], config, historial, momento(config, "2026-10-05 10:00"))
    assert [t.grupo for t in pendientes] == ["Grupo A", "Grupo B"]


def test_todos_excluye_inactivos(config, historial):
    pendientes, _ = tareas_del_momento([pub(grupos=["todos"])], config, historial, momento(config, "2026-10-05 10:00"))
    assert {t.grupo for t in pendientes} == {"Grupo A", "Grupo B", "Solo Sabados"}


def test_desactivada(config, historial):
    pendientes, _ = tareas_del_momento([pub(activa=False)], config, historial, momento(config, "2026-10-05 11:00"))
    assert pendientes == []


def test_vence_si_pasa_el_retraso_maximo(config, historial):
    pendientes, vencidas = tareas_del_momento([pub()], config, historial, momento(config, "2026-10-05 22:01"))
    assert pendientes == [] and len(vencidas) == 2


def test_no_repite_lo_ya_publicado(config, historial):
    p = pub()
    ahora = momento(config, "2026-10-05 10:00")
    pendientes, _ = tareas_del_momento([p], config, historial, ahora)
    historial.agregar(pendientes[0].clave, p.id, pendientes[0].grupo, "publicada", ahora)
    pendientes, _ = tareas_del_momento([p], config, historial, ahora)
    assert [t.grupo for t in pendientes] == ["Grupo B"]


def test_reintentos_por_fallas(config, historial):
    p = pub(grupos=["Grupo A"])
    ahora = momento(config, "2026-10-05 10:00")
    clave = tareas_del_momento([p], config, historial, ahora)[0][0].clave
    historial.agregar(clave, p.id, "Grupo A", "fallida", ahora)
    assert tareas_del_momento([p], config, historial, ahora)[0]
    historial.agregar(clave, p.id, "Grupo A", "fallida", ahora)
    assert not tareas_del_momento([p], config, historial, ahora)[0]


def test_repeticion_periodica(config):
    p = pub(repetir_cada_dias=14)
    assert ocurrencia_vigente(p, config, momento(config, "2026-10-18 12:00")) == momento(config, "2026-10-05 10:00")
    assert ocurrencia_vigente(p, config, momento(config, "2026-10-19 10:00")) == momento(config, "2026-10-19 10:00")
    assert proxima_ocurrencia(p, config, momento(config, "2026-10-20 10:00")) == momento(config, "2026-11-02 10:00")
    assert proxima_ocurrencia(pub(), config, momento(config, "2026-10-06 10:00")) is None
