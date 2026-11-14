"""Coherencia en la puerta: corregir y publicar bien, no retener (desde el 14 de noviembre de
2026; docs/ciclo_de_vida.md, «Coherencia en la puerta»).

Cada hora, dentro del control de las fichas (después del filtro de entrada y antes de la
retención), cada ficha activa pasa por las comprobaciones de proceso/correccion.py. La que tiene
algo que sus frases guardadas no sostienen la relee el modelo grande con el texto de sus fuentes
(modelo/coherencia.py, cupo propio del modo «coherencia») y se corrige con lo que una frase
literal sostiene:

- c) el lugar: se queda si una frase lo da; si no, baja a la región que nombra una frase o al
  país (`barrera.a_nivel_de_pais`), y el titular se rehace a ese nivel (f);
- d) el número de drones: el que da una frase con la palabra dron; si ninguna, «sin dato»;
- b) el día: el que da una frase (`entrada.con_dia`), si no casa con el de la ficha;
- a) dos jornadas: la ficha se separa en una por día (`separar`, con una revisión automática).

Sin respuesta del modelo (sin servicio, cupo, fallo) se corrige con lo seguro: el lugar y los
drones bajan a lo que sostienen las frases guardadas; la fecha y las dos jornadas esperan a la
siguiente recogida (la ficha sigue publicada). Cada decisión se guarda (`coherencia:<id>`) con la
huella de lo que miró: una ficha que no cambia no se vuelve a releer."""

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from esquema import Documento
from modelo import coherencia as peticion
from modelo import coste
from proceso import control_fichas as reglas
from proceso import correccion, decidir, fechas, suceso
from proceso.noticias import nomenclator, normalizar
from recogida import barrera, control_fichas
from recogida.plazo import Plazo

registro = logging.getLogger(__name__)

CLAVE = "coherencia:"
# Tiempo y relecturas de una pasada: lo que no cabe, en la siguiente.
TOPE_S = 300
MAX_RELECTURAS = 40
MOTIVO = "coherencia en la puerta"
# Las que esperan la relectura y, pasada una recogida, el aviso privado (una vez por ficha).
CURSOR_PENDIENTES = "coherencia:pendientes"
ESPERA_AVISO = timedelta(minutes=50)
TITULO_PENDIENTES = "EODI · Coherencia sin relectura"


@dataclass
class Resumen:
    miradas: int = 0
    releidas: int = 0
    corregidas: list[str] = field(default_factory=list)
    sin_relectura: list[str] = field(default_factory=list)
    pendientes: list[str] = field(default_factory=list)
    separar: list[str] = field(default_factory=list)
    protegidas: list[str] = field(default_factory=list)


def huella(ficha: Documento) -> str:
    """Lo que mira la comprobación: el lugar, los drones, el día, el titular y las fuentes."""
    datos = {
        "lugar": ficha.get("lugar"),
        "objetivo": ficha.get("objetivo"),
        "drones": (ficha.get("drones") or {}).get("numero"),
        "inicio": ((ficha.get("tiempo") or {}).get("inicio") or {}).get("valor"),
        "titulo": ficha.get("titulo"),
        "fuentes": sorted(str(f.get("id")) for f in ficha.get("fuentes", [])),
    }
    return hashlib.sha256(
        json.dumps(datos, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]


def noches(almacen: Any) -> dict[str, date]:
    """La noche del episodio de cada ficha (los episodios vigentes)."""
    salida = {}
    for episodio in almacen.episodios():
        if episodio.get("deshecho") or not episodio.get("noche"):
            continue
        for id_ in episodio.get("incidentes", []):
            salida[str(id_)] = date.fromisoformat(str(episodio["noche"])[:10])
    return salida


def _literal(frase: str, numero: Any, comprobar: list[tuple[str, str]]) -> str | None:
    """El id de la fuente si la frase está, literal, en la fuente `numero` (desde 1)."""
    if not isinstance(numero, int) or not 1 <= numero <= len(comprobar) or not frase:
        return None
    id_, texto = comprobar[numero - 1]
    return id_ if reglas.frase_valida(frase, texto) else None


def a_region(ficha: Documento, region: str) -> Documento:
    """La ficha situada solo en una región de su país, con el titular de su país."""
    nuevo = barrera.a_nivel_de_pais(ficha)
    nuevo["lugar"] = {**nuevo["lugar"], "nivel": "region", "region": region, "suceso": region}
    return titulo_rehecho(nuevo)


def sin_drones(ficha: Documento) -> Documento:
    return {**ficha, "drones": {**(ficha.get("drones") or {}), "numero": correccion.SIN_DATO}}


def con_drones(ficha: Documento, valor: dict[str, int], fuente_id: str) -> Documento:
    afirmacion = {
        "campo": "drones",
        "valor": valor,
        "fuente_id": fuente_id,
        "confianza_extraccion": 1.0,
    }
    otras = [a for a in ficha.get("afirmaciones", []) if a.get("campo") != "drones"]
    return {
        **ficha,
        "drones": {**(ficha.get("drones") or {}), "numero": valor},
        "afirmaciones": [*otras, afirmacion],
    }


def titulo_rehecho(ficha: Documento) -> Documento:
    """f) El titular rehecho con los datos de la ficha: el hecho y su país (`barrera`) y, si la
    ficha tiene sitio y es un avistamiento, el sitio delante del país."""
    nuevo = {**ficha, "titulo": barrera.titulo_de_pais(ficha)}
    lugar = ficha.get("lugar") or {}
    sitio = str(lugar.get("suceso") or lugar.get("localidad") or "").strip()
    if (
        lugar.get("nivel") not in (None, "pais")
        and sitio
        and ficha.get("tipo", "sobrevuelo") == "sobrevuelo"
    ):
        es, en = barrera.nombres_de_paises()[str(lugar["pais"])]
        nuevo["titulo"] = {
            "es": nuevo["titulo"]["es"].replace(f" en {es}", f" en {sitio} ({es})"),
            "en": nuevo["titulo"]["en"].replace(f" in {en}", f" in {sitio} ({en})"),
        }
    nuevo["titulo"] = decidir.decidir_titulo(nuevo)
    return nuevo


def con_titular(ficha: Documento, letras: set[str], cambios: list[str]) -> Documento:
    """f) Si el titular sigue nombrando otro país (lo que no arregló bajar el lugar), se rehace."""
    if correccion.TITULAR not in letras or correccion.titulo_de_otro_pais(ficha) is None:
        return ficha
    nuevo = titulo_rehecho(ficha)
    cambios.append(f"titular rehecho con su país: «{nuevo['titulo'].get('es', '')}»")
    return nuevo


def lo_seguro(
    ficha: Documento, hallazgos: list[correccion.Hallazgo]
) -> tuple[Documento, list[str]]:
    """Sin relectura: el lugar y los drones, a lo que sostienen las frases guardadas."""
    letras = {h.comprobacion for h in hallazgos}
    nuevo, cambios = ficha, []
    if correccion.LUGAR in letras:
        nuevo = barrera.a_nivel_de_pais(nuevo)
        cambios.append("lugar sin frase que lo nombre: solo el país, y su titular")
    if correccion.DRONES in letras:
        nuevo = sin_drones(nuevo)
        cambios.append("número de drones sin fuente: sin dato")
    return con_titular(nuevo, letras, cambios), cambios


def aplicar(
    ficha: Documento,
    hallazgos: list[correccion.Hallazgo],
    respuesta: dict[str, Any],
    comprobar: list[tuple[str, str]],
) -> tuple[Documento, list[str], list[dict[str, Any]]]:
    """La ficha corregida con lo que sostiene una frase literal de la relectura, los cambios y,
    si las fuentes cuentan dos jornadas, las partes para separarla ({dia, fuentes: [ids]})."""
    letras = {h.comprobacion for h in hallazgos}
    nuevo, cambios = ficha, []
    if correccion.LUGAR in letras:
        lugar = respuesta.get("lugar") or {}
        frase = str(lugar.get("frase") or "")
        de_quien = _literal(frase, lugar.get("fuente"), comprobar)
        region = str(lugar.get("region") or "").strip()
        if lugar.get("sostenido") and de_quien:
            cambios.append(f"lugar sostenido por «{frase[:120]}»")
        elif (
            lugar.get("nivel") == "region" and region and de_quien
            and correccion.nombra_alguna(normalizar(frase), region)
        ):  # fmt: skip
            nuevo = a_region(nuevo, region)
            cambios.append(f"lugar sin frase que lo nombre: la región {region} («{frase[:120]}»)")
        else:
            nuevo = barrera.a_nivel_de_pais(nuevo)
            cambios.append("lugar sin frase que lo nombre: solo el país, y su titular")
    if correccion.DRONES in letras:
        drones = respuesta.get("drones") or {}
        frase = str(drones.get("frase") or "")
        de_quien = _literal(frase, drones.get("fuente"), comprobar)
        valor = reglas._interpretar("drones", drones.get("valor"), frase) if de_quien else None
        if de_quien and isinstance(valor, dict):
            nuevo = con_drones(nuevo, valor, de_quien)
            cambios.append(f"drones {valor['min']}-{valor['max']} por «{frase[:120]}»")
        else:
            nuevo = sin_drones(nuevo)
            cambios.append("número de drones sin fuente: sin dato")
    partes: list[dict[str, Any]] = []
    if correccion.FECHA in letras or correccion.UN_SUCESO in letras:
        dia = respuesta.get("dia") or {}
        frase = str(dia.get("frase") or "")
        de_quien = _literal(frase, dia.get("fuente"), comprobar)
        valor = str(dia.get("valor") or "")
        pais = str(nuevo["lugar"]["pais"])
        if (
            de_quien
            and _fecha(valor)
            and suceso.dia_local(suceso.instante(nuevo), pais) != _fecha(valor)
        ):
            nuevo = control_fichas_con_dia(nuevo, valor, de_quien, frase)
            cambios.append(f"día {valor} por «{frase[:120]}»")
        dias = [d for d in respuesta.get("dias") or [] if _fecha(str(d.get("dia") or ""))]
        if correccion.UN_SUCESO in letras and len({d["dia"] for d in dias}) >= 2:
            for d in dias:
                ids = [comprobar[n - 1][0] for n in d.get("fuentes", [])
                       if isinstance(n, int) and 1 <= n <= len(comprobar)]  # fmt: skip
                if ids:
                    partes.append({"dia": str(d["dia"]), "fuentes": ids,
                                   "frase": str(d.get("frase") or "")[:300]})  # fmt: skip
    return con_titular(nuevo, letras, cambios), cambios, partes


def _fecha(texto: str) -> date | None:
    try:
        return date.fromisoformat(texto[:10]) if texto else None
    except ValueError:
        return None


def control_fichas_con_dia(ficha: Documento, dia: str, fuente_id: str, frase: str) -> Documento:
    """El día que da la frase, con precisión de día (como el filtro de entrada)."""
    tiempo = {k: v for k, v in (ficha.get("tiempo") or {}).items() if k != "fin"}
    tiempo["inicio"] = {"valor": f"{dia[:10]}T00:00Z", "precision": "dia"}
    tiempo["origen_inicio"] = {
        "tipo": fechas.EXPLICITA,
        "fuente_id": fuente_id,
        "motivo": f"coherencia en la puerta: «{frase}»"[:300],
    }
    return {**ficha, "tiempo": tiempo}


class Relector:
    """Las llamadas de la relectura: siempre al experto, con el cupo del modo «coherencia»."""

    def __init__(self, ctx: control_fichas.Contexto, plazo: Plazo) -> None:
        from recogida import entrada

        self.experto = entrada.Experto(ctx, plazo, modo=coste.Modo.COHERENCIA)

    def llamar(self, cuerpo: dict[str, Any], clave: str) -> dict[str, Any] | None:
        return self.experto.llamar(cuerpo, peticion.MAX_SALIDA, clave)

    @property
    def motivo(self) -> str:
        return self.experto.motivo_espera


def corregir(
    ctx: control_fichas.Contexto, plazo: Plazo, relector: Relector | None = None
) -> Resumen:
    """La pasada de la hora: comprueba cada ficha activa y corrige las que lo necesitan."""
    almacen = ctx.almacen
    resumen = Resumen()
    nom = nomenclator()
    de_episodio = noches(almacen)
    relector = relector or Relector(ctx, plazo)
    activas = sorted(
        control_fichas._activos(almacen), key=lambda d: suceso.orden_registro(str(d["id"]))
    )
    for ficha in activas:
        id_ = str(ficha["id"])
        resumen.miradas += 1
        try:
            hallazgos = correccion.hallazgos(ficha, de_episodio.get(id_), nom)
        except Exception as error:
            registro.warning("coherencia de %s sin mirar: %s", id_, repr(error)[:200])
            continue
        if not hallazgos:
            continue
        clave = CLAVE + id_
        previa = ctx.decision(clave) or {}
        if previa.get("huella") == huella(ficha) and previa.get("version") == peticion.VERSION:
            continue
        letras = {h.comprobacion for h in hallazgos}
        respuesta: dict[str, Any] | None = None
        if letras == {correccion.TITULAR}:
            # El titular se rehace con los datos de la ficha: no hace falta leer las fuentes.
            rehacer = _con_titular(ficha)
        else:
            if resumen.releidas >= MAX_RELECTURAS or plazo.agotado():
                resumen.pendientes.append(id_)
                continue
            respuesta, comprobar = _releer(ctx, relector, ficha, hallazgos, plazo, clave)
            if respuesta is None:
                # Sin relectura, la ficha espera una recogida tal como está (lo publicado no
                # cambia). Si sigue sin relectura y no es por el cupo del día, lo seguro: el lugar
                # y los drones, a lo que sostienen sus frases. La fecha y las dos jornadas siguen
                # esperando la relectura (y el aviso privado, avisar_pendientes).
                resumen.sin_relectura.append(id_)
                resumen.pendientes.append(id_)
                desde = pendiente_desde(almacen, id_)
                if (
                    desde is None
                    or ctx.ahora - desde < ESPERA_AVISO
                    or relector.motivo.startswith("cupo")
                ):
                    continue
                nuevo, cambios, protegidos, _ = sin_lo_protegido(
                    almacen, ficha, hallazgos, _lo_seguro(ficha)
                )
                if protegidos:
                    resumen.protegidas.append(id_)
                if nuevo != ficha and control_fichas._guardar(
                    ctx, ficha, nuevo, f"{MOTIVO} (sin relectura): {'; '.join(cambios)}"[:600]
                ):
                    resumen.corregidas.append(id_)
                continue
            resumen.releidas += 1
            rehacer = _aplicar(ficha, respuesta, comprobar)
        nuevo, cambios, protegidos, partes = sin_lo_protegido(almacen, ficha, hallazgos, rehacer)
        motivo = f"{MOTIVO}: " + "; ".join(cambios) if cambios else MOTIVO
        guardada = False
        if protegidos:
            resumen.protegidas.append(id_)
        if nuevo != ficha:
            guardada = control_fichas._guardar(ctx, ficha, nuevo, motivo[:600])
            if guardada:
                resumen.corregidas.append(id_)
        if partes and separar(almacen, ficha, partes, ctx.ahora):
            resumen.separar.append(id_)
        elif respuesta is not None and correccion.UN_SUCESO in letras:
            # Leídas sus fuentes, una sola jornada: la frase de dos días no la retiene más.
            una_jornada(almacen, ficha, respuesta, ctx.ahora)
        actual = almacen.incidente(id_) or ficha
        ctx.nuevas[clave] = {
            "version": peticion.VERSION,
            "fecha": control_fichas._iso(ctx.ahora),
            "huella": huella(actual),
            "hallazgos": [[h.comprobacion, h.motivo] for h in hallazgos],
            "cambios": cambios,
            "guardada": guardada,
            "relectura": respuesta is not None,
            "partes": partes,
            **({"protegidos": protegidos} if protegidos else {}),
        }
    anotar_pendientes(almacen, resumen, ctx.ahora)
    registro.info(
        "coherencia en la puerta: miradas %d, releídas %d, corregidas %s, sin relectura %s, "
        "pendientes %s, para separar %s, protegidas por el cerrojo %s",
        resumen.miradas, resumen.releidas, resumen.corregidas, resumen.sin_relectura,
        resumen.pendientes, resumen.separar, resumen.protegidas,
    )  # fmt: skip
    return resumen


def revision_de_separar(ficha: Documento, partes: list[dict[str, Any]]) -> Documento | None:
    """La revisión automática que separa la ficha en un suceso por día (la sección `separar`
    de configuracion/incidentes_revisados.json), o None si las partes no la sostienen: cada día
    con al menos una fuente de la ficha y dos días distintos como mínimo."""
    propias = {str(f.get("id")) for f in ficha.get("fuentes", [])}
    por_dia: dict[str, dict[str, Any]] = {}
    for parte in partes:
        dia = str(parte.get("dia") or "")[:10]
        fuentes = [str(f) for f in parte.get("fuentes", []) if str(f) in propias]
        if not _fecha(dia) or not fuentes:
            continue
        hecha = por_dia.setdefault(dia, {"fuentes": [], "frase": str(parte.get("frase") or "")})
        hecha["fuentes"] = list(dict.fromkeys([*hecha["fuentes"], *fuentes]))
    if len(por_dia) < 2:
        return None
    pais = str(ficha["lugar"]["pais"])
    frases = "; ".join(f"{d}: «{p['frase'][:160]}»" for d, p in sorted(por_dia.items()))
    return {
        "incidente": str(ficha["id"]),
        "automatica": True,
        "motivo": {
            "es": f"Coherencia en la puerta: sus fuentes cuentan sucesos de {len(por_dia)} días "
            f"distintos, uno por ficha ({frases}).",
            "en": f"Coherence at the gate: its sources report events on {len(por_dia)} different "
            f"days, one per record ({frases}).",
        },
        "partes": [
            {
                "es_suceso": True,
                "fecha": dia,
                "pais": pais,
                "descripcion": f"El suceso del {dia} ({p['frase'][:200]})",
                "coincide_con": None,
                "fuentes": p["fuentes"],
            }
            for dia, p in sorted(por_dia.items())
        ],
    }


def separar(almacen: Any, ficha: Documento, partes: list[dict[str, Any]], ahora: datetime) -> bool:
    """Guarda la revisión automática que separa la ficha (una vez por ficha). La separación la
    hace, en la siguiente recogida, el mismo paso que las revisadas a mano
    (recogida/revisados.separar); hasta entonces la ficha sigue retenida por sus dos días."""
    revision = revision_de_separar(ficha, partes)
    if revision is None:
        return False
    actual = almacen.cursor(suceso.CURSOR_AUTOMATICAS) or {}
    ya = {str(e.get("incidente")) for e in actual.get("separar", [])}
    if revision["incidente"] in ya:
        return False
    revision["fecha"] = control_fichas._iso(ahora)
    almacen.guardar_cursor(
        suceso.CURSOR_AUTOMATICAS, {**actual, "separar": [*actual.get("separar", []), revision]}
    )
    registro.info("coherencia en la puerta: %s se separa en %d partes", ficha["id"],
                  len(revision["partes"]))  # fmt: skip
    return True


def _anadir(almacen: Any, seccion: str, entrada: Documento) -> bool:
    """Añade una revisión automática (una por ficha y sección)."""
    actual = almacen.cursor(suceso.CURSOR_AUTOMATICAS) or {}
    if str(entrada["incidente"]) in {str(e.get("incidente")) for e in actual.get(seccion, [])}:
        return False
    almacen.guardar_cursor(
        suceso.CURSOR_AUTOMATICAS, {**actual, seccion: [*actual.get(seccion, []), entrada]}
    )
    return True


def una_jornada(almacen: Any, ficha: Documento, respuesta: dict[str, Any], ahora: datetime) -> None:
    """La relectura no sostiene dos días: la ficha queda como un suceso de una jornada
    (sección automática `una_jornada`, que `suceso.dos_dias_sin_revisar` respeta)."""
    dia = respuesta.get("dia") or {}
    _anadir(almacen, "una_jornada", {
        "incidente": str(ficha["id"]),
        "fecha": control_fichas._iso(ahora),
        "dia": str(dia.get("valor") or ""),
        "frase": str(dia.get("frase") or "")[:300],
    })  # fmt: skip


# Los pasos con que guarda la corrección (control_fichas._guardar desde corregir): el cerrojo
# los mira para las revisiones a mano y las retiradas, que aquí no hay.
PASOS_GUARDADO = ["recogida.control_fichas._guardar", "recogida.correccion.corregir"]


def protegidos_por_el_cerrojo(almacen: Any, antes: Documento, nuevo: Documento) -> list[str]:
    """Los datos que el cerrojo (proceso/protegido.py) no dejaría cambiar: lo publicado con cita
    que ninguna fuente nueva desmiente. Vacío si no retendría nada (o si solo observa)."""
    from proceso import protegido

    if protegido.modo() != protegido.APLICAR:
        return []
    veredicto = protegido.juzgar(
        antes, nuevo, PASOS_GUARDADO, almacen.texto_guardado,
        publicada=not almacen.en_el_filtro(str(antes["id"])),
    )  # fmt: skip
    return sorted({c.dato for c in veredicto.retenidos})


# Lo que cambia cada corrección (los datos del cerrojo, proceso/protegido.DATOS_MANUAL).
DATOS_DE = {
    correccion.LUGAR: {"lugar", "objetivo", "titulo"},
    correccion.DRONES: {"drones"},
    correccion.FECHA: {"inicio"},
    correccion.UN_SUCESO: {"inicio"},
    correccion.TITULAR: {"titulo"},
}
Rehacer = Callable[[list[correccion.Hallazgo]], tuple[Documento, list[str], list[dict[str, Any]]]]


def _con_titular(ficha: Documento) -> Rehacer:
    def rehacer(quedan: list[correccion.Hallazgo]) -> tuple[Documento, list[str], list[Documento]]:
        cambios: list[str] = []
        return con_titular(ficha, {h.comprobacion for h in quedan}, cambios), cambios, []

    return rehacer


def _lo_seguro(ficha: Documento) -> Rehacer:
    def rehacer(quedan: list[correccion.Hallazgo]) -> tuple[Documento, list[str], list[Documento]]:
        nuevo, cambios = lo_seguro(ficha, quedan)
        return nuevo, cambios, []

    return rehacer


def _aplicar(
    ficha: Documento, respuesta: dict[str, Any], comprobar: list[tuple[str, str]]
) -> Rehacer:
    def rehacer(quedan: list[correccion.Hallazgo]) -> tuple[Documento, list[str], list[Documento]]:
        return aplicar(ficha, quedan, respuesta, comprobar)

    return rehacer


def sin_lo_protegido(
    almacen: Any, ficha: Documento, hallazgos: list[correccion.Hallazgo], rehacer: Rehacer
) -> tuple[Documento, list[str], list[str], list[dict[str, Any]]]:
    """La corrección sin lo que el cerrojo protege: lo publicado con su cita manda y, si retiene
    un dato, la comprobación que lo cambia no se aplica entera (con el lugar retenido en su
    región, el titular bajaba solo al país: EODI-2026-00747 en el ensayo del 14/11). Las demás,
    sí. Devuelve la ficha, sus cambios, los datos protegidos y las partes."""
    nuevo, cambios, partes = rehacer(hallazgos)
    protegidos = protegidos_por_el_cerrojo(almacen, ficha, nuevo) if nuevo != ficha else []
    if not protegidos:
        return nuevo, cambios, [], partes
    quitar = {letra for letra, datos in DATOS_DE.items() if datos & set(protegidos)}
    quedan = [h for h in hallazgos if h.comprobacion not in quitar]
    nuevo, cambios, partes = rehacer(quedan) if quedan else (ficha, [], [])
    if nuevo != ficha and protegidos_por_el_cerrojo(almacen, ficha, nuevo):
        return ficha, [], protegidos, []
    return nuevo, cambios, protegidos, partes


def pendiente_desde(almacen: Any, id_: str) -> datetime | None:
    """Desde cuándo espera la ficha la relectura (anotado en la pasada anterior), o None."""
    fichas = (almacen.cursor(CURSOR_PENDIENTES) or {}).get("fichas", {})
    desde = (fichas.get(id_) or {}).get("desde")
    return control_fichas._leer(str(desde)) if desde else None


def anotar_pendientes(almacen: Any, resumen: Resumen, ahora: datetime) -> None:
    """Las fichas que esperan la relectura, con la hora desde la que esperan (para el aviso)."""
    antes = dict((almacen.cursor(CURSOR_PENDIENTES) or {}).get("fichas", {}))
    ahora_ = control_fichas._iso(ahora)
    siguen = {id_: antes.get(id_, {"desde": ahora_}) for id_ in resumen.pendientes}
    if siguen != antes:
        almacen.guardar_cursor(CURSOR_PENDIENTES, {"fichas": siguen})


def avisar_pendientes(
    almacen: Any, ahora: datetime, avisador: Callable[[str], Callable[[str], None] | None] | None
) -> list[str]:
    """El último recurso: las fichas que llevan más de una recogida esperando la relectura (sin
    servicio, sin cupo) se avisan por el tema privado, una vez cada una. Devuelve las avisadas."""
    cursor = almacen.cursor(CURSOR_PENDIENTES) or {}
    fichas = dict(cursor.get("fichas", {}))
    viejas = sorted(
        id_ for id_, f in fichas.items()
        if not f.get("avisada") and ahora - control_fichas._leer(str(f["desde"])) >= ESPERA_AVISO
    )  # fmt: skip
    if not viejas or avisador is None:
        return []
    avisar = avisador(TITULO_PENDIENTES)
    if avisar is None:
        return []
    avisar(
        "La coherencia de la puerta no ha podido releer estas fichas en más de una recogida "
        "(sin servicio, sin cupo o sin tiempo). Siguen publicadas como estaban; sin relectura, "
        "el lugar y los drones bajan a lo seguro y la fecha o las dos jornadas esperan: "
        + ", ".join(viejas)
    )
    for id_ in viejas:
        fichas[id_] = {**fichas[id_], "avisada": control_fichas._iso(ahora)}
    almacen.guardar_cursor(CURSOR_PENDIENTES, {**cursor, "fichas": fichas})
    return viejas


def _releer(
    ctx: control_fichas.Contexto, relector: Relector, ficha: Documento,
    hallazgos: list[correccion.Hallazgo], plazo: Plazo, clave: str,
) -> tuple[dict[str, Any] | None, list[tuple[str, str]]]:  # fmt: skip
    enlaces = [str(f["enlace"]) for f in correccion.publicas(ficha) if f.get("enlace")]
    textos = (
        {} if plazo.agotado() else control_fichas.descargar(list(dict.fromkeys(enlaces))[:6], plazo)
    )
    fuentes = control_fichas.fuentes_de_ficha(ctx.almacen, ficha, textos)
    cuerpo = peticion.cuerpo(reglas.vista(ficha), [h.motivo for h in hallazgos], fuentes.bloques)
    return relector.llamar(cuerpo, clave), fuentes.comprobar
