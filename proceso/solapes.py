"""Partes que se solapan en el tiempo: qué tramo cuenta y cuál no se suma.

El Ministerio de Defensa ruso publica tramos del día y de la noche y, a veces,
un parte que resume un periodo que ya cubrían otros («За период с 20.00 мск 8
апреля по 06.00 мск 9 апреля ... 158», tras un tramo de 22.00 a 22.15 con 5).
Sumar todos contaría dos veces. La regla:

- Si un parte con periodo exacto cubre tramos publicados antes que él, sus
  cifras son el total: cuenta el total y los tramos quedan enlazados a él
  («incluido_en») sin sumarse. Solo es total si sus cifras no son menores que
  las de los tramos que cubre, en conjunto y región a región.
- Si no, dos tramos exactos que se solapan más de lo que da el redondeo de las
  horas no se suman los dos: cuenta el de más derribos y el otro queda enlazado
  a él («solapado_con»).
- El parte de toda la noche («В течение прошедшей ночи … 1110», publicado por la
  mañana) cubre la noche entera desde las 20.00 de Moscú, aunque no escriba las horas:
  desde 2026 el ministerio escribe ese mismo parte con ellas («В течение прошедшей ночи
  с 20.00 мск 3 октября до 8.00 мск 4 октября … 559»). Si sus cifras no son menores
  que las de los tramos de esa noche publicados antes, es su total y los tramos quedan
  «incluido_en». Antes se tomaba como contiguo al último tramo y se sumaban los dos.
- Cualquier otro periodo con inicio aproximado no prueba que cubra a nadie y siempre
  cuenta.

Los enlaces se recalculan con todos los ataques del sentido cada vez, así que
un parte nuevo puede cambiar un enlace; el cambio queda en el historial.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from almacen.base import Almacen
from esquema import Documento

INCLUIDO_EN = "incluido_en"
SOLAPADO_CON = "solapado_con"
# Solape que se tolera entre tramos contiguos: los partes redondean las horas de
# los extremos («до 4.05 21 мая» y «с 4.00 до 8.00»). Medido en la caché: los tramos
# consecutivos se pisan como mucho 10 minutos por redondeo; 15 dejan margen.
SOLAPE_TOLERADO = timedelta(minutes=15)
NOCHE_ENTERA = re.compile(
    r"в\s+течение\s+(?:прошедшей\s+)?ночи|за\s+(?:прошедшую\s+)?ночь|прошедшей\s+ночью",
    re.IGNORECASE,
)
EXACTA = "minuto"


@dataclass(frozen=True)
class Tramo:
    id: str
    inicio: datetime
    fin: datetime
    # Inicio declarado al minuto.
    exacto: bool
    # Un instante («около 23.00», «В 14.05 мск»): se sabe cuándo fue aunque sea aproximado.
    puntual: bool
    publicado: str
    derribados: int
    regiones: dict[str, int]
    # Parte de toda la noche sin horas escritas: cubre desde las 20.00 de Moscú.
    noche_entera: bool = False

    @property
    def localizable(self) -> bool:
        return self.exacto or self.puntual


def _momento(instante: Documento) -> datetime:
    return datetime.fromisoformat(instante["valor"].replace("Z", "+00:00"))


def tramo(ataque: Documento) -> Tramo | None:
    """El tramo de un ataque con cifra exacta de derribos, o None si no la tiene."""
    derribados = ataque.get("derribados")
    if not isinstance(derribados, dict) or derribados["min"] != derribados["max"]:
        return None
    periodo = ataque["periodo"]
    inicio, fin = _momento(periodo["inicio"]), _momento(periodo["fin"])
    return Tramo(
        id=ataque["id"],
        inicio=inicio,
        fin=fin,
        # Un fin aproximado es la hora de publicación de un parte que da solo el inicio
        # («В период с 20.00 мск 25.05»): cubre desde ese inicio hasta que se publica.
        exacto=periodo["inicio"]["precision"] == EXACTA
        and periodo["fin"]["precision"] in {EXACTA, "aproximada"},
        puntual=inicio == fin and periodo["inicio"]["precision"] in {EXACTA, "aproximada"},
        publicado=max(f["fecha"]["valor"] for f in ataque["fuentes"]),
        derribados=derribados["min"],
        noche_entera=periodo["inicio"]["precision"] == "aproximada"
        and fin > inicio
        and any(NOCHE_ENTERA.search(f.get("frase_origen", "")) for f in ataque["fuentes"]),
        regiones={
            r["region"]: r["derribados"]["min"]
            for r in ataque.get("regiones", [])
            if isinstance(r.get("derribados"), dict)
        },
    )


def _cubre(total: Tramo, tramo_: Tramo) -> bool:
    return (
        tramo_.id != total.id
        and tramo_.localizable
        and total.inicio <= tramo_.inicio
        and tramo_.fin <= total.fin
        and tramo_.fin - tramo_.inicio < total.fin - total.inicio
        and tramo_.publicado <= total.publicado
    )


def _es_total(total: Tramo, cubiertos: list[Tramo]) -> bool:
    """Las cifras del total no son menores que las de lo que cubre, ni región a región."""
    if sum(t.derribados for t in cubiertos) > total.derribados:
        return False
    if not total.regiones:
        return True
    por_region: dict[str, int] = {}
    for cubierto in cubiertos:
        for region, n in cubierto.regiones.items():
            por_region[region] = por_region.get(region, 0) + n
    return all(total.regiones.get(region, 0) >= n for region, n in por_region.items())


def enlaces(tramos: list[Tramo]) -> dict[str, tuple[str, str]]:
    """Para cada tramo que no se suma: (campo, id del tramo que cuenta en su lugar)."""
    resultado: dict[str, tuple[str, str]] = {}
    # Los totales más largos primero: un tramo cubierto por dos totales anidados va al mayor.
    for total in sorted(
        (t for t in tramos if (t.exacto or t.noche_entera) and t.fin > t.inicio),
        key=lambda t: (t.inicio - t.fin, t.id),
    ):
        if total.id in resultado:
            continue
        cubiertos = [t for t in tramos if _cubre(total, t) and t.id not in resultado]
        if cubiertos and _es_total(total, cubiertos):
            for cubierto in cubiertos:
                resultado[cubierto.id] = (INCLUIDO_EN, total.id)
    cuentan = sorted(
        (t for t in tramos if t.exacto and t.id not in resultado), key=lambda t: (t.inicio, t.id)
    )
    for i, uno in enumerate(cuentan):
        if uno.id in resultado:
            continue
        for otro in cuentan[i + 1 :]:
            if otro.inicio >= uno.fin:
                break
            if otro.id in resultado:
                continue
            if min(uno.fin, otro.fin) - max(uno.inicio, otro.inicio) <= SOLAPE_TOLERADO:
                continue
            # Cuenta el de más derribos; a igualdad, el publicado antes.
            gana, pierde = sorted((uno, otro), key=lambda t: (-t.derribados, t.publicado, t.id))
            resultado[pierde.id] = (SOLAPADO_CON, gana.id)
            if pierde is uno:
                break
    return resultado


def con_enlace(ataque: Documento, enlace: tuple[str, str] | None) -> Documento:
    documento = {k: v for k, v in ataque.items() if k not in {INCLUIDO_EN, SOLAPADO_CON}}
    if enlace is not None:
        documento[enlace[0]] = enlace[1]
    return documento


def enlazar(almacen: Almacen, sentido: str, ahora: datetime) -> int:
    """Recalcula los enlaces de los ataques del sentido. Devuelve cuántos cambian."""
    ataques = [a for a in almacen.ataques_ucrania() if a["sentido"] == sentido]
    tramos = [t for a in ataques if (t := tramo(a)) is not None]
    nuevos = enlaces(tramos)
    cambiados = 0
    for ataque in ataques:
        documento = con_enlace(ataque, nuevos.get(ataque["id"]))
        if documento != ataque:
            almacen.guardar_ataque_ucrania(documento, ahora)
            cambiados += 1
    return cambiados


def derribados_contados(ataques: list[Documento]) -> int:
    """Suma de derribos sin los tramos enlazados a otro."""
    return sum(
        a["derribados"]["min"]
        for a in ataques
        if isinstance(a.get("derribados"), dict)
        and INCLUIDO_EN not in a
        and SOLAPADO_CON not in a
        and "resumen" not in a
    )
