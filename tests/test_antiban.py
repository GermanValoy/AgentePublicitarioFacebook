from agente import antiban

from .conftest import momento


def publicar(historial, config, cuando, grupo="Grupo A", estado="publicada"):
    historial.agregar(f"x|{grupo}|{cuando}", "x", grupo, estado, momento(config, cuando))


def test_permitido_sin_historial(config, historial):
    assert antiban.evaluar(momento(config, "2026-10-05 10:00"), "Grupo A", config, historial).permitido


def test_fuera_de_horario(config, historial):
    d = antiban.evaluar(momento(config, "2026-10-05 22:30"), "Grupo A", config, historial)
    assert not d.permitido and "horario" in d.motivo


def test_minimo_entre_publicaciones(config, historial):
    publicar(historial, config, "2026-10-05 10:00")
    assert not antiban.evaluar(momento(config, "2026-10-05 10:30"), "Grupo B", config, historial).permitido
    assert antiban.evaluar(momento(config, "2026-10-05 10:46"), "Grupo B", config, historial).permitido


def test_maximo_por_dia(config, historial):
    for hora, grupo in (("09:00", "Grupo A"), ("10:00", "Grupo B"), ("11:00", "Solo Sabados")):
        publicar(historial, config, f"2026-10-05 {hora}", grupo)
    d = antiban.evaluar(momento(config, "2026-10-05 15:00"), "Otro", config, historial)
    assert not d.permitido
    d = antiban.evaluar(momento(config, "2026-10-05 15:00"), "Grupo A", config, historial)
    assert not d.permitido and "hoy" in d.motivo


def test_intentos_fallidos_cuentan_simulaciones_no(config, historial):
    publicar(historial, config, "2026-10-05 10:00", estado="fallida")
    assert not antiban.evaluar(momento(config, "2026-10-05 10:10"), "Grupo B", config, historial).permitido
    historial.registros.clear()
    publicar(historial, config, "2026-10-05 10:00", estado="simulada")
    assert antiban.evaluar(momento(config, "2026-10-05 10:10"), "Grupo A", config, historial).permitido


def test_descanso_por_grupo(config, historial):
    publicar(historial, config, "2026-10-01 10:00", "Grupo A")
    assert not antiban.evaluar(momento(config, "2026-10-05 10:00"), "Grupo A", config, historial).permitido
    assert antiban.evaluar(momento(config, "2026-10-05 10:00"), "Grupo B", config, historial).permitido
    assert antiban.evaluar(momento(config, "2026-10-08 10:01"), "Grupo A", config, historial).permitido


def test_dias_permitidos_del_grupo(config, historial):
    assert not antiban.evaluar(momento(config, "2026-10-05 10:00"), "Solo Sabados", config, historial).permitido
    assert antiban.evaluar(momento(config, "2026-10-10 10:00"), "Solo Sabados", config, historial).permitido


def test_grupo_inactivo(config, historial):
    assert not antiban.evaluar(momento(config, "2026-10-05 10:00"), "Inactivo", config, historial).permitido


def test_pausa_de_emergencia(config, historial):
    antiban.pausar(config, "Bloqueo temporal")
    d = antiban.evaluar(momento(config, "2026-10-05 10:00"), "Grupo A", config, historial)
    assert not d.permitido and "pausado" in d.motivo
    antiban.reanudar(config)
    assert antiban.evaluar(momento(config, "2026-10-05 10:00"), "Grupo A", config, historial).permitido
