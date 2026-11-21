"""Notas largas en dos pasos (modelo/detalles.py, proceso/detalles.py). El paso 1 lee el principio
de cada noticia, como siempre, y decide el suceso; el paso 2 lee la nota seguida hasta 3.000 letras
y solo añade detalles de ese suceso, cada uno con su frase literal. Los casos son los del informe
de las notas largas del 12 de noviembre de 2026 (PR #470): lo que mejoraba con la nota larga tiene
que llegar, y lo que empeoraba no puede pasar porque el paso 2 no puede tocar el lugar, el país ni
el día, ni crear sucesos."""

import dataclasses
import json
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from modelo import coste, detalles, ficha, paginas
from proceso import detalles as paso2
from proceso import extraccion
from proceso.validacion_ficha import Contexto, validar
from tests.test_extraccion import AHORA, MODELOS, almacen, candidato_con_articulos

__all__ = ["almacen"]  # el fixture de la base en memoria

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LRT = (FIXTURES / "lrt" / "3111025_larga.html").read_text(encoding="utf-8")
CIERRE = (
    "The initial airport closure took place in Vilnius, followed by Kaunas. As the situation "
    "escalated and the drones entered, the airspace was closed again"
)
VUELOS = "only three flights at Vilnius Airport were affected, involving more than 400 passengers"
ENTRA = (
    "one drone is believed to have entered Lithuania from Belarus in the south, near Druskininkai"
)


def _dato(
    campo: str, valor: str, frase: str, confianza: float = 0.9, fuente: int = 1
) -> dict[str, Any]:
    return {"campo": campo, "valor": valor, "fuente": fuente, "frase": frase,
            "confianza": confianza}  # fmt: skip


def _paso1(*datos: dict[str, Any], titulo: str = "Drones sobre Lituania") -> dict[str, Any]:
    return {"datos": list(datos), "declaraciones": [], "titulo_es": titulo, "titulo_en": titulo}


def _paso2(*datos: dict[str, Any]) -> dict[str, Any]:
    return {"detalles": list(datos), "declaraciones": []}


def _respuesta(cuerpo: dict[str, Any]) -> dict[str, Any]:
    return {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": json.dumps(cuerpo, ensure_ascii=False)}],
        "usage": {"input_tokens": 1500, "output_tokens": 300, "cache_creation_input_tokens": 0,
                  "cache_read_input_tokens": 0},
    }  # fmt: skip


def _fuente(texto: str, nota: str, titular: str = "Drone incursions trigger air alerts") -> Any:
    return ficha.FuenteTexto(medio="lrt.lt", fecha="2026-11-11T08:00Z", idioma="en",
                             titular=titular, texto=texto, nota=nota)  # fmt: skip


LITUANIA = _paso1(
    _dato("es_incidente", "true", "Drone incursions prompted yellow and red air alerts"),
    _dato("pais", "LT", "across large parts of Lithuania"),
    _dato("lugar_suceso", "Lithuania; pais; LT;", "across large parts of Lithuania"),
    _dato("inicio", "2026-11-10", "on Tuesday night"),
    _dato("inicio_precision", "dia", "on Tuesday night"),
)


# --- Lo que se lee ---------------------------------------------------------------------------


def test_el_paso_1_lee_lo_mismo_que_antes_y_el_paso_2_la_nota_hasta_el_cierre() -> None:
    """00792: el cierre de Vilna y Kaunas está en el párrafo 10 de la nota de LRT."""
    principio = paginas.primeras_frases(LRT)
    assert len(principio) <= paginas.MAX_LETRAS == 600
    assert CIERRE not in principio and ENTRA not in principio
    nota = paginas.nota(LRT)
    assert nota.startswith(principio[:200]) and len(nota) <= paginas.MAX_LETRAS_NOTA
    assert CIERRE in nota and VUELOS in nota


def test_la_peticion_del_paso_1_no_cambia_con_la_nota() -> None:
    """Las respuestas guardadas del paso 1 siguen valiendo: la petición es idéntica."""
    sin = _fuente("Un dron obligó a cerrar el aeropuerto.", "")
    con = dataclasses.replace(sin, nota=paginas.nota(LRT))
    assert ficha.cuerpo("x", [sin]) == ficha.cuerpo("x", [con])


def test_la_nota_no_lee_los_parrafos_que_son_titulares_de_otras_noticias() -> None:
    """b92.net (00782): la página trae, como párrafos, titulares enlazados de otras noticias."""
    html = (
        "<html><body><p>Dron iz Belorusije uleteo je tokom noći u litvanski vazdušni prostor, "
        "saopštile su vlasti.</p>"
        "<p><a href='/x'>Dron pao u Rumuniji, vojska kaže da je bio ruski Geran</a></p>"
        "<p>Aerodrom u Vilnjusu bio je zatvoren dva sata zbog drona, navode litvanske vlasti.</p>"
        "</body></html>"
    )
    nota = paginas.nota(html)
    assert "Rumuniji" not in nota and "Vilnjusu" in nota
    # El principio (paso 1) sigue como siempre, con el párrafo enlazado incluido.
    assert "Rumuniji" in paginas.primeras_frases(html)


# --- Lo que puede añadir el paso 2 -----------------------------------------------------------


def test_00792_el_paso_2_anade_el_cierre_y_los_vuelos_con_su_frase() -> None:
    fuentes = [_fuente(paginas.primeras_frases(LRT), paginas.nota(LRT))]
    respuesta = _paso2(
        _dato("cierre", "si", CIERRE[:120]),
        _dato("vuelos_retrasados", "3", VUELOS),
    )
    fusionada, anadidos = paso2.fusionar(LITUANIA, respuesta, fuentes)
    assert anadidos == ["cierre", "vuelos_retrasados"]
    leida = ficha.leer_respuesta(_respuesta(fusionada))
    assert leida["cierre"]["valor"] == "si" and leida["cierre"]["paso"] == 2
    assert leida["vuelos_retrasados"]["valor"] == {"min": 3, "max": 3}
    # La validación busca su frase en la nota; con solo el principio, no vale.
    textos = (f"{fuentes[0].titular}. {fuentes[0].texto}",)
    con_nota = Contexto(textos=textos, pais_objetivo="LT", primer_articulo=AHORA, ahora=AHORA,
                        notas=(f"{textos[0]} {fuentes[0].nota}",))  # fmt: skip
    assert "cierre" in validar(leida, con_nota).campos
    sin_nota = dataclasses.replace(con_nota, notas=())
    assert "cierre" not in validar(leida, sin_nota).campos


def test_el_paso_2_no_cambia_lo_que_dijo_el_paso_1() -> None:
    fuentes = [_fuente("Two drones entered.", "Two drones entered. Officials later said one.")]
    paso1 = _paso1(*LITUANIA["datos"], _dato("drones", "2", "Two drones entered"))
    _, anadidos = paso2.fusionar(paso1, _paso2(_dato("drones", "1", "Officials later said one")),
                                 fuentes)  # fmt: skip
    assert anadidos == []


def test_la_hora_solo_si_es_del_mismo_dia_que_dio_el_paso_1() -> None:
    nota = "Drones over Lithuania. The alert started at 23:20 on Tuesday. Debris found Saturday."
    fuentes = [_fuente("Drones over Lithuania.", nota)]
    mismo = _paso2(
        _dato("inicio", "2026-11-10T21:20", "The alert started at 23:20 on Tuesday"),
        _dato("inicio_precision", "minuto", "The alert started at 23:20 on Tuesday"),
    )
    fusionada, anadidos = paso2.fusionar(LITUANIA, mismo, fuentes)
    assert anadidos == ["inicio", "inicio_precision"]
    inicio = [d for d in fusionada["datos"] if d["campo"] == "inicio"]
    assert [d["valor"] for d in inicio] == ["2026-11-10T21:20"]
    # Otro día (la hora local tomada en otro día, o el día del hallazgo): no cambia el día.
    otro = _paso2(_dato("inicio", "2026-11-11T01:20", "The alert started at 23:20 on Tuesday"))
    assert paso2.fusionar(LITUANIA, otro, fuentes)[1] == []


def test_00817_liepna_el_hallazgo_de_otro_dia_no_entra() -> None:
    """bnn-news: el dron que no se derribó la semana anterior; los restos de Liepna y el ruido del
    18 de octubre son otro suceso que la nota añade. Ni su fecha, ni su lugar, ni su evidencia."""
    nota = (
        "Following the failure to shoot down one of the drones that entered Latvian airspace last "
        "week, procedures have been reviewed. The State Police reported receiving information on "
        "Saturday morning about suspected drone debris found in a forest in Liepna Parish."
    )
    fuentes = [_fuente(nota[:120], nota, titular="Why did Latvia's military fail?")]
    paso1 = _paso1(
        _dato("es_incidente", "true", "the drones that entered Latvian airspace last week"),
        _dato("pais", "LV", "Latvian airspace"),
        _dato("lugar_suceso", "Latvia; pais; LV;", "Latvian airspace"),
        _dato("inicio", "2026-11-09", "entered Latvian airspace last week"),
    )
    propuesta = {
        "detalles": [
            _dato("inicio", "2026-11-07T08:00", "on Saturday morning about suspected drone debris"),
            _dato("lugar_suceso", "Liepna Parish; localidad; LV;", "a forest in Liepna Parish"),
            _dato("evidencia", "restos", "suspected drone debris found in a forest"),
        ],
        "declaraciones": [],
    }
    fusionada, anadidos = paso2.fusionar(paso1, propuesta, fuentes)
    assert anadidos == []
    assert fusionada["datos"] == paso1["datos"]


def test_kotka_druskininkai_y_panevezys_el_lugar_es_siempre_el_del_paso_1() -> None:
    """00793 (Kotka), 00783 (Druskininkai, por donde entró) y 00811 (Panevėžys, el pueblo de un
    vecino): con la nota entera de una vez salían puntos falsos. El paso 2 no tiene ese campo."""
    assert not {"lugar_suceso", "localidad", "pais", "es_incidente", "lugar_nuevo"} & set(
        detalles.CAMPOS
    )
    nota = f"Drone incursions prompted alerts. {ENTRA}. A resident of Panevėžys saw lights."
    fuentes = [_fuente("Drone incursions prompted alerts.", nota)]
    propuesta = {"detalles": [
        _dato("lugar_suceso", "Druskininkai; localidad; LT;", ENTRA),
        _dato("localidad", "Panevėžys", "A resident of Panevėžys saw lights"),
        _dato("pais", "FI", "Kotka and Hamina"),
    ], "declaraciones": []}  # fmt: skip
    fusionada, anadidos = paso2.fusionar(LITUANIA, propuesta, fuentes)
    assert anadidos == [] and fusionada == LITUANIA


def test_una_frase_que_no_esta_en_la_nota_no_vale() -> None:
    """Un dato del avance de otra noticia (b92.net) o inventado: sin su frase en la nota, fuera."""
    fuentes = [_fuente("Dron nad Litvom.", "Dron nad Litvom. Aerodrom zatvoren.")]
    propuesta = _paso2(_dato("cierre", "si", "Aerodrom u Rumuniji zatvoren"),
                       _dato("drones", "4", "četiri drona"))  # fmt: skip
    assert paso2.fusionar(LITUANIA, propuesta, fuentes)[1] == []


def test_las_declaraciones_nuevas_con_su_frase_literal() -> None:
    nota = 'Drones over Lithuania. "The drone came from Belarus," the army said.'
    fuentes = [_fuente("Drones over Lithuania.", nota)]
    buena = {"autoridad": "Lithuanian Armed Forces", "pais": "LT", "categoria": "fuerzas_armadas",
             "afirma": "drones", "autor": "", "autor_tipo": "", "autor_pais": "",
             "autor_situacion": "", "cita_literal": True, "fuente": 1,
             "frase": "The drone came from Belarus"}  # fmt: skip
    mala = {**buena, "frase": "The drone came from Russia"}
    fusionada, anadidos = paso2.fusionar(
        LITUANIA, {"detalles": [], "declaraciones": [buena, mala]}, fuentes
    )
    assert anadidos == ["declaraciones:1"]
    assert [d["frase"] for d in fusionada["declaraciones"]] == ["The drone came from Belarus"]


# --- Cuándo se llama ---------------------------------------------------------------------------


class Cliente:
    """Responde al paso 1 con su ficha y al paso 2 con sus detalles; anota lo que se pide."""

    def __init__(self, paso1: dict[str, Any], paso2_: dict[str, Any]) -> None:
        self.paso1, self.paso2 = paso1, paso2_
        self.pedidas: list[str] = []

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        es_paso2 = cuerpo["system"][0]["text"] == detalles.INSTRUCCIONES
        self.pedidas.append("paso2" if es_paso2 else "paso1")
        return _respuesta(self.paso2 if es_paso2 else self.paso1)


def test_misiles_en_moldavia_sin_incidente_no_hay_paso_2() -> None:
    """La ficha suelta de dos misiles de crucero sobre Moldavia (PR #470): el paso 1 dice que no es
    un incidente con drones y el paso 2 ni se llama, así que no puede crear ningún suceso."""
    nota = "Two cruise missiles crossed Moldovan airspace. " + "x" * 500
    fuentes = [_fuente("Two cruise missiles crossed Moldovan airspace.", nota)]
    paso1 = _paso1(_dato("es_incidente", "false", "Two cruise missiles crossed Moldovan airspace"))
    cliente = Cliente(paso1, {"detalles": [], "declaraciones": []})
    respuesta, anadidos = paso2.completar(
        cliente, _respuesta(paso1), fuentes, 0.0, coste.Modo.HORARIO, None, lambda _r: None
    )
    assert cliente.pedidas == [] and anadidos == [] and respuesta == _respuesta(paso1)


def test_una_nota_corta_no_tiene_paso_2() -> None:
    fuentes = [_fuente("Un dron cerró el aeropuerto.", "Un dron cerró el aeropuerto.")]
    assert not paso2.hace_falta(LITUANIA, fuentes)


def test_sin_margen_en_el_tope_la_ficha_sale_con_el_paso_1() -> None:
    fuentes = [_fuente(paginas.primeras_frases(LRT), paginas.nota(LRT))]
    cliente = Cliente(LITUANIA, _paso2(_dato("cierre", "si", CIERRE[:120])))
    lleno = coste.limite(coste.Modo.HORARIO)
    _, anadidos = paso2.completar(
        cliente, _respuesta(LITUANIA), fuentes, lleno, coste.Modo.HORARIO, None, lambda _r: None
    )
    assert cliente.pedidas == [] and anadidos == []


def test_la_extraccion_hace_el_paso_2_lo_anota_y_publica_el_cierre(almacen: Almacen) -> None:
    candidato = candidato_con_articulos(almacen)
    peticion = extraccion.preparar(almacen, candidato, None)
    from tests.test_extraccion import TEXTO, a_servicio, ficha_ejemplo

    # La ficha de Copenhague sin el cierre ni los vuelos, que la nota da más abajo.
    datos = ficha_ejemplo()
    datos["cierre"] = {"valor": None}
    datos["vuelos_desviados"] = {"valor": None}
    datos["tipo"] = {"valor": None}
    paso1 = a_servicio(datos)
    principio = TEXTO.replace(" 31 fly blev omdirigeret.", "")
    nota = f"{principio} " + "Mere tekst om sagen. " * 20 + "31 fly blev omdirigeret til Billund."
    fuentes = [dataclasses.replace(f, texto=principio, nota=nota) for f in peticion.fuentes]
    peticion = dataclasses.replace(peticion, fuentes=fuentes)
    cliente = Cliente(paso1, _paso2(_dato("vuelos_desviados", "31", "31 fly blev omdirigeret")))
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == ["paso1", "paso2"]
    (id_,) = hechas.incidentes
    assert id_ is not None
    incidente = almacen.incidente(id_)
    assert incidente is not None
    assert incidente["consecuencias"]["vuelos_desviados"]["min"] == 31
    # Con vuelos afectados, el tipo es el de la interrupción (proceso/incidentes.con_tipo).
    assert incidente["tipo"] == "interrupcion_aeroportuaria"
    (extraida,) = almacen.extracciones(candidato["id"])
    assert extraida[paso2.CLAVE] == ["vuelos_desviados"]
    # Las dos llamadas cuentan en el gasto del modo.
    assert len([ll for ll in almacen.llamadas() if ll["candidato"] == candidato["id"]]) == 2
