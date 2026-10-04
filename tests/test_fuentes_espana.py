"""Las dos fuentes españolas (docs/informe_errores_datos.md, bloque 7): las cifras oficiales de
contexto, que nunca se mezclan con los incidentes, y el lector de notas de la Guardia Civil."""

import json
from pathlib import Path

from exportacion.semanal import contexto_pais, validador_propio
from proceso import extraccion_oficial
from recogida import detalle, guardia_civil

FIXTURES = Path(__file__).parent / "fixtures"


def test_cifras_de_contexto_con_su_origen_y_sin_mezclarse() -> None:
    cifras = contexto_pais()
    assert {c["id"] for c in cifras} >= {"es-aena-drones-2019", "es-siglo-cd-semana-2020",
                                         "es-cumbre-granada-2023"}  # fmt: skip
    validador = validador_propio("contexto_pais")
    for cifra in cifras:
        publicada = {k: v for k, v in cifra.items() if k != "origen"}
        assert list(validador.iter_errors(publicada)) == []
        assert cifra["procedencia"]["valor"]["origen"] in {"oficial", "oficial_citado"}
    aena = {c["periodo"]["texto"]: c["valor"]["cifra"] for c in cifras
            if c["categoria"] == "Incidencias con drones en aeropuertos de Aena"}  # fmt: skip
    assert aena["2019"] == 132 and aena["2023 (hasta el 26 de noviembre)"] == 80
    # La respuesta del Gobierno publicada en el Congreso: origen oficial, no la prensa.
    assert all(
        c["origen"] == "oficial" and "congreso.es" in c["enlace"]
        for c in cifras if "Aena" in c["categoria"]
    )  # fmt: skip


LISTA = """
<ul>
<li class="elementoListado pagina_1" data-tipo="Noticia"> <div class="contenido_elemento">
<div class="fecha_elemento">12 marzo 2025</div>
<h3 class="titulo_elemento"> <a href="/es/destacados/noticias/Detenido-el-piloto-de-un-dron-que-sobrevolo-el-centro-penitenciario/" title="Detenido el piloto de un dron que sobrevoló el centro penitenciario de Alhaurín" class="enlace_elemento" target="_self"> Ir al detalle</a> x</h3>
<div class="descripcion"> La Guardia Civil ha identificado al piloto de un dron que sobrevoló sin autorización el centro penitenciario...</div>
</div> </li>
</ul>
"""  # noqa: E501


def test_lista_de_noticias() -> None:
    [entrada] = guardia_civil.entradas(LISTA)
    assert entrada["fecha"] == "2025-03-12"
    assert entrada["enlace"].startswith("https://web.guardiacivil.es/es/destacados/noticias/")
    assert entrada["titulo"].startswith("Detenido el piloto de un dron")


def test_que_es_un_incidente_y_que_no() -> None:
    si = [
        "Detenido el piloto de un dron que sobrevoló sin autorización el centro penitenciario",
        "Un dron intenta introducir hachís en la prisión de Puerto III; la Guardia Civil lo "
        "intercepta",
        "Denunciado el piloto de un dron que sobrevoló el aeropuerto de Málaga",
    ]
    no = [
        ("Desarticulada en Barbate una organización criminal que usaba drones y cámaras para "
         "vigilar los movimientos de los agentes en el narcotráfico", "contrabando"),
        ("132 guardias civiles darán seguridad a la Vuelta, con un equipo anti drones",
         "uso_propio"),
        ("Jornadas sobre sistemas aéreos no tripulados en el proyecto europeo COURAGEOUS",
         "divulgacion"),
    ]  # fmt: skip
    # Las notas reales que el filtro de palabras deja pasar entre 2024 y octubre de 2026: ninguna
    # es un incidente.
    no += [
        ("17 detenidos en una operación contra el tráfico de cocaína en el Guadalquivir. Los "
         "domicilios contaban con sistemas de vigilancia; incautados drones y armas.",
         "sin_instalacion"),
        ("Detenido un agresor que intentó huir saltando por los tejados. La Guardia Civil desplegó "
         "un dispositivo de localización, utilizando medios técnicos como drones.", "uso_propio"),
        ("Ingresa en prisión el supuesto autor. Agentes realizaron un operativo de búsqueda con "
         "apoyo del Servicio GEAS, Cinológico y Equipo de Drones en el embalse.", "uso_propio"),
    ]  # fmt: skip
    for texto in si:
        assert guardia_civil.es_incidente(texto) == (True, "incidente"), texto
    for texto, motivo in no:
        assert guardia_civil.es_incidente(texto) == (False, motivo), texto


def test_registrado_como_fuente_oficial_de_detalle_que_da_de_alta() -> None:
    fuentes = {f["id"]: f for f in detalle.fuentes()}
    fuente = fuentes["guardia_civil"]
    assert (fuente["fiabilidad"], fuente["pais"], fuente["grupo"]) == ("A", "ES", "investigaciones")
    assert detalle.RECOLECTORES["guardia_civil"] is guardia_civil.recolector_guardia_civil
    assert "guardia_civil" in extraccion_oficial.FUENTES_ALTA
    assert json.loads((Path(detalle.__file__).parent.parent / "configuracion" /
                       "fuentes_detalle.json").read_text(encoding="utf-8"))  # fmt: skip
