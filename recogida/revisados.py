"""Correcciones revisadas a mano de incidentes concretos (configuracion/incidentes_revisados.json).

- **Unir**: registros del mismo suceso que las reglas de fusión no juntan, porque las noticias
  que vuelven sobre él semanas después quedan fechadas por su publicación. Se funden en el que
  elige la regla de siempre (`proceso/incidentes.destino_de`), con la fusión anotada y su motivo;
  `incidentes.revisar_fusiones` no las deshace. Si el que queda tiene un inicio posterior a su
  primera noticia, toma el de un registro unido con la fecha escrita por una fuente; si no sabe
  el cierre, toma el del registro que lo sabe.
- **Volver a extraer**: un incidente cuya ficha mezcló dos sucesos. Su candidato se extrae otra
  vez, una sola vez (cursor `revisados:<incidente>`), con una llamada directa dentro del tope de
  la revisión. Si la ficha nueva vuelve a dar el lugar o la fecha del otro suceso, el incidente
  se retira con el motivo.
"""

import copy
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from proceso import atribucion, declaraciones, extraccion, incidentes, titulares
from proceso.credibilidad import Credibilidad
from proceso.estados import RETIRADAS, Estado
from proceso.fronteras import dentro_del_pais
from proceso.presencia import TABLA_MOTIVOS

registro = logging.getLogger(__name__)
RUTA = Path(__file__).resolve().parent.parent / "configuracion" / "incidentes_revisados.json"
CURSOR = "revisados:"


@cache
def cargar(ruta: Path = RUTA) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def _vivo(almacen: Almacen, id_: str) -> Documento | None:
    """El registro, o aquel en que está fundido."""
    vistos = set()
    documento = almacen.incidente(id_)
    while documento is not None and "fusionado_en" in documento and id_ not in vistos:
        vistos.add(id_)
        id_ = documento["fusionado_en"]
        documento = almacen.incidente(id_)
    if documento is None or "retirado" in documento:
        return None
    return documento


def _primera_noticia(documento: Documento) -> str:
    return min(str(f["fecha"]["valor"]) for f in documento["fuentes"])


def _sin_cierre(documento: Documento) -> bool:
    return documento.get("consecuencias", {}).get("cierre", {}).get("valor") in (
        None,
        "desconocido",
    )


def completar(destino: Documento, unidos: list[Documento]) -> Documento:
    """El inicio y el cierre que le faltan al que queda y saben los registros unidos."""
    resultado = copy.deepcopy(destino)
    primera = _primera_noticia(resultado)
    if resultado["tiempo"]["inicio"]["valor"] > primera:
        escritos = sorted(
            (u for u in unidos
             if incidentes.fecha_verificada(u) and u["tiempo"]["inicio"]["valor"] <= primera),
            key=lambda u: (u["tiempo"]["inicio"]["valor"], u["id"]),
        )  # fmt: skip
        if escritos:
            resultado["tiempo"] = copy.deepcopy(escritos[0]["tiempo"])
    if _sin_cierre(resultado):
        con_cierre = [u for u in unidos if not _sin_cierre(u)]
        if con_cierre:
            resultado.setdefault("consecuencias", {})["cierre"] = copy.deepcopy(
                con_cierre[0]["consecuencias"]["cierre"]
            )
    return resultado


def unir(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> int:
    """Funde cada grupo revisado en uno. Devuelve cuántos registros funde."""
    hechas = 0
    for grupo in cargar()["unir"]:
        vivos: dict[str, Documento] = {}
        for id_ in grupo["registros"]:
            documento = _vivo(almacen, id_)
            if documento is not None:
                vivos[documento["id"]] = documento
        if len(vivos) < 2:
            continue
        publicados = frozenset(vivos)
        destino = next(iter(vivos.values()))
        for otro in list(vivos.values())[1:]:
            destino = incidentes.destino_de(destino, otro, publicados)[0]
        unidos = [d for d in vivos.values() if d["id"] != destino["id"]]
        nuevo = destino
        fundidos = []
        for absorbido in unidos:
            nuevo, aportadas = incidentes.absorber(nuevo, absorbido, ahora)
            fundido = {**copy.deepcopy(absorbido), "fusionado_en": destino["id"]}
            fundido.pop("episodio", None)
            fundidos.append((fundido, aportadas))
        nuevo = completar(nuevo, unidos)
        almacen.guardar_incidente(nuevo, ahora, modelos)
        for fundido, aportadas in fundidos:
            almacen.guardar_incidente(fundido, ahora, modelos)
            almacen.registrar_fusion(
                ahora.strftime("%Y-%m-%dT%H:%MZ"), fundido["id"], destino["id"],
                incidentes.PREFIJO_REVISADA + grupo["motivo"], aportadas,
            )  # fmt: skip
            hechas += 1
    return hechas


def _mezcla(documento: Documento, revision: Documento) -> bool:
    """La ficha nueva vuelve a dar el lugar o la fecha del otro suceso."""
    lugar = json.dumps(documento.get("lugar", {}), ensure_ascii=False)
    return revision["no_lugar"].lower() in lugar.lower() or (
        documento["tiempo"]["inicio"]["valor"][:10] < revision["no_antes_de"]
    )


def _extraer(almacen: Almacen, cliente: Any, candidato: Documento, ahora: datetime) -> int:
    """Una llamada directa para el candidato, con la hora de la ejecución (la misma con que se
    valida lo publicado) y dentro del tope de la revisión. Devuelve cuántas llamadas hace."""
    from modelo import coste
    from recogida.descarga import Descargador
    from recogida.extractor import modelos_base, preparar_todas

    peticiones = preparar_todas(almacen, [candidato], Descargador)
    extraidas = extraccion.extraer(
        almacen, cliente, peticiones, ahora, coste.Modo.REVISION, modelos_base()
    )
    return len(extraidas.incidentes)


def reextraer(
    almacen: Almacen, cliente: Any, ahora: datetime, modelos: frozenset[str]
) -> list[str]:
    """Vuelve a extraer, una vez, el candidato de cada incidente revisado. Devuelve los
    incidentes hechos."""
    hechos = []
    candidatos = {c["id"]: c for c in almacen.candidatos()}
    for revision in cargar()["reextraer"]:
        clave = CURSOR + revision["incidente"]
        if almacen.cursor(clave) is not None or revision["candidato"] not in candidatos:
            continue
        llamadas = _extraer(almacen, cliente, candidatos[revision["candidato"]], ahora)
        if llamadas != 1:
            registro.warning("%s sin volver a extraer", revision["incidente"])
            continue
        id_ = extraccion.incidente_del_candidato(almacen, revision["candidato"])
        documento = almacen.incidente(id_) if id_ else None
        if documento is not None and incidentes.activo(documento) and _mezcla(documento, revision):
            extraccion.retirar(
                almacen, documento["id"],
                f"{revision['motivo']}; la ficha vuelta a extraer sigue mezclándolos",
                ahora, modelos,
            )  # fmt: skip
        almacen.guardar_cursor(clave, {"fecha": ahora.strftime("%Y-%m-%dT%H:%MZ"), "llamadas": 1})
        hechos.append(revision["incidente"])
    return hechos


# --- Revisión del contenido (docs/informe_revision_contenido.md) ---------------------------
#
# - Retirar: un registro que no es un suceso (una estadística, una nota de opinión, un «hace
#   hoy ocho años»). Queda retirado con su motivo en español y en inglés; nada se borra.
# - Citas: la frase literal de la fuente que respalda el titular y no se guardó. Entra como
#   fuente del incidente (revisada a mano, con la fecha y el sitio donde se comprobó). Si es la
#   palabra de una autoridad, entra como declaración (citada por un medio, o leída en su página)
#   y pasa por las reglas de siempre (proceso/declaraciones.aplicar_fuentes): confirma solo si
#   la regla lo sostiene.
# - Titulares: el titular que dice solo lo que dicen las citas, con su motivo; y, si la
#   autoridad lo deja abierto o no lo da por hecho, la presencia del dron y el estado que
#   corresponden, cada cambio con su cita y su motivo.
# - Ubicaciones: el lugar del suceso que da una autoridad (su frase), con su punto, su radio y
#   los demás lugares que nombra.
#
# Todo se aplica en cada recogida horaria y es idempotente: lo que ya está no se vuelve a
# guardar. Cada cambio queda como versión nueva del incidente y con su motivo en el historial.

PREFIJO_REVISADA = "revisada-"
# Como las fuentes de las declaraciones citadas que encuentra el extractor
# (exportacion/procedencia.py la reconoce por esta marca).
MARCA_CITADA = "-declaracion-1"
MOTIVO_CITA = "cita revisada a mano (configuracion/incidentes_revisados.json, citas)"
MOTIVO_UBICACION = "lugar del suceso según la autoridad (configuracion/incidentes_revisados.json)"


@dataclass
class Corregidos:
    retirados: list[str] = field(default_factory=list)
    citas: list[str] = field(default_factory=list)
    titulares: list[str] = field(default_factory=list)
    ubicados: list[str] = field(default_factory=list)
    sin_guardar: list[str] = field(default_factory=list)

    def texto(self) -> str:
        return (
            f"retirados {len(self.retirados)}, con citas {len(self.citas)}, titulares "
            f"{len(self.titulares)}, ubicados {len(self.ubicados)}, sin guardar "
            f"{self.sin_guardar}"
        )


def _instante(ahora: datetime) -> Documento:
    return {"valor": ahora.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"}


def _fecha(valor: str) -> Documento:
    """«2025-09-30» o un instante completo, como instante del esquema."""
    if len(valor) == 10:
        return {"valor": f"{valor}T00:00Z", "precision": "dia"}
    return {"valor": valor, "precision": "minuto"}


def fuente_de_cita(cita: Documento, incidente: Documento) -> Documento:
    """La fuente que lleva la frase revisada. La de una autoridad citada por un medio lleva la
    marca de las declaraciones citadas, como las que encuentra el extractor; la leída en la
    página de la autoridad es oficial."""
    clave = hashlib.sha256(f"{cita['enlace']}\n{cita['frase']}".encode()).hexdigest()[:16]
    declaracion: Documento = cita.get("declaracion") or {}
    oficial = bool(declaracion) and bool(cita.get("oficial"))
    citada = bool(declaracion) and not oficial
    misma: Documento = next((f for f in incidente["fuentes"] if f["enlace"] == cita["enlace"]), {})
    if oficial:
        medio, fiabilidad = declaracion["autoridad"], "A"
    elif citada:
        medio = f"{declaracion['autoridad']} (declaración oficial citada en {cita['medio']})"
        fiabilidad = declaraciones.FIABILIDAD
    else:
        medio, fiabilidad = cita["medio"], misma.get("fiabilidad", "C")
    fuente: Documento = {
        "id": PREFIJO_REVISADA + clave + (MARCA_CITADA if citada else ""),
        "enlace": cita["enlace"],
        "medio": medio,
        "fecha": _fecha(cita["fecha"]),
        "idioma": cita["idioma"],
        "fiabilidad": fiabilidad,
        "credibilidad": (
            int(Credibilidad.CONFIRMADO) if declaracion else int(misma.get("credibilidad", 3))
        ),
        "frase_origen": cita["frase"],
        "replicas": 0,
        "campos_respaldados": ["estado", "presencia_dron"] if declaracion else [],
        "es_autoridad": bool(declaracion),
        "interna_fuera_de_ucrania": False,
        "publica": True,
    }
    if oficial:
        # La frase se comprobó en la página de la autoridad, sin extractor.
        fuente["metodo"] = "parser"
    return fuente


def _declaracion(cita: Documento) -> dict[str, Any]:
    declaracion = cita["declaracion"]
    return {
        "autoridad": declaracion["autoridad"],
        "pais": declaracion["pais"],
        "categoria": declaracion["categoria"],
        "afirma": declaracion["afirma"],
        "cita_literal": True,
        "frase": cita["frase"],
    }


def _por_incidente(almacen: Almacen, entradas: list[Documento]) -> dict[str, list[Documento]]:
    resultado: dict[str, list[Documento]] = {}
    for entrada in entradas:
        documento = _vivo(almacen, entrada["incidente"])
        if documento is not None:
            resultado.setdefault(documento["id"], []).append(entrada)
    return resultado


def con_citas(incidente: Documento, citas: list[Documento]) -> Documento:
    """El incidente con las citas revisadas que aún no tiene."""
    tiene = {f["id"] for f in incidente["fuentes"]}
    simples, pares = [], []
    for cita in citas:
        fuente = fuente_de_cita(cita, incidente)
        if fuente["id"] in tiene:
            continue
        tiene.add(fuente["id"])
        if cita.get("declaracion"):
            pares.append((_declaracion(cita), fuente))
        else:
            simples.append(fuente)
    resultado = copy.deepcopy(incidente)
    resultado["fuentes"] = [*resultado["fuentes"], *simples]
    if pares:
        resultado = incidentes.aplicar_reglas(declaraciones.aplicar_fuentes(resultado, pares))
    return resultado


def con_titular(incidente: Documento, revision: Documento, instante: Documento) -> Documento:
    """El titular revisado y, si la revisión lo dice, la presencia y el estado con su cita."""
    resultado = copy.deepcopy(incidente)
    if "titulo" in revision:
        resultado["titulo"] = dict(revision["titulo"])
    fuentes = {f["frase_origen"]: f["id"] for f in resultado["fuentes"]}
    presencia = revision.get("presencia")
    if presencia and resultado.get("presencia_dron") != presencia["valor"]:
        fuente_id = fuentes.get(presencia["cita"])
        if fuente_id is not None:
            resultado["presencia_dron"] = presencia["valor"]
            afirmacion = {
                "campo": "presencia_dron",
                "valor": presencia["valor"],
                "fuente_id": fuente_id,
                "confianza_extraccion": 1.0,
            }
            resultado["afirmaciones"] = [
                a
                for a in resultado.get("afirmaciones", [])
                if not (a.get("campo") == "presencia_dron" and a.get("valor") == "confirmada")
            ] + [afirmacion]
    estado = revision.get("estado")
    if estado and resultado["estado"]["actual"] != estado["valor"]:
        fuente_id = fuentes.get(estado["cita"])
        destino = Estado(estado["valor"])
        if fuente_id is not None and (Estado(resultado["estado"]["actual"]), destino) in RETIRADAS:
            paso = {
                "estado": destino.value,
                "fecha": instante,
                "fuente_id": fuente_id,
                "motivo": estado["motivo"],
            }
            historial = [*resultado["estado"]["historial"], paso]
            resultado["estado"] = {"actual": destino.value, "historial": historial}
    lugar = revision.get("lugar")
    if lugar and "punto" not in resultado["lugar"]:
        # El lugar guardado no era el del suceso (Arna está en Noruega): sin punto, que solo
        # lo da una nota oficial (ubicaciones).
        nuevo = {k: v for k, v in resultado["lugar"].items() if k != "nuts2"}
        resultado["lugar"] = {**nuevo, **lugar}
    # Las mismas reglas de titular que el resto, para que la revisión horaria no lo cambie:
    # coherente con la presencia y sin nacionalidad ni autor si no está atribuido.
    resultado = titulares.ajustar_incidente(resultado)
    resultado["titulo"] = atribucion.titulo_segun_atribucion(resultado)
    return resultado


def con_lugar(incidente: Documento, revision: Documento) -> Documento | None:
    """El lugar que da la autoridad: punto, radio y los demás lugares que nombra. None si el
    incidente ya tiene punto o el punto no cae en su país."""
    lugar = revision["lugar"]
    if "punto" in incidente["lugar"] or not dentro_del_pais(
        incidente["lugar"]["pais"], float(lugar["lat"]), float(lugar["lon"])
    ):
        return None
    cita = revision["fuente"]
    resultado = con_citas(incidente, [cita])
    nuevo = copy.deepcopy(resultado["lugar"])
    nuevo["punto"] = {"lat": round(float(lugar["lat"]), 5), "lon": round(float(lugar["lon"]), 5)}
    nuevo["radio_km"] = float(lugar["radio_km"])
    nuevo["nivel"] = lugar["nivel"]
    nuevo["localidad"] = lugar["nombre"]
    if lugar.get("region"):
        nuevo["region"] = lugar["region"]
    nuevo["geocodificacion"] = "oficial"
    nuevo["fuente_punto"] = fuente_de_cita(cita, incidente)["id"]
    otros = []
    for otro in revision.get("otros_lugares", []):
        entrada: Documento = {"nombre": otro["nombre"]}
        if "lat" in otro:
            entrada["punto"] = {
                "lat": round(float(otro["lat"]), 5),
                "lon": round(float(otro["lon"]), 5),
            }
        otros.append(entrada)
    if otros:
        nuevo["otros_lugares"] = otros
    resultado["lugar"] = nuevo
    return resultado


def _guardar(
    almacen: Almacen,
    antes: Documento,
    despues: Documento,
    ahora: datetime,
    modelos: frozenset[str],
    motivo: str,
    hechos: Corregidos,
) -> bool:
    control = {**despues["control"], "ultima_actualizacion": _instante(ahora)}
    despues = {**despues, "control": control}
    try:
        almacen.guardar_incidente(despues, ahora, modelos)
    except DocumentoInvalido as error:
        registro.warning("revisión sin guardar en %s: %s", antes["id"], str(error)[:300])
        hechos.sin_guardar.append(antes["id"])
        return False
    campos = ("estado", "presencia_dron", "titulo", "lugar", "fuentes", "retirado")
    cambios = {c: antes.get(c) for c in campos if antes.get(c) != despues.get(c)}
    if cambios:
        nuevos = {c: despues.get(c) for c in cambios}
        almacen.anotar_motivo(TABLA_MOTIVOS, antes["id"], cambios, nuevos, motivo)
    return True


def _retirar(
    almacen: Almacen, ahora: datetime, modelos: frozenset[str], hechos: Corregidos
) -> None:
    for revision in cargar().get("retirar", []):
        documento = almacen.incidente(revision["incidente"])
        if documento is None or not incidentes.activo(documento):
            continue
        nuevo = {k: v for k, v in documento.items() if k != "episodio"}
        nuevo["retirado"] = {
            "fecha": _instante(ahora),
            "motivo": revision["motivo"]["es"][: extraccion.MAX_LETRAS_MOTIVO],
            "motivo_en": revision["motivo"]["en"][: extraccion.MAX_LETRAS_MOTIVO],
        }
        if _guardar(almacen, documento, nuevo, ahora, modelos, revision["motivo"]["es"], hechos):
            hechos.retirados.append(documento["id"])


def corregir(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> Corregidos:
    """Aplica las retiradas, las citas, los titulares y las ubicaciones revisados."""
    hechos = Corregidos()
    datos = cargar()
    _retirar(almacen, ahora, modelos, hechos)
    for id_, citas in _por_incidente(almacen, datos.get("citas", [])).items():
        documento = almacen.incidente(id_)
        assert documento is not None
        nuevo = con_citas(documento, citas)
        if nuevo != documento and _guardar(
            almacen, documento, nuevo, ahora, modelos, MOTIVO_CITA, hechos
        ):
            hechos.citas.append(id_)
    for id_, revisiones in _por_incidente(almacen, datos.get("titulares", [])).items():
        documento = almacen.incidente(id_)
        assert documento is not None
        revision = revisiones[-1]
        nuevo = con_titular(documento, revision, _instante(ahora))
        if nuevo != documento and _guardar(
            almacen, documento, nuevo, ahora, modelos, revision["motivo"]["es"], hechos
        ):
            hechos.titulares.append(id_)
    for id_, revisiones in _por_incidente(almacen, datos.get("ubicaciones", [])).items():
        documento = almacen.incidente(id_)
        assert documento is not None
        con_punto = con_lugar(documento, revisiones[-1])
        if (
            con_punto is not None
            and con_punto != documento
            and _guardar(almacen, documento, con_punto, ahora, modelos, MOTIVO_UBICACION, hechos)
        ):
            hechos.ubicados.append(id_)
    registro.info("revisión del contenido: %s", hechos.texto())
    return hechos


def presencia_revisada(id_: str) -> bool:
    """El incidente tiene la presencia del dron revisada a mano: la regla horaria no la cambia."""
    return any(t["incidente"] == id_ and "presencia" in t for t in cargar().get("titulares", []))
