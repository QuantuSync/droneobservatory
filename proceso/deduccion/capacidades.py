"""Cotas físicas de cada clase sacadas del catálogo: lo más que puede recorrer, durar, correr o
aguantar de viento cualquiera de sus modelos.

Para descartar hace falta una cota superior de toda la clase: si a un modelo le falta el dato,
la clase no tiene cota y la regla que la necesita queda indeterminada. Algunas cotas se pueden
deducir de otras (marcadas `deducida`): el alcance en aire en calma no pasa de la autonomía por
la velocidad máxima, y el tiempo de vuelo de un ala fija no pasa de su alcance entre su
velocidad de crucero más baja (no puede volar más despacio sin perder sustentación).

Una cota que sale solo de fuentes de prioridad baja (`debil`) no sirve para descartar.
"""

from collections.abc import Callable
from dataclasses import dataclass

from proceso.deduccion.catalogo import Catalogo, Modelo

MIN_POR_H = 60.0


@dataclass(frozen=True)
class Cota:
    valor: float | None
    deducida: bool = False
    debil: bool = False
    # Modelos sin dato: los que dejan la clase sin cota.
    sin_dato: tuple[str, ...] = ()

    @property
    def sirve(self) -> bool:
        """Se puede usar para descartar: la tienen todos los modelos de la clase, de fuentes que
        no son débiles."""
        return self.valor is not None and not self.debil and not self.sin_dato

    def documento(self) -> dict[str, object]:
        resultado: dict[str, object] = {
            "valor": None if self.valor is None else round(self.valor, 3)
        }
        if self.deducida:
            resultado["deducida"] = True
        if self.debil:
            resultado["debil"] = True
        if self.sin_dato:
            resultado["sin_dato"] = list(self.sin_dato)
        return resultado


SIN_COTA = Cota(None)


def _maximo(modelo: Modelo, campo: str) -> Cota:
    v = modelo.valor(campo)
    return Cota(v.maximo, debil=v.debil) if v.maximo is not None else SIN_COTA


def _minimo(modelo: Modelo, campo: str) -> Cota:
    v = modelo.valor(campo)
    return Cota(v.minimo, debil=v.debil) if v.minimo is not None else SIN_COTA


def alcance_aire_km(modelo: Modelo) -> Cota:
    """Lo más que recorre en aire en calma en un sentido."""
    publicado = _maximo(modelo, "alcance")
    if publicado.valor is not None:
        return publicado
    autonomia = _maximo(modelo, "autonomia")
    velocidad = velocidad_max_ms(modelo)
    if autonomia.valor is not None and velocidad.valor is not None:
        km = autonomia.valor * 60.0 * velocidad.valor / 1000.0
        return Cota(km, deducida=True, debil=autonomia.debil or velocidad.debil)
    return SIN_COTA


def velocidad_max_ms(modelo: Modelo) -> Cota:
    return _maximo(modelo, "velocidad_maxima")


def tiempo_max_min(modelo: Modelo) -> Cota:
    """Lo más que puede estar en el aire."""
    autonomia = _maximo(modelo, "autonomia")
    if autonomia.valor is not None:
        return autonomia
    if modelo.tipo_aeronave in {"ala_fija", "reaccion"}:
        alcance = _maximo(modelo, "alcance")
        crucero = _minimo(modelo, "velocidad_crucero")
        if alcance.valor is not None and crucero.valor:
            minutos = alcance.valor * 1000.0 / crucero.valor / 60.0
            return Cota(minutos, deducida=True, debil=alcance.debil or crucero.debil)
    return SIN_COTA


def viento_max_ms(modelo: Modelo) -> Cota:
    return _maximo(modelo, "viento_maximo")


def crucero_max_ms(modelo: Modelo) -> Cota:
    """La velocidad propia con que un ala fija puede avanzar contra el viento: la de crucero más
    alta o, sin ella, la máxima."""
    crucero = _maximo(modelo, "velocidad_crucero")
    if crucero.valor is not None:
        return crucero
    maxima = velocidad_max_ms(modelo)
    return Cota(maxima.valor, deducida=True, debil=maxima.debil) if maxima.valor else SIN_COTA


def enlace_max_km(modelo: Modelo) -> Cota:
    return _maximo(modelo, "enlace_alcance")


def de_clase(catalogo: Catalogo, clase: str, cota: Callable[[Modelo], "Cota"]) -> "Cota":
    """El máximo de las cotas de los modelos de la clase con dato fiable (no débil). Los demás
    van en `sin_dato`: con alguno ahí, la cota sirve para decir que la clase puede (un modelo
    conocido puede), pero no para descartarla (otro modelo, sin dato, quizá sí)."""
    valores: list[float] = []
    sin_dato: list[str] = []
    deducida = False
    for modelo in catalogo.modelos_de(clase):
        c = cota(modelo)
        if c.valor is None or c.debil:
            sin_dato.append(modelo.id)
            continue
        valores.append(c.valor)
        deducida |= c.deducida
    if not valores:
        return Cota(None, sin_dato=tuple(sin_dato))
    return Cota(max(valores), deducida=deducida, sin_dato=tuple(sin_dato))


def minimo_de_clase(catalogo: Catalogo, clase: str, campo: str) -> Cota:
    """El mínimo de los mínimos de un campo (por ejemplo, la temperatura más baja de trabajo)."""
    valores: list[float] = []
    sin_dato: list[str] = []
    for modelo in catalogo.modelos_de(clase):
        v = modelo.valor(campo)
        if v.minimo is None or v.debil:
            sin_dato.append(modelo.id)
            continue
        valores.append(v.minimo)
    if not valores:
        return Cota(None, sin_dato=tuple(sin_dato))
    return Cota(min(valores), sin_dato=tuple(sin_dato))


def maximo_de_clase(catalogo: Catalogo, clase: str, campo: str) -> Cota:
    return de_clase(catalogo, clase, lambda m: _maximo(m, campo))


def suelo_km(viento_ms: float) -> Callable[[Modelo], Cota]:
    """Alcance en el suelo de un modelo con un viento a favor: en aire en calma más el viento
    por su tiempo máximo de vuelo. Sin viento (o en contra), el de aire en calma."""

    def cota(modelo: Modelo) -> Cota:
        aire = alcance_aire_km(modelo)
        if aire.valor is None or viento_ms <= 0:
            return aire
        tiempo = tiempo_max_min(modelo)
        if tiempo.valor is None:
            return SIN_COTA
        return Cota(
            aire.valor + viento_ms * tiempo.valor * 60.0 / 1000.0,
            deducida=True,
            debil=aire.debil or tiempo.debil,
        )

    return cota


def temperatura_ok(modelo: Modelo, frio: float, calor: float, margen: float) -> bool | None:
    """Si el modelo trabaja a esa temperatura con el margen; None sin los dos extremos."""
    v = modelo.valor("temperatura")
    if v.minimo is None or v.maximo is None or v.debil:
        return None
    return calor >= v.minimo - margen and frio <= v.maximo + margen
