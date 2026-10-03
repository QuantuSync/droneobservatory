"""Aceleraciones máximas derivadas con física de las cifras de ficha del catálogo.

Cuando el fabricante no publica la aceleración, se calcula con una fórmula a partir de otras
cifras de la misma ficha, y la entrada lo dice (`derivada`: fórmula, supuesto y los datos de
partida con su campo y su fuente). Fórmulas (g = 9,80665 m/s², la gravedad normal):

- Multirrotor, horizontal: a = g·tan(θ), con θ el ángulo máximo de inclinación de la ficha. Si
  el modelo tiene un modo manual sin límite de actitud y la ficha solo da el ángulo de otro modo,
  g·tan(θ) es solo una cota inferior (entrada con `min`). Es la
  aceleración horizontal de un multirrotor que mantiene la altura con el empuje inclinado θ: la
  componente vertical del empuje iguala al peso y la horizontal es m·g·tan(θ). Supuesto: vuelo a
  altura constante (como lo hacen los modos con control de altura de los fabricantes), sin contar
  la resistencia del aire (cota superior).
- Multirrotor, horizontal, con el tiempo de 0 a 100 km/h publicado t: la aceleración media es
  (100 km/h)/t, así que la máxima es al menos esa: entrada con solo `min`.
- Multirrotor, vertical: con la relación empuje/peso r publicada, a = g·(r − 1). Sin ella, solo
  una cota inferior: para inclinarse θ sin perder altura el empuje llega al menos a m·g/cos(θ),
  así que la aceleración vertical máxima es al menos g·(1/cos(θ) − 1). La entrada lleva solo
  `min`: el máximo queda sin saber.
- Ala fija, horizontal (en viraje coordinado a altura constante): con el factor de carga máximo
  n, a = g·√(n² − 1); con el ángulo de alabeo máximo φ, a = g·tan(φ); con el radio de viraje
  mínimo r y la velocidad V que la misma fuente da con él, a = V²/r.

Las entradas derivadas se escriben en `configuracion/catalogo_drones.json` con
`python -m proceso.deduccion.aceleraciones --escribir` y un test comprueba que coinciden con lo
que da el código: una cifra de partida que cambie obliga a volver a escribirlas.
"""

import argparse
import json
import math
from typing import Any

from proceso.deduccion.catalogo import CATALOGO, convertir

G = 9.80665
DECIMALES = 4
HORIZONTAL = "aceleracion_horizontal"
VERTICAL = "aceleracion_vertical"
DERIVADOS = (HORIZONTAL, VERTICAL)
MULTIRROTOR = frozenset({"multirrotor", "vtol"})

SUPUESTO_INCLINACION = (
    "vuelo a altura constante con el empuje inclinado el ángulo máximo; sin la resistencia del "
    "aire (cota superior de la aceleración horizontal)"
)
SUPUESTO_VERTICAL = (
    "para inclinarse θ sin perder altura el empuje llega al menos a m·g/cos(θ): cota inferior "
    "de la aceleración vertical máxima; el máximo no se sabe sin la relación empuje/peso"
)
SUPUESTO_VIRAJE = "viraje coordinado a altura constante"
SUPUESTO_MANUAL = (
    "el ángulo publicado es el de un modo con límite de actitud; en el modo manual no hay "
    "límite publicado: cota inferior de la aceleración horizontal máxima"
)
MODO_MANUAL = "Modo: M"
SUPUESTO_MEDIA = (
    "aceleración media de 0 a 100 km/h: la máxima es al menos esa (cota inferior; el máximo no "
    "se sabe)"
)

Dato = dict[str, Any]


def _valores(dato: Dato, destino: str) -> list[tuple[str, float]]:
    """(clave, valor convertido) de una entrada numérica: valor, o min y max."""
    if "texto" in dato:
        return []
    claves = ("valor",) if "valor" in dato else tuple(k for k in ("min", "max") if k in dato)
    return [(k, convertir(float(dato[k]), dato["unidad"], destino)) for k in claves]


def _partida(campo: str, dato: Dato, clave: str) -> Dato:
    return {
        "campo": campo,
        "fuente": dato["fuente"],
        "valor": dato[clave],
        "unidad": dato["unidad"],
    }


def _entrada(valores: dict[str, float], dato: Dato, formula: str, supuesto: str,
             partida: list[Dato]) -> Dato:  # fmt: skip
    entrada: Dato = {"fuente": dato["fuente"], "unidad": "m/s2"}
    for clave, valor in valores.items():
        entrada[clave] = round(valor, DECIMALES)
    if "cita" in dato:
        entrada["cita"] = dato["cita"]
    entrada["derivada"] = {"formula": formula, "supuesto": supuesto, "datos": partida}
    return entrada


def _con_modo_manual(entradas: list[Dato]) -> bool:
    """Alguna entrada es del modo manual (la nota «Modo: M» o «modo manual» en la cita)."""
    return any(
        MODO_MANUAL in str(d.get("nota", "")) or "manual" in str(d.get("cita", "")).lower()
        for d in entradas
    )


def derivar(modelo: Dato) -> dict[str, list[Dato]]:
    """Las entradas derivadas de un modelo, por campo (vacío si no hay cifras de partida)."""
    campos = modelo.get("campos", {})
    resultado: dict[str, list[Dato]] = {HORIZONTAL: [], VERTICAL: []}

    def datos(campo: str) -> list[Dato]:
        return [d for d in campos.get(campo, {}).get("datos", []) if "texto" not in d]

    if modelo["tipo_aeronave"] in MULTIRROTOR:
        empuje = datos("relacion_empuje_peso")
        # Con un modo manual (sin límite de actitud) cuyo ángulo la ficha no da, el ángulo
        # publicado es el de otro modo: g·tan(θ) solo es una cota inferior de la máxima.
        manual = _con_modo_manual(datos("velocidad_maxima")) and not _con_modo_manual(
            datos("angulo_inclinacion")
        )
        for dato in datos("angulo_inclinacion"):
            for clave, theta in _valores(dato, "°"):
                if not 0 < theta < 90:
                    continue
                partida = [_partida("angulo_inclinacion", dato, clave)]
                a = G * math.tan(math.radians(theta))
                resultado[HORIZONTAL].append(
                    _entrada(
                        {"min": a} if manual else {"valor": a},
                        dato,
                        "a ≥ g·tan(θ)" if manual else "a = g·tan(θ)",
                        SUPUESTO_MANUAL if manual else SUPUESTO_INCLINACION,
                        partida,
                    )
                )
                if not empuje:
                    resultado[VERTICAL].append(
                        _entrada(
                            {"min": G * (1 / math.cos(math.radians(theta)) - 1)},
                            dato,
                            "a ≥ g·(1/cos(θ) − 1)",
                            SUPUESTO_VERTICAL,
                            partida,
                        )
                    )
        for dato in datos("tiempo_0_100"):
            for clave, segundos in _valores(dato, "s"):
                if segundos > 0:
                    resultado[HORIZONTAL].append(
                        _entrada(
                            {"min": (100 / 3.6) / segundos},
                            dato,
                            "a ≥ Δv/Δt = (100 km/h)/t",
                            SUPUESTO_MEDIA,
                            [_partida("tiempo_0_100", dato, clave)],
                        )
                    )
        for dato in empuje:
            for clave, r in _valores(dato, "n"):
                if r > 1:
                    resultado[VERTICAL].append(
                        _entrada(
                            {"valor": G * (r - 1)},
                            dato,
                            "a = g·(r − 1)",
                            "empuje máximo de los motores en vertical",
                            [_partida("relacion_empuje_peso", dato, clave)],
                        )
                    )
    elif modelo["tipo_aeronave"] == "ala_fija":
        for dato in datos("factor_carga"):
            for clave, n in _valores(dato, "n"):
                if n > 1:
                    resultado[HORIZONTAL].append(
                        _entrada(
                            {"valor": G * math.sqrt(n * n - 1)},
                            dato,
                            "a = g·√(n² − 1)",
                            SUPUESTO_VIRAJE,
                            [_partida("factor_carga", dato, clave)],
                        )
                    )
        for dato in datos("angulo_alabeo"):
            for clave, phi in _valores(dato, "°"):
                if 0 < phi < 90:
                    resultado[HORIZONTAL].append(
                        _entrada(
                            {"valor": G * math.tan(math.radians(phi))},
                            dato,
                            "a = g·tan(φ)",
                            SUPUESTO_VIRAJE,
                            [_partida("angulo_alabeo", dato, clave)],
                        )
                    )
        velocidades = datos("velocidad_crucero") + datos("velocidad_maxima")
        for dato in datos("radio_viraje"):
            pareja = [v for v in velocidades if v["fuente"] == dato["fuente"] and "valor" in v]
            for clave, radio in _valores(dato, "m"):
                for velocidad in pareja[:1]:
                    v = convertir(float(velocidad["valor"]), velocidad["unidad"], "m/s")
                    if radio > 0:
                        campo_v = (
                            "velocidad_crucero"
                            if velocidad in datos("velocidad_crucero")
                            else "velocidad_maxima"
                        )
                        resultado[HORIZONTAL].append(
                            _entrada(
                                {"valor": v * v / radio},
                                dato,
                                "a = V²/r",
                                SUPUESTO_VIRAJE,
                                [
                                    _partida("radio_viraje", dato, clave),
                                    _partida(campo_v, velocidad, "valor"),
                                ],
                            )
                        )
    return resultado


def con_derivadas(catalogo: Dato) -> Dato:
    """El catálogo con las entradas derivadas recalculadas (las publicadas se conservan)."""
    nuevo: Dato = json.loads(json.dumps(catalogo))
    for modelo in nuevo["modelos"]:
        if "campos" not in modelo:
            continue
        derivadas = derivar(modelo)
        for campo in DERIVADOS:
            actual = modelo["campos"].setdefault(campo, {"datos": [], "sin_fuente": True})
            publicadas = [d for d in actual["datos"] if "derivada" not in d]
            actual["datos"] = publicadas + derivadas[campo]
            actual["sin_fuente"] = not actual["datos"]
    return nuevo


def escribir() -> None:
    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    with open(CATALOGO, "w", encoding="utf-8", newline="\n") as fichero:
        fichero.write(json.dumps(con_derivadas(catalogo), ensure_ascii=False, indent=1) + "\n")


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--escribir", action="store_true", help="reescribe el catálogo")
    args = opciones.parse_args(argumentos)
    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    if args.escribir:
        escribir()
        return 0
    return 0 if con_derivadas(catalogo) == catalogo else 1


if __name__ == "__main__":
    raise SystemExit(principal())
