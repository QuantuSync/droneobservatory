"""Lo que se lee de una nota larga (modelo/paginas.py). Hasta el 12 de noviembre de 2026 el
extractor y el control recibían solo las 600 primeras letras: la nota de LRT de la noche del 10
al 11 de noviembre (EODI-2026-00792, 46 párrafos y 9.000 letras) cuenta el dron que entró desde
Bielorrusia en su párrafo 5 y el cierre de los aeropuertos de Vilna y Kaunas en el 10, y hubo que
ponerlos a mano. Ahora la nota se lee seguida hasta 3.000 letras."""

from pathlib import Path

from almacen.base import Almacen
from modelo import control, paginas
from proceso import extraccion
from recogida import control_fichas, extractor
from recogida.descarga import Descargador, Respuesta
from tests import ejemplos

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LRT = (FIXTURES / "lrt" / "3111025_larga.html").read_text(encoding="utf-8")
URL = (
    "https://www.lrt.lt/en/news-in-english/19/3111025/"
    "drone-incursions-trigger-air-alerts-across-lithuania-nato-jets-scrambled"
)
PRINCIPIO = "Drone incursions prompted yellow and red air alerts across large parts of Lithuania"
ENTRA = (
    "one drone is believed to have entered Lithuania from Belarus in the south, near Druskininkai"
)
CIERRE = (
    "The initial airport closure took place in Vilnius, followed by Kaunas. As the situation "
    "escalated and the drones entered, the airspace was closed again"
)
VUELOS = "only three flights at Vilnius Airport were affected, involving more than 400 passengers"
# Está en la letra 5.000 de la nota: sigue sin leerse.
LEJOS = "said earlier Wednesday that four drones had disrupted airspace in the region overnight"


def _nota(*parrafos: str) -> str:
    return "<html><body>" + "".join(f"<p>{p}</p>" for p in parrafos) + "</body></html>"


def test_el_cierre_de_vilna_y_kaunas_llega_aunque_este_en_el_parrafo_10() -> None:
    # Lo que se mandaba: las 600 primeras letras, sin el dron que entró ni el cierre.
    antes = paginas.primeras_frases(LRT, paginas.MAX_LETRAS_PRINCIPIO)
    assert antes.startswith(PRINCIPIO) and len(antes) <= 600
    assert ENTRA not in antes and "closure" not in antes and "closed" not in antes
    # Lo que se manda ahora: la nota seguida, hasta 3.000 letras.
    ahora = paginas.primeras_frases(LRT)
    assert ahora.startswith(antes) and 2500 < len(ahora) <= paginas.MAX_LETRAS
    assert ENTRA in ahora and CIERRE in ahora and VUELOS in ahora
    assert ahora.index(ENTRA) < ahora.index(CIERRE) < ahora.index(VUELOS)
    # Seguida: nada de frases sueltas de más abajo, y acaba en una frase entera.
    assert LEJOS not in ahora and "[…]" not in ahora
    assert ahora.endswith(".")


def test_quien_lee_la_pagina_recibe_lo_mismo_que_el_extractor() -> None:
    def sitio(url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        return 200, {}, LRT.encode()

    descargador = Descargador(sitio, dormir=lambda _s: None, pausa_minima_s=0)
    pagina = paginas.leer_pagina(descargador, URL)
    assert pagina.texto == paginas.primeras_frases(LRT) == paginas.leer(descargador, URL)
    assert CIERRE in pagina.texto


def test_el_principio_de_lo_leido_es_lo_que_se_leia_antes() -> None:
    # Para comparar fichas y para el filtro de entrada sigue bastando el principio: se saca de
    # lo leído y es, letra a letra, lo que se leía con el tope de 600.
    leido = paginas.primeras_frases(LRT)
    assert paginas.principio(leido) == paginas.primeras_frases(LRT, paginas.MAX_LETRAS_PRINCIPIO)
    corta = "Un dron obligó a cerrar el aeropuerto. El cierre duró 40 minutos."
    assert paginas.principio(corta) == corta and paginas.principio("") == ""


def test_una_nota_corta_se_manda_igual_que_antes() -> None:
    # La petición no cambia (y la respuesta guardada del modelo sigue valiendo).
    corta = _nota(
        "Un dron obligó a cerrar el aeropuerto de Vilna durante 40 minutos el martes por la noche.",
        "El Centro Nacional de Gestión de Crisis dijo que el dron entró desde Bielorrusia.",
    )
    assert paginas.primeras_frases(corta) == paginas.primeras_frases(corta, 600)


def test_verificar_ve_lo_que_leyo_el_extractor_y_comparar_el_principio() -> None:
    # El dato sacado del párrafo 10 tiene su frase delante cuando el control lo verifica; al
    # comparar dos fichas (y en el filtro de entrada) la petición es la de siempre.
    almacen = Almacen.abrir()
    incidente = ejemplos.incidente_minimo()
    enlace = str(incidente["fuentes"][0].get("enlace") or incidente["fuentes"][0]["id"])
    leido = paginas.primeras_frases(LRT)
    fuentes = control_fichas.fuentes_de_ficha(almacen, incidente, {enlace: leido})
    (bloque,) = fuentes.bloques
    assert CIERRE in bloque.bloque(1, completo=True) and CIERRE not in bloque.bloque(1)
    assert bloque.texto.startswith(paginas.principio(leido))
    assert len(bloque.bloque(1)) < 900
    # La frase literal que devuelva la verificación se comprueba contra lo leído entero.
    assert CIERRE in fuentes.comprobar[0][1]
    # La frase guardada de la fuente cabe detrás de lo leído.
    guardada = "Una frase guardada de la fuente, que va detrás de lo leído."
    larga = control.FuenteControl(
        "m", "f", "en", "t", "x", completo=f"{'x' * paginas.MAX_LETRAS} {guardada}"
    )
    assert guardada in larga.bloque(1, completo=True)
    # Quien no trae lo leído entero (el filtro de entrada) manda lo de siempre.
    assert (
        control.FuenteControl("m", "f", "en", "t", "abc").bloque(1, completo=True).endswith("abc")
    )


def test_la_pista_de_un_articulo_dirigido_sigue_delante_de_lo_leido() -> None:
    pista = "El ministro confirmó que eran drones militares."
    leido = "Una noticia que habla de otra cosa en sus primeras frases."
    assert extraccion.con_pista(leido, pista) == f"{pista} … {leido}"
    # Si lo leído ya la trae, o no hay pista, queda como está; sin página, queda la pista.
    assert extraccion.con_pista(f"{leido} {pista}", pista) == f"{leido} {pista}"
    assert extraccion.con_pista(leido, "") == leido
    assert extraccion.con_pista("", pista) == pista


def test_el_gasto_se_estima_con_lo_que_se_manda() -> None:
    assert control.MAX_LETRAS_COMPLETO > paginas.MAX_LETRAS > paginas.MAX_LETRAS_PRINCIPIO
    assert control.MAX_LETRAS_TEXTO == 700
    assert extractor.LETRAS_TITULAR + paginas.MAX_LETRAS == 3300
