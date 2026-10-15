"""Avisos públicos con ntfy (interno: avisos).

Al final de cada recogida horaria que publica bien (servidor/recogida.sh), se envía un aviso por
cada incidente nuevo de Europa que lo merece al tema de toda Europa (drones-europe) y al de su
país, en el servidor ntfy propio (configuracion/avisos.json). Se avisa, y nada más:

- de un incidente de Europa confirmado o atribuido, o notificado con una fuente oficial
  (autoridad, ministerio, gestor aeroportuario o de navegación aérea: origen OFICIAL en
  exportacion/procedencia.py). Una noticia de prensa sin fuente oficial no se avisa;
- con la misma regla, del cierre o la suspensión de un aeropuerto por drones que consta como
  incidente registrado (nunca solo por el detector de tráfico, que no crea incidentes);
- con prioridad alta, de la incursión en un país de la OTAN o en Moldavia desde la guerra (un
  incidente de tipo incursión unido a un ataque de la capa de guerra o con entrada desde fuera).

La capa de guerra de Ucrania y Rusia no avisa: sus ataques no son incidentes. Un incidente se
avisa una sola vez: lo enviado queda en una base propia (avisos.sqlite, en $AVISOS_DATOS) y las
actualizaciones posteriores no avisan. Solo cuentan los incidentes publicados (el enlace del aviso
lleva a su página) cuyo suceso cae en las últimas `ventana_horas` (72): un incidente antiguo que
llega tarde al registro no es un aviso. Sin base de avisos (la primera vez), todos los publicados
se anotan como ya avisados y no se envía nada: los avisos empiezan desde ese momento.

Avisos con retraso: un incidente que la barrera de titulares retuvo sin publicar
(configuracion/avisos_con_retraso.json) se avisa al publicarse si lo habría merecido al publicarse
a tiempo: la ventana se mide desde su alta en la base, no desde ahora. Su texto termina con la
nota «Aviso con retraso por un fallo de publicación» en los dos idiomas. Las demás reglas no
cambian (una sola vez por incidente, fuente oficial, prioridad).

Si un envío falla, se reintenta en la recogida siguiente: lo que salió bien queda anotado por
tema y no se repite. El resultado de cada pasada queda en $SECRETOS/avisos.json, que lee la
vigilancia (dos recogidas seguidas con fallo de envío, problema «avisos»).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from proceso import autoridades, nombres_lugar

registro = logging.getLogger("avisos")

RAIZ = Path(__file__).resolve().parent.parent
CONFIGURACION = RAIZ / "configuracion" / "avisos.json"
CON_RETRASO = RAIZ / "configuracion" / "avisos_con_retraso.json"
BASE_AVISOS = "avisos.sqlite"
ESTADO = "avisos.json"
FICHEROS_PUBLICADOS = ("incidentes.geojson", "incidentes_sin_ubicacion.json")
TIEMPO_ESPERA_S = 15
FALLOS_PARA_PROBLEMA = 2

Documento = dict[str, Any]
Enviar = Callable[[Documento], None]

FRASE_ES = {
    # (clase, estado) -> título en español; el género sigue al sustantivo.
    ("incursion", "confirmado"): "Incursión confirmada",
    ("incursion", "atribuido"): "Incursión atribuida",
    ("incursion", "notificado"): "Incursión notificada por fuente oficial",
    ("cierre", "confirmado"): "Cierre de aeropuerto confirmado",
    ("cierre", "atribuido"): "Cierre de aeropuerto atribuido",
    ("cierre", "notificado"): "Cierre de aeropuerto notificado por fuente oficial",
    ("suspension", "confirmado"): "Suspensión en aeropuerto confirmada",
    ("suspension", "atribuido"): "Suspensión en aeropuerto atribuida",
    ("suspension", "notificado"): "Suspensión en aeropuerto notificada por fuente oficial",
    ("sobrevuelo", "confirmado"): "Sobrevuelo de drones confirmado",
    ("sobrevuelo", "atribuido"): "Sobrevuelo de drones atribuido",
    ("sobrevuelo", "notificado"): "Sobrevuelo de drones notificado por fuente oficial",
}
FRASE_EN = {
    ("incursion", "confirmado"): "Confirmed incursion",
    ("incursion", "atribuido"): "Attributed incursion",
    ("incursion", "notificado"): "Incursion reported by official source",
    ("cierre", "confirmado"): "Confirmed airport closure",
    ("cierre", "atribuido"): "Attributed airport closure",
    ("cierre", "notificado"): "Airport closure reported by official source",
    ("suspension", "confirmado"): "Confirmed airport suspension",
    ("suspension", "atribuido"): "Attributed airport suspension",
    ("suspension", "notificado"): "Airport suspension reported by official source",
    ("sobrevuelo", "confirmado"): "Confirmed drone overflight",
    ("sobrevuelo", "atribuido"): "Attributed drone overflight",
    ("sobrevuelo", "notificado"): "Drone overflight reported by official source",
}
ESTADO_ES = {
    "confirmado": "confirmado",
    "atribuido": "atribuido",
    "notificado": "notificado (fuente oficial)",
}
ESTADO_EN = {
    "confirmado": "confirmed",
    "atribuido": "attributed",
    "notificado": "reported (official source)",
}
MESES_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
PRIORIDAD_ALTA, PRIORIDAD_NORMAL = 4, 3
ETIQUETA_MAPA = "Ver en el mapa / View on map"
NOTA_RETRASO = {
    "es": "Aviso con retraso por un fallo de publicación",
    "en": "Delayed alert due to a publishing fault",
}


# --- Configuración ---------------------------------------------------------------------------
def configuracion(ruta: Path = CONFIGURACION, retraso: Path = CON_RETRASO) -> Documento:
    """La configuración de los avisos, con los incidentes que se avisan con retraso en
    «con_retraso» (fichero aparte: la web importa avisos.json entero)."""
    datos: Documento = json.loads(ruta.read_text(encoding="utf-8"))
    if retraso.exists():
        datos["con_retraso"] = json.loads(retraso.read_text(encoding="utf-8"))
    return datos


def temas_publicos(config: Documento) -> list[str]:
    return [config["general"]["tema"], *(p["tema"] for p in config["paises"].values())]


# --- Qué se avisa ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Aviso:
    id: str
    pais: str
    clase: str  # incursion | cierre | suspension | sobrevuelo
    estado: str  # confirmado | atribuido | notificado
    prioridad: int
    guerra: bool
    retraso: bool = False


def _instante(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        instante = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None
    return instante if instante.tzinfo else instante.replace(tzinfo=UTC)


def momento_del_suceso(incidente: Documento) -> datetime | None:
    """Inicio del suceso; si no consta, la fecha de la primera fuente."""
    inicio = _instante(((incidente.get("tiempo") or {}).get("inicio") or {}).get("valor"))
    if inicio is not None:
        return inicio
    fechas = [_instante((f.get("fecha") or {}).get("valor")) for f in incidente.get("fuentes", [])]
    validas = [f for f in fechas if f is not None]
    return min(validas) if validas else None


def alta_retenida(incidente: Documento, config: Documento) -> datetime | None:
    """Cuándo habría salido el aviso del incidente retenido por la barrera de titulares (su alta
    en la base), o None si no está en la lista de los que se avisan con retraso o entró en la
    base antes de la fecha desde la que vale la lista."""
    retraso = config.get("con_retraso") or {}
    if str(incidente.get("id")) not in retraso.get("incidentes", {}):
        return None
    alta = _instante(((incidente.get("control") or {}).get("alta") or {}).get("valor"))
    desde = _instante(retraso.get("desde"))
    if alta is None or desde is None or alta < desde:
        return None
    return alta


def _origen(fuente: Documento) -> str:
    """Origen de la fuente según el modelo (exportacion/procedencia.py). Se importa aquí: la
    vigilancia lee este módulo y no necesita cargar el modelo entero."""
    from exportacion.procedencia import origen_de_fuente

    return origen_de_fuente(fuente)


def con_fuente_oficial(incidente: Documento) -> bool:
    from exportacion.procedencia import OFICIAL

    return any(_origen(f) == OFICIAL for f in incidente.get("fuentes", []))


def clasificar(incidente: Documento, config: Documento, ahora: datetime) -> Aviso | None:
    """El aviso que merece el incidente, o None si no se avisa."""
    if "retirado" in incidente or "fusionado_en" in incidente:
        return None
    pais = (incidente.get("lugar") or {}).get("pais")
    datos_pais = config["paises"].get(pais)
    if datos_pais is None:
        return None
    estado = (incidente.get("estado") or {}).get("actual")
    if estado not in ("confirmado", "atribuido", "notificado"):
        return None
    if estado == "notificado" and not con_fuente_oficial(incidente):
        return None
    suceso = momento_del_suceso(incidente)
    # Un retenido por la barrera se mide desde cuando se habría publicado.
    alta = alta_retenida(incidente, config)
    referencia = alta if alta is not None else ahora
    if suceso is None or referencia - suceso > timedelta(hours=config["ventana_horas"]):
        return None
    tipo = incidente.get("tipo")
    cierre = ((incidente.get("consecuencias") or {}).get("cierre") or {}).get("valor")
    pruebas = incidente.get("pruebas") or {}
    guerra = bool(incidente.get("ataque")) or bool(pruebas.get("entrada_exterior"))
    if tipo == "incursion":
        clase = "incursion"
    elif cierre == "si":
        clase = "cierre"
    elif tipo == "interrupcion_aeroportuaria":
        clase = "suspension"
    else:
        clase = "sobrevuelo"
    alta_prioridad = clase == "incursion" and guerra and (datos_pais["otan"] or pais == "MD")
    return Aviso(
        id=str(incidente["id"]),
        pais=str(pais),
        clase=clase,
        estado=str(estado),
        prioridad=PRIORIDAD_ALTA if alta_prioridad else PRIORIDAD_NORMAL,
        guerra=guerra,
        retraso=alta is not None,
    )


# --- Cómo se ve ------------------------------------------------------------------------------
def _limpio(texto: str) -> str:
    """Sin los signos que el Markdown interpretaría: el texto viene de las fuentes."""
    return " ".join(texto.replace("*", "").replace("_", " ").replace("`", "'").split())


SIN_FUENTE = {"es": "sin fuente nombrada", "en": "no source named"}


def _fuente(incidente: Documento, idioma: str = "es") -> str:
    """La fuente de más rango (exportacion/procedencia.py): la autoridad antes que la prensa. De
    una declaración citada, quien declara, sin la nota de dónde se cita; escrita en el idioma
    del aviso con la regla de la web (proceso/autoridades.py): la tabla, la traducción que viaja
    con la ficha publicada (`autoridades`) o «una autoridad»."""
    from exportacion.procedencia import RANGO

    fuentes = incidente.get("fuentes", [])
    if not fuentes:
        return SIN_FUENTE[idioma]
    elegida = min(fuentes, key=lambda f: RANGO.index(_origen(f)))
    medio = str(elegida.get("medio") or "")
    if not medio:
        return SIN_FUENTE[idioma]
    return _limpio(autoridades.de_la_fuente(medio, idioma, incidente.get("autoridades")))


def _lugar(incidente: Documento, idioma: str) -> str:
    """El lugar como lo dice la ficha en ese idioma (proceso/nombres_lugar.py): «Pafos, Chipre»."""
    return _limpio(nombres_lugar.nombres_publicos(incidente)["lugar"][idioma])


def _cuando(incidente: Documento, zona: str) -> tuple[str, str]:
    """Fecha y hora del suceso en la hora local del país y en UTC, en español y en inglés."""
    inicio = (incidente.get("tiempo") or {}).get("inicio") or {}
    instante = _instante(inicio.get("valor")) or momento_del_suceso(incidente)
    if instante is None:
        return "fecha no precisada", "date not specified"
    local = instante.astimezone(ZoneInfo(zona))
    dia_es = f"{local.day}/{local.month}/{local.year}"
    dia_en = f"{local.day} {MESES_EN[local.month - 1]} {local.year}"
    if inicio.get("precision") in ("minuto", "hora"):
        utc = instante.astimezone(UTC)
        return (
            f"{dia_es}, {local:%H:%M} hora local ({utc:%H:%M} UTC)",
            f"{dia_en}, {local:%H:%M} local time ({utc:%H:%M} UTC)",
        )
    return f"{dia_es} (hora no precisada)", f"{dia_en} (time not specified)"


def mensaje(aviso: Aviso, incidente: Documento, config: Documento, tema: str) -> Documento:
    """El mensaje de ntfy (publicación en JSON) para un tema."""
    pais = config["paises"][aviso.pais]
    clave = (aviso.clase, aviso.estado)
    titulo_es = f"{pais['es'].upper()} · {FRASE_ES[clave]}"
    titulo_en = f"{pais['en'].upper()} · {FRASE_EN[clave]}"
    titular = nombres_lugar.titulo_corregido(incidente)
    traducidas = incidente.get("autoridades")
    que_es = _limpio(autoridades.en_texto(str(titular.get("es") or FRASE_ES[clave]), "es",
                                          traducidas))  # fmt: skip
    que_en = _limpio(autoridades.en_texto(str(titular.get("en") or FRASE_EN[clave]), "en",
                                          traducidas))  # fmt: skip
    cuando_es, cuando_en = _cuando(incidente, pais["zona_horaria"])
    linea_es = (
        f"{que_es}. **{_lugar(incidente, 'es')}**, {cuando_es}. "
        f"Estado: **{ESTADO_ES[aviso.estado]}**. Fuente: {_fuente(incidente, 'es')}."
    )
    linea_en = (
        f"{titulo_en}. {que_en}. **{_lugar(incidente, 'en')}**, {cuando_en}. "
        f"Status: **{ESTADO_EN[aviso.estado]}**. Source: {_fuente(incidente, 'en')}."
    )
    texto = f"{linea_es}\n\n{linea_en}"
    if aviso.retraso:
        nota = (config.get("con_retraso") or {}).get("nota") or NOTA_RETRASO
        texto += f"\n\n{nota['es']}. / {nota['en']}."
    enlace = f"{config['sitio']}/{aviso.id}"
    return {
        "topic": tema,
        "title": titulo_es,
        "message": texto,
        "markdown": True,
        "priority": aviso.prioridad,
        "click": enlace,
        "icon": config["icono"],
        "actions": [{"action": "view", "label": ETIQUETA_MAPA, "url": enlace}],
    }


# --- Envío -----------------------------------------------------------------------------------
def enviador(servidor: str, token: str) -> Enviar:
    """Publica un mensaje en ntfy (POST en JSON a la raíz del servidor) con el token."""

    def enviar(cuerpo: Documento) -> None:
        peticion = urllib.request.Request(
            servidor.rstrip("/") + "/",
            data=json.dumps(cuerpo, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(peticion, timeout=TIEMPO_ESPERA_S) as respuesta:
            if respuesta.status != 200:
                raise urllib.error.HTTPError(
                    peticion.full_url,
                    respuesta.status,
                    "respuesta inesperada",
                    respuesta.headers,
                    None,
                )

    return enviar


# --- Lo publicado y lo enviado -----------------------------------------------------------------
def ids_publicados(carpeta: Path) -> set[str]:
    """Los incidentes que están en la web (con punto y sin ubicación)."""
    ids: set[str] = set()
    mapa = carpeta / FICHEROS_PUBLICADOS[0]
    if mapa.exists():
        for rasgo in json.loads(mapa.read_text(encoding="utf-8")).get("features", []):
            ids.add(str(rasgo.get("id") or rasgo["properties"]["id"]))
    sin_punto = carpeta / FICHEROS_PUBLICADOS[1]
    if sin_punto.exists():
        for incidente in json.loads(sin_punto.read_text(encoding="utf-8")).get("incidentes", []):
            ids.add(str(incidente["id"]))
    return ids


def autoridades_publicadas(carpeta: Path) -> dict[str, Documento]:
    """Las autoridades traducidas que viajan con cada ficha publicada (`autoridades`,
    exportacion/citas.con_autoridades): los avisos las escriben como la web."""
    resultado: dict[str, Documento] = {}
    mapa = carpeta / FICHEROS_PUBLICADOS[0]
    if mapa.exists():
        for rasgo in json.loads(mapa.read_text(encoding="utf-8")).get("features", []):
            propiedades = rasgo.get("properties") or {}
            if propiedades.get("autoridades"):
                id_ = str(rasgo.get("id") or propiedades["id"])
                resultado[id_] = dict(propiedades["autoridades"])
    sin_punto = carpeta / FICHEROS_PUBLICADOS[1]
    if sin_punto.exists():
        for incidente in json.loads(sin_punto.read_text(encoding="utf-8")).get("incidentes", []):
            if incidente.get("autoridades"):
                resultado[str(incidente["id"])] = dict(incidente["autoridades"])
    return resultado


def con_autoridades(internos: dict[str, Documento], carpeta: Path) -> dict[str, Documento]:
    """Los documentos internos con las autoridades traducidas de su ficha publicada."""
    traducidas = autoridades_publicadas(carpeta)
    return {
        id_: {**documento, "autoridades": traducidas[id_]} if id_ in traducidas else documento
        for id_, documento in internos.items()
    }


def documentos(base: Path, ids: Iterable[str]) -> dict[str, Documento]:
    """Los documentos internos de esos incidentes, leídos sin escribir en la base."""
    lista = sorted(ids)
    if not lista:
        return {}
    conexion = sqlite3.connect(f"{base.resolve().as_uri()}?mode=ro", uri=True)
    try:
        resultado: dict[str, Documento] = {}
        for i in range(0, len(lista), 500):
            trozo = lista[i : i + 500]
            filas = conexion.execute(
                f"SELECT id, documento FROM incidentes WHERE id IN ({','.join('?' * len(trozo))})",
                trozo,
            ).fetchall()
            resultado.update({str(i_): json.loads(d) for i_, d in filas})
        return resultado
    finally:
        conexion.close()


def unidos_en(base: Path) -> dict[str, set[str]]:
    """Los registros fundidos en cada incidente (fusiones no revertidas, también en cadena),
    leídos sin escribir en la base: un suceso ya avisado con otro número no se vuelve a avisar
    cuando se une a otro registro (recogida/control_fichas.py)."""
    conexion = sqlite3.connect(f"{base.resolve().as_uri()}?mode=ro", uri=True)
    try:
        filas = conexion.execute(
            "SELECT absorbido, destino FROM fusiones WHERE revertida = 0 ORDER BY id"
        ).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        conexion.close()
    destino = {str(a): str(d) for a, d in filas}
    unidos: dict[str, set[str]] = {}
    for absorbido in destino:
        final, vistos = absorbido, set()
        while final in destino and final not in vistos:
            vistos.add(final)
            final = destino[final]
        unidos.setdefault(final, set()).add(absorbido)
    return unidos


class Enviados:
    """Lo ya avisado, por incidente y tema, en una base propia (no toca la del observatorio).
    Lo anotado con el nombre anterior de un tema (`temas_anteriores` de la configuración: general,
    slovakia...) cuenta como enviado al tema que lo sustituye, para no repetir avisos."""

    def __init__(self, ruta: Path, anteriores: dict[str, str] | None = None) -> None:
        self._anteriores = dict(anteriores or {})
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self._conexion = sqlite3.connect(ruta)
        self._conexion.executescript(
            "CREATE TABLE IF NOT EXISTS avisos ("
            " id TEXT NOT NULL, tema TEXT NOT NULL, momento TEXT NOT NULL,"
            " inicial INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (id, tema));"
            "CREATE TABLE IF NOT EXISTS activacion (momento TEXT NOT NULL);"
        )
        self._conexion.commit()

    @property
    def nueva(self) -> bool:
        """Sin activar todavía: la primera pasada anota los existentes y no envía nada."""
        filas: int = self._conexion.execute("SELECT COUNT(*) FROM activacion").fetchone()[0]
        return filas == 0

    def activar(self, publicados: Iterable[str], ahora: datetime) -> None:
        momento = ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._conexion:
            self._conexion.executemany(
                "INSERT OR IGNORE INTO avisos (id, tema, momento, inicial) VALUES (?, '*', ?, 1)",
                [(id_, momento) for id_ in sorted(publicados)],
            )
            self._conexion.execute("INSERT INTO activacion (momento) VALUES (?)", (momento,))

    def cerrar(self) -> None:
        self._conexion.close()

    def incidentes(self) -> set[str]:
        return {r[0] for r in self._conexion.execute("SELECT DISTINCT id FROM avisos")}

    def temas(self, id_: str) -> set[str]:
        return {
            self._anteriores.get(r[0], r[0])
            for r in self._conexion.execute("SELECT tema FROM avisos WHERE id = ?", (id_,))
        }

    def iniciales(self) -> set[str]:
        return {r[0] for r in self._conexion.execute("SELECT id FROM avisos WHERE inicial = 1")}

    def anotar(self, id_: str, tema: str, ahora: datetime, inicial: bool = False) -> None:
        self._conexion.execute(
            "INSERT OR IGNORE INTO avisos (id, tema, momento, inicial) VALUES (?, ?, ?, ?)",
            (id_, tema, ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), int(inicial)),
        )
        self._conexion.commit()


@dataclass
class Pasada:
    enviados: int = 0
    fallidos: int = 0
    marcados: int = 0
    error: str | None = None


def pasar(
    publicados: set[str],
    internos: dict[str, Documento],
    enviados: Enviados,
    config: Documento,
    ahora: datetime,
    enviar: Enviar | None,
    unidos: dict[str, set[str]] | None = None,
) -> Pasada:
    """Una pasada: anota los existentes la primera vez; si no, envía los avisos que faltan.
    Con `enviar` None, ensayo: dice lo que enviaría sin enviar ni anotar. Lo avisado con el
    número de un registro que se unió después a otro cuenta como avisado para el que queda
    (`unidos`): el mismo suceso no se avisa dos veces."""
    pasada = Pasada()
    if enviados.nueva:
        pasada.marcados = len(publicados)
        if enviar is not None:
            enviados.activar(publicados, ahora)
        registro.info("primera pasada: %d incidentes anotados como ya avisados", pasada.marcados)
        return pasada
    ya = enviados.iniciales()
    general = config["general"]["tema"]
    for id_ in sorted(publicados - ya):
        incidente = internos.get(id_)
        if incidente is None:
            continue
        aviso = clasificar(incidente, config, ahora)
        if aviso is None:
            continue
        hechos = enviados.temas(id_)
        for otro in sorted((unidos or {}).get(id_, set())):
            hechos |= enviados.temas(otro)
        if "*" in hechos:
            # Unido a uno anotado como ya avisado en la primera pasada.
            continue
        # Un solo aviso por incidente: si ya salió a un país, no sale a otro aunque cambie.
        pais_hecho = bool(hechos - {general})
        for tema in (general, config["paises"][aviso.pais]["tema"]):
            if tema in hechos or (tema != general and pais_hecho):
                continue
            cuerpo = mensaje(aviso, incidente, config, tema)
            if enviar is None:
                registro.info(
                    "ensayo: %s a %s: %s%s",
                    id_,
                    tema,
                    cuerpo["title"],
                    " (con retraso)" if aviso.retraso else "",
                )
                pasada.enviados += 1
                continue
            try:
                enviar(cuerpo)
            except (urllib.error.URLError, OSError, ValueError) as error:
                pasada.fallidos += 1
                pasada.error = f"{type(error).__name__}: {error}"[:200]
                registro.warning("aviso de %s a %s sin enviar: %s", id_, tema, pasada.error)
                continue
            enviados.anotar(id_, tema, ahora)
            pasada.enviados += 1
            registro.info(
                "aviso de %s enviado a %s (prioridad %d%s)",
                id_,
                tema,
                aviso.prioridad,
                ", con retraso" if aviso.retraso else "",
            )
    return pasada


# --- Estado para la vigilancia ---------------------------------------------------------------
def guardar_estado(ruta: Path, pasada: Pasada, ahora: datetime) -> Documento:
    anterior: Documento = {}
    if ruta.exists():
        try:
            anterior = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            anterior = {}
    fallo = pasada.fallidos > 0
    estado = {
        "ultima": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "enviados": pasada.enviados,
        "fallidos": pasada.fallidos,
        "fallos_seguidos": (int(anterior.get("fallos_seguidos", 0)) + 1) if fallo else 0,
        "error": pasada.error,
        "ultimo_envio": (
            ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
            if pasada.enviados
            else anterior.get("ultimo_envio")
        ),
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(estado, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)
    return estado


def problema_para_vigilancia(estado: Documento) -> str | None:
    """La frase del problema si los envíos han fallado dos recogidas seguidas."""
    seguidos = int(estado.get("fallos_seguidos", 0) or 0)
    if seguidos < FALLOS_PARA_PROBLEMA:
        return None
    return (
        f"Los avisos de ntfy han fallado {seguidos} recogidas seguidas"
        + (f" ({estado['error']})" if estado.get("error") else "")
        + ": se reintentan en la siguiente."
    )


# --- Órdenes ---------------------------------------------------------------------------------
def principal(argumentos: list[str] | None = None, ahora: datetime | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = analizador.add_subparsers(dest="orden", required=True)
    for nombre in ("enviar", "ensayo"):
        orden = sub.add_parser(nombre)
        orden.add_argument("--publicacion", type=Path, required=True)
        orden.add_argument("--base", type=Path, required=True)
        orden.add_argument("--datos", type=Path, required=True, help="carpeta de avisos.sqlite")
        orden.add_argument("--estado", type=Path, help="avisos.json para la vigilancia")
        orden.add_argument("--token", type=Path, help="fichero con el token de observatorio")
    ejemplo = sub.add_parser("ejemplo", help="envía un incidente a un tema de pruebas, sin anotar")
    ejemplo.add_argument("--base", type=Path, required=True)
    ejemplo.add_argument("--publicacion", type=Path, help="para las autoridades traducidas")
    ejemplo.add_argument("--id", required=True)
    ejemplo.add_argument("--tema", required=True)
    ejemplo.add_argument("--clase", choices=("incursion", "cierre", "suspension", "sobrevuelo"))
    ejemplo.add_argument("--prioridad", type=int, choices=(3, 4))
    ejemplo.add_argument("--token", type=Path, required=True)
    args = analizador.parse_args(argumentos)
    ahora = ahora or datetime.now(UTC)
    config = configuracion()

    if args.orden == "ejemplo":
        if args.tema in temas_publicos(config) or args.tema in config.get("temas_anteriores", {}):
            registro.error("los ejemplos van a un tema de pruebas, nunca a uno público")
            return 1
        incidente = documentos(args.base, [args.id]).get(args.id)
        if incidente is not None and args.publicacion is not None:
            incidente = con_autoridades({args.id: incidente}, args.publicacion)[args.id]
        if incidente is None:
            registro.error("%s no está en la base", args.id)
            return 1
        pais = incidente["lugar"]["pais"]
        aviso = Aviso(
            id=args.id,
            pais=pais,
            clase=args.clase or "sobrevuelo",
            estado=incidente["estado"]["actual"]
            if incidente["estado"]["actual"] != "desmentido"
            else "notificado",
            prioridad=args.prioridad or PRIORIDAD_NORMAL,
            guerra=bool(incidente.get("ataque")),
        )
        cuerpo = mensaje(aviso, incidente, config, args.tema)
        enviador(config["servidor"], args.token.read_text(encoding="utf-8").strip())(cuerpo)
        print(json.dumps(cuerpo, ensure_ascii=False, indent=1))
        return 0

    publicados = ids_publicados(args.publicacion)
    internos = con_autoridades(documentos(args.base, publicados), args.publicacion)
    enviados = Enviados(args.datos / BASE_AVISOS, config.get("temas_anteriores"))
    try:
        if args.orden == "ensayo":
            pasada = pasar(
                publicados, internos, enviados, config, ahora, None, unidos_en(args.base)
            )
            print(
                f"ensayo: {pasada.enviados} avisos se enviarían"
                + (
                    f"; primera pasada: {pasada.marcados} se anotarían como ya avisados"
                    if pasada.marcados
                    else ""
                )
            )
            return 0
        if args.token is None or not args.token.exists():
            registro.error("falta el token de observatorio")
            pasada = Pasada(fallidos=1, error="falta el token")
        else:
            token = args.token.read_text(encoding="utf-8").strip()
            pasada = pasar(
                publicados,
                internos,
                enviados,
                config,
                ahora,
                enviador(config["servidor"], token),
                unidos_en(args.base),
            )
    finally:
        enviados.cerrar()
    if args.estado is not None:
        guardar_estado(args.estado, pasada, ahora)
    print(
        f"avisos: {pasada.enviados} enviados, {pasada.fallidos} sin enviar"
        + (f", {pasada.marcados} anotados como ya avisados" if pasada.marcados else "")
    )
    return 1 if pasada.fallidos else 0


if __name__ == "__main__":
    sys.exit(principal())
