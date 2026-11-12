"""Lo que se lee de una nota larga (modelo/paginas.py). Hasta el 12 de noviembre de 2026 el
extractor y el control recibían solo las 600 primeras letras: la nota de LRT de la noche del 10
al 11 de noviembre (EODI-2026-00792, 46 párrafos y 9.000 letras) cuenta el dron que entró desde
Bielorrusia en su párrafo 5 y el cierre de los aeropuertos de Vilna y Kaunas en el 10, y hubo que
ponerlos a mano. Ahora la nota se lee seguida hasta 3.000 letras."""

from pathlib import Path

from almacen.base import Almacen
from modelo import control, coste, ficha, paginas
from proceso import atribucion, extraccion, protegido, suceso, validacion_ficha, validaciones
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
    # El peor caso de una petición con tres notas largas cabe muchas veces en el tope del día.
    assert extractor.peor_caso_peticion() * 20 < coste.LIMITE_DIARIO_USD


# --- Lo que leer más texto no puede estropear (reproducción del 9 al 12 de noviembre de 2026) ---

# La nota de bnn-news.com del 9 de noviembre de 2026 (EODI-2026-00817): el ministro explica por
# qué no se derribó un dron «la semana pasada» y, más abajo, cuenta otro suceso: los restos
# hallados el sábado en Liepna, del objeto del 18 de octubre. Con 3.000 letras entran los dos.
BNN_PRINCIPIO = (
    "Following the failure to shoot down one of the drones that entered Latvian airspace last "
    "week, procedures have been reviewed and the decision-making chain shortened to enable "
    "faster responses in the future, Defence Minister Raivis Melnis said on Monday."
)
BNN_RESTOS = (
    "The State Police reported receiving information on Saturday morning about suspected drone "
    "debris found in a forest in Liepna Parish."
)
BNN_OCTUBRE = (
    "According to the NBS, information was received on the 18th of October about an "
    "explosion-like sound in Liepna Parish, Alūksne Municipality."
)
RELLENO = (
    "The minister explained that the teams on the ground will have greater authority to act "
    "when they detect a target, and that additional radar systems have been deployed."
)


def test_parish_no_es_paris() -> None:
    # «Liepna Parish» (un pagasts letón, en inglés) casaba con «Paris»: la validación daba la
    # frase por francesa y quitaba de la ficha la fecha, el lugar y la evidencia («la frase
    # habla de otro país (FR)»). En las noticias de Letonia en inglés, casi todos los sitios
    # son un «parish».
    for frase in (BNN_RESTOS, BNN_OCTUBRE, "the parish council met on Monday"):
        assert atribucion.de_otro_pais(frase, "LV") is None, frase
    # París sigue siendo Francia, también declinado.
    de_paris = (
        "a drone over Paris",
        "un dron sobre París",
        "dron nad Paryżem",
        "survolul Parisului de către o dronă",
        "Paris-Orly airport was closed",
    )
    for frase in de_paris:
        assert atribucion.de_otro_pais(frase, "LV") == "FR", frase
    validada = validacion_ficha.Validada(titulo_es="t", titulo_en="t")
    validada.campos = {
        "pais": {"valor": "LV", "fuente": 1, "frase": BNN_PRINCIPIO[:60], "confianza": 0.9},
        "inicio": {"valor": "2026-10-18", "fuente": 1, "frase": BNN_OCTUBRE, "confianza": 0.5},
        "lugar_suceso": {
            "valor": {"nombre": "Liepna Parish", "nivel": "localidad", "pais": "LV", "region": ""},
            "fuente": 1, "frase": BNN_RESTOS, "confianza": 0.9,
        },
    }  # fmt: skip
    validacion_ficha._sin_otro_pais(validada)
    assert {"inicio", "lugar_suceso"} <= set(validada.campos)
    assert not validada.motivos


def test_los_titulares_de_otras_noticias_no_son_texto_de_la_nota() -> None:
    # La página de b92.net de EODI-2026-00782 era su primera frase y una ristra de titulares de
    # otras noticias, cada uno un párrafo que es un enlace. Con 600 letras apenas entraban; con
    # 3.000, la ficha salió con el lugar y la presencia de uno de ellos.
    propia = (
        "Stanovnicima delova Letonije i Litvanije vlasti su poručile da se sklone na sigurno "
        "nakon što su neidentifikovani dronovi ušli u vazdušni prostor tih država."
    )
    otra = (
        "Borbeni avioni NATO-a dva puta su pokušali da obore dron koji je tokom noći iz "
        "Belorusije uleteo u litvanski vazdušni prostor, jedna od raketa pala je u okrugu Biržaj."
    )
    tarjeta = "Jato ptica pogrešno protumačeno kao dron, vlasti zatvorile aerodrom u Vilnjusu."
    con_enlace = (
        "Kako prenosi <a href='/agencija'>agencija</a>, upozorenje je važilo i za grad Kaunas "
        "i trajalo je do ranih jutarnjih sati u sredu."
    )
    html = (
        f"<html><body><p>{propia}</p><p><a href='/vest/1'>{otra}</a></p>"
        f"<a href='/vest/2'><p>{tarjeta}</p></a><p>{con_enlace}</p></body></html>"
    )
    leido = paginas.primeras_frases(html)
    assert propia in leido and "upozorenje je važilo i za grad Kaunas" in leido
    assert "Biržaj" not in leido and "Vilnjusu" not in leido
    # Una nota normal, con algún enlace dentro de sus frases, se lee igual que antes.
    assert CIERRE in paginas.primeras_frases(LRT)


def test_la_nota_con_dos_sucesos_llega_entera_y_las_instrucciones_dicen_cual_es_el_de_la_ficha(
) -> None:  # fmt: skip
    leido = paginas.primeras_frases(_nota(BNN_PRINCIPIO, *[RELLENO] * 8, BNN_RESTOS, BNN_OCTUBRE))
    assert BNN_RESTOS in leido and BNN_OCTUBRE in leido
    assert BNN_RESTOS not in paginas.principio(leido)
    # El modelo recibe los dos sucesos: lo que evita que los mezcle (la ficha de esa nota salió
    # como «restos de un dron en Liepna tras fallar su derribo», con el día del hallazgo) es que
    # las instrucciones digan cuál es el de la ficha, con esa nota de ejemplo.
    for regla in (
        "La ficha es de un solo suceso: el que cuentan el titular y el principio de las fuentes",
        "De esos otros sucesos no sale ningún dato de la ficha",
        "los titulares de otras noticias que el medio enlaza o añade al final",
        "Si no está claro que una frase hable del suceso de la ficha, no la uses",
        "Ejemplo 9 (una nota larga que cuenta además otro suceso)",
        "ni su lugar, ni la evidencia «restos» entran en la ficha ni en el título",
    ):
        assert regla in ficha.INSTRUCCIONES, regla
    for regla in (
        "Una nota larga cuenta a menudo, además, otros sucesos",
        "de esos no se toma ningún dato",
        "El día en que se halló algo, se investigó o se habló del suceso no es el día del suceso",
    ):
        assert regla in " ".join(control.INSTRUCCIONES_VERIFICAR.split()), regla
    # El ejemplo cabe en lo que se manda y no toma nada de Liepna.
    assert "lugar_suceso «Latvia; pais; LV;»" in ficha.INSTRUCCIONES


def test_leer_mas_texto_no_quita_precision_al_lugar() -> None:
    # EODI-2026-00788 (la nota de LRT): con la nota entera el lugar pasó a Druskininkai, que es
    # solo por donde entró el dron antes de cruzar el país; EODI-2026-00797: a Kaunas, donde
    # solo se le identificó, y no a Biržai, donde se le disparó y cayeron los restos del misil;
    # EODI-2026-00781: a uno de los dos municipios en alerta (Jēkabpils y Madona).
    # EODI-2026-00811: a Panevėžys, donde vive el vecino que cuenta la alerta.
    leido = paginas.primeras_frases(LRT)
    assert ENTRA in leido
    for texto in (ficha.INSTRUCCIONES, control.INSTRUCCIONES_VERIFICAR):
        junto = " ".join(texto.split())
        assert "donde cayó, explotó, se le disparó o se hallaron sus restos" in junto
        assert "el punto por el que entró" in junto
        assert "el pueblo de un testigo" in junto
    extractor_ = " ".join(ficha.INSTRUCCIONES.split())
    assert "Es el sitio más concreto que alguna fuente dé para este suceso" in extractor_
    # Sin sitio del suceso, el país; una región solo si la fuente la nombra (EODI-2026-00776:
    # «Tulcea» no estaba en la nota). Y no se elige la región en vez de la instalación cuando la
    # fuente da dos (La Hague y Flamanville, EODI-2026-00772): esa regla se probó y se quitó.
    assert "pon el país (o la región, solo si la fuente la nombra)" in extractor_
    assert "que los contiene" not in extractor_
    # El municipio va siempre que la fuente lo nombre, aunque el sitio sea una aldea que no se
    # sabe situar: sin él, EODI-2026-00795 (Eiminiškių kaimas, Biržų rajonas) quedó sin punto.
    assert "con lugar_suceso «Eiminiškių kaimas», localidad «Biržų rajonas»" in extractor_
    # Pero la localidad es la del lugar del suceso, no otra: con «ponla siempre» a secas, las
    # fichas de la noche de Lituania salieron con el punto en Druskininkai (por donde entró el
    # dron) o en Kaunas (por donde pasó).
    assert "Si lugar_suceso es el país o una región, no pongas localidad" in extractor_
    # Los tres drones que se vieron en Bielorrusia y no entraron no son los del suceso
    # (EODI-2026-00783, 00786 y 00789).
    assert "los que se detectaron en otro país y no entraron no cuentan" in " ".join(
        ficha.INSTRUCCIONES.split()
    )
    assert "no entraron en el de la ficha no cuentan" in " ".join(
        control.INSTRUCCIONES_VERIFICAR.split()
    )


def test_un_resumen_de_varios_paises_y_un_cierre_de_otra_causa() -> None:
    extractor_ = " ".join(ficha.INSTRUCCIONES.split())
    # EODI-2026-00807: un resumen de las alertas de Lituania, Letonia y Estonia (lo único
    # concreto, Kaunas) salió como suceso de Letonia, el país del candidato, y quedó suelto; el
    # mismo despacho en otra nota (EODI-2026-00820) dio Kaunas y se unió a la ficha de Lituania.
    # La regla es de la definición de suceso (proceso/suceso.py) y de allí la toman, con las
    # mismas palabras, las instrucciones del extractor y quien compara dos fichas.
    assert "del país del que la noticia da el dato más concreto" in suceso.PAIS_DEL_RESUMEN
    assert suceso.PAIS_DEL_RESUMEN in ficha.INSTRUCCIONES
    assert suceso.PAIS_DEL_RESUMEN in suceso.DEFINICION
    assert suceso.DEFINICION in control.INSTRUCCIONES_COMPARAR
    assert ficha.INSTRUCCIONES.count("el dato más concreto") == 1
    # EODI-2026-00790: el cierre de Vilna y Kaunas «įvyko būtent dėl balionų» (por los globos)
    # hizo la ficha interrupción aeroportuaria; el cierre de los drones es el segundo.
    assert "Un cierre que la fuente atribuye a otra causa (globos, niebla, otro suceso)" in (
        extractor_
    )
    assert "sí el que atribuye a los drones, aunque antes hubiera otro" in extractor_
    assert "atribuye a otra causa" in " ".join(control.INSTRUCCIONES_VERIFICAR.split())
    # La frase del cierre de la nota de LRT sigue siendo de su suceso.
    assert "the drones entered, the airspace was closed again" in paginas.primeras_frases(LRT)


def test_viena_en_lituano_no_es_austria() -> None:
    # «viena», «vienas», «vieną» son «una» y «uno» en lituano y casaban con Viena: la validación
    # quitaba el dato por «la frase habla de otro país (AT)» (la localidad de EODI-2026-00809,
    # el inicio de EODI-2026-00794, los drones de EODI-2026-00803).
    for frase in (
        "Netoli Vabalninko miestelio esančiame Eiminiškių kaime viena gyvenama sodyba",
        "šalies gyventojus vienas po kito pasiekė skirtingi oro pavojaus signalai",
        "Vienas dronas – trys NATO valstybės.",
    ):
        assert atribucion.de_otro_pais(frase, "LT") is None, frase
    for frase in ("Drohne über Wien gesichtet", "a drone over Vienna airport", "dron nad Wiedniem"):
        assert atribucion.de_otro_pais(frase, "LT") == "AT", frase


def test_la_respuesta_de_tres_notas_largas_cabe() -> None:
    # EODI-2026-00795: con tres notas largas de LRT la respuesta se cortó en el máximo de salida
    # (1.500 más el margen del razonamiento) y la lectura se perdió entera.
    assert ficha.MAX_TOKENS_SALIDA >= 2500
    assert ficha.cuerpo("x", [])["max_tokens"] == ficha.MAX_TOKENS_SALIDA


def test_el_tipo_retenido_se_queda_con_sus_vuelos() -> None:
    # EODI-2026-00792, publicada como «incursión»: al leerse su nota hasta más abajo («only three
    # flights at Vilnius Airport were affected») la versión nueva traía tres vuelos retrasados y
    # el tipo «interrupción aeroportuaria». El cerrojo retenía el tipo y dejaba pasar los vuelos:
    # lo retenido no validaba («hay interrupción de aeropuerto: manda ese tipo»), el cerrojo
    # fallaba y se quedaba con la versión guardada entera, con su aviso en la vigilancia.
    guardado = ejemplos.incidente_minimo()
    guardado["tipo"] = "sobrevuelo"
    nuevo = {
        **guardado,
        "tipo": "interrupcion_aeroportuaria",
        "consecuencias": {
            **(guardado.get("consecuencias") or {}),
            "vuelos_retrasados": {"min": 3, "max": 3},
        },
    }
    assert VUELOS in paginas.primeras_frases(LRT)
    assert validaciones.errores_tipo({**nuevo, "tipo": "sobrevuelo"})
    cambio = protegido.Cambio("tipo", protegido.MANUAL, "sobrevuelo", "interrupcion_aeroportuaria")
    resultado = protegido.conservar(nuevo, guardado, [cambio])
    assert resultado["tipo"] == "sobrevuelo"
    assert "vuelos_retrasados" not in (resultado.get("consecuencias") or {})
    assert not validaciones.errores_tipo(resultado)
    # Si el tipo no se retiene, los vuelos pasan con él.
    assert protegido.conservar(nuevo, guardado, [])["consecuencias"]["vuelos_retrasados"] == {
        "min": 3,
        "max": 3,
    }
