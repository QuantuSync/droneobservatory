"""Lectura de METAR y regla de exclusión meteorológica de las interrupciones.

De cada METAR: viento (dirección, velocidad y racha en nudos), visibilidad en metros
(CAVOK y 9999 son 10 km o más), techo de nubes (la primera capa BKN u OVC, o la visibilidad
vertical VV, en pies), fenómenos (FG, TS, SN...) y estado de pista contaminada (grupos
R..//.. de depósito y SNOCLO).

**El tiempo explica una interrupción** si en algún METAR de su ventana (de una hora antes a
su fin) hay:

- niebla o visibilidad por debajo de 550 m, o techo por debajo de 200 pies (los mínimos de
  una aproximación de precisión de categoría I);
- tormenta (TS) o granizo (GR, GS);
- nieve (SN, SG), lluvia o llovizna engelante (FZRA, FZDZ) o hielo granulado (PL);
- viento medio de 35 nudos o más, o rachas de 45 nudos o más;
- pista contaminada: SNOCLO o un grupo de estado de pista con depósito de nieve, nieve
  fundente, hielo o escarcha (cifras de depósito 3 a 9).

Entonces la interrupción no es anomalía: queda con el motivo meteorológico.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime

VISIBILIDAD_MINIMA_M = 550
TECHO_MINIMO_FT = 200
VIENTO_MAXIMO_KT = 35
RACHA_MAXIMA_KT = 45
FENOMENOS_EXCLUYENTES = ("TS", "GR", "GS", "SN", "SG", "FZRA", "FZDZ", "PL", "FG")

_VIENTO = re.compile(r"^(?P<dir>\d{3}|VRB)(?P<vel>\d{2,3})(?:G(?P<racha>\d{2,3}))?(?P<u>KT|MPS)$")
_VISIBILIDAD = re.compile(r"^(?P<v>\d{4})(?:NDV)?$")
_MILLAS = re.compile(r"^(?P<e>\d+)?(?:(?P<n>\d)/(?P<d>\d))?SM$")
_NUBES = re.compile(r"^(?P<c>FEW|SCT|BKN|OVC|VV)(?P<h>\d{3}|///)")
_FENOMENO = re.compile(
    r"^(?:\+|-|VC)?(?:MI|BC|PR|DR|BL|SH|TS|FZ)?(?:DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS)*$"
)
_PISTA_ESTADO = re.compile(
    r"^R\d{2}[LCR]?/(?P<dep>[0-9/])[0-9/]{5}$|^\d{2}(?P<dep2>[0-9/])[0-9/]{5}$"
)
NUDOS_POR_MPS = 1.943844


@dataclass
class Metar:
    hora: datetime
    texto: str
    viento_dir: int | None = None
    viento_kt: float | None = None
    racha_kt: float | None = None
    visibilidad_m: int | None = None
    techo_ft: int | None = None
    fenomenos: list[str] = field(default_factory=list)
    pista_contaminada: bool = False


def leer(hora: datetime, texto: str) -> Metar:
    m = Metar(hora, texto)
    partes = texto.split()
    # Las tendencias (BECMG, TEMPO, NOSIG) y los comentarios (RMK) no son observación.
    for corte in ("BECMG", "TEMPO", "NOSIG", "RMK", "TREND"):
        if corte in partes:
            partes = partes[: partes.index(corte)]
    for p in partes[2:]:
        if (v := _VIENTO.match(p)) is not None:
            factor = NUDOS_POR_MPS if v["u"] == "MPS" else 1.0
            m.viento_dir = None if v["dir"] == "VRB" else int(v["dir"])
            m.viento_kt = round(int(v["vel"]) * factor, 1)
            m.racha_kt = round(int(v["racha"]) * factor, 1) if v["racha"] else None
        elif p == "CAVOK":
            m.visibilidad_m = 10000
        elif (v := _VISIBILIDAD.match(p)) is not None and m.visibilidad_m is None:
            m.visibilidad_m = int(v["v"])
        elif (v := _MILLAS.match(p)) is not None and m.visibilidad_m is None and (v["e"] or v["n"]):
            millas = int(v["e"] or 0) + (int(v["n"]) / int(v["d"]) if v["n"] else 0.0)
            m.visibilidad_m = round(millas * 1609.344)
        elif (v := _NUBES.match(p)) is not None:
            if v["c"] in ("BKN", "OVC", "VV") and v["h"] != "///" and m.techo_ft is None:
                m.techo_ft = int(v["h"]) * 100
        elif p == "SNOCLO" or p.endswith("/SNOCLO"):
            m.pista_contaminada = True
        elif (v := _PISTA_ESTADO.match(p)) is not None:
            deposito = v["dep"] or v["dep2"]
            if deposito and deposito.isdigit() and 3 <= int(deposito) <= 9:
                m.pista_contaminada = True
        elif (
            len(p) >= 2 and _FENOMENO.match(p) and not p.isdigit() and p not in ("M", "AUTO", "COR")
        ):
            m.fenomenos.append(p)
    return m


def motivos(m: Metar) -> list[str]:
    """Por qué este METAR explica una interrupción (vacío si no la explica)."""
    resultado = []
    fenomenos = " ".join(m.fenomenos)
    if (
        "FG" in fenomenos
        and "BCFG" not in fenomenos
        and "MIFG" not in fenomenos
        and "VCFG" not in fenomenos
    ):
        resultado.append("niebla")
    if m.visibilidad_m is not None and m.visibilidad_m < VISIBILIDAD_MINIMA_M:
        resultado.append("visibilidad")
    if m.techo_ft is not None and m.techo_ft < TECHO_MINIMO_FT:
        resultado.append("techo")
    if "TS" in fenomenos and "VCTS" not in fenomenos:
        resultado.append("tormenta")
    if any(f in fenomenos for f in ("GR", "GS")):
        resultado.append("granizo")
    if any(f in fenomenos for f in ("SN", "SG", "FZRA", "FZDZ", "PL")):
        resultado.append("nieve_o_engelamiento")
    if (m.viento_kt or 0) >= VIENTO_MAXIMO_KT or (m.racha_kt or 0) >= RACHA_MAXIMA_KT:
        resultado.append("viento")
    if m.pista_contaminada:
        resultado.append("pista_contaminada")
    return sorted(set(resultado))


def explica(metares: list[Metar], inicio: datetime, fin: datetime) -> list[str]:
    """Motivos meteorológicos de los METAR entre `inicio` y `fin` (vacío si ninguno)."""
    encontrados: set[str] = set()
    for m in metares:
        if inicio <= m.hora <= fin:
            encontrados.update(motivos(m))
    return sorted(encontrados)
