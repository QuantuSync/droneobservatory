"""Restricciones temporales de aeropuertos rusos que anuncia Rosaviatsia (canal «Говорит
Росавиация», t.me/favt_info), como serie interna.

Formatos que se leen (comprobados en el canal de 2025 y 2026):

- «Аэропорт КАЛУГА (Грабцево) ✈️ВВЕДЕНЫ временные ограничения на прием и выпуск воздушных
  судов» y «Аэропорт КАЛУГА (Грабцево) ✈️СНЯТЫ ограничения…», a veces con varios
  aeropuertos («Аэропорты — ПЕНЗА — САРАТОВ (Гагарин)»). El levantamiento suele responder al
  mensaje que la anunció.
- El de 2025: «…временные ограничения на их прием и выпуск с 04:45 МСК введены в аэропорту
  Калуга (Грабцево; код ИКАО: UUBC)» y «…сняты в аэропорту…». Si da la hora (de Moscú), es la
  del inicio o el fin; si no, la de la publicación.

Otros mensajes (vuelos «по согласованию», avisos generales) no se registran. Los mensajes no
dicen la causa: la serie se enlaza con el ataque UA_RU del mismo periodo, si lo hay, y no
crea incidentes de interrupción aeroportuaria.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from esquema import Documento
from proceso.lugares_guerra import Lugar, Nomenclator, normalizar

if TYPE_CHECKING:
    from almacen.base import Almacen
    from proceso.impactos_guerra import Ataques

MOSCU = ZoneInfo("Europe/Moscow")
CANAL = "favt_info"
# Un levantamiento sin respuesta empareja con la restricción abierta más reciente del mismo
# aeropuerto de las últimas 48 horas.
MAX_DURACION = timedelta(hours=48)

_INTRODUCIDA = re.compile(r"введен[аоы]?|ввели|вводятся|введении", re.IGNORECASE)
_LEVANTADA = re.compile(r"снят[аоы]?|сняли|отмен[её]н[аоы]?", re.IGNORECASE)
_RESTRICCION = re.compile(r"ограничени", re.IGNORECASE)
# «Принимает и отправляет рейсы по согласованию»: régimen de coordinación, no restricción.
_POR_ACUERDO = re.compile(r"по\s+согласованию", re.IGNORECASE)
_LISTA = re.compile(
    r"Аэропорт(?:ы)?\s*[—–-]?\s*(.+?)\s*(?:✈|ВВЕДЕН|СНЯТ|введен|снят|$)", re.IGNORECASE | re.DOTALL
)
_ANTIGUO = re.compile(r"в\s+аэропорт(?:у|ах)\s+(.+?)(?:\.|$)", re.IGNORECASE | re.DOTALL)
_OACI = re.compile(r"код\s+ИКАО:?\s*([A-Z]{4})")
_HORA = re.compile(r"с\s+(\d{1,2})[:.](\d{2})\s*МСК", re.IGNORECASE)


@dataclass(frozen=True)
class Anuncio:
    accion: str  # inicio o fin
    aeropuertos: tuple[str, ...]
    oaci: tuple[str, ...]
    hora: datetime


def _nombres(lista: str) -> tuple[str, ...]:
    """«— ПЕНЗА — САРАТОВ (Гагарин)» → («ПЕНЗА», «САРАТОВ (Гагарин)»)."""
    limpio = re.sub(r"[^\w()\s,—–-]", " ", lista)
    partes = re.split(r"\s*[—–,]\s*|\s+и\s+", limpio)
    nombres = []
    for parte in partes:
        parte = " ".join(parte.split()).strip("-– ")
        parte = re.sub(r";\s*код.*$", "", parte)
        if len(parte) >= 3 and not re.fullmatch(r"[\d\s]+", parte):
            nombres.append(parte)
    return tuple(nombres)


def leer(texto: str, publicado: datetime) -> Anuncio | None:
    """El anuncio de Rosaviatsia, o None si el mensaje no introduce ni levanta restricciones."""
    if not _RESTRICCION.search(texto) or _POR_ACUERDO.search(texto):
        return None
    introducida, levantada = _INTRODUCIDA.search(texto), _LEVANTADA.search(texto)
    if bool(introducida) == bool(levantada):
        return None
    accion = "inicio" if introducida else "fin"
    m = _LISTA.search(texto)
    nombres: tuple[str, ...] = _nombres(m.group(1)) if m else ()
    if not nombres:
        antiguo = _ANTIGUO.search(texto)
        nombres = (
            _nombres(re.sub(r"\(([^;)]*);[^)]*\)", r"(\1)", antiguo.group(1))) if antiguo else ()
        )
    if not nombres:
        return None
    hora = publicado
    reloj = _HORA.search(texto)
    if reloj:
        local = publicado.astimezone(MOSCU)
        candidata = datetime.combine(local.date(), time(int(reloj[1]) % 24, int(reloj[2])), MOSCU)
        # La hora es de antes de publicar: si sale después, es del día anterior.
        if candidata > local + timedelta(minutes=5):
            candidata -= timedelta(days=1)
        hora = candidata.astimezone(UTC)
    return Anuncio(accion, nombres, tuple(_OACI.findall(texto)), hora)


def aeropuerto(nombre: str, nomenclator: Nomenclator) -> Lugar | None:
    """El aeródromo ruso del nomenclátor que casa con «КАЛУГА (Грабцево)»: el nombre entre
    paréntesis o el de la ciudad en el nombre del aeródromo; uno solo."""
    entre = re.search(r"\(([^)]+)\)", nombre)
    ciudad = normalizar(re.sub(r"\(.*\)", "", nombre))
    candidatos = [
        i
        for i in nomenclator.instalaciones.values()
        if i.categoria == "aerodromo" and i.pais == "RU"
    ]
    for clave in ([normalizar(entre.group(1))] if entre else []) + [ciudad]:
        raiz = clave[:6]
        if len(raiz) < 4:
            continue
        hallados = [
            c for c in candidatos
            if any(raiz in n for n in nomenclator.nombres_instalacion.get(c.id, []))
        ]  # fmt: skip
        con_oaci = [c for c in hallados if c.oaci]
        if len(con_oaci) == 1:
            return con_oaci[0]
        if len(hallados) == 1:
            return hallados[0]
    return None


def _instante(momento: datetime) -> Documento:
    return {"valor": momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"}


def _leer_instante(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(UTC)


def incorporar(
    almacen: "Almacen",
    nomenclator: Nomenclator,
    ataques: "Ataques",
    publicacion_id: int,
    publicado: datetime,
    responde_a: int | None,
    anuncio: Anuncio,
) -> int:
    """Guarda la restricción (inicio) o le pone fin. Devuelve cuántas ha cambiado."""
    enlace = f"https://t.me/{CANAL}/{publicacion_id}"
    cambiadas = 0
    existentes = almacen.restricciones()
    for k, nombre in enumerate(anuncio.aeropuertos):
        if anuncio.accion == "inicio":
            id_ = f"{CANAL}-{publicacion_id}" + (
                f"/{k + 1}" if len(anuncio.aeropuertos) > 1 else ""
            )
            previo = next((r for r in existentes if r["id"] == id_), None)
            documento: Documento = dict(previo) if previo else {}
            datos_aeropuerto: Documento = {"nombre": nombre}
            lugar = aeropuerto(nombre, nomenclator)
            oaci = anuncio.oaci[k] if k < len(anuncio.oaci) else (lugar.oaci if lugar else None)
            if oaci:
                datos_aeropuerto["oaci"] = oaci
            if lugar is not None:
                datos_aeropuerto["lugar_id"] = lugar.id
                datos_aeropuerto["region"] = lugar.region
                datos_aeropuerto["punto"] = {"lat": lugar.lat, "lon": lugar.lon}
            documento.update(
                id=id_, aeropuerto=datos_aeropuerto, inicio=_instante(anuncio.hora),
                fuente_inicio=enlace,
            )  # fmt: skip
            periodo = ataques.que_contiene("UA_RU", anuncio.hora)
            if periodo is not None:
                documento["ataque"] = periodo.id
            if documento != previo:
                almacen.guardar_restriccion(documento)
                cambiadas += 1
            existentes = almacen.restricciones()
            continue
        abiertas = [
            r for r in existentes
            if normalizar(r["aeropuerto"]["nombre"]) == normalizar(nombre)
            and _leer_instante(r["inicio"]["valor"]) <= anuncio.hora
            and anuncio.hora - _leer_instante(r["inicio"]["valor"]) <= MAX_DURACION
            and (r.get("fuente_fin") in (None, enlace))
        ]  # fmt: skip
        por_respuesta = [
            r for r in abiertas
            if responde_a is not None and r["fuente_inicio"] == f"https://t.me/{CANAL}/{responde_a}"
        ]  # fmt: skip
        elegida = por_respuesta[0] if por_respuesta else (
            max(abiertas, key=lambda r: r["inicio"]["valor"]) if abiertas else None
        )  # fmt: skip
        if elegida is None:
            continue
        cerrada = {
            **elegida, "fin": _instante(anuncio.hora), "fuente_fin": enlace,
            "emparejado": "respuesta" if por_respuesta else "siguiente",
            "horas": round((anuncio.hora - _leer_instante(elegida["inicio"]["valor"]))
                           .total_seconds() / 3600, 2),
        }  # fmt: skip
        if cerrada != elegida:
            almacen.guardar_restriccion(cerrada)
            cambiadas += 1
            existentes = almacen.restricciones()
    return cambiadas


def por_ataque(restricciones: list[Documento]) -> dict[str, Documento]:
    """Por ataque UA_RU: aeropuertos restringidos y horas de restricción sumadas (de las que
    tienen fin)."""
    resultado: dict[str, Documento] = {}
    for r in restricciones:
        if "ataque" not in r:
            continue
        fila = resultado.setdefault(r["ataque"], {"aeropuertos": set(), "horas": 0.0})
        fila["aeropuertos"].add(r["aeropuerto"].get("oaci") or r["aeropuerto"]["nombre"])
        fila["horas"] += r.get("horas", 0.0)
    return {
        a: {"aeropuertos": len(f["aeropuertos"]), "horas": round(f["horas"], 2)}
        for a, f in resultado.items()
    }


def dia(momento: datetime) -> date:
    return momento.astimezone(MOSCU).date()
