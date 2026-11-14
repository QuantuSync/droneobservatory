"""Las invariantes del ciclo de vida de una ficha (docs/ciclo_de_vida.md). Las mismas funciones
corren en la puerta de la publicación (cada recogida), en el ensayo y en la CI.

- I1: ninguna ficha publicada sin pase del control.
- I2: ninguna dirección publicada en 404: toda fila de lo publicado es una ficha publicada, una
  unida a una publicada o una retirada con su motivo.
- I3: ningún dato revisado a mano distinto de su revisión.
- I4: ninguna versión nueva igual a la anterior salvo la fecha.
- I5: ningún aviso con datos distintos de lo publicado.
- I6: ninguna unión vigente entre fichas que la definición de suceso da por distintos
  (proceso/suceso.py): lo que `incidentes.revisar_fusiones` tenía que haber deshecho.
- I7: ninguna dirección publicada lleva a una ficha de otro suceso: la de una ficha unida lleva a
  una ficha de su unión vigente, y esa no es de otro país ni la separó de ella una revisión.
- I8: ningún suceso en dos fichas: ninguna ficha publicada al lado de otra publicada que la
  definición da por el mismo suceso (proceso/suceso.del_mismo_suceso), y ninguna ficha con el
  pase del control parada por el candado de la publicación porque no se pudo unir a la suya
  (exportacion/puerta.candado).

`de_ficha` es lo que la puerta mira de cada versión antes de dejarla entrar (I3); `comprobar` las
mira todas sobre la base y lo publicado, sin escribir nada. `avisar` manda por el tema privado,
una vez por ficha e invariante, lo que se rompe en producción."""

import contextlib
import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from esquema import Documento

registro = logging.getLogger(__name__)

I1, I2, I3, I4, I5, I6, I7, I8 = "I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8"
TODAS = (I1, I2, I3, I4, I5, I6, I7, I8)
SIN_COMPROBAR = "invariantes"
CURSOR = "invariantes"
TITULO_AVISO = "EODI · Invariante rota"
# Lo que puede cambiar en una versión sin que cambie la ficha.
SOLO_FECHA = ("ultima_actualizacion",)
DIAS_AVISADAS = 14
# Los datos de un aviso que tienen que ser los de la ficha publicada.
MAX_IDS = 20


def de_ficha(interno: Documento) -> list[str]:
    """Las invariantes que rompe esta versión de la ficha y que la puerta no deja pasar: I3."""
    from proceso import decidir

    return [I3] if decidir.distinto_de_su_revision(interno) else []


def sin_fecha(documento: Documento) -> Documento:
    """El documento sin lo que cambia en un guardado aunque la ficha diga lo mismo: la fecha de
    su última actualización y el orden de sus afirmaciones (son un conjunto: el cerrojo, al
    conservar un dato, vuelve a poner las suyas al final)."""
    resultado = documento
    control = documento.get("control")
    if isinstance(control, dict) and any(c in control for c in SOLO_FECHA):
        resultado = {
            **resultado,
            "control": {k: v for k, v in control.items() if k not in SOLO_FECHA},
        }
    afirmaciones = documento.get("afirmaciones")
    if isinstance(afirmaciones, list) and len(afirmaciones) > 1:
        ordenadas = sorted(
            afirmaciones, key=lambda a: json.dumps(a, sort_keys=True, ensure_ascii=False)
        )
        resultado = {**resultado, "afirmaciones": ordenadas}
    return resultado


def dice_lo_mismo(anterior: Documento | None, nuevo: Documento) -> bool:
    """La versión nueva dice lo mismo que la anterior, sea idéntica o cambie solo la fecha de
    actualización o el orden de las afirmaciones: no hay nada que escribir."""
    return anterior is not None and (anterior == nuevo or sin_fecha(anterior) == sin_fecha(nuevo))


def igual_salvo_la_fecha(anterior: Documento | None, nuevo: Documento) -> bool:
    """Una versión guardada que dice lo mismo que la anterior (I4): solo cambia la fecha de
    actualización o el orden de las afirmaciones."""
    return anterior is not None and anterior != nuevo and sin_fecha(anterior) == sin_fecha(nuevo)


def sin_pase(filas: dict[str, Documento], vistos: frozenset[str] | set[str]) -> list[str]:
    """I1: las fichas publicadas que no han pasado el control."""
    return sorted(i for i, f in filas.items() if f["estado"] == "publicada" and i not in vistos)


def sin_direccion(filas: dict[str, Documento], base: dict[str, Documento]) -> list[str]:
    """I2: las direcciones publicadas que no llevan a ningún sitio: una fila unida cuyo destino no
    acaba en una ficha publicada ni en una retirada con motivo, o una retirada sin motivo."""
    from exportacion import puerta

    unidos, retirados = puerta.direcciones(filas, base)
    rotas = []
    for id_, fila in sorted(filas.items()):
        if fila["estado"] == puerta.PUBLICADA:
            continue
        if id_ in unidos:
            continue
        motivo = (retirados.get(id_) or {}).get("motivo") or {}
        if not (str(motivo.get("es") or "").strip() and str(motivo.get("en") or "").strip()):
            rotas.append(id_)
    return rotas


def revisados_distintos(base: dict[str, Documento], ids: set[str]) -> list[str]:
    """I3: «ficha dato» de las fichas publicadas con un dato revisado a mano distinto de su
    revisión."""
    from proceso import decidir, incidentes

    rotas = []
    for id_ in sorted(ids):
        documento = base.get(id_)
        if documento is None or not incidentes.activo(documento):
            continue
        rotas += [f"{id_} {dato}" for dato in decidir.distinto_de_su_revision(documento)]
    return rotas


def versiones_iguales(cambios: list[Documento]) -> list[str]:
    """I4: las fichas con una versión guardada que solo cambia la fecha (de `Almacen.
    cambios_desde`: los cambios de los incidentes, no sus motivos)."""
    return sorted({
        str(c["entidad_id"])
        for c in cambios
        if c.get("tabla") == "incidentes" and igual_salvo_la_fecha(c.get("anterior"), c["nuevo"])
    })  # fmt: skip


def uniones_de_sucesos_distintos(almacen: Any) -> list[str]:
    """I6: «absorbida→destino (regla)» de las uniones vigentes que la definición da por sucesos
    distintos por una regla firme (países distintos con una autoridad del suyo, una revisión que
    las separó, dos cierres de noches distintas): las que `incidentes.revisar_fusiones` deshace
    sola en cada recogida. Si queda alguna es que no pudo (el cerrojo, un fallo): hay una ficha
    de un suceso dentro de la de otro."""
    from proceso import incidentes, suceso

    decididas: dict[str, dict[str, str]] | None = None
    rotas = []
    for fusion in almacen.fusiones():
        if fusion["revertida"]:
            continue
        absorbido = almacen.incidente(fusion["absorbido"])
        destino = almacen.incidente(fusion["destino"])
        if absorbido is None or destino is None:
            continue
        if absorbido.get("fusionado_en") != destino["id"]:
            continue
        if decididas is None:
            decididas = suceso.autoridades_decididas(almacen)
        dicho = incidentes.union_que_se_deshace(fusion, absorbido, destino, decididas)
        if dicho is not None:
            rotas.append(f"{fusion['absorbido']}→{fusion['destino']} ({dicho.regla})")
    return sorted(set(rotas))


# Las reglas firmes de la definición que valen también entre una ficha unida y la última de su
# cadena de uniones (no solo entre las dos de cada unión, que es I6): el país y lo que separó una
# revisión. La jornada de una ficha unida no se mira aquí: su fecha es la que tenía antes de
# unirse, muchas veces la de publicación de una noticia posterior (medido el 12 de noviembre de
# 2026: 104 de 654 unidas tienen otra jornada que la ficha que queda, y las leídas están bien
# unidas); las noches distintas de dos cierres las mira I6 en cada unión.
REGLAS_DE_OTRO_SUCESO = frozenset({"paises_distintos", "revision"})


def _cadena(id_: str, destino: dict[str, str]) -> list[str]:
    """Las fichas por las que pasa la unión vigente de `id_`, hasta la que queda."""
    cadena: list[str] = []
    actual = id_
    while actual in destino and destino[actual] not in cadena and destino[actual] != id_:
        actual = destino[actual]
        cadena.append(actual)
    return cadena


def direcciones_a_otro_suceso(
    almacen: Any, filas: dict[str, Documento], base: dict[str, Documento]
) -> list[str]:
    """I7: «unida→adonde lleva (por qué)» de las direcciones publicadas que llevan a una ficha de
    otro suceso. Se mira adónde lleva cada ficha unida, en su fila y en lo que se publica
    (`puerta.direcciones`):

    - a una ficha que no es de su unión vigente: la unieron a otra, o volvió a estar suelta, y su
      dirección sigue llevando a la anterior (EODI-2026-00218 y EODI-2026-00522, el 12 de
      noviembre de 2026);
    - a una ficha que la definición da por otro suceso por una regla firme (otro país con una
      autoridad del suyo, o una revisión que las dio por distintas), salvo que alguna unión de la
      cadena sea una revisión a mano, que manda."""
    from exportacion import puerta
    from proceso import suceso

    unidos, _ = puerta.direcciones(filas, base)
    destino = {i: str(d["fusionado_en"]) for i, d in base.items() if "fusionado_en" in d}
    a_mano: set[str] | None = None
    decididas: dict[str, dict[str, str]] | None = None
    rotas: list[str] = []
    for id_, fila in sorted(filas.items()):
        if fila["estado"] != puerta.UNIDA or id_ not in base:
            continue
        cadena = _cadena(id_, destino)
        llevan = {str(fila["detalle"].get("destino") or ""), unidos.get(id_, "")} - {""}
        for adonde in sorted(llevan):
            if adonde not in cadena:
                vigente = cadena[-1] if cadena else "ninguna"
                rotas.append(f"{id_}→{adonde} (su unión vigente es {vigente})")
                continue
            otra = base.get(adonde)
            if otra is None:
                continue
            if a_mano is None:
                a_mano = {
                    str(f["absorbido"])
                    for f in almacen.fusiones()
                    if not f["revertida"]
                    and str(f["motivo"]).startswith(suceso.PREFIJO_REVISADA)
                    and not str(f["motivo"]).startswith(suceso.PREFIJO_CONTROL)
                }
            tramo = [id_, *cadena[: cadena.index(adonde)]]
            if any(t in a_mano for t in tramo):
                continue
            if decididas is None:
                decididas = suceso.autoridades_decididas(almacen)
            propia = {k: v for k, v in base[id_].items() if k != "fusionado_en"}
            dicho = suceso.veredicto(
                propia, otra, de_a=decididas.get(id_), de_b=decididas.get(adonde), vigente=True
            )
            if dicho.relacion == suceso.DISTINTOS and dicho.regla in REGLAS_DE_OTRO_SUCESO:
                rotas.append(f"{id_}→{adonde} ({dicho.regla})")
    return rotas


def mismo_suceso_en_dos_fichas(
    almacen: Any, filas: dict[str, Documento], vistos: frozenset[str] | set[str]
) -> list[str]:
    """I8: «una=otra (regla)» de cada par de fichas publicadas que la definición da por el mismo
    suceso, y «ficha parada: el mismo suceso que otra» de las fichas activas que tienen el pase
    del control y no se publican porque hay una publicada de su suceso y no se pudieron unir
    (exportacion/puerta.candado). EODI-2026-00817 y EODI-2026-00814 (Estonia, 11 de noviembre
    de 2026) estuvieron publicadas a la vez."""
    from exportacion import puerta
    from proceso import incidentes, suceso

    publicadas = puerta.publicadas_activas(almacen, filas)
    del_experto = suceso.distintos_del_experto(almacen)
    decididas = suceso.autoridades_decididas(almacen)
    rotas: set[str] = set()
    for id_, ficha in sorted(publicadas.items()):
        for otra, dicho in puerta.mismo_suceso_publicado(ficha, publicadas, del_experto, decididas):
            uno, dos = sorted((id_, str(otra["id"])), key=suceso.orden_registro)
            rotas.add(f"{uno}={dos} ({dicho.regla})")
    for ficha in almacen.incidentes():
        id_ = str(ficha["id"])
        if id_ in publicadas or id_ not in vistos or not incidentes.activo(ficha):
            continue
        mismos = puerta.mismo_suceso_publicado(ficha, publicadas, del_experto, decididas)
        if mismos:
            otras = ", ".join(str(o["id"]) for o, _ in mismos)
            rotas.add(f"{id_} parada: el mismo suceso que {otras}")
    return sorted(rotas)


def datos_del_aviso(documento: Documento) -> dict[str, Any]:
    """Lo que un aviso cuenta de una ficha (recogida/avisos.mensaje), de su documento interno o
    de su entrada publicada: el titular, el estado, el tipo, el país y el inicio."""
    propio = documento.get("properties", documento)
    return {
        "titulo": propio.get("titulo"),
        "estado": (propio.get("estado") or {}).get("actual"),
        "tipo": propio.get("tipo"),
        "pais": (propio.get("lugar") or {}).get("pais"),
        "inicio": ((propio.get("tiempo") or {}).get("inicio") or {}).get("valor"),
    }


def aviso_distinto(interno: Documento, entrada: Documento) -> list[str]:
    """I5: los datos del aviso que no son los de la ficha publicada. El titular publicado se
    escribe con los nombres de lugar de la web (exportacion/geojson.con_nombres), así que solo se
    compara si la entrada lo trae igual que la base; lo demás, siempre.

    La exportación pone de acuerdo el inicio con el primer aviso (proceso/coherencia.coherente):
    el documento interno se compara después de ese mismo paso. EODI-2026-00777 (11 de noviembre de
    2026) tenía en la base el día 11 y en la web el 10, y eso no es un aviso distinto: el aviso
    lleva el inicio de la entrada publicada (recogida/avisos.con_lo_publicado)."""
    from proceso import coherencia

    # Un documento que la coherencia no sabe leer se compara tal cual.
    with contextlib.suppress(Exception):
        interno = coherencia.coherente(interno)
    del_aviso, publicado = datos_del_aviso(interno), datos_del_aviso(entrada)
    return [
        campo
        for campo in ("estado", "tipo", "pais", "inicio")
        if del_aviso[campo] != publicado[campo]
    ]


def comprobar(almacen: Any, ahora: datetime) -> dict[str, list[str]]:
    """Todas las invariantes que se pueden mirar en la base, sin escribir nada: {invariante:
    [lo que la rompe]}, con todas las claves (vacías si se cumplen). I5 se comprueba al componer
    cada aviso (recogida/avisos.py) y aquí se mira lo mismo sobre lo publicado."""
    from exportacion import puerta

    filas = almacen.publicado()
    base = {str(d["id"]): d for d in almacen.incidentes()}
    pase = puerta.pase_del_control(almacen, ahora)
    publicadas = {i for i, f in filas.items() if f["estado"] == puerta.PUBLICADA}
    # I4, sobre lo que ha escrito esta recogida (`ahora` es su hora de arranque): lo anterior es
    # de recogidas ya comprobadas, o de antes de que existiera la comprobación.
    desde = ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
    internos = almacen.publicado_interno(publicadas)
    return {
        I1: sin_pase(filas, pase.vistos),
        I2: sin_direccion(filas, base),
        I3: revisados_distintos(internos, publicadas),
        I4: versiones_iguales(almacen.cambios_desde(desde)),
        I5: sorted(
            f"{i} {', '.join(distintos)}"
            for i in publicadas
            if i in internos and (distintos := aviso_distinto(internos[i], filas[i]["entrada"]))
        ),
        I6: uniones_de_sucesos_distintos(almacen),
        I7: direcciones_a_otro_suceso(almacen, filas, base),
        I8: mismo_suceso_en_dos_fichas(almacen, filas, pase.vistos),
    }


def rotas(resultado: dict[str, list[str]]) -> dict[str, list[str]]:
    return {clave: lista for clave, lista in resultado.items() if lista}


def texto_aviso(invariante: str, que: str) -> str:
    nombres = {
        I1: "ficha publicada sin pase del control",
        I2: "dirección publicada que no lleva a ninguna ficha",
        I3: "dato revisado a mano distinto de su revisión",
        I4: "versión nueva igual a la anterior salvo la fecha",
        I5: "aviso con datos distintos de lo publicado",
        I6: "unión de dos fichas que la definición da por sucesos distintos",
        I7: "dirección publicada que lleva a una ficha de otro suceso",
        I8: "el mismo suceso en dos fichas",
    }
    return f"{invariante} ({nombres.get(invariante, invariante)}): {que}"


def avisar(
    almacen: Any,
    ahora: datetime,
    resultado: dict[str, list[str]],
    avisador: Callable[[str], Callable[[str], None] | None] | None,
) -> list[str]:
    """Deja en el cursor `invariantes` lo que se rompe y manda por el tema privado cada rotura
    nueva, una vez por ficha e invariante (lo avisado se olvida a los 14 días). Sin quien avise
    (fuera del servidor, ensayo) solo lo apunta. Devuelve lo avisado ahora. El cursor no se toca
    si todo sigue igual: una recogida sin nada nuevo no cambia la base."""
    anterior = almacen.cursor(CURSOR) or {}
    limite = (ahora - timedelta(days=DIAS_AVISADAS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    avisadas = {k: v for k, v in (anterior.get("avisadas") or {}).items() if v >= limite}
    nuevas = [
        (invariante, que)
        for invariante, lista in sorted(rotas(resultado).items())
        for que in lista[:MAX_IDS]
        if f"{invariante}:{que}" not in avisadas
    ]
    hechas: list[str] = []
    avisar_ = avisador(TITULO_AVISO) if avisador is not None and nuevas else None
    for invariante, que in nuevas:
        registro.error("invariante rota: %s", texto_aviso(invariante, que))
        if avisar_ is None:
            continue
        try:
            avisar_(texto_aviso(invariante, que))
        except Exception as error:
            registro.warning("invariante rota sin avisar: %s", str(error)[:200])
            continue
        avisadas[f"{invariante}:{que}"] = ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
        hechas.append(f"{invariante}:{que}")
    nuevo = {"rotas": rotas(resultado), "avisadas": dict(sorted(avisadas.items()))}
    if nuevo != {k: v for k, v in anterior.items() if k != "fecha"}:
        almacen.guardar_cursor(CURSOR, {**nuevo, "fecha": ahora.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return hechas
