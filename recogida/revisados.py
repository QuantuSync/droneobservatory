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
from proceso import (
    decidir,
    declaraciones,
    extraccion,
    incidentes,
    presencia,
    rectificaciones,
)
from proceso.credibilidad import Credibilidad
from proceso.estados import (
    RETIRADAS,
    REVERSIONES,
    Estado,
    error_reversion,
    nuevo_estado,
    transitar,
)
from proceso.fronteras import dentro_del_pais
from proceso.presencia import TABLA_MOTIVOS
from proceso.validaciones import derivar_duracion_min

registro = logging.getLogger(__name__)
RUTA = Path(__file__).resolve().parent.parent / "configuracion" / "incidentes_revisados.json"
RUTA_PUNTO = Path(__file__).resolve().parent.parent / "configuracion" / "punto_principal.json"
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


def unir_grupo(
    almacen: Almacen, registros: list[str], motivo: str, ahora: datetime,
    modelos: frozenset[str], conserva: str | None = None,
) -> int:  # fmt: skip
    """Funde en uno los registros vivos del grupo. Devuelve cuántos funde. Con `conserva`, queda
    ese registro (el más antiguo, para que su enlace siga siendo el del suceso)."""
    vivos: dict[str, Documento] = {}
    for id_ in registros:
        documento = _vivo(almacen, id_)
        if documento is not None:
            vivos[documento["id"]] = documento
    if len(vivos) < 2:
        return 0
    publicados = frozenset(vivos)
    destino = next(iter(vivos.values()))
    for otro in list(vivos.values())[1:]:
        destino = incidentes.destino_de(destino, otro, publicados)[0]
    elegido = _vivo(almacen, conserva) if conserva else None
    if elegido is not None and elegido["id"] in vivos:
        destino = vivos[elegido["id"]]
    unidos = [d for d in vivos.values() if d["id"] != destino["id"]]
    nuevo = destino
    fundidos = []
    for absorbido in unidos:
        nuevo, aportadas = incidentes.absorber(nuevo, absorbido, ahora)
        fundido = {**copy.deepcopy(absorbido), "fusionado_en": destino["id"]}
        fundido.pop("episodio", None)
        fundidos.append((fundido, aportadas))
    # Lo que trae del unido (su cierre) cambia el tipo: las reglas otra vez (EODI-2026-00183, un
    # sobrevuelo que recibe el cierre del aeropuerto de Gran Canaria de la EODI-2026-00398).
    nuevo = incidentes.aplicar_reglas(completar(nuevo, unidos))
    almacen.guardar_incidente(nuevo, ahora, modelos)
    for fundido, aportadas in fundidos:
        almacen.guardar_incidente(fundido, ahora, modelos)
        almacen.registrar_fusion(
            ahora.strftime("%Y-%m-%dT%H:%MZ"), fundido["id"], destino["id"],
            incidentes.PREFIJO_REVISADA + motivo, aportadas,
        )  # fmt: skip
    return len(fundidos)


def unir(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> int:
    """Funde cada grupo revisado en uno. Devuelve cuántos registros funde."""
    return sum(
        unir_grupo(
            almacen, grupo["registros"], grupo["motivo"], ahora, modelos, grupo.get("conserva")
        )
        for grupo in cargar()["unir"]
    )


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


# --- Revisión del contenido (interno: informe_revision_contenido) ---------------------------
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
#   corresponden, cada cambio con su cita y su motivo; la instalación afectada («objetivo»)
#   si la ficha no la reconoció; y el inicio («inicio») que escribe una fuente cuando la ficha
#   tomó la fecha de publicación, con esa cita.
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
MOTIVO_LUGAR_REVISADO = "lugar revisado a mano (configuracion/incidentes_revisados.json, datos)"
MOTIVO_INICIO_REVISADO = "inicio revisado a mano (configuracion/incidentes_revisados.json, datos)"


@dataclass
class Corregidos:
    retirados: list[str] = field(default_factory=list)
    citas: list[str] = field(default_factory=list)
    titulares: list[str] = field(default_factory=list)
    ubicados: list[str] = field(default_factory=list)
    lugares: list[str] = field(default_factory=list)
    inicios: list[str] = field(default_factory=list)
    sin_guardar: list[str] = field(default_factory=list)
    contradicen_rectificacion: list[str] = field(default_factory=list)

    def texto(self) -> str:
        return (
            f"retirados {len(self.retirados)}, con citas {len(self.citas)}, titulares "
            f"{len(self.titulares)}, ubicados {len(self.ubicados)}, lugares revisados "
            f"{self.lugares}, inicios revisados {self.inicios}, sin guardar "
            f"{self.sin_guardar}, presencias revisadas que contradicen una rectificación oficial "
            f"{self.contradicen_rectificacion}"
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
        # La autoría que afirma la autoridad (proceso/atribucion.evaluar), si la revisión la da.
        **{c: declaracion[c] for c in ("autor", "autor_tipo", "autor_pais") if c in declaracion},
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


def reconfirmar(incidente: Documento, citas: list[Documento], instante: Documento) -> Documento:
    """El incidente que el control de fichas volvió a «notificado» porque la confirmación era una
    cita de autoridad vacía (EODI-2026-00648, «… Komendy Stołecznej Policji przekazała»), otra vez
    confirmado con la cita revisada de esa autoridad que afirma el suceso. Solo si ningún paso del
    historial es ya de esa cita: no deshace un desmentido ni repite la confirmación."""
    if incidente["estado"]["actual"] != Estado.NOTIFICADO:
        return incidente
    pasos = {p.get("fuente_id") for p in incidente["estado"]["historial"]}
    fuentes = {f["id"]: f for f in incidente["fuentes"]}
    for cita in citas:
        declaracion = cita.get("declaracion") or {}
        if declaracion.get("afirma") not in declaraciones.CONFIRMAN:
            continue
        fuente_id = fuente_de_cita(cita, incidente)["id"]
        if fuente_id in fuentes and fuente_id not in pasos:
            resultado = copy.deepcopy(incidente)
            resultado["estado"] = transitar(
                resultado["estado"], Estado.CONFIRMADO, instante, fuente_id, fuentes
            )
            return resultado
    return incidente


def _fuente_de_la_presencia(incidente: Documento, presencia: Documento) -> str | None:
    """La fuente de la cita de una presencia revisada cuando el extractor, al leer de nuevo la
    noticia, se quedó con otra frase suya: con el enlace de la revisión, la misma fuente con la
    frase revisada (se añade una vez a la ficha). Sin el enlace o sin esa fuente en la ficha, None
    (EODI-2026-00515: el 20 de octubre de 2026 schwaebische.de pasó a dar otra frase y la ficha
    volvió a «Dron confirmado» sin que nadie lo revisara)."""
    enlace = presencia.get("enlace")
    misma = next((f for f in incidente["fuentes"] if enlace and f.get("enlace") == enlace), None)
    if misma is None:
        return None
    clave = hashlib.sha256(f"{enlace}\n{presencia['cita']}".encode()).hexdigest()[:16]
    fuente_id = PREFIJO_REVISADA + clave
    if not any(f["id"] == fuente_id for f in incidente["fuentes"]):
        incidente["fuentes"].append({
            **copy.deepcopy(misma), "id": fuente_id, "frase_origen": presencia["cita"],
            "replicas": 0, "campos_respaldados": ["presencia_dron"],
        })  # fmt: skip
    return fuente_id


def con_titular(incidente: Documento, revision: Documento, instante: Documento) -> Documento:
    """El titular revisado y, si la revisión lo dice, la presencia y el estado con su cita."""
    resultado = copy.deepcopy(incidente)
    fuentes = {f["frase_origen"]: f["id"] for f in resultado["fuentes"]}
    presencia = revision.get("presencia")
    if presencia and resultado.get("presencia_dron") != presencia["valor"]:
        fuente_id = fuentes.get(presencia["cita"]) or _fuente_de_la_presencia(resultado, presencia)
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
    ultimo_paso = resultado["estado"]["historial"][-1]
    if (
        estado
        and resultado["estado"]["actual"] == estado["valor"]
        and ultimo_paso.get("fuente_id") == fuentes.get(estado["cita"])
        and "motivo" in ultimo_paso
        and ultimo_paso["motivo"] != estado["motivo"]
    ):
        # La revisión ya aplicada con otro texto del motivo (se corrigió su redacción): el paso
        # que dejó es el suyo y toma el texto nuevo; el estado y el historial no cambian.
        resultado["estado"]["historial"][-1] = {**ultimo_paso, "motivo": estado["motivo"]}
    elif estado and resultado["estado"]["actual"] != estado["valor"]:
        fuente_id = fuentes.get(estado["cita"])
        origen = Estado(resultado["estado"]["actual"])
        destino = Estado(estado["valor"])
        # Una retirada, o la reversión de un desmentido por una autoridad de fiabilidad igual o
        # mayor que la de quien desmintió (EODI-2026-00293: prevalece skeyes, el control aéreo,
        # sobre el aeropuerto; proceso/competencia.py). El desmentido sigue en el historial.
        porfuente = {f["id"]: f for f in resultado["fuentes"]}
        ultimo = porfuente.get(str(resultado["estado"]["historial"][-1].get("fuente_id")))
        vale = (origen, destino) in RETIRADAS or (
            (origen, destino) in REVERSIONES
            and fuente_id is not None
            and error_reversion(ultimo, porfuente.get(fuente_id)) is None
        )
        if fuente_id is not None and vale:
            paso = {
                "estado": destino.value,
                "fecha": instante,
                "fuente_id": fuente_id,
                "motivo": estado["motivo"],
            }
            historial = [*resultado["estado"]["historial"], paso]
            resultado["estado"] = {"actual": destino.value, "historial": historial}
            if destino != Estado.DESMENTIDO:
                resultado["control"].pop("motivo_desmentido", None)
    drones = revision.get("drones")
    if drones and resultado.get("drones", {}).get("numero") != drones["valor"]:
        # Ninguna fuente da el número de drones: sin dato, y fuera las afirmaciones que lo daban.
        resultado["drones"] = {**resultado.get("drones", {}), "numero": drones["valor"]}
        resultado["afirmaciones"] = [
            a for a in resultado.get("afirmaciones", []) if a.get("campo") != "drones"
        ]
    inicio = revision.get("inicio")
    fuente_inicio = fuentes.get(inicio["cita"]) if inicio else None
    if inicio and fuente_inicio is not None:
        # El día que escribe una fuente cuando la ficha tomó el de la publicación
        # (EODI-2026-00622: la noche del 18 de septiembre de 2026, publicado el 25).
        nuevo_inicio = {"valor": inicio["valor"], "precision": inicio["precision"]}
        # El fin que da una fuente («entre las 07:00 y las 08:10 horas», «durante 40 minutos»),
        # con su cita («fin_cita»); si no, el que ya tenía la ficha, si sigue siendo posterior.
        fin_citado = (
            {"valor": inicio["fin"], "precision": inicio["precision"]}
            if inicio.get("fin") and fuentes.get(inicio.get("fin_cita", "")) is not None
            else None
        )
        if resultado["tiempo"]["inicio"] != nuevo_inicio or (
            fin_citado is not None and resultado["tiempo"].get("fin") != fin_citado
        ):
            tiempo: Documento = {
                "inicio": nuevo_inicio,
                "origen_inicio": {"tipo": "explicita", "fuente_id": fuente_inicio,
                                  "motivo": inicio["motivo"]},
            }  # fmt: skip
            fin = fin_citado or resultado["tiempo"].get("fin")
            if fin and inicio["precision"] in incidentes.PRECISIONES_HORA:
                tiempo["fin"] = fin
                if (duracion := derivar_duracion_min(tiempo)) is None:
                    tiempo.pop("fin")
                else:
                    tiempo["duracion_min"] = duracion
            if fin_citado is not None and tiempo.get("fin") == fin_citado:
                # El fin lo dice la fuente de su cita: su afirmación, como la de una ficha, para
                # que el valor lleve su origen (exportacion/procedencia.py).
                afirmacion = {"campo": "fin", "valor": fin_citado,
                              "fuente_id": fuentes[inicio["fin_cita"]],
                              "confianza_extraccion": 1.0}  # fmt: skip
                resultado["afirmaciones"] = [
                    *(a for a in resultado.get("afirmaciones", []) if a != afirmacion),
                    afirmacion,
                ]
            resultado["tiempo"] = tiempo
    objetivo = revision.get("objetivo")
    if objetivo and resultado.get("objetivo") != objetivo:
        # La instalación afectada que la ficha no reconoció (EODI-2026-00146: «Melilla», categoría
        # «otra», en vez del aeropuerto de Melilla; las cárceles, con el nombre de la ciudad).
        resultado["objetivo"] = dict(objetivo)
    lugar = revision.get("lugar")
    if lugar and "punto" not in resultado["lugar"]:
        # El lugar guardado no era el del suceso (Arna está en Noruega): sin punto, que solo
        # lo da una nota oficial (ubicaciones).
        nuevo = {k: v for k, v in resultado["lugar"].items() if k != "nuts2"}
        resultado["lugar"] = {**nuevo, **lugar}
    # El titular revisado lo decide proceso/decidir.py, con la presencia y la atribución.
    resultado["titulo"] = decidir.decidir_titulo(resultado)
    return resultado


@cache
def _regla_punto() -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(RUTA_PUNTO.read_text(encoding="utf-8"))
    return datos


def punto_de_respuesta_defensiva(frase: str) -> bool:
    """La frase que daría el punto habla de un daño de la respuesta defensiva (un misil, el avión
    que lo dispara) y no del dron: ese lugar nunca es el punto principal
    (configuracion/punto_principal.json)."""
    texto = frase.lower()
    regla = _regla_punto()
    defensiva = any(t in texto for t in regla["respuesta_defensiva"])
    return defensiva and not any(t in texto for t in regla["dron"])


@cache
def _objetivos_revisados() -> dict[str, Documento]:
    return {
        str(r["incidente"]): dict(r["objetivo"])
        for r in cargar().get("titulares", [])
        if r.get("objetivo")
    }


def objetivo_revisado(incidente: str) -> Documento | None:
    """La instalación revisada a mano en «titulares» (con su motivo), si la hay."""
    objetivo = _objetivos_revisados().get(incidente)
    return dict(objetivo) if objetivo else None


def con_lugar(incidente: Documento, revision: Documento, instante: Documento) -> Documento | None:
    """El lugar que da la autoridad: punto, radio y los demás lugares que nombra, cada uno con la
    fuente que lo explica si la revisión la da. None si el punto no cae en su país, si su frase
    habla de la respuesta defensiva y no del dron, o si el incidente ya tiene otro punto y la
    revisión no trae el cambio con su motivo. Con el cambio, el punto anterior queda en
    lugar.historial con el motivo en español y en inglés."""
    lugar = revision["lugar"]
    cita = revision["fuente"]
    if not dentro_del_pais(incidente["lugar"]["pais"], float(lugar["lat"]), float(lugar["lon"])):
        return None
    if punto_de_respuesta_defensiva(cita["frase"]):
        registro.warning(
            "punto sin poner en %s: la frase habla de la respuesta defensiva, no del dron",
            incidente["id"],
        )
        return None
    punto = {"lat": round(float(lugar["lat"]), 5), "lon": round(float(lugar["lon"]), 5)}
    antes = incidente["lugar"]
    historial = list(antes.get("historial", []))
    if "punto" in antes and antes["punto"] != punto:
        cambio = revision.get("cambio")
        if cambio is None:
            return None
        anterior: Documento = {"punto": antes["punto"], "radio_km": antes["radio_km"]}
        for campo in ("localidad", "fuente_punto"):
            if campo in antes:
                anterior[campo] = antes[campo]
        historial.append(
            {"fecha": instante, "anterior": anterior, "motivo": dict(cambio["motivo"])}
        )
    explicaciones = [o["fuente"] for o in revision.get("otros_lugares", []) if "fuente" in o]
    resultado = con_citas(incidente, [cita, *explicaciones])
    nuevo = copy.deepcopy(resultado["lugar"])
    nuevo["punto"] = punto
    nuevo["radio_km"] = float(lugar["radio_km"])
    nuevo["nivel"] = lugar["nivel"]
    # La localidad la decide la revisión de datos si la hay (proceso/decidir.py): «Akrotiri», la
    # península, y no «RAF Akrotiri», la base (EODI-2026-00268 iba y volvía cada hora).
    datos = (decidir.revision_de(incidente, "lugar") or {}).get("valor") or {}
    nuevo["localidad"] = datos.get("localidad") or lugar["nombre"]
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
        if "fuente" in otro:
            entrada["fuente"] = fuente_de_cita(otro["fuente"], incidente)["id"]
        otros.append(entrada)
    if otros:
        nuevo["otros_lugares"] = otros
    if historial:
        nuevo["historial"] = historial
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
    campos = (
        "estado",
        "presencia_dron",
        "titulo",
        "lugar",
        "fuentes",
        "retirado",
        "relacionados",
        "drones",
        "objetivo",
    )
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
    """Aplica las retiradas, las citas, los titulares, las ubicaciones y los lugares revisados."""
    hechos = Corregidos()
    datos = cargar()
    _retirar(almacen, ahora, modelos, hechos)
    for id_, citas in _por_incidente(almacen, datos.get("citas", [])).items():
        documento = almacen.incidente(id_)
        assert documento is not None
        nuevo = reconfirmar(con_citas(documento, citas), citas, _instante(ahora))
        if nuevo != documento and _guardar(
            almacen, documento, nuevo, ahora, modelos, MOTIVO_CITA, hechos
        ):
            hechos.citas.append(id_)
    for id_, revisiones in _por_incidente(almacen, datos.get("titulares", [])).items():
        documento = almacen.incidente(id_)
        assert documento is not None
        revision = revisiones[-1]
        if contradice_rectificacion(revision, documento):
            # Una rectificación oficial manda sobre la revisión a mano (solo otra rectificación la
            # cambia): la presencia revisada no se aplica y queda en el registro para corregirla.
            hechos.contradicen_rectificacion.append(id_)
            registro.warning("%s: la presencia revisada a mano (%s) contradice la rectificación "
                             "oficial (%s); no se aplica", id_, revision["presencia"]["valor"],
                             rectificaciones.vigente(documento))  # fmt: skip
            revision = {k: v for k, v in revision.items() if k != "presencia"}
        nuevo = con_titular(documento, revision, _instante(ahora))
        if nuevo != documento and _guardar(
            almacen, documento, nuevo, ahora, modelos, revision["motivo"]["es"], hechos
        ):
            hechos.titulares.append(id_)
    for id_, revisiones in _por_incidente(almacen, datos.get("ubicaciones", [])).items():
        documento = almacen.incidente(id_)
        assert documento is not None
        revision = revisiones[-1]
        con_punto = con_lugar(documento, revision, _instante(ahora))
        motivo = revision["cambio"]["motivo"]["es"] if "cambio" in revision else MOTIVO_UBICACION
        if (
            con_punto is not None
            and con_punto != documento
            and _guardar(almacen, documento, con_punto, ahora, modelos, motivo, hechos)
        ):
            hechos.ubicados.append(id_)
    # El lugar y el inicio revisados («datos») se aplican al guardar la ficha
    # (decidir.decidir_datos); una ficha que nada vuelve a guardar se quedaba con el punto de antes
    # (EODI-2026-00238, en Tulcea con la revisión en Rachelu) o con su hora de antes
    # (EODI-2026-00108, Auvere, a las 06:00 UTC con la revisión a las 01:43). Solo se guarda si
    # cambia el dato revisado.
    for campo, clave, motivo, lista in (
        ("lugar", "lugar", MOTIVO_LUGAR_REVISADO, hechos.lugares),
        ("inicio", "tiempo", MOTIVO_INICIO_REVISADO, hechos.inicios),
    ):
        revisadas = [e for e in datos.get("datos", []) if e.get("campo") == campo]
        for id_ in _por_incidente(almacen, revisadas):
            documento = almacen.incidente(id_)
            assert documento is not None
            decidido = decidir.decidir_datos(documento)
            if decidido.get(clave) != documento.get(clave) and _guardar(
                almacen, documento, decidido, ahora, modelos, motivo, hechos
            ):
                lista.append(id_)
    registro.info("revisión del contenido: %s", hechos.texto())
    return hechos


def inicios_revisados(ruta: Path = RUTA) -> dict[str, dict[str, Any]]:
    """Los inicios revisados a mano (`titulares.inicio`, con su cita), por incidente."""
    return {
        str(r["incidente"]): r["inicio"]
        for r in cargar(ruta).get("titulares", [])
        if isinstance(r.get("inicio"), dict)
    }


def contradice_rectificacion(revision: Documento, incidente: Documento) -> bool:
    """La presencia revisada a mano contradice la que dejó una rectificación oficial de la ficha
    (el último paso de su `presencia_historial` que no es una nota, cuando hay más de uno). Desde el
    20 de octubre de 2026: EODI-2025-00164 seguía revisada «no confirmada» cuando la rectificación
    del UK Airprox Board la había dejado «descartada»."""
    presencia = revision.get("presencia") or {}
    pasos = rectificaciones.pasos_de_valor(incidente)
    return bool(presencia) and len(pasos) > 1 and presencia.get("valor") != pasos[-1].get("valor")


def revisiones_contra_rectificaciones(
    revisiones: Documento | None = None, oficiales: Documento | None = None
) -> list[str]:
    """Las revisiones a mano de la presencia (`titulares` con `presencia`) que no dicen lo mismo que
    la última rectificación oficial revisada a mano del mismo incidente
    (configuracion/rectificaciones_oficiales.json, sin las parciales ni los cierres sin cambio).
    Vacía si todo cuadra."""
    from recogida import rectificaciones as oficiales_

    revisiones = cargar() if revisiones is None else revisiones
    oficiales = oficiales_.cargar() if oficiales is None else oficiales
    ultima: dict[str, Documento] = {}
    for r in sorted(oficiales.get("rectificaciones", []), key=lambda r: r["fecha_declaracion"]):
        if r.get("tipo") not in rectificaciones.SIN_CAMBIO:
            ultima[r["incidente"]] = r
    return [
        f"{t['incidente']}: revisada «{t['presencia']['valor']}», rectificada "
        f"«{ultima[t['incidente']]['tipo']}» el {ultima[t['incidente']]['fecha_declaracion']}"
        for t in revisiones.get("titulares", [])
        if "presencia" in t
        and t["incidente"] in ultima
        and t["presencia"]["valor"] != ultima[t["incidente"]]["tipo"]
    ]


def presencia_revisada(id_: str) -> bool:
    """El incidente tiene la presencia del dron revisada a mano: la regla horaria no la cambia."""
    return any(t["incidente"] == id_ and "presencia" in t for t in cargar().get("titulares", []))


# --- Sucesos mezclados (docs/sucesos_mezclados.md) ---------------------------------------
#
# Un incidente que juntó sucesos distintos (EODI-2026-00072: el cierre del aeropuerto de Vilna
# del 13 de septiembre de 2026 y el derribo de la noche del 14 al 15) se separa una sola vez:
# - cada fuente va a la parte del suceso del que habla (revisado a mano, `separar`);
# - el identificador se queda con el suceso más temprano: pierde las fuentes de los demás y lo
#   que solo ellas sostenían, y su candidato, sin esos artículos, se vuelve a extraer;
# - cada otro suceso abre un candidato propio («separado_de») con sus artículos y recibe un
#   identificador por el camino normal de altas (su ficha la hace el extractor); lo que no es un
#   suceso (una declaración política, un parte de la guerra) sale del incidente y no forma otro;
# - una fusión anterior cuyas fuentes son todas de otra parte se deshace (las revisadas a mano,
#   no);
# - una parte que es el mismo suceso que otra ficha se une a ella (`coincide_con`), con la
#   regla de siempre para elegir cuál queda;
# - las fichas que quedan de cada separación se enlazan entre sí («Suceso relacionado»).

CURSOR_SEPARAR = CURSOR + "separar:"
# Llamadas al extractor por pasada horaria: cada una lee las páginas y tarda unos segundos.
MAX_EXTRACCIONES_PASADA = 12
MOTIVO_NO_SUCESO = "revisión: no es un suceso (configuracion/incidentes_revisados.json, separar)"


@dataclass
class Separados:
    repartidos: list[str] = field(default_factory=list)
    extraidos: list[str] = field(default_factory=list)
    pendientes: list[str] = field(default_factory=list)
    unidos: int = 0
    relacionados: list[str] = field(default_factory=list)

    def texto(self) -> str:
        return (
            f"repartidos {self.repartidos}, partes extraídas {len(self.extraidos)}, partes "
            f"pendientes de extraer {len(self.pendientes)}, unidos {self.unidos}, con suceso "
            f"relacionado {len(self.relacionados)}"
        )


def _clave_parte(parte: Documento) -> tuple[bool, str]:
    return (not parte.get("es_suceso", True), str(parte.get("fecha") or "9999"))


def conservada(revision: Documento) -> int:
    """La parte que se queda con el identificador: el suceso más temprano."""
    partes = revision["partes"]
    return min(range(len(partes)), key=lambda n: _clave_parte(partes[n]))


def _fecha_articulo(articulo: Documento) -> datetime:
    return datetime.fromisoformat(str(articulo["fecha"]).replace("Z", "+00:00"))


def _id_candidato(base: Documento, articulos: list[Documento], ocupados: set[str]) -> str:
    primero = min(_fecha_articulo(a) for a in articulos)
    raiz = f"CAND-{primero:%Y%m%dT%H%M}-{base['lugar']}-{base['tipo']}"
    id_, n = raiz, 1
    while id_ in ocupados:
        n += 1
        id_ = f"{raiz}-{n}"
    return id_


def _documento_candidato(
    base: Documento, id_: str, articulos: list[Documento], separado_de: str | None
) -> Documento:
    fechas = sorted(_fecha_articulo(a) for a in articulos)
    documento = {
        **copy.deepcopy(base),
        "id": id_,
        "articulos": [a["url"] for a in sorted(articulos, key=lambda a: (a["fecha"], a["url"]))],
        "inicio": fechas[0].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ultimo": fechas[-1].strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    documento.pop("separado_de", None)
    if separado_de is not None:
        documento["separado_de"] = separado_de
    return documento


def _parte_de_fuentes(revision: Documento, ids: list[str]) -> int | None:
    """La única parte a la que van esas fuentes, o None si van a varias o a ninguna."""
    partes = {n for n, p in enumerate(revision["partes"]) for i in ids if i in p["fuentes"]}
    return partes.pop() if len(partes) == 1 else None


def ficha_version() -> str:
    from modelo import ficha

    return ficha.VERSION


def _sin_afirmar(resultado: Documento, quitadas: set[str]) -> None:
    """Quita los valores que solo afirmaban las fuentes quitadas (`quitadas`: los campos de la
    ficha que ya no tienen ninguna afirmación): sin respaldo, un valor no tiene origen. Lo que
    se puede dejar sin saber queda «desconocido»; la fecha vuelve a la de publicación de la
    primera noticia que queda, como la de una ficha que no la escribe."""
    if "medidas" in quitadas and "respuesta" in resultado:
        resultado["respuesta"].pop("medidas", None)
        if not resultado["respuesta"]:
            resultado.pop("respuesta")
    drones = resultado.get("drones")
    if isinstance(drones, dict):
        if "drones" in quitadas:
            drones["numero"] = "desconocido"
        if "modelo_dron" in quitadas:
            drones.pop("modelo", None)
    consecuencias = resultado.get("consecuencias", {})
    if "cierre" in quitadas and "cierre" in consecuencias:
        consecuencias["cierre"] = {"valor": "desconocido"}
    elif "cierre_minutos" in quitadas and "cierre" in consecuencias:
        consecuencias["cierre"].pop("minutos", None)
    for campo in ("vuelos_desviados", "vuelos_cancelados", "vuelos_retrasados"):
        if campo in quitadas:
            consecuencias.pop(campo, None)
    if {"fin", "inicio"} & quitadas:
        resultado["tiempo"].pop("fin", None)
        resultado["tiempo"].pop("duracion_min", None)
    if "inicio" in quitadas:
        primera = min(
            (f for f in resultado["fuentes"] if not f.get("es_autoridad")),
            key=lambda f: (f["fecha"]["valor"], f["id"]),
            default=resultado["fuentes"][0],
        )
        resultado["tiempo"] = {
            "inicio": {"valor": primera["fecha"]["valor"], "precision": "aproximada"},
            "origen_inicio": {
                "tipo": "publicacion",
                "fuente_id": primera["id"],
                "motivo": "la fuente que daba la fecha era de otro suceso (separar)",
            },
        }
    pruebas = resultado.get("pruebas")
    if isinstance(pruebas, dict):
        if "dron_estatal" in quitadas:
            pruebas["dron_estatal"] = False
        if "entrada_exterior" in quitadas:
            pruebas["entrada_exterior"] = False
        if {"evidencia", "origen_demostrado"} & quitadas:
            pruebas["evidencia"] = []


def sin_fuentes(documento: Documento, enlaces: set[str]) -> Documento | None:
    """El incidente sin las fuentes de esos enlaces ni lo que solo ellas sostenían: sus
    afirmaciones, los pasos del estado que dieron, la atribución y la investigación que citan y
    la presencia del dron que afirmaban; con las reglas de siempre aplicadas de nuevo. None si
    no le queda ninguna fuente."""
    fuentes = [f for f in documento["fuentes"] if f["enlace"] not in enlaces]
    if not fuentes:
        return None
    if len(fuentes) == len(documento["fuentes"]):
        return documento
    quedan = {f["id"] for f in fuentes}
    resultado = copy.deepcopy(documento)
    nivel = incidentes.credibilidad_noticias(len(fuentes))
    for fuente in fuentes:
        if fuente.get("fiabilidad") == incidentes.FIABILIDAD_NOTICIAS:
            fuente["credibilidad"] = nivel
    resultado["fuentes"] = copy.deepcopy(fuentes)
    antes = {a["campo"] for a in resultado.get("afirmaciones", [])}
    resultado["afirmaciones"] = [
        a for a in resultado.get("afirmaciones", []) if a["fuente_id"] in quedan
    ]
    _sin_afirmar(resultado, antes - {a["campo"] for a in resultado["afirmaciones"]})
    pasos = [p for p in resultado["estado"]["historial"] if p.get("fuente_id") in quedan]
    if not pasos or pasos[0]["estado"] != Estado.NOTIFICADO:
        # Todo estado empieza en «notificado», con la primera noticia que queda.
        primera = min(fuentes, key=lambda f: (f["fecha"]["valor"], f["id"]))
        inicial = nuevo_estado(primera["fecha"], primera["id"])["historial"][0]
        if pasos and pasos[0]["fecha"]["valor"] < inicial["fecha"]["valor"]:
            inicial["fecha"] = pasos[0]["fecha"]
        pasos = [inicial, *pasos]
    resultado["estado"] = {"actual": pasos[-1]["estado"], "historial": pasos}
    if resultado["estado"]["actual"] != Estado.DESMENTIDO:
        resultado["control"].pop("motivo_desmentido", None)
    if resultado["estado"]["actual"] != Estado.ATRIBUIDO:
        resultado.pop("atribucion", None)
    if "investigacion" in resultado:
        investigacion = [i for i in resultado["investigacion"] if i["fuente_id"] in quedan]
        if investigacion:
            resultado["investigacion"] = investigacion
        else:
            resultado.pop("investigacion")
    origen = resultado["tiempo"].get("origen_inicio", {})
    if origen.get("fuente_id") not in (None, *quedan):
        origen.pop("fuente_id")
    afirmadas = [a["valor"] for a in resultado["afirmaciones"] if a["campo"] == "presencia_dron"]
    if resultado.get("presencia_dron") not in (*afirmadas, None):
        orden = ("confirmada", "descartada", "no_confirmada")
        resultado["presencia_dron"] = min(afirmadas, key=orden.index, default="no_confirmada")
    resultado["control"]["huella_fuentes"] = incidentes.huella([f["enlace"] for f in fuentes])
    return presencia.aplicar(incidentes.aplicar_reglas(resultado))


# Valores que se dejan sin saber en vez de quitarlos (el esquema no deja quitarlos).
DESCONOCIDOS = {"drones.numero": "desconocido", "consecuencias.cierre.valor": "desconocido"}
MAX_PASADAS_ORIGEN = 5


def con_origen(documento: Documento, fichas: Any) -> Documento:
    """El incidente sin los valores que se han quedado sin origen al perder fuentes, con la misma
    comprobación que la exportación semanal (exportacion/procedencia.py). Un valor obligatorio
    sin origen no se toca: la exportación lo dirá."""
    from exportacion import procedencia as origenes

    resultado = copy.deepcopy(documento)
    for _ in range(MAX_PASADAS_ORIGEN):
        try:
            origenes.procedencia_incidente(resultado, fichas)
        except origenes.SinOrigen as error:
            texto = str(error)
            if "sin origen en " not in texto:
                return resultado
            rutas = texto.split("sin origen en ", 1)[1].split(", ")
            quitables = [r for r in rutas if r not in origenes.OBLIGATORIAS]
            if not quitables:
                return resultado
            for ruta in quitables:
                if ruta in DESCONOCIDOS:
                    padre, _, hoja = ruta.rpartition(".")
                    nodo = origenes.leer(resultado, padre)
                    if isinstance(nodo, dict):
                        if ruta == "consecuencias.cierre.valor":
                            # Sin cierre sabido tampoco hay duración.
                            nodo.clear()
                        nodo[hoja] = DESCONOCIDOS[ruta]
                elif origenes.leer(resultado, ruta) is not None:
                    origenes.quitar(resultado, ruta)
            resultado = incidentes.aplicar_reglas(resultado)
        else:
            return resultado
    return resultado


def repartir(
    almacen: Almacen, revision: Documento, ahora: datetime, modelos: frozenset[str]
) -> Documento | None:
    """Reparte el incidente en sus sucesos (una sola vez). Devuelve lo hecho, para el cursor, o
    None si no se puede (el incidente ya no está activo o se quedaría sin fuentes)."""
    id_ = revision["incidente"]
    original = almacen.incidente(id_)
    if (
        original is not None
        and "fusionado_en" in original
        and "retirado" not in original
        and any(
            f["absorbido"] == id_
            and not f["revertida"]
            and not f["motivo"].startswith(incidentes.PREFIJO_REVISADA)
            for f in almacen.fusiones()
        )
    ):
        # Un registro que una regla fundió en otro después de recibir las fuentes de otro suceso
        # (EODI-2025-00199, el cierre de Zaventem del 5 de diciembre de 2025, fundido en
        # EODI-2026-00094 el 25 de octubre de 2026): la fusión se deshace y se separa como los
        # demás. Las fusiones revisadas a mano, no.
        incidentes.revertir(almacen, id_, ahora, modelos)
        original = almacen.incidente(id_)
    if original is None or not incidentes.activo(original):
        registro.warning("separación sin hacer: %s no está activo", id_)
        return None
    motivo = revision["motivo"]["es"]
    queda = conservada(revision)
    enlace_de = {f["id"]: f["enlace"] for f in original["fuentes"]}
    enlaces_parte = [
        {enlace_de[f] for f in parte["fuentes"] if f in enlace_de} for parte in revision["partes"]
    ]
    # Lo que sale del que se queda: los enlaces de las otras partes que no son también suyos.
    # Un artículo que cuenta dos sucesos va a los dos.
    salen = set().union(*(e for n, e in enumerate(enlaces_parte) if n != queda))
    salen -= enlaces_parte[queda]
    if sin_fuentes(original, salen) is None:
        registro.warning("separación sin hacer: a %s no le quedaría ninguna fuente", id_)
        return None
    # Las fusiones anteriores cuyas fuentes son todas de otra parte se deshacen: el registro
    # absorbido vuelve con sus fuentes y es la ficha de esa parte. Las revisadas a mano, no.
    vueltos: dict[int, list[str]] = {}
    for fusion in almacen.fusiones():
        if (
            fusion["destino"] != id_
            or fusion["revertida"]
            or fusion["motivo"].startswith(incidentes.PREFIJO_REVISADA)
        ):
            continue
        parte = _parte_de_fuentes(revision, fusion["fuentes"])
        if parte is not None and parte != queda:
            incidentes.revertir(almacen, fusion["absorbido"], ahora, modelos)
            vueltos.setdefault(parte, []).append(fusion["absorbido"])
    # Los artículos que salen dejan su candidato (el del incidente o el de un registro fundido)
    # y forman el de su parte, del mismo sitio y tipo que el candidato del incidente.
    candidatos = {c["id"]: c for c in almacen.candidatos()}
    todos = set().union(*(e for n, e in enumerate(enlaces_parte) if n != queda))
    articulos = {a["url"]: a for a in almacen.articulos_de(sorted(todos))}
    propio = candidatos.get(str(original["control"].get("candidato")))
    cambiados: dict[str, Documento] = {}
    for url, articulo in articulos.items():
        if url not in salen:
            continue
        origen = cambiados.get(str(articulo.get("candidato"))) or candidatos.get(
            str(articulo.get("candidato"))
        )
        if origen is not None:
            restantes = [u for u in origen["articulos"] if u != url]
            cambiados[origen["id"]] = {**origen, "articulos": restantes}
    documentos = [c for c in cambiados.values() if c["articulos"]]
    ocupados = set(candidatos)
    hecho: Documento = {"fecha": ahora.strftime("%Y-%m-%dT%H:%MZ"), "partes": []}
    for n, parte in enumerate(revision["partes"]):
        entrada: Documento = {"vueltos": vueltos.get(n, [])}
        if n == queda:
            if propio is not None:
                entrada["candidato"] = propio["id"]
        else:
            suyos = [a for u, a in articulos.items() if u in enlaces_parte[n]]
            base = propio or (candidatos.get(str(suyos[0].get("candidato"))) if suyos else None)
            if suyos and base is not None:
                sitio = {**base, "lugar": parte.get("lugar", base["lugar"])}
                cand = _documento_candidato(
                    sitio, _id_candidato(sitio, suyos, ocupados), suyos, base["id"]
                )
                ocupados.add(cand["id"])
                documentos.append(cand)
                entrada["candidato"] = cand["id"]
        hecho["partes"].append(entrada)
    almacen.corregir_candidatos(documentos, f"{CURSOR_SEPARAR}{id_}: {motivo}")
    hecho["conservado_perdio"] = propio is not None and propio["id"] in cambiados
    articulos_de = {d["id"]: d["articulos"] for d in documentos}
    for parte, entrada in zip(revision["partes"], hecho["partes"], strict=True):
        if "candidato" in entrada and not parte.get("es_suceso", True):
            # Lo que no es un suceso no se extrae: queda anotado, sin incidente.
            almacen.guardar_extraccion(
                entrada["candidato"], ahora.strftime("%Y-%m-%dT%H:%MZ"), ficha_version(),
                incidentes.huella(articulos_de[entrada["candidato"]]), False,
                {"motivos": [f"{MOTIVO_NO_SUCESO}: {motivo}"], "campos": {}, "incidente": None},
            )  # fmt: skip
    # El que se queda, sin las fuentes que salen. Los registros que tiene fundidos no se
    # publican y se quedan como estaban: al volver a extraerlo, solo recupera de ellos las
    # fuentes que conserva (reabsorber).
    documento = almacen.incidente(id_)
    nuevo = sin_fuentes(documento, salen) if documento is not None else None
    if nuevo is not None:
        # También si no pierde fuentes aquí: deshacer una fusión le quita las fuentes del
        # registro que vuelve, pero no los valores que trajeron.
        from exportacion.procedencia import Fichas

        nuevo = con_origen(nuevo, Fichas.de(almacen))
    if documento is not None and nuevo is not None and nuevo != documento:
        _guardar(almacen, documento, nuevo, ahora, modelos, f"separado: {motivo}", Corregidos())
    conservado = almacen.incidente(id_)
    hecho["fuentes_conservadas"] = (
        sorted(f["id"] for f in conservado["fuentes"]) if conservado else []
    )
    return hecho


def _extraer_parte(
    almacen: Almacen, cliente: Any, candidato: Documento, separado: str, ahora: datetime,
    modelos: frozenset[str],
) -> bool:  # fmt: skip
    """Una llamada al extractor para el candidato de una parte. El lugar que dio una autoridad
    (ubicaciones) se conserva en el incidente que ya lo tenía. True si deja incidente."""
    anterior = extraccion.incidente_del_candidato(almacen, candidato["id"])
    documento = almacen.incidente(anterior) if anterior else None
    oficial = (
        copy.deepcopy(documento["lugar"])
        if documento is not None and documento["lugar"].get("geocodificacion") == "oficial"
        else None
    )
    if _extraer(almacen, cliente, candidato, ahora) != 1:
        registro.warning("parte de %s sin incidente tras extraer %s", separado, candidato["id"])
        return False
    id_ = extraccion.incidente_del_candidato(almacen, candidato["id"])
    nuevo = almacen.incidente(id_) if id_ else None
    if oficial is not None and nuevo is not None and nuevo["lugar"] != oficial:
        _guardar(almacen, nuevo, {**nuevo, "lugar": oficial}, ahora, modelos,
                 MOTIVO_UBICACION, Corregidos())  # fmt: skip
    return True


def reabsorber(
    almacen: Almacen, id_: str, conservadas: set[str], ahora: datetime, modelos: frozenset[str]
) -> bool:
    """Tras volver a extraer su candidato, el incidente se rehace solo con los artículos del
    candidato: vuelve a tener las fuentes que le daban los registros que tiene fundidos, solo las
    que ya tenía al separarse (`conservadas`). True si cambia."""
    documento = almacen.incidente(id_)
    if documento is None or not incidentes.activo(documento):
        return False
    nuevo = documento
    for fusion in almacen.fusiones():
        if fusion["destino"] != id_ or fusion["revertida"]:
            continue
        absorbido = almacen.incidente(fusion["absorbido"])
        if absorbido is None:
            continue
        tiene = {f["id"] for f in nuevo["fuentes"]}
        suyas = [f for f in absorbido["fuentes"] if f["id"] in conservadas and f["id"] not in tiene]
        if not suyas:
            continue
        propio = {k: v for k, v in absorbido.items() if k != "fusionado_en"}
        propio["fuentes"] = suyas
        nuevo, _ = incidentes.absorber(nuevo, propio, ahora)
    if nuevo == documento:
        return False
    almacen.guardar_incidente(nuevo, ahora, modelos)
    return True


def _incidentes_de(almacen: Almacen, entrada: Documento) -> list[str]:
    ids = list(entrada.get("vueltos", []))
    if "candidato" in entrada:
        propio = extraccion.incidente_del_candidato(almacen, entrada["candidato"])
        if propio is not None and propio not in ids:
            ids.append(propio)
    return ids


def separar(
    almacen: Almacen, ahora: datetime, modelos: frozenset[str], cliente: Any = None
) -> Separados:
    """Separa los incidentes revisados que juntaban sucesos distintos y mantiene, en cada
    pasada, las partes extraídas, unidas a su ficha si ya la tenían y enlazadas entre sí."""
    hechos = Separados()
    relaciones: dict[str, dict[str, Documento]] = {}
    for revision in cargar().get("separar", []):
        clave = CURSOR_SEPARAR + revision["incidente"]
        hecho = almacen.cursor(clave)
        if hecho is None:
            hecho = repartir(almacen, revision, ahora, modelos)
            if hecho is None:
                continue
            almacen.guardar_cursor(clave, hecho)
            hechos.repartidos.append(revision["incidente"])
        candidatos = {c["id"]: c for c in almacen.candidatos()}
        vivos: list[str] = []
        queda = conservada(revision)
        for n, (parte, entrada) in enumerate(zip(revision["partes"], hecho["partes"], strict=True)):
            if not parte.get("es_suceso", True):
                continue
            cand = candidatos.get(str(entrada.get("candidato")))
            pendiente = (
                bool(hecho.get("conservado_perdio"))
                and cand is not None
                and extraccion.articulos_retirados(almacen, cand)
                if n == queda
                else not almacen.extracciones(str(entrada.get("candidato")))
            )
            if cand is not None and pendiente:
                # El extractor, por el camino normal de altas: la parte nueva y también la que
                # conserva el identificador, cuya ficha anterior hablaba de los dos sucesos (su
                # titular, sus datos). Sin servicio (un ensayo) o pasado el tope de la pasada,
                # queda para la siguiente o para el extractor de la horaria, que lleva delante
                # los candidatos separados.
                if (
                    cliente is not None
                    and len(hechos.extraidos) < MAX_EXTRACCIONES_PASADA
                    and _extraer_parte(almacen, cliente, cand, revision["incidente"], ahora,
                                       modelos)
                ):  # fmt: skip
                    hechos.extraidos.append(cand["id"])
                else:
                    hechos.pendientes.append(cand["id"])
            if n == queda and cand is not None and hecho.get("conservado_perdio"):
                # Ya extraído de nuevo (aquí o por el extractor de la horaria): una vez por ficha.
                ultima = (almacen.extracciones(cand["id"]) or [{}])[-1].get("fecha")
                if ultima and hecho.get("reabsorbido") != ultima and not pendiente:
                    reabsorber(
                        almacen,
                        revision["incidente"],
                        set(hecho.get("fuentes_conservadas", [])),
                        ahora,
                        modelos,
                    )
                    hecho["reabsorbido"] = ultima
                    almacen.guardar_cursor(clave, hecho)
            ids = _incidentes_de(almacen, entrada)
            if n == queda and revision["incidente"] not in ids:
                ids.insert(0, revision["incidente"])
            if parte.get("coincide_con") and ids:
                hechos.unidos += unir_grupo(
                    almacen, [*ids, parte["coincide_con"]], revision["motivo"]["es"], ahora,
                    modelos,
                )  # fmt: skip
            for propio in ids:
                documento = _vivo(almacen, propio)
                if documento is not None and documento["id"] not in vivos:
                    vivos.append(documento["id"])
        nota = {"es": revision["motivo"]["es"], "en": revision["motivo"]["en"]}
        for uno in vivos:
            for otro in vivos:
                if otro != uno:
                    relaciones.setdefault(uno, {})[otro] = {
                        "id": otro,
                        "separado_de": revision["incidente"],
                        "nota": nota,
                    }
    hechos.relacionados = _enlazar(almacen, relaciones, ahora, modelos)
    registro.info("sucesos mezclados: %s", hechos.texto())
    return hechos


def _enlazar(
    almacen: Almacen, relaciones: dict[str, dict[str, Documento]], ahora: datetime,
    modelos: frozenset[str],
) -> list[str]:  # fmt: skip
    """Cada ficha activa con sus sucesos relacionados, ni más ni menos. Devuelve las que
    cambian."""
    cambiadas = []
    for documento in almacen.incidentes():
        if not incidentes.activo(documento):
            continue
        quiere = sorted(relaciones.get(documento["id"], {}).values(), key=lambda r: r["id"])
        if documento.get("relacionados", []) == quiere:
            continue
        nuevo = {k: v for k, v in documento.items() if k != "relacionados"}
        if quiere:
            nuevo["relacionados"] = quiere
        if _guardar(almacen, documento, nuevo, ahora, modelos,
                    "sucesos relacionados de una separación (separar)", Corregidos()):  # fmt: skip
            cambiadas.append(documento["id"])
    return cambiadas
