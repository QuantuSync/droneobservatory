"""Validación del motor con casos de modelo conocido (configuracion/validacion_deduccion.json).

Cada caso tiene el modelo establecido por restos o por una confirmación oficial, con su fuente, y
la clase (o clases) del catálogo que le corresponden. Se evalúa como un incidente más, con el
viento y la temperatura medidos en su punto y su día, pero sin el nombre del modelo: el modelo es
lo que se valida, y si entrara en la descripción la regla R7 lo apoyaría por sí misma. Si el
caso está en la base, se da además el resultado que el motor guardó para ese incidente.

Resultado de cada caso:

- acierto: alguna de sus clases reales queda compatible;
- fallo_grave: todas sus clases reales quedan descartadas (objetivo: ninguno);
- indeterminado: ni lo uno ni lo otro (sin datos o con conflicto).
"""

import json
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from proceso import condiciones as meteo_lugar
from proceso.deduccion import motor
from proceso.deduccion.catalogo import CONFIGURACION, Catalogo
from proceso.deduccion.reglas import Caso

CASOS = CONFIGURACION / "validacion_deduccion.json"
ACIERTO, FALLO_GRAVE, INDETERMINADO = "acierto", "fallo_grave", "indeterminado"
# Radio de un caso situado por el nombre de su localidad.
RADIO_LOCALIDAD_KM = 5.0

Horario = dict[str, list[Any]]
# (lat, lon, día) → series horarias de Open-Meteo, o None si no hay.
Meteo = Callable[[float, float, date], Horario | None]


def cargar(ruta: Path = CASOS) -> dict[str, Any]:
    contenido: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return contenido


def _momento(caso: dict[str, Any]) -> tuple[datetime, str]:
    dia = date.fromisoformat(caso["fecha"])
    if caso.get("hora_utc"):
        hora, minuto = (int(x) for x in caso["hora_utc"].split(":"))
        return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=UTC), "minuto"
    return datetime(dia.year, dia.month, dia.day, tzinfo=UTC), "dia"


def caso_motor(caso: dict[str, Any], meteo: Meteo | None) -> Caso:
    momento, precision = _momento(caso)
    lat, lon = caso["punto"]["lat"], caso["punto"]["lon"]
    condiciones = None
    if meteo is not None:
        horario = meteo(lat, lon, momento.date())
        if horario:
            lugar = meteo_lugar.lugar_incidente(
                None,
                lat,
                lon,
                momento if precision == "minuto" else None,
                momento.date(),
                horario,
                [],
                None,
            )
            condiciones = {"lugar": lugar}
    return Caso(
        id=caso["id"],
        tipo="incidente",
        pais=caso["pais"],
        lat=lat,
        lon=lon,
        radio_km=RADIO_LOCALIDAD_KM,
        inicio=momento.timestamp(),
        precision=precision,
        entrada_exterior=bool(caso.get("entrada_exterior")),
        entrada_confirmada=bool(caso.get("entrada_exterior")),
        condiciones=condiciones,
    )


def resultado_de(deduccion: dict[str, Any], clases: list[str]) -> str:
    compatibles = {x["clase"] for x in deduccion.get("compatibles", [])}
    descartadas = {x["clase"] for x in deduccion.get("descartadas", [])}
    if compatibles & set(clases):
        return ACIERTO
    if set(clases) <= descartadas:
        return FALLO_GRAVE
    return INDETERMINADO


def validar(
    catalogo: Catalogo,
    casos: dict[str, Any],
    meteo: Meteo | None,
    de_la_base: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Evalúa cada caso y devuelve el detalle y el resumen."""
    detalle = []
    cuentas: Counter[str] = Counter()
    cuentas_base: Counter[str] = Counter()
    for caso in casos["casos"]:
        clases = caso.get("clases_reales") or []
        if not clases:
            detalle.append({"id": caso["id"], "resultado": "excluido", "motivo": caso.get("nota")})
            continue
        deduccion = motor.evaluar_incidente(catalogo, caso_motor(caso, meteo), [])
        resultado = resultado_de(deduccion, clases)
        cuentas[resultado] += 1
        fila: dict[str, Any] = {
            "id": caso["id"],
            "modelo": caso["modelo"],
            "clases_reales": clases,
            "resultado": resultado,
            "compatibles": [x["clase"] for x in deduccion["compatibles"]],
            "descartadas": {
                x["clase"]: [p["regla"] for p in x["por"]] for x in deduccion["descartadas"]
            },
            "con_meteo": caso_tiene_meteo(deduccion),
        }
        incidente = caso.get("incidente")
        if incidente and incidente in de_la_base:
            fila["incidente"] = incidente
            fila["resultado_en_la_base"] = resultado_de(de_la_base[incidente], clases)
            cuentas_base[fila["resultado_en_la_base"]] += 1
        detalle.append(fila)
    evaluados = sum(cuentas.values())
    return {
        "version_motor": motor.VERSION,
        "version_catalogo": catalogo.version,
        "version_casos": casos["version"],
        "casos": len(casos["casos"]),
        "evaluados": evaluados,
        "aciertos": cuentas[ACIERTO],
        "fallos_graves": cuentas[FALLO_GRAVE],
        "indeterminados": cuentas[INDETERMINADO],
        "en_la_base": dict(sorted(cuentas_base.items())),
        "detalle": detalle,
    }


def caso_tiene_meteo(deduccion: dict[str, Any]) -> bool:
    return any("meteorologia" in x.get("reglas", []) for x in deduccion.get("compatibles", []))


def poder_de_descarte(resultados: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Por tipo de caso: en cuántos se descarta al menos una clase y cuántas quedan compatibles
    de media."""
    por_tipo: dict[str, Counter[str]] = {}
    compatibles: dict[str, int] = {}
    for registro in resultados.values():
        tipo = registro["tipo"]
        d = registro["deduccion"]
        cuenta = por_tipo.setdefault(tipo, Counter())
        cuenta["casos"] += 1
        cuenta["con_descarte"] += bool(d.get("descartadas"))
        cuenta["con_conflicto"] += bool(d.get("conflictos"))
        cuenta["sin_ninguna_compatible"] += not d.get("compatibles")
        compatibles[tipo] = compatibles.get(tipo, 0) + len(d.get("compatibles", []))
    return {
        tipo: {
            **dict(sorted(c.items())),
            "compatibles_media": round(compatibles[tipo] / c["casos"], 2) if c["casos"] else None,
        }
        for tipo, c in sorted(por_tipo.items())
    }


# Clases del catálogo que corresponden a la clase que da la UK Airprox Board a un encuentro.
CLASES_AIRPROX = {
    "multirrotor_pequeno": (
        "multirrotor_consumo_sub250",
        "multirrotor_consumo",
        "multirrotor_profesional",
        "fpv",
    ),
    "ala_fija": (
        "ala_fija_tactica_electrica",
        "ala_fija_reconocimiento_combustion",
        "municion_merodeadora",
        "aeromodelo_ala_fija_pequeno",
    ),
}
DESDE_AIRPROX = "2022-01-01"


def airprox(
    catalogo: Catalogo, encuentros: list[dict[str, Any]], meteo: Meteo | None
) -> dict[str, Any]:
    """Coherencia de las reglas de viento (R2) y de descripción (R7) con los encuentros de la UK
    Airprox Board que tienen altura, descripción y una clase (multirrotor o ala fija) desde 2022
    (Open-Meteo da los niveles de presión desde entonces). Incoherente: la regla de viento
    descarta todas las clases de ese tipo, o la descripción apoya el tipo contrario."""
    from proceso.deduccion import reglas

    cuentas: Counter[str] = Counter()
    incoherentes = []
    for encuentro in encuentros:
        objeto = encuentro.get("objeto", {})
        tipo = objeto.get("clase")
        punto = encuentro.get("posicion", {}).get("punto")
        if (
            tipo not in CLASES_AIRPROX
            or not objeto.get("descripcion")
            or not punto
            or "altitud" not in encuentro
            or encuentro["instante"]["valor"] < DESDE_AIRPROX
        ):
            continue
        cuentas["evaluados"] += 1
        momento = datetime.fromisoformat(encuentro["instante"]["valor"].replace("Z", "+00:00"))
        caso = Caso(
            id=encuentro["id"],
            tipo="encuentro",
            pais="GB",
            lat=punto["lat"],
            lon=punto["lon"],
            inicio=momento.timestamp(),
            precision="minuto",
            textos=[objeto["descripcion"]],
        )
        if meteo is not None:
            horario = meteo(punto["lat"], punto["lon"], momento.date())
            if horario:
                caso.condiciones = {
                    "lugar": meteo_lugar.lugar_incidente(
                        None, punto["lat"], punto["lon"], momento, momento.date(), horario, [], None
                    )
                }
                cuentas["con_meteo"] += 1
        propias = CLASES_AIRPROX[tipo]
        viento_ev = reglas.r2_meteorologia(catalogo, caso)
        descartadas = {e.clase for e in viento_ev if e.efecto == reglas.DESCARTA}
        if set(propias) <= descartadas:
            cuentas["viento_descarta_su_tipo"] += 1
            incoherentes.append({"id": encuentro["id"], "regla": "meteorologia", "tipo": tipo})
        elif descartadas & set(propias):
            cuentas["viento_descarta_parte_de_su_tipo"] += 1
        descripcion = reglas.r7_descripcion(catalogo, caso)
        a_favor = {e.clase for e in descripcion if e.efecto == reglas.A_FAVOR}
        en_contra = {e.clase for e in descripcion if e.efecto == reglas.EN_CONTRA}
        if a_favor & set(propias):
            cuentas["descripcion_apoya_su_tipo"] += 1
        if set(propias) <= en_contra and not a_favor & set(propias):
            cuentas["descripcion_contra_su_tipo"] += 1
            incoherentes.append({"id": encuentro["id"], "regla": "descripcion", "tipo": tipo})
        if not descripcion:
            cuentas["descripcion_sin_rasgos"] += 1
    return {**dict(sorted(cuentas.items())), "incoherentes": incoherentes}
