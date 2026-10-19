"""Segunda lectura de lo publicado con un servicio secundario de modelos (docs/segunda_lectura.md).

Una capa gratuita y prescindible: si el servicio se cae o desaparece, el observatorio sigue
exactamente igual. **No decide nada**: nunca publica, retira, une, separa ni cambia un estado, una
presencia ni un dato. Solo marca candidatos, que pasan por el circuito de siempre.

Dos partes, separadas:

- **La pasada** (`python -m recogida.segunda_lectura pasada`), con su propio temporizador en el
  servidor y su propia base (`segunda_lectura.sqlite`, en su carpeta de datos). Lee la base
  principal **solo para leer** (abierta en modo de solo lectura) y nunca escribe en ella. Hace:
  1. la segunda lectura de las fichas publicadas (lo nunca leído, lo que cambió y después la
     lectura más antigua): cada dato clave «apoyado», «contradicho» o «sin apoyo» por las citas
     literales de sus fuentes, y si la ficha parece resumir varios sucesos;
  2. los posibles duplicados con márgenes más amplios que los del control;
  3. una vez al día, en la primera pasada desde las 02:00 UTC, el barrido de rectificaciones
     sobre todo lo publicado con presencia confirmada, no confirmada o no acreditada.
  Si el servicio falla, se anota en el registro y se sigue en la pasada siguiente; con 3 fallos
  seguidos, la pasada termina. Nunca avisa y siempre sale con código 0.
- **El paso de la recogida horaria** (`paso_horario`): lee los candidatos de esa base (aislado,
  con un tope de 30 s; si no está, está bloqueada o rota, no hace nada) y los manda al circuito
  existente, como mucho `por_recogida` por recogida: los de datos, a la verificación del control
  de las fichas hecha por el experto; los duplicados, a su comparación hecha por el experto; los
  de rectificaciones, a la cola del barrido mensual (recogida/rectificaciones.encolar). El
  experto los paga con el modo «segunda_lectura» (0,10 dólares al día dentro de su tope normal,
  nunca de la reserva crítica); lo que no cabe espera al día siguiente. Lo que decide el experto
  se aplica con las reglas de siempre y queda guardado (clave `segunda:…` del control de las
  fichas) para no repetirlo. Nunca cambia el código de salida de la recogida.

Se desactiva quitando EODI_SECUNDARIO_URL: la pasada no hace nada y la recogida no lee nada.
"""

import argparse
import json
import logging
import sqlite3
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from almacen.sitio import casa
from esquema import Documento
from modelo import control as peticiones
from modelo import coste, secundario
from modelo.cliente import LlamadaFallida
from proceso import control_fichas as reglas
from proceso import incidentes
from proceso import segunda_lectura as lectura
from recogida import control_fichas, rectificaciones
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger(__name__)

CONFIGURACION = Path(__file__).resolve().parent.parent / "configuracion" / "segunda_lectura.json"
VARIABLE_DATOS = "EODI_SEGUNDA_LECTURA_DATOS"
DATOS = casa() / "datos" / "segunda_lectura"
BASE = "segunda_lectura.sqlite"
ESTADO = "segunda_lectura.json"
# Las decisiones del experto sobre lo marcado, en el control de las fichas.
PREFIJO = "segunda:"
CAMPOS, DUPLICADO, RECTIFICACION = "campos", "duplicado", "rectificacion"
MOTIVO = "segunda lectura"

ESQUEMA_SQL = """
CREATE TABLE IF NOT EXISTS lecturas (
    id TEXT PRIMARY KEY, huella TEXT NOT NULL, fecha TEXT NOT NULL, hallazgos TEXT NOT NULL,
    invalida INTEGER NOT NULL DEFAULT 0, version TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pares (
    clave TEXT PRIMARY KEY, huella TEXT NOT NULL, fecha TEXT NOT NULL, decision TEXT NOT NULL,
    motivo TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS titulares (clave TEXT PRIMARY KEY, fecha TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS candidatos (
    clave TEXT PRIMARY KEY, tipo TEXT NOT NULL, incidente TEXT NOT NULL, otro TEXT,
    fecha TEXT NOT NULL, vigente INTEGER NOT NULL DEFAULT 1, datos TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pasadas (
    id INTEGER PRIMARY KEY, inicio TEXT NOT NULL, fin TEXT NOT NULL, resumen TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS estado (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS busquedas (
    clave TEXT PRIMARY KEY, huella TEXT NOT NULL, fecha TEXT NOT NULL, hallados INTEGER NOT NULL);
"""
TAREAS_LECTURA = frozenset({"lectura", "pares", "rectificaciones"})
# La pasada del temporizador: también las búsquedas de lo que falta y el barrido del país.
TAREAS = TAREAS_LECTURA | {"busqueda", "pais"}


@cache
def configuracion() -> Documento:
    datos: Documento = json.loads(CONFIGURACION.read_text(encoding="utf-8"))
    return datos


def directorio_datos() -> Path:
    import os

    return Path(os.environ.get(VARIABLE_DATOS) or DATOS)


def activa() -> bool:
    """La capa está activa si el servicio secundario está configurado."""
    return secundario.configuracion() is not None


def _iso(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json(datos: Any) -> str:
    return json.dumps(datos, ensure_ascii=False, sort_keys=True)


# --- La base propia ------------------------------------------------------------------------


class Propia:
    """La base de la capa: lo leído, lo comparado, los titulares vistos y los candidatos."""

    def __init__(self, conexion: sqlite3.Connection) -> None:
        self.conexion = conexion
        conexion.executescript(ESQUEMA_SQL)

    @classmethod
    def abrir(cls, ruta: Path) -> "Propia":
        ruta.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        return cls(sqlite3.connect(ruta, timeout=30))

    def cerrar(self) -> None:
        self.conexion.close()

    def lecturas(self) -> dict[str, tuple[str, str]]:
        filas = self.conexion.execute("SELECT id, huella, fecha FROM lecturas").fetchall()
        return {i: (h, f) for i, h, f in filas}

    def guardar_lectura(self, id_: str, huella: str, fecha: str,
                        hallazgos: list[lectura.Hallazgo] | None) -> None:  # fmt: skip
        with self.conexion:
            self.conexion.execute(
                "INSERT INTO lecturas (id, huella, fecha, hallazgos, invalida, version) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO UPDATE SET "
                "huella = excluded.huella, fecha = excluded.fecha, hallazgos = excluded.hallazgos, "
                "invalida = excluded.invalida, version = excluded.version",
                (id_, huella, fecha, _json([h.documento() for h in hallazgos or []]),
                 int(hallazgos is None), lectura.VERSION),
            )  # fmt: skip

    def par(self, clave: str) -> str | None:
        fila = self.conexion.execute(
            "SELECT huella FROM pares WHERE clave = ?", (clave,)
        ).fetchone()
        return str(fila[0]) if fila else None

    def guardar_par(self, clave: str, huella: str, fecha: str, decision: str, motivo: str) -> None:
        with self.conexion:
            self.conexion.execute(
                "INSERT INTO pares (clave, huella, fecha, decision, motivo) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (clave) DO UPDATE SET huella = excluded.huella, "
                "fecha = excluded.fecha, decision = excluded.decision, motivo = excluded.motivo",
                (clave, huella, fecha, decision, motivo[:500]),
            )

    def titulares_vistos(self) -> set[str]:
        return {f[0] for f in self.conexion.execute("SELECT clave FROM titulares").fetchall()}

    def ver_titulares(self, claves: list[str], fecha: str) -> None:
        with self.conexion:
            self.conexion.executemany(
                "INSERT OR IGNORE INTO titulares (clave, fecha) VALUES (?, ?)",
                [(c, fecha) for c in claves],
            )

    def marcar(self, clave: str, tipo: str, incidente: str, otro: str | None, fecha: str,
               datos: Documento) -> None:  # fmt: skip
        with self.conexion:
            self.conexion.execute(
                "INSERT INTO candidatos (clave, tipo, incidente, otro, fecha, vigente, datos) "
                "VALUES (?, ?, ?, ?, ?, 1, ?) ON CONFLICT (clave) DO UPDATE SET vigente = 1",
                (clave, tipo, incidente, otro, fecha, _json(datos)),
            )

    def superar(self, tipo: str, incidente: str, salvo: str | None = None) -> None:
        """Los candidatos anteriores de una ficha ya no valen (se volvió a leer)."""
        with self.conexion:
            self.conexion.execute(
                "UPDATE candidatos SET vigente = 0 WHERE tipo = ? AND incidente = ? "
                "AND clave IS NOT ?",
                (tipo, incidente, salvo),
            )

    def candidatos(self) -> list[Documento]:
        return _filas_candidatos(self.conexion)

    def estado(self, clave: str) -> str | None:
        fila = self.conexion.execute(
            "SELECT valor FROM estado WHERE clave = ?", (clave,)
        ).fetchone()
        return str(fila[0]) if fila else None

    def fijar(self, clave: str, valor: str) -> None:
        with self.conexion:
            self.conexion.execute(
                "INSERT INTO estado (clave, valor) VALUES (?, ?) "
                "ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor",
                (clave, valor),
            )

    def busqueda(self, clave: str) -> str | None:
        """La huella de lo último que se mandó en esa búsqueda, o None."""
        fila = self.conexion.execute(
            "SELECT huella FROM busquedas WHERE clave = ?", (clave,)
        ).fetchone()
        return str(fila[0]) if fila else None

    def guardar_busqueda(self, clave: str, huella: str, fecha: str, hallados: int) -> None:
        with self.conexion:
            self.conexion.execute(
                "INSERT INTO busquedas (clave, huella, fecha, hallados) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (clave) DO UPDATE SET huella = excluded.huella, "
                "fecha = excluded.fecha, hallados = excluded.hallados",
                (clave, huella, fecha, hallados),
            )

    def guardar_pasada(self, inicio: str, fin: str, resumen: Documento) -> None:
        with self.conexion:
            self.conexion.execute(
                "INSERT INTO pasadas (inicio, fin, resumen) VALUES (?, ?, ?)",
                (inicio, fin, _json(resumen)),
            )


def _filas_candidatos(conexion: sqlite3.Connection) -> list[Documento]:
    filas = conexion.execute(
        "SELECT clave, tipo, incidente, otro, fecha, datos FROM candidatos WHERE vigente = 1 "
        "ORDER BY fecha DESC, clave"
    ).fetchall()
    resultado = []
    for clave, tipo, incidente, otro, fecha, datos in filas:
        try:
            resultado.append({
                "clave": str(clave), "tipo": str(tipo), "incidente": str(incidente),
                "otro": otro, "fecha": str(fecha), "datos": json.loads(datos),
            })  # fmt: skip
        except (TypeError, ValueError):
            continue
    return resultado


# --- La pasada -----------------------------------------------------------------------------


@dataclass
class Resumen:
    inicio: str = ""
    fin: str = ""
    leidas: int = 0
    invalidas: int = 0
    con_hallazgos: list[str] = field(default_factory=list)
    pares_vistos: int = 0
    duplicados: list[str] = field(default_factory=list)
    rectificaciones: Documento = field(default_factory=dict)
    busquedas: Documento = field(default_factory=dict)
    barrido_pais: Documento = field(default_factory=dict)
    fallos: int = 0
    errores: list[str] = field(default_factory=list)
    parada: str | None = None
    peticiones: int = 0

    def documento(self) -> Documento:
        return {
            "inicio": self.inicio, "fin": self.fin, "leidas": self.leidas,
            "invalidas": self.invalidas, "con_hallazgos": len(self.con_hallazgos),
            "fichas_con_hallazgos": self.con_hallazgos[:50], "pares_vistos": self.pares_vistos,
            "duplicados": self.duplicados[:50], "rectificaciones": self.rectificaciones,
            "busquedas": self.busquedas, "barrido_pais": self.barrido_pais,
            "fallos": self.fallos, "errores": self.errores[:10], "parada": self.parada,
            "peticiones": self.peticiones,
        }  # fmt: skip


class Lector:
    """Las preguntas al servicio secundario de una pasada, con su tiempo y sus fallos seguidos."""

    def __init__(self, cliente: secundario.Cliente, hasta: float,
                 reloj: Callable[[], float], resumen: Resumen) -> None:  # fmt: skip
        self.cliente, self.hasta, self.reloj, self.resumen = cliente, hasta, reloj, resumen
        self.seguidos = 0
        self.tope_fallos = int(configuracion()["ritmo"]["fallos_seguidos"])
        cliente.hasta = hasta

    @property
    def parado(self) -> bool:
        return self.resumen.parada is not None

    def preguntar(self, instrucciones: str, contenido: str, nombre: str,
                  esquema: Documento, max_tokens: int) -> Documento | None:  # fmt: skip
        """La respuesta válida, o None (inválida o servicio caído: se anota y se sigue)."""
        if self.parado:
            return None
        # Una petición entera tiene que caber antes del final de la pasada.
        if self.reloj() + self.cliente.ritmo.limite_s > self.hasta:
            self.resumen.parada = "tiempo"
            return None
        try:
            respuesta = self.cliente.json(lectura.con_esquema(instrucciones, esquema), contenido,
                                          nombre, esquema, max_tokens)  # fmt: skip
        except secundario.SinTiempo:
            self.resumen.parada = "tiempo"
            return None
        except secundario.ServicioCaido as error:
            self.seguidos += 1
            self.resumen.fallos += 1
            self.resumen.errores.append(str(error)[:200])
            registro.info("servicio secundario: %s", str(error)[:200])
            if self.seguidos >= self.tope_fallos:
                self.resumen.parada = f"{self.seguidos} fallos seguidos del servicio"
            return None
        except secundario.RespuestaInvalida as error:
            self.seguidos = 0
            self.resumen.invalidas += 1
            registro.info("servicio secundario: respuesta inválida (%s)", str(error)[:150])
            return None
        self.seguidos = 0
        if not lectura.valida(respuesta, esquema):
            self.resumen.invalidas += 1
            return None
        return respuesta


def publicadas(principal: Almacen) -> list[Documento]:
    """Las fichas que se ven en la web: vigentes, no retenidas y con fuentes públicas."""
    retenidas = control_fichas.retenidos(principal)
    return [
        d for d in principal.incidentes()
        if incidentes.activo(d) and d["id"] not in retenidas and control_fichas._publicas(d)
    ]  # fmt: skip


@dataclass
class Leida:
    datos: dict[str, str]
    citas: list[lectura.Cita]
    huella: str


def preparar(principal: Almacen, fichas: list[Documento]) -> dict[str, Leida]:
    """Lo que se manda de cada ficha, con su huella."""
    enlaces = [str(f["enlace"]) for d in fichas for f in control_fichas._publicas(d)
               if f.get("enlace")]  # fmt: skip
    titulares = {a["url"]: str(a["titular"]) for a in principal.articulos_de(enlaces)}
    resultado = {}
    for d in fichas:
        datos = lectura.ficha(d)
        citas = lectura.citas_de(control_fichas._publicas(d), titulares)
        if citas:
            resultado[d["id"]] = Leida(datos, citas, lectura.huella(datos, citas))
    return resultado


def leer_fichas(principal: Almacen, propia: Propia, lector: Lector, ahora: datetime,
                leidas: dict[str, Leida], maximo: int | None) -> None:  # fmt: skip
    """La segunda lectura de las fichas, en su orden, hasta el final de la pasada."""
    orden = lectura.orden_lectura({i: v.huella for i, v in leidas.items()}, propia.lecturas())
    for id_ in orden[:maximo] if maximo is not None else orden:
        if lector.parado:
            return
        leida = leidas[id_]
        respuesta = lector.preguntar(lectura.INSTRUCCIONES,
                                     lectura.contenido(leida.datos, leida.citas), "lectura",
                                     lectura.ESQUEMA, lectura.MAX_SALIDA)  # fmt: skip
        if respuesta is None:
            if lector.parado:
                return
            if lector.seguidos == 0:
                # Respuesta inválida: se descarta y la ficha vuelve a leerse otro día.
                propia.guardar_lectura(id_, leida.huella, _iso(ahora), None)
            continue
        hallados = lectura.hallazgos(respuesta, leida.datos, leida.citas)
        lector.resumen.leidas += 1
        propia.guardar_lectura(id_, leida.huella, _iso(ahora), hallados)
        clave = f"{CAMPOS}:{id_}:{leida.huella}"
        propia.superar(CAMPOS, id_, clave if hallados else None)
        if hallados:
            propia.marcar(clave, CAMPOS, id_, None, _iso(ahora), {
                "huella": leida.huella, "hallazgos": [h.documento() for h in hallados],
            })  # fmt: skip
            lector.resumen.con_hallazgos.append(id_)


def comparar_pares(principal: Almacen, propia: Propia, lector: Lector, ahora: datetime,
                   fichas: list[Documento], leidas: dict[str, Leida],
                   maximo: int) -> None:  # fmt: skip
    """Los posibles duplicados con márgenes amplios que el control no compara."""
    margen = configuracion()["pares"]
    ya = set(principal.controles("par:"))
    vistos = 0
    for a, b in lectura.pares_amplios(fichas, float(margen["horas"]), float(margen["km"]), ya):
        if lector.parado or vistos >= maximo:
            return
        la, lb = leidas.get(a["id"]), leidas.get(b["id"])
        if la is None or lb is None:
            continue
        clave = reglas.clave_par(a["id"], b["id"])
        huella = la.huella + lb.huella
        if propia.par(clave) == huella:
            continue
        contenido = lectura.contenido_par(la.datos, la.citas, lb.datos, lb.citas)
        respuesta = lector.preguntar(lectura.INSTRUCCIONES_PAR, contenido, "par",
                                     lectura.ESQUEMA_PAR, lectura.MAX_SALIDA_PAR)  # fmt: skip
        if respuesta is None:
            if lector.parado:
                return
            continue
        vistos += 1
        lector.resumen.pares_vistos += 1
        mismo = lectura.mismo_suceso(respuesta, la.citas, lb.citas)
        propia.guardar_par(clave, huella, _iso(ahora), "mismo" if mismo else
                           str(respuesta["decision"]), str(respuesta["motivo"]))  # fmt: skip
        if mismo:
            propia.marcar(f"{DUPLICADO}:{clave.removeprefix('par:')}:{huella}", DUPLICADO,
                          a["id"], b["id"], _iso(ahora),
                          {"huella": huella, "motivo": str(respuesta["motivo"])[:500],
                           "frase_a": respuesta["frase_a"],
                           "frase_b": respuesta["frase_b"]})  # fmt: skip
            lector.resumen.duplicados.append(clave.removeprefix("par:"))


def toca_diaria(propia: Propia, ahora: datetime) -> bool:
    hora = int(configuracion()["rectificaciones"]["hora_utc"])
    return ahora.hour >= hora and propia.estado("diaria") != coste.dia(ahora)


def barrido_diario(principal: Almacen, propia: Propia, lector: Lector, ahora: datetime,
                   maximo: int | None) -> Documento:  # fmt: skip
    """Los titulares posteriores de cada incidente publicado (con presencia confirmada, no
    confirmada o no acreditada y al menos un día) que suenan a rectificación y nombran su lugar,
    con la selección del barrido mensual. El modelo secundario dice cuáles merecen la pregunta al
    experto; lo elegido queda como candidato y la recogida lo pone en la cola del mensual."""
    desde = propia.estado("diaria_desde") or (ahora - timedelta(days=400)).strftime("%Y-%m-%d")
    por_incidente = rectificaciones.titulares_mensuales(
        principal, ahora, desde, rectificaciones.PRESENCIAS_DIARIAS,
        int(configuracion()["rectificaciones"]["dias_desde_el_suceso"]),
    )  # fmt: skip
    por_id = {d["id"]: d for d in principal.incidentes()}
    vistos = propia.titulares_vistos()
    decididas = {c.removeprefix(rectificaciones.PREFIJO)
                 for c in principal.controles(rectificaciones.PREFIJO + "mensual:")}  # fmt: skip
    cola = (principal.cursor(rectificaciones.CURSOR_MENSUAL) or {}).get("pendientes") or []
    en_cola = {rectificaciones.clave_titular(p) for p in cola}
    hecho: Documento = {"incidentes": len(por_incidente), "preguntados": 0, "elegidos": 0}
    completo = True
    for id_, articulos in sorted(por_incidente.items()):
        nuevos = []
        for articulo in articulos:
            elegido = {"incidente": id_, **articulo}
            clave = rectificaciones.clave_titular(elegido)
            if clave not in vistos and clave not in decididas and clave not in en_cola:
                nuevos.append((clave, elegido))
        if not nuevos:
            continue
        if lector.parado or (maximo is not None and hecho["preguntados"] >= maximo):
            completo = False
            break
        lineas = [f"{n}. ({a['medio']}, {str(a['fecha'])[:10]}) {a['titular']}"
                  for n, (_, a) in enumerate(nuevos[:lectura.MAX_TITULARES], 1)]  # fmt: skip
        contenido = ("Ficha:\n" + "\n".join(f"- {k}: {v}" for k, v in
                     rectificaciones.ficha(por_id[id_]).items()) + "\n\nTitulares:\n"
                     + "\n".join(lineas))  # fmt: skip
        respuesta = lector.preguntar(lectura.INSTRUCCIONES_RECTIFICACION, contenido,
                                     "rectificacion", lectura.ESQUEMA_RECTIFICACION,
                                     lectura.MAX_SALIDA_RECTIFICACION)  # fmt: skip
        if respuesta is None:
            completo = False
            if lector.parado:
                break
            continue
        hecho["preguntados"] += 1
        enviados = nuevos[: lectura.MAX_TITULARES]
        for numero in lectura.elegidos(respuesta, len(enviados)):
            clave, elegido = enviados[numero - 1]
            propia.marcar(f"{RECTIFICACION}:{clave}", RECTIFICACION, id_, None, _iso(ahora),
                          {"elegido": elegido})  # fmt: skip
            hecho["elegidos"] += 1
        propia.ver_titulares([c for c, _ in enviados], _iso(ahora))
        if len(nuevos) > lectura.MAX_TITULARES:
            completo = False
    if hecho["preguntados"] or completo or lector.resumen.parada == "tiempo":
        # Hecho el de hoy. Con el servicio caído desde el principio, se intenta en la pasada
        # siguiente.
        propia.fijar("diaria", coste.dia(ahora))
    if completo:
        # La próxima vez, desde dos días antes de hoy (los titulares se guardan con su fecha).
        propia.fijar("diaria_desde", (ahora - timedelta(days=2)).strftime("%Y-%m-%d"))
    hecho["completo"] = completo
    return hecho


def fin_de_pasada(ahora: datetime) -> datetime | None:
    """Hasta cuándo puede seguir una pasada del temporizador: hasta el minuto `minuto_fin` de la
    hora siguiente (o de esta, si empezó pasada la hora). Fuera de su ventana (entre el minuto
    `minuto_fin` y el `minuto_inicio`, cuando corre la recogida) no se lanza: None."""
    ventana = configuracion()["pasada"]
    inicio, fin = int(ventana["minuto_inicio"]), int(ventana["minuto_fin"])
    base = ahora.astimezone(UTC).replace(second=0, microsecond=0)
    if ahora.minute >= inicio:
        return (base + timedelta(hours=1)).replace(minute=fin)
    if ahora.minute < fin:
        return base.replace(minute=fin)
    return None


def pasada(
    principal: Almacen, propia: Propia, cliente: secundario.Cliente, ahora: datetime, hasta: float,
    reloj: Callable[[], float] = time.monotonic, max_fichas: int | None = None,
    max_incidentes: int | None = None, tareas: frozenset[str] = TAREAS_LECTURA,
    forzar_diaria: bool = False, descargador: Any = None, pais: str | None = None,
    cupos: dict[str, int] | None = None,
) -> Resumen:  # fmt: skip
    """Una pasada: el barrido diario si toca, el barrido del país del día si toca, las búsquedas
    de lo que falta, los posibles duplicados y la segunda lectura, hasta `hasta` (reloj
    monótono). Con `pais`, el barrido de ese país ahora (comprobaciones a mano)."""
    from proceso import segunda_busqueda as busqueda_pura
    from recogida import segunda_busqueda

    resumen = Resumen(inicio=_iso(ahora))
    lector = Lector(cliente, hasta, reloj, resumen)
    if "rectificaciones" in tareas and (forzar_diaria or toca_diaria(propia, ahora)):
        resumen.rectificaciones = barrido_diario(principal, propia, lector, ahora, max_incidentes)
    fichas = publicadas(principal)
    if pais is not None:
        tope = int(segunda_busqueda.conf()["barrido_pais"]["por_pasada"])
        resumen.barrido_pais = {"pais": pais, **segunda_busqueda.buscar(
            principal, propia, lector, ahora, fichas, descargador, pais,
            dict.fromkeys(busqueda_pura.BUSQUEDAS, tope))}  # fmt: skip
    elif "pais" in tareas and not lector.parado and segunda_busqueda.toca_barrido(propia, ahora):
        resumen.barrido_pais = segunda_busqueda.barrido_pais(principal, propia, lector, ahora,
                                                             fichas, descargador)  # fmt: skip
    if "busqueda" in tareas and pais is None and not lector.parado:
        resumen.busquedas = segunda_busqueda.buscar(principal, propia, lector, ahora, fichas,
                                                    descargador, cupos=cupos)  # fmt: skip
    leidas = preparar(principal, fichas)
    if "pares" in tareas and not lector.parado:
        comparar_pares(principal, propia, lector, ahora, fichas, leidas,
                       int(configuracion()["pares"]["por_pasada"]))  # fmt: skip
    if "lectura" in tareas and not lector.parado:
        leer_fichas(principal, propia, lector, ahora, leidas, max_fichas)
    resumen.peticiones = cliente.peticiones
    return resumen


def escribir_estado(carpeta: Path, resumen: Documento, propia: Propia) -> None:
    """El estado de la última pasada (lo lee la recogida para el estado interno, control.json)."""
    datos = {"ultima_pasada": resumen, "candidatos_vigentes": len(propia.candidatos()),
             "diaria": propia.estado("diaria")}  # fmt: skip
    ruta = carpeta / ESTADO
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(ruta)


def abrir_principal(base: Path | None) -> Almacen:
    """La base principal, abierta solo para leer: la capa nunca escribe en ella."""
    from almacen import sitio

    ruta = base or sitio.ruta_base()
    return Almacen(sqlite3.connect(f"{ruta.resolve().as_uri()}?mode=ro", uri=True))


def _cupos(texto: str | None) -> dict[str, int] | None:
    """Los cupos de las búsquedas de una pasada a mano («declaracion=8,rescate=20»); las que no
    se dicen, 0."""
    if not texto:
        return None
    from proceso import segunda_busqueda as busqueda_pura

    dados = dict(parte.split("=", 1) for parte in texto.split(",") if "=" in parte)
    return {b: int(dados.get(b, 0)) for b in busqueda_pura.BUSQUEDAS}


def ejecutar_pasada(args: argparse.Namespace, ahora: datetime) -> Documento:
    secundario.cargar_local()
    config = secundario.configuracion()
    if config is None:
        registro.info("segunda lectura desactivada: sin servicio secundario configurado")
        return {"parada": "desactivada"}
    if args.manual:
        minutos = args.tope_min or float(configuracion()["pasada"]["tope_min"])
        hasta_fecha = ahora + timedelta(minutes=minutos)
    else:
        fin = fin_de_pasada(ahora)
        if fin is None:
            registro.info("segunda lectura: fuera de su ventana (corre la recogida): no se lanza")
            return {"parada": "fuera_de_ventana"}
        hasta_fecha = fin
    hasta = time.monotonic() + (hasta_fecha - ahora).total_seconds()
    carpeta = args.datos or directorio_datos()
    ritmo = secundario.Ritmo.de(configuracion()["ritmo"])
    cliente = secundario.Cliente(config, ritmo)
    tareas = frozenset(args.solo.split(",")) if args.solo else TAREAS
    propia = Propia.abrir(carpeta / BASE)
    principal = abrir_principal(args.base)
    from recogida.descarga import Descargador

    try:
        resumen = pasada(principal, propia, cliente, ahora, hasta, max_fichas=args.max_fichas,
                         max_incidentes=args.max_incidentes, tareas=tareas,
                         forzar_diaria=args.forzar_diaria, descargador=Descargador(),
                         pais=args.pais, cupos=_cupos(args.cupos))  # fmt: skip
        resumen.fin = _iso(datetime.now(UTC))
        documento = resumen.documento()
        propia.guardar_pasada(resumen.inicio, resumen.fin, documento)
        escribir_estado(carpeta, documento, propia)
        return documento
    finally:
        principal.cerrar()
        propia.cerrar()


# --- El paso de la recogida horaria ----------------------------------------------------------


def leer_candidatos(ruta: Path, tope_s: float) -> list[Documento]:
    """Los candidatos vigentes de la base de la capa, solo leyendo y con tope de tiempo. Si no
    está, está bloqueada o rota, ninguno."""
    if not ruta.exists():
        return []
    try:
        conexion = sqlite3.connect(
            f"{ruta.resolve().as_uri()}?mode=ro", uri=True, timeout=min(5.0, tope_s)
        )
        try:
            limite = time.monotonic() + tope_s
            conexion.set_progress_handler(lambda: int(time.monotonic() > limite), 10_000)
            return _filas_candidatos(conexion)
        finally:
            conexion.close()
    except (sqlite3.Error, OSError, ValueError) as error:
        registro.info("segunda lectura: candidatos sin leer (%s)", str(error)[:200])
        return []


class Experto:
    """Las llamadas al experto con lo marcado, en el modo «segunda_lectura»: dentro de sus 0,30
    dólares al día y del tope normal del experto, nunca de la reserva crítica."""

    def __init__(self, almacen: Almacen, ahora: datetime, plazo: Plazo) -> None:
        self.almacen, self.ahora, self.plazo = almacen, ahora, plazo
        self.parado: str | None = None
        self.gasto = 0.0
        self.ultimo_modelo = ""
        self._cliente: Any = None

    def cliente(self) -> Any:
        if self._cliente is None:
            fabrica = control_fichas._fabrica()
            servicio = fabrica() if fabrica is not None else None
            experto = getattr(servicio, "experto", None)
            self._cliente = experto() if callable(experto) else None
        return self._cliente

    def llamar(self, cuerpo: Documento, max_salida: int, clave: str) -> Documento | None:
        if self.parado:
            return None
        cliente = self.cliente()
        if cliente is None:
            self.parado = "sin experto"
            return None
        modelo = str(getattr(cliente, "modelo", ""))
        esfuerzo = (cuerpo.get("output_config") or {}).get("effort")
        previsto = coste.peor_caso(peticiones.letras(cuerpo), max_salida, modelo=modelo,
                                   esfuerzo=esfuerzo)  # fmt: skip
        dia = coste.dia(self.ahora)
        try:
            self.plazo.comprobar()
            coste.comprobar_segunda(
                self.almacen.gastado_modelo(modelo, dia),
                self.almacen.gastado_experto_en(coste.Modo.SEGUNDA_LECTURA.value, dia), previsto,
                self.ahora, coste.del_mes(self.almacen, self.ahora, modelo),
            )  # fmt: skip
            respuesta = cliente.mensaje(cuerpo)
        except coste.LimiteGasto as error:
            self.parado = f"tope: {str(error)[:150]}"
            return None
        except TiempoAgotado:
            self.parado = "tiempo"
            return None
        except LlamadaFallida as error:
            self.parado = f"experto: {str(error)[:150]}"
            return None
        uso = coste.Uso.de_mensaje(respuesta)
        gasto = uso.coste()
        self.almacen.registrar_llamada({
            "fecha": _iso(self.ahora), "modo": coste.Modo.SEGUNDA_LECTURA.value,
            "candidato": (PREFIJO + clave)[:200], "lote": False, "entrada": uso.entrada,
            "salida": uso.salida, "escritura_cache": uso.escritura_cache,
            "lectura_cache": uso.lectura_cache, "coste": gasto, "modelo": uso.modelo,
            "escalada": True,
        })  # fmt: skip
        self.gasto += gasto
        self.ultimo_modelo = uso.modelo
        try:
            return peticiones.leer(respuesta)
        except peticiones.RespuestaInvalida:
            return {}


def _contexto(almacen: Almacen, ahora: datetime, modelos: frozenset[str], plazo: Plazo,
              decisiones: dict[str, Documento], experto: Experto,
              motivo: str) -> control_fichas.Contexto:  # fmt: skip
    resultado = control_fichas.Resultado()
    llamador = control_fichas.Llamador(almacen, None, coste.Modo.SEGUNDA_LECTURA, ahora, plazo,
                                       resultado)  # fmt: skip
    ctx = control_fichas.Contexto(almacen, ahora, modelos, llamador, resultado, None, plazo,
                                  decisiones)  # fmt: skip
    llamador.ultimos_motivos = [f"{MOTIVO}: {motivo}"]
    return ctx


def _motivo(candidato: Documento) -> str:
    if candidato["tipo"] == DUPLICADO:
        return f"posible duplicado ({candidato['datos'].get('motivo', '')[:120]})"
    partes = [f"{h['campo']} {h['valoracion']}" for h in candidato["datos"].get("hallazgos", [])]
    return ", ".join(partes)[:200]


def verificar(almacen: Almacen, ahora: datetime, modelos: frozenset[str], experto: Experto,
              candidato: Documento) -> Documento | None:  # fmt: skip
    """La verificación del control de las fichas, hecha por el experto, de una ficha marcada. Lo
    que decide se guarda como la verificación de la ficha y lo aplica el control con sus reglas
    (control_fichas.aplicar_verificaciones). None si el experto no puede ahora."""
    incidente = almacen.incidente(candidato["incidente"])
    if incidente is None or not incidentes.activo(incidente):
        return {"resultado": "sin_ficha"}
    ctx = _contexto(almacen, ahora, modelos, experto.plazo, {}, experto, _motivo(candidato))
    peticion = control_fichas.peticion_verificacion(ctx, incidente)
    respuesta = experto.llamar(peticion.cuerpo, peticion.max_salida, candidato["clave"])
    if respuesta is None:
        return None
    if not respuesta:
        return {"resultado": "respuesta_invalida"}
    ctx.llamador.ultimo_modelo = experto.ultimo_modelo
    control_fichas.procesar_verificacion(ctx, peticion, respuesta)
    almacen.guardar_controles(ctx.nuevas, _iso(ahora))
    contradice = control_fichas.contradice(peticion.datos["vista"], respuesta)
    return {"resultado": "verificada", "contradice": contradice}


def comparar(almacen: Almacen, ahora: datetime, modelos: frozenset[str], experto: Experto,
             candidato: Documento) -> Documento | None:  # fmt: skip
    """La comparación del control de las fichas, hecha por el experto, de un par marcado: si
    decide que son el mismo suceso, se unen con las reglas de siempre (se conserva la más
    antigua). None si el experto no puede ahora."""
    a, b = almacen.incidente(candidato["incidente"]), almacen.incidente(str(candidato["otro"]))
    if a is None or b is None or not incidentes.activo(a) or not incidentes.activo(b):
        return {"resultado": "sin_ficha"}
    clave = reglas.clave_par(a["id"], b["id"])
    ctx = _contexto(almacen, ahora, modelos, experto.plazo, almacen.controles(clave), experto,
                    _motivo(candidato))  # fmt: skip
    huella = reglas.huella_fuentes(a) + reglas.huella_fuentes(b)
    peticion = control_fichas.peticion_par(ctx, a, b, huella, {})
    respuesta = experto.llamar(peticion.cuerpo, peticion.max_salida, candidato["clave"])
    if respuesta is None:
        return None
    if not respuesta:
        return {"resultado": "respuesta_invalida"}
    ctx.llamador.ultimo_modelo = experto.ultimo_modelo
    control_fichas.procesar_par(ctx, peticion, respuesta)
    almacen.guardar_controles(ctx.nuevas, _iso(ahora))
    decision = (ctx.nuevas.get(clave) or {}).get("decision")
    return {"resultado": "comparada", "decision": decision, "unidos": ctx.resultado.unidos}


def estado_capa(carpeta: Path) -> Documento:
    """Lo que dejó escrito la última pasada (segunda_lectura.json), o vacío."""
    try:
        datos: Documento = json.loads((carpeta / ESTADO).read_text(encoding="utf-8"))
        return datos
    except (OSError, ValueError):
        return {}


def _paso(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> Documento:
    hecho: Documento = {"activa": activa()}
    if not hecho["activa"]:
        return hecho
    carpeta = directorio_datos()
    tope = float(configuracion()["recogida"]["tope_lectura_s"])
    candidatos = leer_candidatos(carpeta / BASE, tope)
    decididas = almacen.controles(PREFIJO)
    pendientes = [c for c in candidatos if PREFIJO + c["clave"] not in decididas]
    hecho["candidatos"] = len(candidatos)
    hecho["pendientes"] = len(pendientes)
    nuevas: dict[str, Documento] = {}
    # Rectificaciones: a la cola del barrido mensual; las decide el experto en el paso de las
    # rectificaciones, con sus reglas y su límite por recogida.
    rect = [c for c in pendientes if c["tipo"] == RECTIFICACION and c["datos"].get("elegido")]
    encoladas = rectificaciones.encolar(almacen, [c["datos"]["elegido"] for c in rect])
    for c in rect:
        nuevas[PREFIJO + c["clave"]] = {"fecha": _iso(ahora), "resultado": "en_cola"}
    hecho["rectificaciones_encoladas"] = len(encoladas)
    # Datos, duplicados y lo que buscan las búsquedas, por prioridad (proceso/segunda_busqueda:
    # declaraciones e incidentes que faltan, lo contradicho, duplicados, atribución y efectos, el
    # resto) y, a la par, lo más reciente primero. Una fecha que solo «no tiene apoyo», o un tipo
    # contradicho sin frase de otro tipo, no va al experto.
    from proceso import segunda_busqueda as busqueda
    from recogida import segunda_busqueda

    tipos = {CAMPOS, DUPLICADO, *busqueda.BUSQUEDAS}
    resto = sorted((c for c in pendientes
                    if c["tipo"] in tipos and (c["tipo"] not in {CAMPOS, DUPLICADO}
                                               or lectura.al_experto(c))),
                   key=lambda c: c["fecha"], reverse=True)  # fmt: skip
    resto.sort(key=busqueda.prioridad)
    maximo = int(configuracion()["recogida"]["por_recogida"])
    ajustes = configuracion()["busqueda"]
    hoy = coste.dia(ahora)
    entregadas_hoy = sum(
        1 for d in decididas.values()
        if d.get("resultado") == "a_la_extraccion" and str(d.get("fecha", "")).startswith(hoy)
    )  # fmt: skip
    max_entregas = min(int(ajustes["por_recogida"]),
                       max(0, int(ajustes["por_dia"]) - entregadas_hoy))  # fmt: skip
    experto = Experto(almacen, ahora, Plazo(float(configuracion()["recogida"]["tope_experto_s"])))
    decididos: list[str] = []
    entregados: list[str] = []
    try:
        for candidato in resto:
            if candidato["tipo"] in busqueda.A_LA_EXTRACCION:
                if len(entregados) >= max_entregas:
                    continue
                decision: Documento | None = segunda_busqueda.entregar(almacen, ahora, candidato)
                entregados.append(candidato["clave"])
            else:
                if len(decididos) >= maximo or experto.parado:
                    continue
                revisar = comparar if candidato["tipo"] == DUPLICADO else verificar
                decision = revisar(almacen, ahora, modelos, experto, candidato)
                if decision is None:
                    continue
                decididos.append(candidato["clave"])
            if decision is not None:
                nuevas[PREFIJO + candidato["clave"]] = {"fecha": _iso(ahora), **decision}
    finally:
        almacen.guardar_controles(nuevas, _iso(ahora))
    hecho.update(decididos=decididos, entregados=entregados,
                 esperan=len(resto) - len(decididos) - len(entregados),
                 experto=experto.parado, gasto_experto=round(experto.gasto, 6))  # fmt: skip
    return hecho


def paso_horario(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> Documento:
    """En la recogida horaria: nada de lo que falle aquí sale de esta función ni cambia el código
    de salida."""
    try:
        hecho = _paso(almacen, ahora, modelos)
    except Exception as error:
        registro.warning("segunda lectura: candidatos sin revisar: %s", str(error)[:300])
        hecho = {"error": str(error)[:300]}
    registro.info("segunda lectura (lectura de candidatos): %s", _json(hecho))
    return hecho


def estado_para_control(almacen: Almacen, ahora: datetime, paso: Documento | None) -> Documento:
    """Lo de la capa que va al estado interno (control.json): la última pasada, sus candidatos y
    lo que gastó hoy el experto con ellos. Nunca falla."""
    try:
        return _estado_para_control(almacen, ahora, paso)
    except Exception as error:
        return {"error": str(error)[:300]}


def _estado_para_control(almacen: Almacen, ahora: datetime, paso: Documento | None) -> Documento:
    capa = estado_capa(directorio_datos())
    dia = coste.dia(ahora)
    return {
        "activa": activa(),
        "ultima_pasada": capa.get("ultima_pasada"),
        "candidatos_vigentes": capa.get("candidatos_vigentes"),
        "barrido_diario": capa.get("diaria"),
        "recogida": paso,
        "experto_hoy": round(almacen.gastado_experto_en(coste.Modo.SEGUNDA_LECTURA.value, dia), 6),
        "limite_experto": coste.LIMITE_SEGUNDA_EXPERTO_DIARIO_USD,
    }


# --- Entrada -------------------------------------------------------------------------------


def principal(argumentos: list[str] | None = None) -> int:
    """`pasada`: una pasada (la del temporizador o, con --manual, a cualquier hora). `candidatos`:
    los candidatos vigentes. Siempre termina con código 0: la capa no es vital."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    orden = parser.add_subparsers(dest="orden", required=True)
    una = orden.add_parser("pasada")
    una.add_argument("--base", type=Path, help="base principal (por defecto, la del disco)")
    una.add_argument("--datos", type=Path, help="carpeta de la base de la capa")
    una.add_argument("--max-fichas", type=int)
    una.add_argument("--max-incidentes", type=int)
    una.add_argument("--solo", help="lectura,pares,rectificaciones,busqueda,pais")
    una.add_argument("--pais", help="el barrido de ese país ahora (código ISO)")
    una.add_argument("--cupos", help="preguntas por búsqueda: declaracion=8,rescate=20,...")
    una.add_argument("--tope-min", type=float, help="con --manual, minutos de la pasada")
    una.add_argument("--manual", action="store_true", help="a cualquier hora, con su tope")
    una.add_argument("--forzar-diaria", action="store_true")
    lista = orden.add_parser("candidatos")
    lista.add_argument("--datos", type=Path)
    args = parser.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        if args.orden == "candidatos":
            carpeta = args.datos or directorio_datos()
            for c in leer_candidatos(carpeta / BASE, 30.0):
                print(_json(c))
            return 0
        documento = ejecutar_pasada(args, datetime.now(UTC))
        registro.info("segunda lectura: %s", _json(documento))
    except Exception as error:
        registro.warning("segunda lectura: pasada sin terminar: %s", repr(error)[:300])
    return 0


if __name__ == "__main__":
    sys.exit(principal())
