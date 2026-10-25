"""Un solo sitio decide los datos de un incidente: el estado, la presencia del dron, el tipo, la
instalación afectada (objetivo), el lugar, el día de inicio, el número de drones, el titular (en
español y en inglés) y, con ellos, la cabecera de la ficha.

Los demás pasos de la recogida (el extractor, las declaraciones oficiales, la competencia entre
autoridades, las rectificaciones, el control de las fichas, las fusiones y las revisiones a mano de
configuracion/incidentes_revisados.json) aportan pruebas: fuentes con su frase, pasos del historial
del estado con su fuente, afirmaciones y pasos de `presencia_historial`. `decidir_estado` y
`decidir_presencia` calculan el valor a partir de esas pruebas con el método
(docs/rectificaciones.md, docs/control_fichas.md) y devuelven también qué fuente y qué regla lo
deciden; `decidir_datos` decide los demás datos con las reglas de docs/control_fichas.md
(«Criterios de cada dato») y las revisiones a mano de esos datos, cada una con su cita
(configuracion/incidentes_revisados.json, «datos»). `aplicar` deja el incidente con esos valores;
lo llama `Almacen.guardar_incidente` cada vez que se guarda, así que lo que escriba otro paso
antes no es lo que queda.
"""

import copy
import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso import atribucion, competencia, declaraciones, incidentes, rectificaciones, titulares
from proceso.estados import Estado
from proceso.noticias import normalizar

CONFIGURACION = Path(__file__).resolve().parent.parent / "configuracion"
# Los datos que una revisión a mano puede fijar, con su cita («datos»).
CAMPOS_REVISABLES = ("objetivo", "lugar", "inicio", "drones", "cierre", "titulo", "zona")
# Una cárcel es una instalación de categoría «otra» (docs/control_fichas.md).
_CARCEL = re.compile(
    r"\b(?:centro penitenciario|prisi[oó]n|c[aá]rcel|prison|penitenciar|zak[lł]ad karny|"
    r"wi[eę]zienie|justizvollzugsanstalt|jva|f[aä]ngelse|vankila|v[aä]ngelse|gevangenis)",
    re.IGNORECASE,
)

# Las fuentes de una revisión a mano (configuracion/incidentes_revisados.json): mandan.
REVISADA = "revisada-"


@dataclass(frozen=True)
class Decision:
    valor: str
    fuente_id: str | None
    regla: str


def _historial_vigente(incidente: Documento) -> Documento:
    """El incidente con el desmentido que no vale ya corregido (proceso/competencia.py): una frase
    que no niega nada o una autoridad que cede frente a otra competente que lo confirmó. Tampoco
    vale el desmentido que solo niega el dron o su hallazgo («n'avaient permis de retrouver aucun
    drone», EODI-2025-00357) o lo explica por otra causa (una bandada de pájaros, EODI-2026-00007):
    el suceso, el aviso, ocurrió; lo que se rectifica es la presencia."""
    corregido = competencia.corregir_desmentido(incidente)
    resultado = corregido[0] if corregido else incidente
    historial = resultado["estado"]["historial"]
    if len(historial) > 1 and historial[-1]["estado"] == Estado.DESMENTIDO:
        from proceso import presencia

        fuentes = {f["id"]: f for f in resultado.get("fuentes", [])}
        frase = str((fuentes.get(historial[-1].get("fuente_id") or "") or {}).get("frase_origen"))
        if presencia.dice_no_hallado(frase) or presencia.otra_causa(resultado):
            resultado = copy.deepcopy(resultado)
            resultado["estado"]["historial"] = historial[:-1]
            resultado["estado"]["actual"] = historial[-2]["estado"]
            resultado.get("control", {}).pop("motivo_desmentido", None)
    return resultado


def _autoridad_que_lo_cuenta(incidente: Documento) -> Documento | None:
    """La primera autoridad u operador oficial que cuenta lo ocurrido (el portavoz del aeropuerto,
    el control aéreo, la policía o el ministerio), aunque diga que no encontró el dron o que era
    otra cosa: el suceso queda confirmado (docs/control_fichas.md, «estado»)."""
    autoridades = [
        f for f in incidente.get("fuentes", [])
        if declaraciones.de_autoridad(f) and str(f.get("frase_origen") or "").strip()
    ]  # fmt: skip
    return min(autoridades, key=lambda f: (f["fecha"]["valor"], f["id"]), default=None)


def decidir_estado(incidente: Documento) -> Decision:
    """El estado es el último paso de su historial (cada paso lo da una fuente: la noticia, la
    declaración de una autoridad, la revisión a mano o la rectificación del control), salvo un
    desmentido que no vale; y «confirmado» si sigue «notificado» y una autoridad cuenta lo
    ocurrido."""
    vigente = _historial_vigente(incidente)
    historial = vigente["estado"]["historial"]
    if not historial:
        return Decision(str(incidente["estado"]["actual"]), None, "sin_historial")
    ultimo = historial[-1]
    # Un paso que retira la confirmación con su motivo (una revisión a mano o el control de las
    # fichas) manda: la regla no la vuelve a confirmar.
    if (
        ultimo["estado"] == Estado.NOTIFICADO
        and not ultimo.get("motivo")
        and (cuenta := _autoridad_que_lo_cuenta(vigente))
    ):
        return Decision(Estado.CONFIRMADO.value, str(cuenta["id"]), "autoridad_lo_cuenta")
    regla = "competencia" if historial is not incidente["estado"]["historial"] else "historial"
    return Decision(str(ultimo["estado"]), ultimo.get("fuente_id"), regla)


def _afirmada(incidente: Documento, fuente_id: str) -> str | None:
    for afirmacion in incidente.get("afirmaciones", []):
        if afirmacion.get("campo") == "presencia_dron" and afirmacion.get("fuente_id") == fuente_id:
            return str(afirmacion["valor"])
    return None


@cache
def _revisadas() -> dict[str, str]:
    """La presencia revisada a mano de cada incidente, con su cita (configuracion/
    incidentes_revisados.json, «titulares»)."""
    from proceso import presencia

    datos = json.loads(presencia.REVISADOS.read_text(encoding="utf-8"))
    return {
        str(t["incidente"]): str(t["presencia"]["valor"])
        for t in datos.get("titulares", [])
        if isinstance(t.get("presencia"), dict) and t["presencia"].get("valor")
    }


def revisiones(incidente: Documento) -> dict[str, Documento]:
    """{dato: revisión} a mano de la ficha (incidentes_revisados.json, «datos»)."""
    return _revisiones(incidente)


@cache
def _inicios_revisados() -> frozenset[str]:
    """Los incidentes con el inicio revisado a mano («titulares.inicio» o «datos», «inicio»), sea
    cual sea la fuente de su cita (una noticia, una revisada-…)."""
    from proceso import presencia

    datos = json.loads(presencia.REVISADOS.read_text(encoding="utf-8"))
    ids = {
        str(t["incidente"]) for t in datos.get("titulares", []) if isinstance(t.get("inicio"), dict)
    }
    ids |= {str(r["incidente"]) for r in datos.get("datos", []) if r.get("campo") == "inicio"}
    return frozenset(ids)


def inicio_revisado(incidente: Documento) -> bool:
    """El inicio de la ficha está revisado a mano: ninguna regla lo pisa (lo reconoce por el
    identificador de la ficha, no por la fuente: el de EODI-2025-00154 cita una noticia)."""
    return str(incidente.get("id")) in _inicios_revisados()


def presencias_revisadas() -> dict[str, str]:
    """{incidente: presencia} revisada a mano con su cita: manda también en la validación."""
    return _revisadas()


def _abierta(incidente: Documento, negadas: frozenset[str]) -> bool:
    """Lo que deja abierta la presencia aunque una autoridad la atribuya a un dron (las mismas
    condiciones que proceso/presencia.pendientes): un desmentido,
    una fuente que cuenta que no se encontró el dron sin pruebas físicas, o una fuente
    en que el control de las fichas lee que no se encontró o que se desmiente."""
    from proceso import presencia

    if incidente["estado"]["actual"] == Estado.DESMENTIDO:
        return True
    if presencia.no_hallado(incidente) is not None and not (
        presencia.pruebas_fisicas_confirmadas(incidente)
    ):
        return True
    return bool(negadas & {str(f["id"]) for f in incidente.get("fuentes", [])})


def decidir_presencia(
    incidente: Documento, negadas: frozenset[str] = frozenset(), confirmada: bool = False
) -> Decision:
    """La presencia del dron por orden de prioridad:

    1. rectificación: el último paso de `presencia_historial` (una autoridad lo rectificó; lo
       decide el experto o una revisión a mano con su cita);
    2. revisión a mano: la cita revisada de configuracion/incidentes_revisados.json, que entra como
       una fuente más con su afirmación;
    3. documento oficial: la autoridad lo dice en su propio documento;
    4. descartada: una fuente afirma que era otra cosa (la autoridad, o la noticia que cuenta lo
       que concluyó);
    5. una autoridad lo atribuye a un dron (salvo lo que la deja abierta, `_abierta`; `negadas`
       son las fuentes en que el control de las fichas lee que no se encontró el dron), o
       pruebas físicas con el suceso confirmado: confirmada;
    6. si no, no confirmada (lo dejan abierto o solo lo cuentan la prensa o los testigos).
    """
    pasos = [p for p in incidente.get("presencia_historial") or [] if not p.get("parcial")]
    if pasos:
        return Decision(str(pasos[-1]["valor"]), pasos[-1].get("fuente_id"), "rectificacion")
    fuentes = incidente.get("fuentes", [])
    # La presencia revisada a mano manda sobre lo que afirma una cita revisada: la cita del MApN
    # en EODI-2025-00378 confirma la alerta, y la revisión dice que el dron no entró en Rumanía.
    if incidente["id"] in _revisadas():
        return Decision(_revisadas()[incidente["id"]], REVISADA + "titular", "revision")
    for afirmacion in incidente.get("afirmaciones", []):
        if afirmacion.get("campo") == "presencia_dron" and str(
            afirmacion.get("fuente_id", "")
        ).startswith(REVISADA):
            return Decision(str(afirmacion["valor"]), str(afirmacion["fuente_id"]), "revision")
    for fuente in fuentes:
        if fuente.get("documento_oficial") and "presencia_dron" in fuente.get(
            "campos_respaldados", []
        ):
            valor = _afirmada(incidente, str(fuente["id"]))
            if valor is not None:
                return Decision(valor, str(fuente["id"]), "documento_oficial")
    for afirmacion in incidente.get("afirmaciones", []):
        # La autoridad dice que era otra cosa, en su declaración o en la noticia que la cuenta.
        if afirmacion.get("campo") == "presencia_dron" and afirmacion.get("valor") == (
            rectificaciones.DESCARTADA
        ):
            return Decision(rectificaciones.DESCARTADA, str(afirmacion["fuente_id"]), "descartada")
    # Lo que la deja abierta impide confirmarla de nuevo, pero no baja la que ya estaba confirmada
    # (`confirmada`, lo guardado): eso lo hacen las rectificaciones y el criterio de presencia.
    for fuente in fuentes if confirmada or not _abierta(incidente, negadas) else []:
        # Una autoridad lo atribuye a un dron sin dejarlo abierto.
        if declaraciones.de_autoridad(fuente) and declaraciones.atribuye_dron(
            str(fuente.get("frase_origen") or "")
        ):
            return Decision("confirmada", str(fuente["id"]), "autoridad_atribuye")
    fisicas = set((incidente.get("pruebas") or {}).get("evidencia", [])) & (
        incidentes.PRUEBAS_FISICAS
    )
    if fisicas and incidente["estado"]["actual"] in incidentes.CONFIRMADOS:
        return Decision("confirmada", None, "pruebas_fisicas")
    return Decision("no_confirmada", None, "sin_autoridad")


@cache
def _revisiones_de_datos() -> dict[str, dict[str, Documento]]:
    """{incidente: {dato: revisión}} de configuracion/incidentes_revisados.json, «datos»: el
    valor correcto de un dato que la regla no puede sacar de las fuentes de la ficha, con la cita
    de la fuente que lo dice y su enlace."""
    from proceso import presencia

    datos = json.loads(presencia.REVISADOS.read_text(encoding="utf-8"))
    resultado: dict[str, dict[str, Documento]] = {}
    for revision in datos.get("datos", []):
        resultado.setdefault(str(revision["incidente"]), {})[str(revision["campo"])] = revision
    return resultado


def _revisiones(incidente: Documento) -> dict[str, Documento]:
    """Las revisiones de datos de este incidente: las que citan una de sus fuentes o, si la fuente
    leída no está en la ficha, las de su país (una ficha de prueba con el mismo identificador no
    las toma)."""
    enlaces = {f.get("enlace") for f in incidente.get("fuentes", [])}
    pais = (incidente.get("lugar") or {}).get("pais")
    return {
        campo: revision
        for campo, revision in _revisiones_de_datos().get(str(incidente.get("id")), {}).items()
        if revision.get("enlace") in enlaces or revision.get("pais") == pais
    }


def revision_de(incidente: Documento, campo: str) -> Documento | None:
    """La revisión a mano de un dato de este incidente (la zona la lee proceso/zona.py)."""
    return _revisiones(incidente).get(campo)


@cache
def _nomenclator() -> dict[tuple[str, str], Documento]:
    """{(país, nombre normalizado): instalación} de los aeropuertos, bases e instalaciones del
    nomenclátor; con el mismo alias en un país, la del nomenclátor inicial (lugares_europa.json)."""
    indice: dict[tuple[str, str], Documento] = {}
    for fichero in ("lugares_europa.json", "instalaciones_europa.json"):
        lugares = json.loads((CONFIGURACION / fichero).read_text(encoding="utf-8"))["lugares"]
        for lugar in lugares.values():
            for alias in {lugar["nombre"], *lugar.get("alias", [])}:
                indice.setdefault((str(lugar.get("pais")), normalizar(alias)), lugar)
    return indice


def instalacion_del_nomenclator(objetivo: Documento, pais: str | None) -> Documento | None:
    """La instalación del nomenclátor que nombra el objetivo en su país, si la hay: la de ese
    nombre o, si no, la única con OACI cuyo nombre lo contiene («Schiphol», Luchthaven
    Schiphol)."""
    nombre = normalizar(str(objetivo.get("nombre") or ""))
    if not nombre:
        return None
    if (exacta := _nomenclator().get((str(pais), nombre))) is not None:
        return exacta
    patron = re.compile(rf"(?<!\w){re.escape(nombre)}(?!\w)")
    candidatas = {
        lugar["oaci"]: lugar
        for (p, alias), lugar in _nomenclator().items()
        if p == str(pais) and lugar.get("oaci") and patron.search(alias)
    }
    return next(iter(candidatas.values())) if len(candidatas) == 1 else None


def decidir_objetivo(incidente: Documento) -> Documento | None:
    """La instalación afectada: la revisión a mano con su cita; la que nombran el titular y las
    fuentes si la ficha no tiene una (proceso/objetivo_del_titular.py); si no, la de la ficha con el
    OACI de la instalación del nomenclátor que su nombre nombra (el nombre es uno de los suyos:
    la cabecera lo escribe en cada idioma con proceso/nombres_lugar.py); con OACI, la categoría es
    «aeropuerto» (también una base aérea: Kleine-Brogel, EBBL); una cárcel es «otra»."""
    revision = _revisiones(incidente).get("objetivo")
    if revision is not None:
        # Sin OACI, sin la clave (el esquema no admite un OACI nulo).
        valor = revision["valor"]
        return None if valor is None else {k: v for k, v in valor.items() if v is not None}
    objetivo = incidente.get("objetivo")
    if not objetivo or objetivo.get("categoria") in (None, "otra"):
        # La instalación que nombran el titular y las fuentes y la ficha no reconoció.
        from proceso import objetivo_del_titular

        if (nombrado := objetivo_del_titular.objetivo_nombrado(incidente)) is not None:
            return nombrado
    if not objetivo or not objetivo.get("nombre"):
        return copy.deepcopy(objetivo)
    nuevo = dict(objetivo)
    if es_carcel(objetivo):
        nuevo["categoria"] = "otra"
    elif objetivo.get("categoria") in ("aeropuerto", "base_militar"):
        lugar = instalacion_del_nomenclator(objetivo, (incidente.get("lugar") or {}).get("pais"))
        if lugar is not None and lugar.get("oaci"):
            nuevo.update(categoria="aeropuerto", oaci=lugar["oaci"])
    return nuevo


def decidir_drones(incidente: Documento) -> Any:
    """El número de drones: la revisión a mano con su cita; si no, «desconocido» cuando la
    autoridad concluye que no era un dron (presencia descartada); si no, el de la ficha. «Al menos
    N» (mínimo sin máximo) espera al esquema que lo admita: el 1.20.0 exige el máximo."""
    revision = _revisiones(incidente).get("drones")
    if revision is not None:
        return copy.deepcopy(revision["valor"])
    numero = (incidente.get("drones") or {}).get("numero", "desconocido")
    if incidente.get("presencia_dron") == rectificaciones.DESCARTADA:
        return "desconocido"
    return copy.deepcopy(numero)


def _con_drones(incidente: Documento) -> Documento:
    """El incidente con el número de drones que decide `decidir_drones` (sin cambios si ya lo
    tenía)."""
    if "drones" not in incidente and not _revisiones(incidente).get("drones"):
        return incidente
    numero = decidir_drones(incidente)
    if (incidente.get("drones") or {}).get("numero") == numero:
        return incidente
    return {**incidente, "drones": {**incidente.get("drones", {}), "numero": numero}}


def _con_revision(resultado: Documento, campo: str, revision: Documento) -> None:
    valor = copy.deepcopy(revision["valor"])
    if campo == "lugar":
        # La localidad del suceso que dice la fuente (no la instalación, la provincia ni el
        # destino del avión); en el mar, sin localidad ni nombre del sitio.
        quitar = {"localidad"} if valor is not None else {"localidad", "suceso"}
        lugar = {k: v for k, v in resultado.get("lugar", {}).items() if k not in quitar}
        if valor is not None:
            lugar.update(valor)
            if "punto" not in valor:
                lugar = en_la_localidad_revisada(lugar)
        resultado["lugar"] = lugar
    elif campo == "inicio":
        # El día del suceso en UTC que dice la fuente (no el de la publicación ni el día local).
        inicio = valor if isinstance(valor, dict) else {"valor": f"{valor}T00:00Z",
                                                        "precision": "dia"}  # fmt: skip
        if (resultado.get("tiempo") or {}).get("inicio") != inicio:
            origen = {"tipo": "explicita", "motivo": str(revision["motivo"])[:200]}
            resultado["tiempo"] = {"inicio": inicio, "origen_inicio": origen}
    elif campo == "cierre":
        # Si hubo cierre; su duración con su cita (el control de las fichas) se queda: antes se
        # perdía en cada guardado y el control la volvía a poner (EODI-2025-00001, 2026-00322).
        anterior = (resultado.get("consecuencias") or {}).get("cierre") or {}
        cierre = {**anterior, "valor": valor} if valor == "si" else {"valor": valor}
        resultado["consecuencias"] = {**resultado.get("consecuencias", {}), "cierre": cierre}


# Lo más lejos que puede quedar el punto de la localidad revisada, además del radio de esta: el
# de la instalación de la ficha suele estar a pocos km (la base aérea junto a Geilenkirchen); más
# lejos, el punto es de otro sitio que dejó una extracción anterior.
MAX_KM_LOCALIDAD_REVISADA = 15.0


def en_la_localidad_revisada(lugar: Documento) -> Documento:
    """El lugar de una revisión a mano que da la localidad sin el punto, con el nivel y el punto
    de esa localidad (la del nomenclátor, si es una sola) cuando el punto que tenía queda lejos
    de ella: la revisión fija la localidad, y lo que deje después una extracción no la mueve a
    otro sitio (EODI-2026-00278: Dublín con el punto y el nivel de antes de revisarlo). Sin
    cambios si la localidad no está en el nomenclátor o el punto ya es de ella."""
    from proceso import control_fichas, noticias
    from proceso.deduccion.geo import distancia_km

    pais, nombre = lugar.get("pais"), lugar.get("localidad")
    if not pais or not nombre:
        return lugar
    hallado = control_fichas.lugar_de_nombre(
        str(nombre), "localidad", str(pais), lugar.get("region"), noticias.nomenclator()
    )
    if hallado is None:
        return lugar
    sitio = hallado[0]
    punto = lugar.get("punto")
    if punto and distancia_km(punto["lat"], punto["lon"], sitio.lat, sitio.lon) <= (
        MAX_KM_LOCALIDAD_REVISADA + sitio.radio_km
    ):
        return lugar
    nuevo = {k: v for k, v in lugar.items() if k != "fuente_punto"}
    nuevo.update(
        nivel="localidad",
        punto={"lat": round(sitio.lat, incidentes.DECIMALES),
               "lon": round(sitio.lon, incidentes.DECIMALES)},
        radio_km=sitio.radio_km,
    )  # fmt: skip
    return nuevo


def decidir_datos(incidente: Documento) -> Documento:
    """El incidente con el objetivo, el lugar, el inicio y el cierre que deciden sus fuentes y sus
    revisiones a mano (el titular, al final de `aplicar`). Sin cambios si ya los tenía. Si cambia
    la instalación o el lugar, los nombres publicados se vuelven a calcular."""
    resultado = copy.deepcopy(incidente)
    revisiones = _revisiones(incidente)
    for campo in ("lugar", "inicio", "cierre"):
        if campo in revisiones:
            _con_revision(resultado, campo, revisiones[campo])
    if "lugar" not in revisiones:
        # Con homónimos, la localidad que dice la fuente (su municipio): Józefów de Nieporęt.
        from proceso import noticias, ubicacion

        homonimo = ubicacion.lugar_del_homonimo(resultado, noticias.nomenclator())
        if homonimo is not None:
            resultado["lugar"] = {"localidad": homonimo.get("suceso"), **homonimo}
    objetivo = decidir_objetivo(resultado)
    if objetivo:
        resultado["objetivo"] = objetivo
    else:
        resultado.pop("objetivo", None)
    if resultado == incidente:
        return incidente
    if "nombres" in resultado and any(
        resultado.get(c) != incidente.get(c) for c in ("objetivo", "lugar", "titulo")
    ):
        # Una ficha ya publicada (las copias de la referencia): los nombres de lo que cambia.
        from proceso import nombres_lugar

        nombres = resultado.pop("nombres")
        nuevos = nombres_lugar.nombres_publicos(resultado)
        if resultado.get("objetivo") != incidente.get("objetivo"):
            nombres["objetivo"] = nuevos.get("objetivo")
            nombres["localidad"] = nuevos.get("localidad") or nombres.get("localidad")
        if resultado.get("lugar") != incidente.get("lugar"):
            nombres["localidad"] = nuevos.get("localidad")
        resultado["nombres"] = {k: v for k, v in nombres.items() if v is not None}
    return resultado


def es_carcel(objetivo: Documento | None) -> bool:
    return bool(_CARCEL.search(str((objetivo or {}).get("nombre") or "")))


def aplicar(
    incidente: Documento, negadas: frozenset[str] = frozenset(), confirmada: bool = False
) -> Documento:
    """El incidente con el estado, la presencia y los demás datos que deciden sus pruebas, y el
    titular que decide `decidir_titulo` con todo eso. Sin cambios si ya los tenía."""
    incidente = decidir_datos(incidente)
    resultado = _historial_vigente(incidente)
    estado = decidir_estado(resultado)
    if resultado is incidente and estado.valor == incidente["estado"]["actual"]:
        resultado = incidente
    else:
        resultado = copy.deepcopy(resultado)
        if estado.regla == "autoridad_lo_cuenta":
            fuente = next(f for f in resultado["fuentes"] if f["id"] == estado.fuente_id)
            resultado["estado"]["historial"].append({
                "estado": estado.valor, "fecha": copy.deepcopy(fuente["fecha"]),
                "fuente_id": estado.fuente_id,
            })  # fmt: skip
        resultado["estado"]["actual"] = estado.valor
        if estado.valor != Estado.DESMENTIDO:
            resultado.get("control", {}).pop("motivo_desmentido", None)
    presencia = decidir_presencia(resultado, negadas, confirmada)
    if presencia.valor != resultado.get("presencia_dron"):
        resultado = {**copy.deepcopy(resultado), "presencia_dron": presencia.valor}
    # Los drones y el tipo, con el estado y la presencia ya decididos (sin dron según la
    # autoridad, número desconocido; la atribución demuestra la entrada).
    resultado = _con_drones(resultado)
    tipo = incidentes.con_tipo(copy.deepcopy(resultado))
    if (tipo.get("tipo"), tipo.get("origen_demostrado_por")) != (
        resultado.get("tipo"),
        resultado.get("origen_demostrado_por"),
    ):
        resultado = tipo
    titulo = decidir_titulo(resultado)
    if titulo != resultado.get("titulo"):
        resultado = {**resultado, "titulo": titulo}
    # La zona, con todo lo demás decidido: un guardado que rehacía la ficha sin ella la quitaba y
    # la clasificación horaria la volvía a poner en la misma recogida (EODI-2026-00019, 23/10).
    if "fusionado_en" not in resultado and "retirado" not in resultado:
        from proceso import zona

        grupo = zona.clasificar(resultado)
        if grupo != resultado.get("zona"):
            resultado = {**resultado, "zona": grupo}
    return resultado


@cache
def _titulos_revisados() -> dict[str, dict[str, str]]:
    """{incidente: titular} revisado a mano en «titulares» de incidentes_revisados.json."""
    from proceso import presencia

    datos = json.loads(presencia.REVISADOS.read_text(encoding="utf-8"))
    return {
        str(t["incidente"]): dict(t["titulo"])
        for t in datos.get("titulares", [])
        if isinstance(t.get("titulo"), dict)
    }


def decidir_titulo(incidente: Documento) -> dict[str, str]:
    """El titular en español y en inglés, decidido con lo que ya está decidido:

    1. el texto: el revisado a mano con su cita (incidentes_revisados.json, «datos» y si no
       «titulares»); si no, el de la ficha (el extractor, la barrera de titulares, el de país);
    2. el dron como confirmado o posible según la presencia (proceso/titulares.py);
    3. sin atribución de una autoridad, sin el país del dron ni su autor
       (proceso/atribucion.titulo_sin_atribucion), lo mismo en los dos idiomas.

    Cada paso deja igual un titular que ya lo cumple: guardar dos veces da el mismo titular, y
    ningún otro paso de la recogida lo escribe (antes cuatro reglas se pisaban cada hora y quedaba
    el valor viejo: EODI-2025-00378, 22-23 de octubre de 2026)."""
    revision = _revisiones(incidente).get("titulo")
    if revision is not None:
        base = dict(revision["valor"])
    elif (revisado := _titulos_revisados().get(str(incidente.get("id")))) is not None:
        base = revisado
    else:
        base = dict(incidente.get("titulo") or {})
    if not base:
        return base
    ajustado = titulares.ajustar_incidente({**incidente, "titulo": base})
    return atribucion.titulo_segun_atribucion(ajustado)


def motivo(
    incidente: Documento, negadas: frozenset[str] = frozenset(), confirmada: bool = False
) -> str:
    """El motivo del cambio que hace `aplicar`, para el historial: el del criterio de presencia
    si es una presencia sin base (proceso/presencia.py); si no, la regla que decide."""
    from proceso import presencia

    if presencia.sin_base(incidente):
        return presencia.motivo_sin_base(incidente)
    estado, decision = decidir_estado(incidente), decidir_presencia(incidente, negadas, confirmada)
    return (
        f"un solo sitio decide (proceso/decidir.py): estado por {estado.regla}, presencia "
        f"{decision.valor} por {decision.regla}"
    )
