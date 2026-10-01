"""Impactos con lugar de la capa de guerra: alta, enlace con el ataque, fuentes y credibilidad.

Un impacto es un lugar concreto (localidad o instalación del nomenclátor) alcanzado en un
ataque. Varios mensajes sobre el mismo lugar y el mismo ataque son el mismo impacto, con
una fuente por mensaje.

**Enlace con el ataque** (ataques de la capa de Ucrania del mismo sentido; no se usan los
tramos incluidos en un total ni los solapados):

1. si el mensaje declara la noche («у ніч на 22 серпня», «в ночь на 5 октября»), el ataque
   que contiene las 02:00 locales de ese día;
2. si nombra un día anterior a su publicación («вночі 29 вересня», «26 сентября»), con noche
   el ataque que contiene las 02:00 de ese día y sin ella el único ataque que se solapa con
   ese día (si hay más de uno, ninguno);
3. si habla de la noche sin fecha («вночі», «ночью») y se publica antes de las 18:00 locales,
   el ataque que contiene las 02:00 de ese día;
4. si no, el ataque cuyo periodo contiene la publicación o, si acaba de terminar, el último
   que terminó como mucho 6 horas antes.

Lo que no encaja queda sin ataque y se vuelve a intentar durante 4 días: el parte del
ataque puede publicarse después que el mensaje de la administración regional.

**Credibilidad** (regla general, proceso/credibilidad.py): los mensajes de un mismo canal no
son independientes entre sí. Administraciones militares regionales de Ucrania: fiabilidad B,
origen oficial. Estado Mayor ucraniano, gobernadores rusos y autoridades instaladas por
Rusia: fiabilidad C, origen parte (reivindicación de parte). Sube con otra fuente
independiente o con un dato medido: el foco térmico de FIRMS detectado en el lugar cuenta
como una fuente A independiente (medida física), y la confirmación cruzada (una fuente de
cada lado de la guerra sobre el mismo lugar y el mismo ataque) da como mínimo «probable»
(2). Trato simétrico: la reivindicación ucraniana confirmada por el gobernador ruso sube
igual que la rusa confirmada por la administración ucraniana.
"""

import bisect
import copy
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import cache
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from esquema import Documento
from proceso.credibilidad import Credibilidad, Declaracion, Fiabilidad, Postura, credibilidad
from proceso.mensajes_guerra import VERSION, ImpactoLeido, MensajeLeido

if TYPE_CHECKING:
    from almacen.base import Almacen
    from recogida.canales_guerra import Canal

ZONAS = {"RU_UA": ZoneInfo("Europe/Kyiv"), "UA_RU": ZoneInfo("Europe/Moscow")}
HORA_NOCHE = time(2, 0)
# Una publicación de la tarde o la noche que dice «вночі» habla de la noche que empieza.
HORA_TARDE = 18
TRAS_PERIODO = timedelta(hours=6)
# Un impacto sin ataque se vuelve a intentar enlazar mientras no tenga más de 4 días.
REENLAZAR = timedelta(days=4)
# Un impacto sin ataque es el mismo que otro del mismo lugar sin ataque a menos de 12 horas.
MISMO_IMPACTO = timedelta(hours=12)
DIA_SIGUIENTE = timedelta(hours=24)
FIRMS = "firms"


def _leer(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(UTC)


def instante(momento: datetime, precision: str = "minuto") -> Documento:
    return {"valor": momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": precision}


# --- Enlace con el ataque ----------------------------------------------------------------


@dataclass(frozen=True)
class Periodo:
    id: str
    inicio: datetime
    fin: datetime


class Ataques:
    """Ataques de un sentido ordenados por inicio, para buscar el que contiene un instante."""

    def __init__(self, ataques: list[Documento]) -> None:
        self.por_sentido: dict[str, list[Periodo]] = {}
        for ataque in ataques:
            if "incluido_en" in ataque or "solapado_con" in ataque:
                continue
            periodo = ataque["periodo"]
            self.por_sentido.setdefault(ataque["sentido"], []).append(
                Periodo(
                    ataque["id"], _leer(periodo["inicio"]["valor"]), _leer(periodo["fin"]["valor"])
                )
            )
        self.inicios: dict[str, list[datetime]] = {}
        for sentido, lista in self.por_sentido.items():
            lista.sort(key=lambda p: (p.inicio, p.id))
            self.inicios[sentido] = [p.inicio for p in lista]

    def _cerca(self, sentido: str, momento: datetime) -> list[Periodo]:
        lista = self.por_sentido.get(sentido, [])
        hasta = bisect.bisect_right(self.inicios.get(sentido, []), momento)
        desde = bisect.bisect_left(self.inicios.get(sentido, []), momento - timedelta(days=3))
        return lista[desde:hasta]

    def que_contiene(self, sentido: str, momento: datetime) -> Periodo | None:
        dentro = [p for p in self._cerca(sentido, momento) if p.inicio <= momento <= p.fin]
        # Si hay varios (un total y otro sin tramos), el más largo.
        return max(dentro, key=lambda p: (p.fin - p.inicio, p.id)) if dentro else None

    def acabado(self, sentido: str, momento: datetime) -> Periodo | None:
        antes = [
            p for p in self._cerca(sentido, momento) if p.fin <= momento <= p.fin + TRAS_PERIODO
        ]
        return max(antes, key=lambda p: (p.fin, p.id)) if antes else None

    def del_dia(self, sentido: str, dia: date) -> list[Periodo]:
        zona = ZONAS[sentido]
        inicio = datetime.combine(dia, time(0, 0), tzinfo=zona).astimezone(UTC)
        fin = inicio + timedelta(days=1)
        return [p for p in self._cerca(sentido, fin) if p.inicio < fin and p.fin > inicio]


def _dos_de_la_noche(dia: date, sentido: str) -> datetime:
    return datetime.combine(dia, HORA_NOCHE, tzinfo=ZONAS[sentido]).astimezone(UTC)


def enlazar(
    ataques: Ataques, sentido: str, publicado: datetime, leido: MensajeLeido
) -> tuple[str | None, str | None]:
    """(id del ataque, cómo se enlazó), o (None, None) si ninguno encaja."""
    if leido.noche is not None:
        periodo = ataques.que_contiene(sentido, _dos_de_la_noche(leido.noche, sentido))
        return (periodo.id, "noche_declarada") if periodo else (None, None)
    if leido.parte_diario:
        # Las 24 horas anteriores: un día y una noche, ningún ataque concreto.
        return None, None
    if leido.dia is not None:
        if leido.es_noche:
            periodo = ataques.que_contiene(sentido, _dos_de_la_noche(leido.dia, sentido))
            return (periodo.id, "dia_declarado") if periodo else (None, None)
        del_dia = ataques.del_dia(sentido, leido.dia)
        return (del_dia[0].id, "dia_declarado") if len(del_dia) == 1 else (None, None)
    local = publicado.astimezone(ZONAS[sentido])
    if leido.es_noche and local.hour < HORA_TARDE:
        periodo = ataques.que_contiene(sentido, _dos_de_la_noche(local.date(), sentido))
        if periodo:
            return periodo.id, "noche_mencionada"
    periodo = ataques.que_contiene(sentido, publicado)
    if periodo:
        return periodo.id, "periodo"
    periodo = ataques.acabado(sentido, publicado)
    return (periodo.id, "tras_periodo") if periodo else (None, None)


# --- Fuentes y credibilidad -----------------------------------------------------------------


@cache
def _canales() -> dict[str, "Canal"]:
    from recogida.canales_guerra import cargar_canales

    return {c.canal.lower(): c for c in cargar_canales()}


def canal_de_fuente(fuente: Documento) -> "Canal | None":
    """El canal de la configuración del que sale la fuente («https://t.me/<canal>/<n>»)."""
    partes = fuente["enlace"].split("/")
    return _canales().get(partes[3].lower()) if len(partes) > 4 else None


def credibilidad_impacto(fuentes: list[Documento], foco_detectado: bool) -> int:
    declaraciones = []
    lados = set()
    for fuente in fuentes:
        canal = canal_de_fuente(fuente)
        nota = canal.institucion if canal else fuente["id"]
        if canal:
            lados.add(canal.pais)
        declaraciones.append(
            Declaracion(nota, Fiabilidad(fuente["fiabilidad"]), False, Postura.RESPALDA)
        )
    if foco_detectado:
        declaraciones.append(Declaracion(FIRMS, Fiabilidad.A, False, Postura.RESPALDA))
    resultado = credibilidad(declaraciones)
    if {"UA", "RU"} <= lados:
        resultado = min(resultado, Credibilidad.PROBABLE)
    return int(resultado)


def es_reivindicacion(fuentes: list[Documento], foco_detectado: bool) -> bool:
    """Solo lo dicen partes en guerra, sin fuente oficial independiente ni dato medido, y sin
    confirmación del otro lado."""
    canales = [canal_de_fuente(f) for f in fuentes]
    if foco_detectado or any(c is None or c.origen != "parte" for c in canales):
        return False
    return len({c.pais for c in canales if c}) < 2


def fuente_de(
    canal: "Canal", publicacion_id: int, publicado: datetime, impacto: ImpactoLeido
) -> Documento:
    declaracion = Declaracion(
        canal.institucion, Fiabilidad(canal.fiabilidad), False, Postura.RESPALDA
    )
    campos = ["lugar", "impacto", "categorias_objetivo"]
    campos += [c for c in ("heridos", "fallecidos") if getattr(impacto, c) is not None]
    fuente: Documento = {
        "id": f"{canal.canal}-{publicacion_id}",
        "enlace": f"https://t.me/{canal.canal}/{publicacion_id}",
        "medio": canal.medio,
        "fecha": instante(publicado),
        "idioma": canal.idioma,
        "fiabilidad": canal.fiabilidad,
        "credibilidad": int(credibilidad([declaracion])),
        "frase_origen": impacto.frase,
        "replicas": 0,
        "campos_respaldados": campos,
        "es_autoridad": False,
        "interna_fuera_de_ucrania": False,
        "publica": True,
    }
    if canal.autoridad_ocupacion:
        fuente["autoridad_ocupacion"] = True
    return fuente


def _rango(n: int | None) -> Documento | None:
    return {"min": n, "max": n} if n is not None else None


# --- Alta y actualización -----------------------------------------------------------------


@dataclass
class Resumen:
    nuevos: int = 0
    actualizados: int = 0
    reenlazados: int = 0
    fusionados: int = 0


def _vigentes(almacen: "Almacen", lugar_id: str) -> list[Documento]:
    return [
        d for d in almacen.impactos_guerra_en(lugar_id)
        if "fusionado_en" not in d and "retirado" not in d
    ]  # fmt: skip


def _mismo(
    existentes: list[Documento], ataque: str | None, publicado: datetime
) -> Documento | None:
    """El impacto ya guardado del mismo lugar: el del mismo ataque; sin ataque, el del mismo
    lugar sin ataque a menos de 12 horas o, si no lo hay, el último del mismo lugar de las 24
    horas anteriores (el mensaje del día siguiente sobre el ataque de la noche)."""
    if ataque is not None:
        return next((d for d in existentes if d.get("ataque") == ataque), None)
    for documento in existentes:
        if (
            "ataque" not in documento
            and abs(_leer(documento["fecha"]["valor"]) - publicado) <= MISMO_IMPACTO
        ):  # fmt: skip
            return documento
    anteriores = [
        d for d in existentes
        if timedelta(0) <= publicado - _leer(d["fecha"]["valor"]) <= DIA_SIGUIENTE
    ]  # fmt: skip
    return max(anteriores, key=lambda d: d["fecha"]["valor"]) if anteriores else None


def _anadir_fuente(
    documento: Documento, fuente: Documento, lectura: Documento, impacto: ImpactoLeido,
    foco: bool,
) -> Documento:  # fmt: skip
    resultado = copy.deepcopy(documento)
    otras = [f for f in resultado["fuentes"] if f["id"] != fuente["id"]]
    resultado["fuentes"] = sorted([*otras, fuente], key=lambda f: (f["fecha"]["valor"], f["id"]))
    lecturas = [x for x in resultado.get("lecturas", []) if x["fuente_id"] != fuente["id"]]
    resultado["lecturas"] = sorted([*lecturas, lectura], key=lambda x: x["fuente_id"])
    cats = set(resultado.get("categorias_objetivo", [])) | set(impacto.categorias)
    resultado["categorias_objetivo"] = sorted(cats)
    if impacto.tipo == "impacto":
        resultado["impacto"] = "impacto"
    for campo in ("heridos", "fallecidos"):
        nuevo = getattr(impacto, campo)
        if nuevo is not None:
            anterior = resultado.get(campo)
            maximo = max(nuevo, anterior["max"]) if isinstance(anterior, dict) else nuevo
            resultado[campo] = _rango(maximo)
    resultado["fecha"] = min(resultado["fecha"], fuente["fecha"], key=lambda i: i["valor"])
    _recalcular(resultado, foco)
    return resultado


def _recalcular(documento: Documento, foco: bool) -> None:
    documento["credibilidad"] = credibilidad_impacto(documento["fuentes"], foco)
    if es_reivindicacion(documento["fuentes"], foco):
        documento["reivindicacion_de_parte"] = True
    else:
        documento.pop("reivindicacion_de_parte", None)


def incorporar(
    almacen: "Almacen",
    ataques: Ataques,
    canal: "Canal",
    publicacion_id: int,
    publicado: datetime,
    leido: MensajeLeido,
    ahora: datetime,
    metodo: str = "parser",
    confianza: float | None = None,
    version: str = VERSION,
) -> Resumen:
    """Da de alta o actualiza los impactos del mensaje."""
    resumen = Resumen()
    focos = almacen.focos_termicos()
    ataque, como = enlazar(ataques, canal.sentido, publicado, leido)
    for impacto in leido.impactos:
        fuente = fuente_de(canal, publicacion_id, publicado, impacto)
        lectura: Documento = {"fuente_id": fuente["id"], "metodo": metodo, "version": version}
        if confianza is not None:
            lectura["confianza"] = round(confianza, 3)
        existente = _mismo(_vigentes(almacen, impacto.lugar.id), ataque, publicado)
        if existente is not None:
            foco = focos.get(existente["id"], {}).get("resultado") == "detectado"
            documento = _anadir_fuente(existente, fuente, lectura, impacto, foco)
            if documento != existente:
                documento["control"]["ultima_actualizacion"] = instante(ahora)
                almacen.guardar_impacto_guerra(documento)
                resumen.actualizados += 1
            continue
        anio = publicado.astimezone(ZONAS[canal.sentido]).year
        documento = {
            "id": almacen.siguiente_id_impacto_guerra(anio),
            "tipo": "impacto_guerra",
            "sentido": canal.sentido,
            "region": impacto.lugar.region,
            "lugar": impacto.lugar.documento(),
            "impacto": impacto.tipo,
            "categorias_objetivo": sorted(set(impacto.categorias)),
            "fecha": instante(publicado),
            "credibilidad": 6,
            "fuentes": [fuente],
            "lecturas": [lectura],
            "control": {"alta": instante(ahora), "ultima_actualizacion": instante(ahora)},
        }
        if ataque is not None:
            documento["ataque"] = ataque
            documento["enlace_ataque"] = como
        if leido.dia is not None:
            documento["dia"] = leido.dia.isoformat()
        if leido.parte_diario:
            documento["parte_diario"] = True
        for campo in ("heridos", "fallecidos"):
            valor = _rango(getattr(impacto, campo))
            if valor is not None:
                documento[campo] = valor
        _recalcular(documento, False)
        almacen.guardar_impacto_guerra(documento)
        resumen.nuevos += 1
    return resumen


def reenlazar(almacen: "Almacen", ataques: Ataques, ahora: datetime) -> Resumen:
    """Enlaza los impactos recientes que aún no tienen ataque; si ya hay otro del mismo lugar
    en ese ataque, se une a él (queda con `fusionado_en`, nada se borra)."""
    resumen = Resumen()
    for documento in vigentes(almacen):
        if "ataque" in documento or documento.get("parte_diario"):
            continue
        publicado = _leer(documento["fecha"]["valor"])
        if ahora - publicado > REENLAZAR:
            continue
        leido = MensajeLeido(
            noche=None, es_noche=False,
            dia=date.fromisoformat(documento["dia"]) if "dia" in documento else None,
        )  # fmt: skip
        ataque, como = enlazar(ataques, documento["sentido"], publicado, leido)
        if ataque is None:
            continue
        destino = next(
            (d for d in _vigentes(almacen, documento["lugar"]["id"]) if d.get("ataque") == ataque),
            None,
        )
        if destino is not None:
            unido = copy.deepcopy(destino)
            for fuente in documento["fuentes"]:
                if fuente["id"] not in {f["id"] for f in unido["fuentes"]}:
                    unido["fuentes"].append(fuente)
            unido["fuentes"].sort(key=lambda f: (f["fecha"]["valor"], f["id"]))
            unido["lecturas"] = sorted(
                {x["fuente_id"]: x for x in [*unido.get("lecturas", []),
                                             *documento.get("lecturas", [])]}.values(),
                key=lambda x: x["fuente_id"],
            )  # fmt: skip
            unido["categorias_objetivo"] = sorted(
                set(unido.get("categorias_objetivo", []))
                | set(documento.get("categorias_objetivo", []))
            )
            _recalcular(unido, False)
            unido["control"]["ultima_actualizacion"] = instante(ahora)
            almacen.guardar_impacto_guerra(unido)
            absorbido = {**documento, "fusionado_en": unido["id"]}
            absorbido["control"] = {**documento["control"], "ultima_actualizacion": instante(ahora)}
            almacen.guardar_impacto_guerra(absorbido)
            resumen.fusionados += 1
            continue
        actualizado = {**documento, "ataque": ataque, "enlace_ataque": como}
        actualizado["control"] = {**documento["control"], "ultima_actualizacion": instante(ahora)}
        almacen.guardar_impacto_guerra(actualizado)
        resumen.reenlazados += 1
    return resumen


def aplicar_focos(almacen: "Almacen", ahora: datetime) -> int:
    """Recalcula la credibilidad con el foco térmico de FIRMS de cada impacto. Devuelve
    cuántos han cambiado."""
    focos = almacen.focos_termicos()
    cambiados = 0
    for documento in vigentes(almacen):
        nuevo = copy.deepcopy(documento)
        detectado = focos.get(documento["id"], {}).get("resultado") == "detectado"
        _recalcular(nuevo, detectado and con_firms(documento))
        if nuevo != documento:
            nuevo["control"]["ultima_actualizacion"] = instante(ahora)
            almacen.guardar_impacto_guerra(nuevo)
            cambiados += 1
    return cambiados


def vigentes(almacen: "Almacen") -> list[Documento]:
    return [d for d in almacen.impactos_guerra() if "fusionado_en" not in d and "retirado" not in d]


def con_firms(documento: Documento) -> bool:
    """Si el impacto se cruza con FIRMS. Los partes diarios no: sobre todo son ataques de
    corto alcance en la línea del frente, donde la artillería y los incendios dan focos todos
    los días, y el foco no diría nada del dron."""
    return not documento.get("parte_diario")


def periodo_del_impacto(
    documento: Documento, ataques: dict[str, Documento]
) -> tuple[datetime, datetime]:
    """Ventana del impacto para FIRMS: el periodo de su ataque; sin ataque, el día que nombra
    el mensaje o las 12 horas anteriores a su publicación."""
    ataque = ataques.get(documento.get("ataque", ""))
    if ataque is not None:
        return _leer(ataque["periodo"]["inicio"]["valor"]), _leer(ataque["periodo"]["fin"]["valor"])
    if "dia" in documento:
        inicio = datetime.combine(date.fromisoformat(documento["dia"]), time(0, 0), tzinfo=UTC)
        return inicio - timedelta(hours=3), inicio + timedelta(days=1)
    publicado = _leer(documento["fecha"]["valor"])
    return publicado - MISMO_IMPACTO, publicado


def resumen_por_sentido(documentos: list[Documento]) -> dict[str, Any]:
    cuentas: dict[str, dict[str, int]] = {}
    for d in documentos:
        fila = cuentas.setdefault(d["sentido"], {"impactos": 0, "con_ataque": 0, "instalacion": 0})
        fila["impactos"] += 1
        fila["con_ataque"] += "ataque" in d
        fila["instalacion"] += d["lugar"]["nivel"] == "instalacion"
    return cuentas
