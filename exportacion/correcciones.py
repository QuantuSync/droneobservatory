"""Registro público de correcciones (correcciones.json), sacado de lo que la base ya guarda.

Entra en el registro cada cambio en un incidente que ya se había publicado, hecho al revisar su
contenido (a mano o con una regla de revisión aplicada a lo ya publicado) y guardado con su
motivo, que cambia lo que el observatorio decía de él: el titular, el estado, el lugar, la
atribución o la presencia del dron, su unión con otro incidente o su retirada. No entran los
datos nuevos (fuentes, citas, una autoridad que confirma o atribuye, las noticias que se unen a
su suceso al registrarlas) ni lo que la recogida recalcula cada hora (frontera o interior,
episodios, tipo de dron, mediciones). La web escribe este mismo criterio en la página del
registro (web/src/texto/correcciones.ts): si cambia aquí, cambia allí.

De dónde sale cada entrada:

- los cambios anotados con su motivo en el historial (tabla `incidentes_motivos`: las revisiones
  a mano de configuracion/incidentes_revisados.json y las reglas de revisión);
- las retiradas (`retirado`, con su fecha y su motivo) de los incidentes que siguen retirados;
- las uniones que siguen en pie (tabla `fusiones`): las revisadas a mano y las que juntaron dos
  incidentes que ya se habían publicado por separado.

«Ya publicado» quiere decir que el incidente estaba activo (ni retirado ni fundido) al terminar
una recogida anterior a la del cambio: la recogida empieza en el minuto 17 de cada hora y publica
al terminar. El motivo sale en los dos idiomas: el de la revisión a mano, de su configuración;
el de las reglas, de configuracion/correcciones.json. Un motivo que no está en ninguna de las dos
sale con una frase general y el original entre comillas, y queda un aviso en el diario.
"""

import json
import logging
import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from esquema import Documento

registro = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent.parent
RUTA = RAIZ / "configuracion" / "correcciones.json"
RUTA_REVISADOS = RAIZ / "configuracion" / "incidentes_revisados.json"
RUTA_ATRIBUCIONES = RAIZ / "configuracion" / "atribuciones_revisadas.json"
FICHERO = "correcciones.json"
VERSION = 1
TABLA_MOTIVOS = "incidentes_motivos"
PREFIJO_REVISADA = "revisión: "
MOTIVO_FUSION_AUTOMATICA = "mismo sitio y misma ventana"
# La recogida horaria empieza en este minuto (servidor/recogida.sh): dos cambios son de la misma
# recogida si caen en la misma hora contada desde aquí.
MINUTO_RECOGIDA = 17
CAMPOS_LUGAR = ("pais", "region", "localidad", "suceso", "punto", "nivel")
ORDEN_CAMPOS = ("titulo", "estado", "presencia_dron", "lugar", "atribucion", "union", "retirada")
# Un motivo de la validación de la ficha: «campo: problema» separados por «; ».
VALIDACION = re.compile(r"^[a-z_]+: [^;]+(?:; [a-z_]+: [^;]+)*$")


@cache
def configuracion(ruta: Path = RUTA) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


@cache
def _json(ruta: Path) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def _instante(fecha: str) -> datetime:
    """Una fecha del historial («…T…:…:…Z») o de un documento («…T…:…Z»)."""
    texto = fecha.rstrip("Z")
    formato = "%Y-%m-%dT%H:%M:%S" if texto.count(":") == 2 else "%Y-%m-%dT%H:%M"
    return datetime.strptime(texto, formato).replace(tzinfo=UTC)


def recogida_de(momento: datetime) -> datetime:
    """El comienzo de la recogida a la que pertenece un momento."""
    hora = momento.replace(minute=0, second=0, microsecond=0)
    return hora if momento.minute >= MINUTO_RECOGIDA else hora - timedelta(hours=1)


def publicado_antes(activas: Iterable[str], momento: datetime) -> bool:
    """Estaba activo al terminar una recogida anterior a la del cambio."""
    recogida = recogida_de(momento)
    return any(recogida_de(_instante(fecha)) < recogida for fecha in activas)


class Motivos:
    """El motivo de cada cambio en los dos idiomas, y si es una corrección."""

    def __init__(self) -> None:
        conf = configuracion()
        revisados = _json(RUTA_REVISADOS)
        atribuciones = _json(RUTA_ATRIBUCIONES)
        self.exactos: dict[str, dict[str, Any]] = {}
        for clave in ("retirar", "titulares"):
            for entrada in revisados.get(clave, []):
                self._exacto(entrada["motivo"], entrada)
        for entrada in revisados.get("ubicaciones", []):
            if "cambio" in entrada:
                self._exacto(entrada["cambio"]["motivo"], entrada)
        for entrada in revisados.get("unir", []):
            if "motivo_en" in entrada:
                motivo = {"es": entrada["motivo"], "en": entrada["motivo_en"]}
                self._exacto(motivo, entrada)
        for entrada in revisados.get("reextraer", []):
            if "motivo_en" in entrada:
                self._exacto({"es": entrada["motivo"], "en": entrada["motivo_en"]}, entrada)
        for motivo in atribuciones.get("motivos", {}).values():
            self._exacto(motivo, {})
        for motivo in atribuciones.get("por_regla", {}).values():
            self._exacto(motivo, {})
        self.reglas: list[dict[str, Any]] = list(conf["motivos"])
        self.nombres_en: dict[str, str] = dict(conf.get("nombres_en", {}))
        # Las uniones revisadas a mano, por cada registro del grupo: el motivo de la fusión que
        # guarda la base es el de cuando se hizo, y el texto de la configuración puede haberse
        # ampliado después.
        self.grupos: dict[str, dict[str, Any]] = {}
        for entrada in revisados.get("unir", []):
            if "motivo_en" in entrada:
                for id_ in entrada["registros"]:
                    self.grupos[id_] = {
                        "es": entrada["motivo"], "en": entrada["motivo_en"],
                        "aviso": bool(entrada.get("aviso")),
                    }  # fmt: skip
        self.avisos: list[dict[str, str]] = list(conf.get("a_raiz_de_un_aviso", []))
        self.sin_traducir: set[str] = set()

    def _exacto(self, motivo: dict[str, str], entrada: dict[str, Any]) -> None:
        self.exactos[motivo["es"]] = {
            "es": motivo["es"], "en": motivo["en"], "aviso": bool(entrada.get("aviso")),
        }  # fmt: skip

    def de(self, texto: str) -> tuple[dict[str, str], bool, bool] | None:
        """(motivo en los dos idiomas, a raíz de un aviso, revisado a mano), o None si el cambio
        no es una corrección (un dato nuevo)."""
        if texto in self.exactos:
            exacto = self.exactos[texto]
            return {"es": exacto["es"], "en": exacto["en"]}, exacto["aviso"], True
        for regla in self.reglas:
            casa = re.fullmatch(regla["patron"], texto, re.DOTALL)
            if casa is None:
                continue
            if not regla.get("corrige", True):
                return None
            grupos = {k: (v or "").strip() for k, v in casa.groupdict().items()}
            nombres = self.nombres_en
            motivo = {
                "es": regla["es"].format(**grupos),
                "en": regla["en"].format(**{k: nombres.get(v, v) for k, v in grupos.items()}),
            }
            return motivo, False, bool(regla.get("a_mano"))
        general = configuracion()["general"]
        clave = "validacion" if VALIDACION.match(texto) else "otro"
        if clave == "otro":
            self.sin_traducir.add(texto)
        motivo = {
            idioma: general[clave][idioma].replace("{resto}", texto) for idioma in ("es", "en")
        }
        return motivo, False, False


def _nombre_lugar(lugar: Documento | None) -> Documento | None:
    if not lugar:
        return None
    nombre = lugar.get("localidad") or lugar.get("region") or lugar.get("suceso")
    resultado: Documento = {"pais": lugar.get("pais")}
    if nombre:
        resultado["nombre"] = nombre
    return resultado


def _titulo(valor: Any) -> Documento | None:
    if isinstance(valor, dict) and "es" in valor and "en" in valor:
        return {"es": valor["es"], "en": valor["en"]}
    return None


def cambios_visibles(anterior: Documento, nuevo: Documento) -> list[Documento]:
    """Lo que cambia de lo que se ve: titular, estado, presencia, lugar y atribución."""
    cambios: list[Documento] = []
    if "titulo" in anterior and _titulo(anterior["titulo"]) != _titulo(nuevo.get("titulo")):
        cambios.append(
            {"campo": "titulo", "antes": _titulo(anterior["titulo"]),
             "despues": _titulo(nuevo.get("titulo"))}
        )  # fmt: skip
    if "estado" in anterior:
        antes = (anterior.get("estado") or {}).get("actual")
        despues = (nuevo.get("estado") or {}).get("actual")
        if antes != despues:
            cambios.append({"campo": "estado", "antes": antes, "despues": despues})
    if "presencia_dron" in anterior and anterior["presencia_dron"] != nuevo.get("presencia_dron"):
        cambios.append(
            {"campo": "presencia_dron", "antes": anterior["presencia_dron"],
             "despues": nuevo.get("presencia_dron")}
        )  # fmt: skip
    if "lugar" in anterior:
        antes_l, despues_l = anterior.get("lugar") or {}, nuevo.get("lugar") or {}
        if any(antes_l.get(c) != despues_l.get(c) for c in CAMPOS_LUGAR):
            cambios.append(
                {"campo": "lugar", "antes": _nombre_lugar(antes_l),
                 "despues": _nombre_lugar(despues_l)}
            )  # fmt: skip
    if "atribucion" in anterior and anterior["atribucion"] != nuevo.get("atribucion"):
        # Sin los valores: lo que se corrige de una atribución puede ser un nombre que no debía
        # publicarse (EODI-2026-00015).
        cambios.append({"campo": "atribucion", "retirada": not nuevo.get("atribucion")})
    return cambios


def _final(incidentes: dict[str, Documento], id_: str) -> str | None:
    """El incidente que se publica en lugar de este: él mismo, o aquel en que está fundido;
    None si está retirado."""
    vistos: set[str] = set()
    actual = incidentes.get(id_)
    while actual is not None and "fusionado_en" in actual and id_ not in vistos:
        vistos.add(id_)
        id_ = actual["fusionado_en"]
        actual = incidentes.get(id_)
    if actual is None or "retirado" in actual:
        return None
    return id_


def _entrada(
    fecha: str,
    id_: str,
    incidentes: dict[str, Documento],
    cambios: list[Documento],
    motivo: tuple[dict[str, str], bool, bool],
) -> Documento:
    documento = incidentes.get(id_, {})
    texto, aviso, a_mano = motivo
    entrada: Documento = {
        "fecha": _instante(fecha).strftime("%Y-%m-%dT%H:%MZ"),
        "incidente": id_,
        "enlace": _final(incidentes, id_),
        "cambios": sorted(cambios, key=lambda c: ORDEN_CAMPOS.index(c["campo"])),
        "motivo": texto,
        "revision": "a_mano" if a_mano else "regla",
    }
    titulo = _titulo(documento.get("titulo"))
    if titulo is not None:
        entrada["titulo"] = titulo
    if aviso:
        entrada["a_raiz_de_un_aviso"] = True
    return entrada


def construir(almacen: Almacen, ahora: datetime) -> Documento:
    """El registro, de la corrección más reciente a la más antigua."""
    motivos = Motivos()
    incidentes = {d["id"]: d for d in almacen.incidentes()}
    activas = almacen.versiones_activas()
    entradas: list[Documento] = []
    for fila in almacen.motivos_anotados(TABLA_MOTIVOS):
        id_ = fila["entidad_id"]
        anterior = {k: v for k, v in fila["anterior"].items() if k != "retirado"}
        cambios = cambios_visibles(anterior, fila["nuevo"])
        if not cambios or not publicado_antes(activas.get(id_, []), _instante(fila["fecha"])):
            continue
        motivo = motivos.de(str(fila["nuevo"].get("motivo", "")))
        if motivo is not None:
            entradas.append(_entrada(fila["fecha"], id_, incidentes, cambios, motivo))
    for id_, documento in incidentes.items():
        retirado = documento.get("retirado")
        if retirado is None:
            continue
        fecha = retirado["fecha"]["valor"]
        if not publicado_antes(activas.get(id_, []), _instante(fecha)):
            continue
        if "motivo_en" in retirado:
            motivo = (
                {"es": retirado["motivo"], "en": retirado["motivo_en"]},
                motivos.exactos.get(retirado["motivo"], {}).get("aviso", False),
                True,
            )
        else:
            de_regla = motivos.de(retirado["motivo"])
            if de_regla is None:
                continue
            motivo = de_regla
        entradas.append(_entrada(fecha, id_, incidentes, [{"campo": "retirada"}], motivo))
    for fusion in almacen.fusiones():
        if fusion["revertida"]:
            continue
        absorbido, destino = fusion["absorbido"], fusion["destino"]
        if incidentes.get(absorbido, {}).get("fusionado_en") != destino:
            continue
        if not publicado_antes(activas.get(absorbido, []), _instante(fusion["fecha"])):
            continue
        texto = fusion["motivo"]
        grupo = motivos.grupos.get(absorbido)
        encontrado: tuple[dict[str, str], bool, bool] | None
        if texto.startswith(PREFIJO_REVISADA) and grupo is not None:
            encontrado = ({"es": grupo["es"], "en": grupo["en"]}, grupo["aviso"], True)
        elif texto.startswith(PREFIJO_REVISADA):
            encontrado = motivos.de(texto[len(PREFIJO_REVISADA) :])
            if encontrado is not None:
                encontrado = (encontrado[0], encontrado[1], True)
        else:
            encontrado = motivos.de(texto)
        if encontrado is None:
            continue
        cambio = {"campo": "union", "destino": destino}
        entradas.append(_entrada(fusion["fecha"], absorbido, incidentes, [cambio], encontrado))
    if motivos.sin_traducir:
        registro.warning(
            "correcciones: %d motivos sin traducir en configuracion/correcciones.json: %s",
            len(motivos.sin_traducir), "; ".join(sorted(motivos.sin_traducir))[:600],
        )  # fmt: skip
    for entrada in entradas:
        if any(
            aviso["incidente"] == entrada["incidente"]
            and entrada["fecha"].startswith(aviso.get("dia", ""))
            for aviso in motivos.avisos
        ):
            entrada["a_raiz_de_un_aviso"] = True
    entradas.sort(key=lambda e: (e["fecha"], e["incidente"]), reverse=True)
    return {
        "version": VERSION,
        # La fecha de la última corrección, no la de la recogida: el fichero solo cambia (y la web
        # solo se reconstruye por él) cuando hay una corrección nueva.
        "actualizado": entradas[0]["fecha"] if entradas else None,
        "correcciones": entradas,
    }
