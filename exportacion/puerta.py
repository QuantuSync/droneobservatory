"""La puerta de la publicación (docs/ciclo_de_vida.md): lo que entra en la tabla `publicado`, la
única fuente de lo que sale en la web, en los datos abiertos y en los avisos.

Cerrada por defecto. La versión de una ficha que la base propone entra solo si:

- el control de las fichas terminó en esta pasada (`pase_del_control`);
- la ficha tiene el pase del control: está entre las vistas (recogida/control_fichas.retener);
- la auditoría de protección no la marca (P, R, V, W o X: `proceso/protegido.AUDITORIA`);
- cumple las invariantes de ficha (proceso/invariantes.py);
- su entrada pública se pudo generar y valida (exportacion/geojson.py, `apartados`).

Si no, su fila no se toca: sigue saliendo su última versión buena y, si nunca salió, no sale.
Una ficha publicada que se une pasa a «unida» cuando la que queda está publicada; una que se
retira, a «retirada» con su motivo. Ninguna fila se borra: toda dirección publicada lleva a una
ficha, a la que queda o a la explicación de su retirada.

Sustituye a la lista de retenidos del control como filtro de la publicación (lo que no estaba en
la lista salía: si el control fallaba, las fichas nuevas de esa hora se publicaban sin filtro) y a
la red de versiones buenas (un fichero al lado de la publicación). Lo que no pasa queda en el
cursor `publicacion_buena`, que leen el estado del control (control.json), la vigilancia y el
resumen diario («Fichas publicadas en su versión anterior: N»)."""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from modelo import coste
from proceso import suceso

registro = logging.getLogger(__name__)

CURSOR = "publicacion_buena"
CURSOR_CONTROL = "control_fichas"
PUBLICADA, UNIDA, RETIRADA = "publicada", "unida", "retirada"
# La clave de las entradas de cada fichero publicado.
LISTAS = {"incidentes.geojson": "features", "incidentes_sin_ubicacion.json": "incidentes"}
MAPA = "incidentes.geojson"
# Lo que dicen las diferencias: unos pocos campos y valores cortos (salud.json es público).
MAX_DIFERENCIAS = 6
MAX_VALOR = 80
DIAS = 8
BUENA, NINGUNA = "buena", "ninguna"
# Por qué no pasa una versión, además de las letras de la auditoría y de las invariantes.
SIN_CONTROL = "control"
SIN_PASE = "sin_pase"
SIN_AUDITORIA = "auditoria"
SIN_ENTRADA = "sin_entrada"
UNIDA_A_NO_PUBLICADA = "unida_a_no_publicada"
# Lo que es retención normal de una ficha nueva: no es una ficha en su versión anterior.
NORMALES = frozenset({SIN_PASE})
_INSTANTE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$")
MOTIVO_SIN_MOTIVO = {
    "es": "Retirada tras su revisión: no cumplía los criterios del registro.",
    "en": "Withdrawn after review: it did not meet the criteria of the register.",
}


# Lo que un motivo de retirada dice de cómo se decidió (qué paso del proceso), que no es parte
# de la explicación pública: «… (repaso de entrada con el experto).»
_PROCESO = re.compile(
    r"\s*\((?:repaso de entrada[^)]*|entry review[^)]*)\)"
    r"|^(?:repaso de entrada[^:]*|entry review):\s*",
    re.IGNORECASE,
)


def _sin_proceso(motivo: str) -> str:
    """El motivo sin la nota del paso interno que lo decidió."""
    return _PROCESO.sub("", motivo).strip()


def detalle_de_retirada(retirado: Documento, fecha: str) -> Documento:
    """Lo que explica la dirección de una ficha retirada: cuándo y por qué. El motivo se publica
    tal cual solo si la retirada lo trae en los dos idiomas (está escrito para leerse: las
    revisiones a mano, el filtro de entrada, el veredicto de que no es un suceso). El de una regla
    interna, que solo está en español y habla de pasos del proceso, no se publica: sale el motivo
    general."""
    es = _sin_proceso(str(retirado.get("motivo") or ""))
    en = _sin_proceso(str(retirado.get("motivo_en") or ""))
    motivo = {"es": es, "en": en} if es and en else dict(MOTIVO_SIN_MOTIVO)
    cuando = retirado.get("fecha")
    valor = str(cuando.get("valor") or "") if isinstance(cuando, dict) else ""
    # La web valida la fecha como un instante: una que no lo sea invalidaría el fichero entero.
    return {"fecha": valor if _INSTANTE.match(valor) else fecha, "motivo": motivo}


def _iso(ahora: datetime) -> str:
    return ahora.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Pase:
    """El pase del control de las fichas: las que ya pasó (`vistos`) y si terminó en esta pasada."""

    vistos: frozenset[str]
    terminado: bool


def pase_del_control(almacen: Almacen, ahora: datetime) -> Pase:
    """Lo que dejó el control (recogida/control_fichas.ejecutar) en su cursor: las fichas que han
    pasado el control y la pasada que terminó. Sin cursor, nadie ha pasado nada."""
    cursor = almacen.cursor(CURSOR_CONTROL) or {}
    return Pase(frozenset(cursor.get("vistos") or {}), cursor.get("pasada") == _iso(ahora))


def dar_pase(almacen: Almacen, ahora: datetime, ids: list[str] | None = None) -> None:
    """Anota en el cursor del control que terminó en esta pasada y, con `ids`, que esas fichas lo
    han pasado. Lo usa el propio control al terminar; fuera de él, solo las pruebas y las
    herramientas que publican una base que no ha pasado por la recogida."""
    cursor = dict(almacen.cursor(CURSOR_CONTROL) or {})
    vistos = dict(cursor.get("vistos") or {})
    for id_ in ids or []:
        vistos.setdefault(id_, _iso(ahora))
    almacen.guardar_cursor(CURSOR_CONTROL, {**cursor, "vistos": vistos, "pasada": _iso(ahora)})


def marcadas(almacen: Almacen, ahora: datetime) -> dict[str, list[str]]:
    """{ficha: [comprobaciones]} de las fichas vigentes en P, R, V, W o X ahora, con los mismos
    datos que la auditoría del control (recogida/control_fichas.auditoria_del_dia). En V cuenta la
    ficha que queda publicada (la de destino)."""
    from proceso import auditoria_fichas, protegido
    from recogida import revisados

    desde = (ahora - timedelta(hours=auditoria_fichas.HORAS_OSCILA)).strftime("%Y-%m-%dT%H:%M:%SZ")
    documentos = almacen.incidentes()
    cambios = almacen.cambios_desde(desde)
    permitidos = protegido.permitidos(almacen.controles(protegido.PREFIJO_PERMITIDO))
    resultado = auditoria_fichas.auditar(
        documentos,
        cambios,
        None,
        suceso.distintos_del_experto(almacen) | revisados.pares_de_partes(almacen),
        suceso.uniones_a_mano(almacen),
        almacen.fechas_extraccion(desde),
        permitidos,
        primeras=almacen.primeras_publicaciones(),
    )
    # X mira 48 horas de historial: aquí solo cuenta lo que la ficha aún tiene.
    resultado["X"] = x_vigentes(
        cambios, permitidos, {str(d["id"]): d for d in documentos},
        almacen.primeras_publicaciones(),
    )  # fmt: skip
    salida: dict[str, list[str]] = {}
    for comprobacion in protegido.AUDITORIA:
        for entrada in resultado.get(comprobacion, []):
            texto = str(entrada)
            id_ = texto.split("→")[-1] if "→" in texto else texto.split(" ")[0]
            if id_.startswith("EODI-") and comprobacion not in salida.get(id_, []):
                salida.setdefault(id_, []).append(comprobacion)
    return salida


def x_vigentes(
    cambios: list[Documento],
    permitidos: frozenset[tuple[str, str, str]],
    vigentes: dict[str, Documento],
    primeras: dict[str, str] | None = None,
) -> list[str]:
    """X (proceso/protegido.cambios_sin_permiso) de lo que la ficha aún tiene, la misma que la
    auditoría: un cambio sin permiso que ya se deshizo (una revisión, el control) o un dato que
    ahora fija una revisión no la dejan en su versión anterior, que taparía la corrección hasta
    que el cambio salga de las 48 horas."""
    from proceso import protegido

    return protegido.cambios_sin_permiso(cambios, permitidos, vigentes, primeras)


def _id(entrada: Documento) -> str:
    return str(entrada.get("id") or (entrada.get("properties") or {}).get("id") or "")


def _entradas(documento: Documento | None, nombre: str) -> list[Documento]:
    lista = (documento or {}).get(LISTAS[nombre])
    return lista if isinstance(lista, list) else []


def _corto(valor: Any) -> str:
    texto = json.dumps(valor, ensure_ascii=False, sort_keys=True)
    return texto if len(texto) <= MAX_VALOR else texto[: MAX_VALOR - 1] + "…"


def diferencias(publicada: Documento | None, actual: Documento | None) -> dict[str, list[str]]:
    """Los campos que cambian entre lo que se publica y lo que tiene ahora la base, con los dos
    valores recortados."""
    uno = {**(publicada or {}), **((publicada or {}).get("properties") or {})}
    otro = {**(actual or {}), **((actual or {}).get("properties") or {})}
    salida: dict[str, list[str]] = {}
    for campo in sorted(set(uno) | set(otro)):
        if campo in ("properties", "citas", "fuentes", "afirmaciones_publicas"):
            continue
        if uno.get(campo) != otro.get(campo):
            salida[campo] = [_corto(uno.get(campo)), _corto(otro.get(campo))]
        if len(salida) >= MAX_DIFERENCIAS:
            break
    return salida


def final_de(id_: str, destino: dict[str, str]) -> str:
    """La ficha en que acaba la cadena de uniones de `id_` (ella misma si no está unida)."""
    actual, vistos = id_, set()
    while actual in destino and actual not in vistos:
        vistos.add(actual)
        actual = destino[actual]
    return actual


@dataclass
class Resultado:
    """Lo que hizo la puerta en una publicación."""

    ficheros: dict[str, Documento] = field(default_factory=dict)
    # Fichas que no pasaron: {"id", "comprobaciones", "origen", "diferencias"}.
    retenidas: list[Documento] = field(default_factory=list)
    entradas: int = 0
    cambiadas: int = 0
    unidas: list[str] = field(default_factory=list)
    retiradas: list[str] = field(default_factory=list)
    terminado: bool = True

    def sustituidas(self) -> list[Documento]:
        """Las fichas que salen en su versión anterior, o que no salen, por algo que no es la
        retención normal de una ficha nueva: lo que mira la vigilancia."""
        return [r for r in self.retenidas if not set(r["comprobaciones"]) <= NORMALES]


def _motivos_de_ficha(
    id_: str, interno: Documento, pase: Pase, marcas: dict[str, list[str]] | None
) -> list[str]:
    """Por qué la versión de la base de esa ficha no entra en lo publicado (vacío si entra)."""
    from proceso import invariantes

    motivos: list[str] = []
    if not pase.terminado:
        motivos.append(SIN_CONTROL)
    if id_ not in pase.vistos:
        motivos.append(SIN_PASE)
    if marcas is None:
        motivos.append(SIN_AUDITORIA)
    else:
        motivos += marcas.get(id_, [])
    try:
        motivos += invariantes.de_ficha(interno)
    except Exception as error:
        registro.warning("invariantes de %s sin comprobar: %s", id_, str(error)[:200])
        motivos.append(invariantes.SIN_COMPROBAR)
    return motivos


def pasar(
    almacen: Almacen,
    ahora: datetime,
    generados: dict[str, Documento],
    base: dict[str, Documento],
    apartados: dict[str, str] | None = None,
) -> Resultado:
    """Pasa por la puerta las entradas generadas de la base y deja la tabla `publicado` al día.
    Devuelve los ficheros que se escriben, hechos solo con las filas publicadas.

    `generados`: los documentos de `LISTAS` recién generados de la base (los que no se pudieron
    generar no vienen, y sus fichas quedan como estaban). `base`: {ficha: documento de la base}.
    `apartados`: {ficha: motivo} de las que no se pudieron preparar (exportacion/geojson.py)."""
    resultado = Resultado()
    pase = pase_del_control(almacen, ahora)
    resultado.terminado = pase.terminado
    marcas: dict[str, list[str]] | None
    try:
        marcas = marcadas(almacen, ahora)
    except Exception as error:
        # Sin auditoría no se sabe qué está protegido: ninguna versión nueva pasa.
        registro.warning("puerta de la publicación sin auditoría: %s", str(error)[:200])
        marcas = None
    filas = almacen.publicado()
    fecha = _iso(ahora)
    candidatas = {
        _id(e): (nombre, e) for nombre, d in generados.items() for e in _entradas(d, nombre)
    }
    for id_, (nombre, entrada) in sorted(candidatas.items()):
        interno = base.get(id_)
        fila = filas.get(id_)
        if interno is None:
            continue
        try:
            motivos = _motivos_de_ficha(id_, interno, pase, marcas)
            if not motivos:
                if almacen.guardar_publicado(id_, PUBLICADA, nombre, entrada, interno, {}, fecha):
                    resultado.cambiadas += 1
                filas[id_] = {"id": id_, "estado": PUBLICADA, "fichero": nombre,
                              "entrada": entrada, "detalle": {}}  # fmt: skip
                continue
        except Exception as error:
            # Cada ficha, aislada: la que falla se queda como estaba y las demás siguen.
            registro.exception("puerta de la publicación: %s se queda como estaba", id_)
            motivos = [f"fallo: {type(error).__name__}"]
        igual = fila is not None and fila["estado"] == PUBLICADA and fila["entrada"] == entrada
        if igual:
            continue
        publicada = fila is not None and fila["estado"] == PUBLICADA
        resultado.retenidas.append({
            "id": id_, "comprobaciones": motivos, "origen": BUENA if publicada else NINGUNA,
            "diferencias": diferencias(fila["entrada"] if publicada and fila else None, entrada),
        })  # fmt: skip
    _sin_candidata(almacen, resultado, filas, candidatas, base, apartados or {}, pase, fecha)
    resultado.ficheros = ficheros(generados, filas, base)
    resultado.entradas = sum(
        len(_entradas(d, n)) for n, d in resultado.ficheros.items() if n in LISTAS
    )
    anotar(almacen, ahora, resultado)
    for s in resultado.sustituidas():
        registro.warning("%s (%s): %s", *linea(s))
    return resultado


def _sin_candidata(
    almacen: Almacen,
    resultado: Resultado,
    filas: dict[str, Documento],
    candidatas: dict[str, tuple[str, Documento]],
    base: dict[str, Documento],
    apartados: dict[str, str],
    pase: Pase,
    fecha: str,
) -> None:
    """Las filas publicadas cuya ficha ya no da una entrada: unida, retirada o que no se puede
    publicar como está. Las dos primeras cambian de estado (con el control terminado); la tercera
    se queda como estaba."""
    destino = {i: str(d["fusionado_en"]) for i, d in base.items() if "fusionado_en" in d}
    pendientes: list[tuple[str, str]] = []
    for id_, fila in sorted(filas.items()):
        if id_ in candidatas or fila["estado"] != PUBLICADA:
            continue
        interno = base.get(id_)
        if interno is None:
            continue
        if not pase.terminado:
            resultado.retenidas.append({"id": id_, "comprobaciones": [SIN_CONTROL],
                                        "origen": BUENA, "diferencias": {}})  # fmt: skip
        elif "retirado" in interno:
            detalle = detalle_de_retirada(interno["retirado"], fecha)
            almacen.cambiar_estado_publicado(id_, RETIRADA, detalle, fecha)
            filas[id_] = {**fila, "estado": RETIRADA, "detalle": detalle}
            resultado.retiradas.append(id_)
        elif "fusionado_en" in interno:
            pendientes.append((id_, final_de(id_, destino)))
        else:
            motivo = apartados.get(id_, SIN_ENTRADA)
            resultado.retenidas.append({
                "id": id_, "comprobaciones": [SIN_ENTRADA], "origen": BUENA,
                "diferencias": {"motivo": ["", motivo[:MAX_VALOR]]},
            })  # fmt: skip
    for id_, final in pendientes:
        # La dirección de una ficha unida solo redirige a una ficha que está publicada; si la que
        # queda aún no lo está (nueva, sin pase), la unida sigue saliendo como estaba.
        queda = filas.get(final)
        if queda is not None and queda["estado"] == PUBLICADA:
            almacen.cambiar_estado_publicado(id_, UNIDA, {"destino": final}, fecha)
            filas[id_] = {**filas[id_], "estado": UNIDA, "detalle": {"destino": final}}
            resultado.unidas.append(f"{id_}→{final}")
        elif queda is not None and queda["estado"] == RETIRADA:
            almacen.cambiar_estado_publicado(id_, RETIRADA, queda["detalle"], fecha)
            filas[id_] = {**filas[id_], "estado": RETIRADA, "detalle": queda["detalle"]}
            resultado.retiradas.append(id_)
        else:
            resultado.retenidas.append({
                "id": id_, "comprobaciones": [UNIDA_A_NO_PUBLICADA], "origen": BUENA,
                "diferencias": {"fusionado_en": ["", final]},
            })  # fmt: skip


def sin_enlaces_rotos(entrada: Documento, publicadas: set[str]) -> Documento:
    """La entrada sin los sucesos relacionados que no están publicados: su página no existe y el
    enlace daría 404 (EODI-2025-00066 enlazaba a la 00444, retenida, el 20 de octubre de 2026).
    El enlace vuelve solo cuando la otra se publica."""
    propiedades = entrada.get("properties", entrada)
    relacionados = propiedades.get("relacionados")
    if not relacionados or all(r.get("id") in publicadas for r in relacionados):
        return entrada
    quedan = [r for r in relacionados if r.get("id") in publicadas]
    nuevas = {k: v for k, v in propiedades.items() if k != "relacionados"}
    if quedan:
        nuevas["relacionados"] = quedan
    return {**entrada, "properties": nuevas} if "properties" in entrada else nuevas


def direcciones(
    filas: dict[str, Documento], base: dict[str, Documento]
) -> tuple[dict[str, str], dict[str, Documento]]:
    """Adónde lleva cada dirección que no es una ficha publicada: ({unida: la que queda},
    {retirada: {fecha, motivo}}). Las unidas salen de la base (también las de antes de existir la
    tabla) y de las filas; una cadena que acaba en una retirada explica esa retirada."""
    publicadas = {i for i, f in filas.items() if f["estado"] == PUBLICADA}
    destino = {i: str(d["fusionado_en"]) for i, d in base.items() if "fusionado_en" in d}
    for id_, fila in filas.items():
        if fila["estado"] == UNIDA and id_ not in destino:
            destino[id_] = str(fila["detalle"].get("destino") or "")
    unidos: dict[str, str] = {}
    retirados: dict[str, Documento] = {
        i: dict(f["detalle"]) for i, f in filas.items() if f["estado"] == RETIRADA
    }
    for origen in destino:
        if origen in publicadas or origen in retirados:
            continue
        final = final_de(origen, destino)
        if final in publicadas:
            unidos[origen] = final
        elif final in retirados and origen in filas:
            retirados[origen] = dict(retirados[final])
    return dict(sorted(unidos.items())), dict(sorted(retirados.items()))


def ficheros(
    generados: dict[str, Documento], filas: dict[str, Documento], base: dict[str, Documento]
) -> dict[str, Documento]:
    """Los ficheros que se escriben: lo que traía cada documento generado fuera de su lista (el
    tipo, lo que añada la proyección) y, en la lista, las filas publicadas de ese fichero."""
    publicadas = {i for i, f in filas.items() if f["estado"] == PUBLICADA}
    salida: dict[str, Documento] = {}
    for nombre, documento in generados.items():
        if nombre not in LISTAS:
            salida[nombre] = documento
            continue
        lista = [
            sin_enlaces_rotos(f["entrada"], publicadas)
            for i, f in sorted(filas.items())
            if f["estado"] == PUBLICADA and f["fichero"] == nombre
        ]
        nuevo = {k: v for k, v in documento.items() if k not in (LISTAS[nombre], "unidos")}
        nuevo[LISTAS[nombre]] = lista
        if nombre == MAPA:
            unidos, retirados = direcciones(filas, base)
            if unidos:
                nuevo["unidos"] = unidos
            if retirados:
                nuevo["retirados"] = retirados
        salida[nombre] = nuevo
    return salida


def sembrar(almacen: Almacen, ahora: datetime, publicacion: Path) -> int:
    """La tabla `publicado`, vacía, con lo que hay publicado en `publicacion`: la migración (una
    vez). Cada ficha de los ficheros, tal como sale, con su documento de la base; las unidas de
    `unidos`; y las retiradas de la base que habían pasado el control (tenían dirección). Devuelve
    cuántas filas pone; 0 si la tabla ya tiene alguna o no hay ficheros."""
    if almacen.estados_publicados():
        return 0
    base = {str(d["id"]): d for d in almacen.incidentes()}
    fecha = _iso(ahora)
    puestas = 0
    unidos: dict[str, str] = {}
    for nombre in LISTAS:
        ruta = publicacion / nombre
        if not ruta.exists():
            continue
        documento = json.loads(ruta.read_text(encoding="utf-8"))
        if nombre == MAPA:
            unidos = dict(documento.get("unidos") or {})
        for entrada in _entradas(documento, nombre):
            id_ = _id(entrada)
            if id_ in base:
                almacen.guardar_publicado(id_, PUBLICADA, nombre, entrada, base[id_], {}, fecha)
                puestas += 1
    if not puestas:
        return 0
    for id_, final in sorted(unidos.items()):
        if id_ in base:
            minima = {"id": id_}
            almacen.guardar_publicado(
                id_, UNIDA, MAPA, minima, base[id_], {"destino": final}, fecha
            )
            puestas += 1
    vistos = set((almacen.cursor(CURSOR_CONTROL) or {}).get("vistos") or {})
    ya = almacen.estados_publicados()
    for id_, documento in sorted(base.items()):
        if id_ in ya or "retirado" not in documento or id_ not in vistos:
            continue
        detalle = detalle_de_retirada(documento["retirado"], fecha)
        almacen.guardar_publicado(id_, RETIRADA, MAPA, {"id": id_}, documento, detalle, fecha)
        puestas += 1
    registro.info("lo publicado, sembrado con lo que había en %s: %d filas", publicacion, puestas)
    return puestas


def linea(retenida: Documento) -> tuple[str, str, str]:
    """Lo que dice el registro de una ficha que no pasó: «publicada en su versión buena» o «no
    publicada» (nunca salió en la web)."""
    if retenida["origen"] == NINGUNA:
        que = f"{retenida['id']} no publicada"
    else:
        que = f"{retenida['id']} publicada en su versión {retenida['origen']}"
    cambios = ", ".join(retenida["diferencias"]) or "sin diferencias"
    return que, ", ".join(retenida["comprobaciones"]), cambios


def anotar(almacen: Almacen, ahora: datetime, resultado: Resultado) -> None:
    """El cursor: lo de la última publicación y, por día UTC, las fichas en su versión anterior.
    No se vuelve a escribir si dice lo mismo que el anterior salvo la fecha: una recogida sin nada
    nuevo no cambia la base."""
    anterior = almacen.cursor(CURSOR) or {}
    sustituidas = resultado.sustituidas()
    limite = coste.dia(ahora - timedelta(days=DIAS))
    dias = {d: v for d, v in (anterior.get("dias") or {}).items() if d >= limite}
    hoy = coste.dia(ahora)
    if sustituidas or hoy in dias:
        dias[hoy] = sorted(set(dias.get(hoy, [])) | {str(s["id"]) for s in sustituidas})
    nuevo = {
        "fecha": _iso(ahora),
        "sustituidas": sustituidas,
        "dias": dict(sorted(dias.items())),
        "terminado": resultado.terminado,
        "sin_pase": sorted(
            str(r["id"]) for r in resultado.retenidas if set(r["comprobaciones"]) <= NORMALES
        ),
    }
    if {k: v for k, v in nuevo.items() if k != "fecha"} == {
        k: v for k, v in anterior.items() if k != "fecha"
    }:
        return
    almacen.guardar_cursor(CURSOR, nuevo)
