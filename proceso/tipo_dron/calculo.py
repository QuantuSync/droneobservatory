"""Tipo de dron de cada incidente: lo que identificó la autoridad, los rasgos descritos y la
clase probable, con lo que se publica de ello.

Para cada incidente vigente:

1. si una frase oficial nombra el modelo o la familia sin duda, «identificado» (modelo tal como lo
   escribe la autoridad, su grupo, la frase y la fuente);
2. los rasgos descritos en todas sus frases (proceso/tipo_dron/rasgos.py);
3. la probabilidad de cada clase y de cada grupo (proceso/tipo_dron/modelo.py), con la frecuencia
   de partida de todos los casos de respuesta conocida;
4. lo que se publica: si no está identificado, hay base (modelo.con_base) y el grupo más probable
   es uno de los que pasan la comprobación (proceso/tipo_dron/comprobacion.py), los grupos
   publicados con su probabilidad (los de un 10 % o más) y el resto junto como «otras clases».
   Sin base, o con el grupo más probable sin comprobar, no se publica nada del incidente.

Un incidente identificado cuenta como caso de respuesta conocida: su clase deducida se calcula
igual (para la exportación), pero no se publica.
"""

from collections.abc import Iterable
from typing import Any

from esquema import Documento
from proceso.deduccion.catalogo import Catalogo
from proceso.rutas import incursiones
from proceso.tipo_dron import casos, comprobacion, identificacion, modelo, rasgos
from proceso.tipo_dron.casos import Conocido

REDONDEO = 3


def _redondo(valores: dict[str, float]) -> dict[str, float]:
    return {k: round(v, REDONDEO) for k, v in sorted(valores.items())}


def _razon(razon: modelo.Razon) -> Documento:
    documento: Documento = {
        "tipo": razon.tipo,
        "clave": razon.clave,
        "clases": list(razon.clases),
        "factor": razon.factor,
    }
    detalle = {k: v for k, v in razon.detalle.items() if v is not None}
    if detalle:
        documento["datos"] = detalle
    return documento


def publicable(resultado: modelo.Resultado, grupos_publicados: Iterable[str]) -> Documento | None:
    """Los grupos que se enseñan: el más probable tiene que estar comprobado; se enseñan los
    comprobados con un 10 % o más y el resto va junto."""
    publicados = set(grupos_publicados)
    minimo = float(modelo.configuracion()["publicar"]["probabilidad_minima_mostrada"])
    orden = resultado.ordenados()
    if not orden or orden[0][0] not in publicados:
        return None
    compatibles: list[dict[str, Any]] = [
        {"grupo": g, "probabilidad": round(p, 2)}
        for g, p in orden
        if g in publicados and p >= minimo
    ]
    otras = round(1.0 - sum(float(c["probabilidad"]) for c in compatibles), 2)
    return {"compatible": compatibles, "otras": max(otras, 0.0)}


def documento_incidente(
    catalogo: Catalogo,
    documento: Documento,
    frases: list[tuple[str, str, str, str | None]],
    deduccion: Documento | None,
    conocidos: list[Conocido],
    grupos_publicados: Iterable[str],
    velocidad_episodio: dict[str, Any] | None = None,
) -> Documento:
    lista = casos.frases_de(frases)
    entrada = casos.entrada_de_incidente(documento, lista, deduccion)
    # Recorrido que da la autoridad (incursiones en Rumanía, Moldavia y Polonia) y velocidad
    # necesaria entre avistamientos encadenados: una restricción más si decide algo.
    recorrido = incursiones.recorrido(documento, frases)
    velocidades = [velocidad_episodio] if velocidad_episodio else []
    if recorrido is not None:
        de_recorrido = incursiones.velocidad(recorrido["puntos"])
        if de_recorrido is not None:
            recorrido["velocidad"] = de_recorrido
            velocidades.append({**de_recorrido, "fuente": recorrido["fuente"]})
    for v in velocidades:
        if v.get("decide") == "reaccion":
            entrada.rasgos.append({
                "rasgo": rasgos.VELOCIDAD,
                "valor": {"kmh": float(v["min_kmh"])},
                "cita": f"{v['distancia_km']} km en {v['minutos']} min",
                "fuente": str(v.get("fuente") or v.get("desde") or v.get("hasta")),
                "origen": "deducido",
            })  # fmt: skip
    hallado = identificacion.identificado(lista)
    previa = [(k.entrada.zona, k.respuesta) for k in conocidos if k.id != documento["id"]]
    resultado = modelo.calcular(catalogo, entrada, previa)
    base = modelo.con_base(entrada, resultado)
    salida: Documento = {
        "version": modelo.version(),
        "version_rasgos": rasgos.VERSION,
        "rasgos": entrada.rasgos,
        "probabilidades": _redondo(resultado.por_clase),
        "grupos": _redondo(resultado.por_grupo),
        "razones": [_razon(r) for r in resultado.razones],
        "con_base": base,
    }
    if recorrido is not None:
        salida["recorrido"] = recorrido
    # Solo se dice qué dron pudo ser cuando el dron está confirmado y el incidente no está
    # desmentido: de un «posible dron» que luego no lo era no se publica ninguna clase.
    confirmado = documento.get("presencia_dron") == "confirmada" and (
        (documento.get("estado") or {}).get("actual") != "desmentido"
    )
    if hallado is not None:
        salida["identificado"] = hallado
    elif base and confirmado:
        publicado = publicable(resultado, grupos_publicados)
        if publicado is not None:
            # Cuántos casos de respuesta conocida de su zona dan la frecuencia de partida.
            zona = entrada.zona
            publicado["casos_referencia"] = sum(
                1 for k in conocidos if k.id != documento["id"] and k.entrada.zona == zona
            )
            salida["publicado"] = publicado
    return salida


def calcular(
    catalogo: Catalogo,
    incidentes: list[tuple[Documento, list[tuple[str, str, str, str | None]], Documento | None]],
    encuentros: Iterable[Documento],
    episodios: Iterable[Documento] = (),
) -> tuple[dict[str, Documento], dict[str, Any]]:
    """Documento de cada incidente y resumen de la comprobación."""
    de_base = casos.de_la_base(incidentes)
    conocidos = de_base + casos.de_validacion(de_base) + casos.de_ukab(encuentros)
    evaluados = comprobacion.evaluar(catalogo, conocidos)
    resumen = comprobacion.resumen(evaluados)
    resumen["casos"] = comprobacion.tabla_de_casos(evaluados)
    publicados = resumen["grupos_publicados"] if resumen["pasa"] else []
    por_id = {d["id"]: d for d, _, _ in incidentes}
    velocidades: dict[str, Any] = {}
    for episodio in episodios:
        miembros = [por_id[i] for i in episodio.get("incidentes", []) if i in por_id]
        for id_, v in incursiones.velocidades_de_episodio(miembros).items():
            velocidades[id_] = {**v, "fuente": episodio["id"]}
    documentos = {
        d["id"]: documento_incidente(
            catalogo, d, frases, deduccion, conocidos, publicados, velocidades.get(d["id"])
        )
        for d, frases, deduccion in incidentes
    }
    return documentos, resumen


def recuento(documentos: dict[str, Documento]) -> dict[str, int]:
    return {
        "identificados": sum(1 for d in documentos.values() if "identificado" in d),
        "deducidos": sum(1 for d in documentos.values() if "publicado" in d),
        "con_base_sin_publicar": sum(
            1
            for d in documentos.values()
            if d["con_base"] and "identificado" not in d and "publicado" not in d
        ),
        "sin_base": sum(
            1 for d in documentos.values() if not d["con_base"] and "identificado" not in d
        ),
    }
