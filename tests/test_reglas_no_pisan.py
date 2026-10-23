"""Reglas que todavía pisaban lo revisado a mano o se pisaban entre ellas (23 de octubre de 2026):
una prueba por causa, con la ficha real cuando la hay."""

import json

from esquema import Documento
from proceso import control_fichas, decidir, detalle, incidentes, referencia, zona
from proceso.textos_dron import hora_local


def _copia(id_: str) -> Documento:
    ruta = referencia.DIRECTORIO / "fichas" / f"{id_}.json"
    documento: Documento = json.loads(ruta.read_text(encoding="utf-8"))
    return documento


def test_el_inicio_revisado_con_cita_de_una_noticia_no_lo_pisa_la_fecha_oficial() -> None:
    # Copenhague (2025-00154): el inicio revisado (18:30, cita de radiozet.pl) lleva el
    # identificador de la noticia, no uno revisada-…; la nota de balance de la policía ponía las
    # 20:00 cada hora y la revisión lo devolvía.
    copenhague = _copia("EODI-2025-00154")
    assert decidir.inicio_revisado(copenhague)
    tiempo = {
        "inicio": {"valor": "2025-09-22T18:30Z", "precision": "minuto"},
        "fin": {"valor": "2025-09-22T23:00Z", "precision": "minuto"},
        "duracion_min": 270,
        "origen_inicio": {"tipo": "explicita", "fuente_id": "gdelt-c3fd314cfffd8761"},
    }
    oficial = {"valor": "2025-09-22T20:00Z", "precision": "hora"}
    fuente = {"id": "detalle-1", "medio": "Politi", "enlace": "https://politi.dk"}
    assert detalle.inicio_oficial(tiempo, oficial, fuente, revisado=True) == tiempo
    # Sin revisión, la fecha oficial sigue mandando.
    assert detalle.inicio_oficial(tiempo, oficial, fuente)["inicio"] == oficial
    assert not decidir.inicio_revisado({"id": "EODI-2099-00001"})


def test_conservar_impide_tambien_sustituir_el_numero_de_drones() -> None:
    # Leipzig (2026-00134): la revisión dice 1-2; la verificación lee «eine Drohne» (1) y el
    # control apuntaba el cambio cada hora aunque el guardado volviera a 1-2.
    leipzig = {"id": "EODI-2026-00134", "drones": {"numero": {"min": 1, "max": 2}}}
    frase = "Spezialisten der Bundespolizei eine Drohne mit einer Sprengvorrichtung entschärft."
    verificada = control_fichas.Verificada({"drones": ({"min": 1, "max": 1}, "f1", frase)})
    correccion = control_fichas.Correccion(leipzig)
    control_fichas._drones(correccion, verificada, frozenset({"drones"}))
    assert correccion.incidente == leipzig and not correccion.cambios
    # Sin conservar, la verificación corrige el número.
    correccion = control_fichas.Correccion(leipzig)
    control_fichas._drones(correccion, verificada, frozenset())
    assert correccion.incidente["drones"]["numero"] == {"min": 1, "max": 1}


def test_conservar_impide_tambien_sustituir_la_duracion_del_cierre() -> None:
    ficha = {
        "id": "EODI-2099-00001",
        "consecuencias": {"cierre": {"valor": "si", "minutos": {"min": 210, "max": 210}}},
    }
    verificada = control_fichas.Verificada({
        "cierre": ("si", "f1", "Der Flughafen wurde gesperrt."),
        "duracion_min": ({"min": 60, "max": 60}, "f1", "Der Flughafen war eine Stunde gesperrt."),
    })  # fmt: skip
    correccion = control_fichas.Correccion(ficha)
    control_fichas._cierre(correccion, verificada, False, frozenset({"duracion_min"}))
    assert correccion.incidente == ficha and not correccion.cambios


def test_la_zona_la_decide_el_guardado() -> None:
    # 2026-00019 (23/10, 05:23): una unión del extractor rehacía la ficha sin zona y la
    # clasificación horaria la volvía a poner a los :32. Ahora cada guardado la decide.
    ficha = _copia("EODI-2025-00154")
    ficha.pop("zona", None)
    decidida = decidir.aplicar(ficha)
    assert decidida["zona"] == zona.clasificar(decidida)
    assert decidir.aplicar(decidida) == decidida


def test_la_instalacion_como_lugar_no_es_un_objetivo_que_se_llama_como_la_localidad() -> None:
    # Tarragona (2025-00404): con el lugar a nivel de instalación, el sitio del suceso es la
    # propia cárcel de Mas d'Enric; la auditoría A la contaba y el control la quitaba.
    carcel = {"categoria": "otra", "nombre": "Centre Penitenciari Mas d'Enric"}
    lugar = {"pais": "ES", "nivel": "instalacion", "suceso": "Centre penitenciari Mas d'Enric"}
    assert not incidentes.objetivo_es_la_localidad(carcel, lugar)
    # Un «objetivo» que es la localidad sigue sin serlo (2026-00648, Józefów).
    jozefow = {"categoria": "otra", "nombre": "Józefów"}
    assert incidentes.objetivo_es_la_localidad(jozefow, {"nivel": "localidad", "suceso": "Józefów"})


def test_la_hora_con_minutos_separados_por_h() -> None:
    # «à 4 h 30» se leía como las 4:00 (la forma «à 4» ganaba por empezar antes).
    for frase in (
        "Un drone a été aperçu à 4 h 30 au-dessus de la base",
        "Un drone a été aperçu à 4h30 au-dessus de la base",
        "Un drone a été aperçu à 4 h 30 min au-dessus de la base",
        "Un drone a été aperçu à 4 h 30 au-dessus de la base",
    ):
        assert hora_local(frase) == (4, 30), frase
    assert hora_local("Un drone a été aperçu à 4 h au-dessus de la base") == (4, 0)
    assert hora_local("Eine Drohne wurde um 21 Uhr gesichtet") == (21, 0)
