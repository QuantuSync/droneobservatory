"""Comprobación del periodo (inicio y fin) de cada parte y marca de los partes de resumen.

Cada parte cubre una noche, un día o un tramo, y su periodo decide a qué noche pertenece
(proceso/ataques.jornada). En la recogida horaria, sobre todos los ataques guardados, se
corrigen los periodos que el parte escribe mal o que el lector leía mal, y se marcan los partes
de resumen, que nunca se suman con los diarios. Cada cambio es una versión nueva con su motivo:

- **Año equivocado**: «У ніч на 5 січня 2023 року» publicado el 5 de enero de 2024 empezaba un
  año antes de acabar. Un inicio más de 300 días anterior a la publicación lleva el año de la
  publicación.
- **Tarde del día escrito**: «Увечері 11 лютого», «У вечірній час 10 лютого»: el ataque empieza
  esa tarde (18:00 de Kiev, aproximada), no a medianoche de ese día.
- **Noche publicada tarde**: un parte de «у ніч на N» o «вночі N» con el fin aproximado (la hora
  de publicación) más de 12 horas después de la mañana de N acaba a las 09:00 de Kiev de N.
- **Resumen**: un parte de una semana o desde el inicio («за тиждень», «за неделю», «итоги
  недели», «з початку», «с начала») o que cubre más de dos días lleva `resumen` y no se suma
  (como `incluido_en`). Los resúmenes diarios y semanales del Ministerio de Defensa ruso
  («Главное за день», «Итоги недели», «Сводка») ya no se guardan como parte
  (recogida/mindef.py).
"""

import copy
import re
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from esquema import Documento

if TYPE_CHECKING:
    from almacen.base import Almacen

KYIV = ZoneInfo("Europe/Kyiv")
RESUMEN = "resumen"
MESES_UK = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6, "липня": 7,
    "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}  # fmt: skip
_MES = "(" + "|".join(MESES_UK) + ")"
TARDE = re.compile(r"(?:увечері|ввечері|у\s+вечірній\s+час)\s+(\d{1,2})\s+" + _MES, re.I)
NOCHE = re.compile(r"(?:у\s+ніч\s+на|вночі)\s+(\d{1,2})\s+" + _MES, re.I)
TEXTO_RESUMEN = re.compile(
    r"за\s+(?:минулий\s+|цей\s+)?тиждень|за\s+(?:прошедшую\s+)?неделю|итоги\s+недели|"
    r"з\s+початку\s+(?:року|місяця|тижня|повномасштабн)|с\s+начала\s+(?:года|месяца|недели|СВО)",
    re.IGNORECASE,
)
MAX_PERIODO = timedelta(days=2)
NOCHE_TARDIA = timedelta(hours=12)
MOTIVO_PERIODO = "periodo del parte corregido (proceso/periodos.py): {}"
MOTIVO_RESUMEN = "parte de resumen: no se suma con los diarios (proceso/periodos.py)"


def _leer(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(UTC)


def _instante(momento: datetime, precision: str) -> Documento:
    return {"valor": momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": precision}


def _dia(frase_match: re.Match[str], referencia: datetime) -> date | None:
    try:
        mes = MESES_UK[frase_match.group(2).lower()]
        dia = date(referencia.year, mes, int(frase_match.group(1)))
    except ValueError:
        return None
    if (dia - referencia.date()).days > 1:
        dia = dia.replace(year=dia.year - 1)
    return dia


def corregido(ataque: Documento) -> tuple[Documento, list[str]]:
    """El ataque con el periodo corregido y la marca de resumen, y los motivos."""
    nuevo = copy.deepcopy(ataque)
    motivos: list[str] = []
    periodo = nuevo["periodo"]
    inicio, fin = _leer(periodo["inicio"]["valor"]), _leer(periodo["fin"]["valor"])
    frase = " ".join(f.get("frase_origen", "") for f in ataque["fuentes"][:1])
    publicado = min(_leer(f["fecha"]["valor"]) for f in ataque["fuentes"])
    if (publicado - inicio).days > 300:
        try:
            propuesto = inicio.replace(year=publicado.year)
        except ValueError:
            propuesto = inicio
        if propuesto <= fin and fin - propuesto <= MAX_PERIODO:
            inicio = propuesto
            periodo["inicio"] = _instante(inicio, periodo["inicio"]["precision"])
            motivos.append("año del inicio equivocado en el parte")
    if ataque["sentido"] == "RU_UA":
        tarde = TARDE.search(frase)
        if tarde and periodo["inicio"]["precision"] == "dia":
            dia = _dia(tarde, publicado)
            if dia is not None:
                propuesto = datetime.combine(dia, datetime.min.time(), KYIV) + timedelta(hours=18)
                if propuesto < fin:
                    inicio = propuesto.astimezone(UTC)
                    periodo["inicio"] = _instante(inicio, "aproximada")
                    motivos.append("el ataque empieza la tarde del día que escribe el parte")
        noche = NOCHE.search(frase)
        if noche and periodo["fin"]["precision"] == "aproximada":
            dia = _dia(noche, publicado)
            if dia is not None:
                manana = (datetime.combine(dia, datetime.min.time(), KYIV)
                          + timedelta(hours=9)).astimezone(UTC)  # fmt: skip
                if fin - manana > NOCHE_TARDIA and manana > inicio:
                    fin = manana
                    periodo["fin"] = _instante(fin, "aproximada")
                    motivos.append("la noche acaba por la mañana, no cuando se publica el parte")
    textos = " ".join(f.get("frase_origen", "") for f in ataque["fuentes"])
    if TEXTO_RESUMEN.search(textos) or fin - inicio > MAX_PERIODO:
        nuevo[RESUMEN] = True
    else:
        nuevo.pop(RESUMEN, None)
    return nuevo, motivos


def revisar(almacen: "Almacen", ahora: datetime) -> dict[str, int]:
    """Aplica `corregido` a todos los ataques y guarda lo que cambia, con su motivo."""
    resumen = {"periodos": 0, "resumenes": 0}
    for ataque in almacen.ataques_ucrania():
        nuevo, motivos = corregido(ataque)
        if nuevo == ataque:
            continue
        almacen.guardar_ataque_ucrania(nuevo, ahora)
        if motivos:
            resumen["periodos"] += 1
            almacen.anotar_motivo(
                "ataques_ucrania", ataque["id"], {"periodo": ataque["periodo"]},
                {"periodo": nuevo["periodo"]}, MOTIVO_PERIODO.format("; ".join(motivos)),
            )  # fmt: skip
        if nuevo.get(RESUMEN) != ataque.get(RESUMEN):
            resumen["resumenes"] += 1
            almacen.anotar_motivo(
                "ataques_ucrania", ataque["id"], {RESUMEN: ataque.get(RESUMEN)},
                {RESUMEN: nuevo.get(RESUMEN)}, MOTIVO_RESUMEN,
            )  # fmt: skip
    return resumen
