"""Aviso de segunda noche: tras una oleada grande sobre Ucrania, ¿la noche siguiente también?

Una noche es grande si los drones lanzados llegan al percentil 90 de las 60 noches anteriores
con parte (el tamaño de los ataques ha cambiado mucho desde 2022: lo grande se mide contra lo
reciente). Tras una noche grande, la probabilidad de que la siguiente lo sea es la proporción
con que eso pasó antes (solo con noches anteriores). Se compara con la frecuencia de siempre de
las noches grandes, en las noches que siguen a una grande (las únicas en que sale el aviso).
Se publica si mejora a la referencia en un 5 % de Brier y la mejora se sostiene al remuestrear
semanas.
"""

from datetime import date, timedelta

from esquema import Documento
from proceso.prevision import metodos
from proceso.prevision.datos import Datos

VERSION = "segunda-noche-1.0.0"
VENTANA = 60
PERCENTIL = 0.9
NOCHES_MINIMAS = 20
COMPROBAR_DESDE = date(2024, 1, 1)
MEJORA_MINIMA = 0.05
GRANDES_MINIMAS = 30


def grandes(datos: Datos) -> dict[date, bool]:
    """Si cada noche con parte fue grande respecto de las 60 anteriores."""
    fechas = sorted(datos.noches)
    resultado: dict[date, bool] = {}
    for k, fecha in enumerate(fechas):
        previas = [
            datos.noches[f].lanzados
            for f in fechas[max(0, k - VENTANA) : k]
            if f >= fecha - timedelta(days=VENTANA)
        ]
        if len(previas) < NOCHES_MINIMAS:
            continue
        umbral = sorted(previas)[int(PERCENTIL * len(previas))]
        resultado[fecha] = (
            datos.noches[fecha].lanzados >= umbral and datos.noches[fecha].lanzados > 0
        )
    return resultado


def calcular(datos: Datos, conocida_hasta: date) -> Documento:
    grande = grandes(datos)
    fechas = sorted(grande)
    p, referencia, y, bloques = [], [], [], []
    for fecha in fechas:
        siguiente = fecha + timedelta(days=1)
        if fecha < COMPROBAR_DESDE or siguiente > conocida_hasta or not grande[fecha]:
            continue
        previas = [f for f in fechas if f < fecha - timedelta(days=1)]
        tras = [grande.get(f + timedelta(days=1), False) for f in previas if grande[f]]
        if len(tras) < GRANDES_MINIMAS:
            continue
        p.append((sum(tras) + 1) / (len(tras) + 2))
        referencia.append(sum(grande[f] for f in previas) / len(previas))
        y.append(int(grande.get(siguiente, False)))
        bloques.append(fecha.isocalendar()[0] * 100 + fecha.isocalendar()[1])
    relativa, mejora = metodos.mejora_brier(p, referencia, y, bloques) if p else (0.0, None)
    publicable = bool(p) and relativa >= MEJORA_MINIMA and mejora is not None and mejora.sostenida
    todas = [grande[f] for f in fechas]
    tras_todas = [grande.get(f + timedelta(days=1), False) for f in fechas if grande[f]]
    comprobacion = {
        "noches_grandes": len(p),
        "siguiente_grande": sum(y),
        "proporcion_tras_grande": round(sum(tras_todas) / max(1, len(tras_todas)), 3),
        "proporcion_de_siempre": round(sum(todas) / max(1, len(todas)), 3),
        "mejora_sobre_frecuencia": round(relativa, 3),
        "mejora_cota": None if mejora is None else round(mejora.cota, 5),
        "publicable": publicable,
    }
    ultima = fechas[-1] if fechas else None
    documento: Documento = {"comprobacion": comprobacion}
    if publicable and ultima is not None and grande[ultima]:
        probabilidad = (sum(tras_todas) + 1) / (len(tras_todas) + 2)
        documento["aviso"] = {
            "tras_noche": ultima.isoformat(),
            "lanzados": round(datos.noches[ultima].lanzados),
            "probabilidad": round(probabilidad, 3),
            "de_cada_10": max(0, min(10, round(probabilidad * 10))),
        }
    return documento
