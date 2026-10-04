"""Paso de la recogida horaria para la capa de guerra con lugar: lee las publicaciones que el
lector de canales (`recogida/canales_guerra.py`, temporizador propio en el servidor) dejó en
el disco, las analiza (`proceso/mensajes_guerra.py`), guarda los impactos con lugar
(`proceso/impactos_guerra.py`) y las restricciones de aeropuertos de Rosaviatsia
(`proceso/restricciones.py`), y vuelve a enlazar con su ataque los impactos recientes que aún
no lo tenían.

No descarga nada: si el lector no ha dejado datos (aún no hay histórico, el disco no está),
el paso no hace nada y lo dice. Un fallo aquí no cambia el resultado de la recogida.

Cada mensaje se registra en la tabla `mensajes_guerra` con su huella (texto, versión del
analizador y del nomenclátor) y su resultado, sin el texto: uno ya leído con la misma huella
no se vuelve a leer. En cada hora se leen las publicaciones nuevas y las de las últimas 12
horas; `procesar --todo` vuelve a mirar todas (tras cambiar el analizador o el nomenclátor),
con el cerrojo de la recogida.

Uso: python -m recogida.guerra procesar [--todo] | corregir (--base local.age [--guardar] | --remoto
    --correo <autor>)
"""

import argparse
import copy
import hashlib
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from almacen import remoto
from almacen.base import Almacen
from esquema import Documento
from proceso import impactos_guerra, restricciones
from proceso.impactos_guerra import Ataques, instante
from proceso.lugares_guerra import NOMENCLATOR, Nomenclator, cargar
from proceso.mensajes_guerra import VERSION, MensajeLeido, analizar
from recogida.canales_guerra import Canal, Datos, cargar_canales, directorio_datos
from recogida.parte import vocabulario
from recogida.plazo import Plazo

registro = logging.getLogger("recogida.guerra")

# Tope del paso en la ejecución horaria: leer un centenar de mensajes nuevos son segundos; el
# nomenclátor tarda unos 15 s en cargarse. Lo que no cabe sigue en la hora siguiente.
TOPE_S = 240.0
RELECTURA = timedelta(hours=12)
GRUPOS = ("ova_ua", "estado_mayor_ua", "gobernadores_ru", "rosaviatsia")


@cache
def huella_nomenclator(ruta: Path = NOMENCLATOR) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()[:16] if ruta.exists() else "sin"


def huella(texto: str) -> str:
    return hashlib.sha256(f"{VERSION}\n{huella_nomenclator()}\n{texto}".encode()).hexdigest()


@cache
def raices_regiones() -> tuple[tuple[str, str], ...]:
    """Raíces de las regiones de Ucrania y de Rusia (con lo ocupado con su código ucraniano),
    para los canales de todo el país."""
    from recogida.mindef import vocabulario as vocabulario_ruso

    ucranianas = list(vocabulario().regiones)
    rusas = list(vocabulario_ruso().regiones)
    return tuple(sorted(ucranianas + rusas, key=lambda x: -len(x[0])))


def regiones_del_canal(canal: Canal) -> frozenset[str] | None:
    return frozenset({canal.region}) if canal.region else None


@dataclass
class Resumen:
    mensajes: int = 0
    con_impactos: int = 0
    para_extractor: int = 0
    impactos_nuevos: int = 0
    impactos_actualizados: int = 0
    restricciones: int = 0
    retirados: int = 0
    motivos: dict[str, int] = field(default_factory=dict)
    pendientes: bool = False

    def texto(self) -> str:
        return (
            f"mensajes={self.mensajes} con_impactos={self.con_impactos} "
            f"para_extractor={self.para_extractor} nuevos={self.impactos_nuevos} "
            f"actualizados={self.impactos_actualizados} restricciones={self.restricciones} "
            f"retirados={self.retirados} pendientes={self.pendientes}"
        )


def _fecha(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(UTC)


def quitar_fuente(almacen: Almacen, impacto_id: str, fuente_id: str, ahora: datetime) -> bool:
    """El mensaje editado ya no da ese impacto: se quita su fuente. Si era la única, el
    impacto queda retirado (nada se borra). True si queda retirado."""
    documento = next((d for d in almacen.impactos_guerra() if d["id"] == impacto_id), None)
    if documento is None:
        return False
    fuentes = [f for f in documento["fuentes"] if f["id"] != fuente_id]
    if fuentes == documento["fuentes"]:
        return False
    if not fuentes:
        retirado = {**documento, "retirado": {"fecha": instante(ahora),
                                              "motivo": "el mensaje ya no lo dice"}}  # fmt: skip
        almacen.guardar_impacto_guerra(retirado)
        return True
    nuevo = {**documento, "fuentes": fuentes}
    nuevo["lecturas"] = [x for x in documento.get("lecturas", []) if x["fuente_id"] != fuente_id]
    impactos_guerra._recalcular(nuevo, False)
    nuevo["control"] = {**documento["control"], "ultima_actualizacion": instante(ahora)}
    almacen.guardar_impacto_guerra(nuevo)
    return False


def registrar(
    almacen: Almacen,
    canal: Canal,
    publicacion: Documento,
    leido: MensajeLeido,
    ids: list[str],
    huella_mensaje: str,
    ahora: datetime,
) -> str:
    """Guarda el registro del mensaje y quita su fuente de los impactos que ya no da."""
    enlace = f"https://t.me/{canal.canal}/{publicacion['id']}"
    anterior = almacen.mensaje_guerra(enlace) or {}
    resultado = (
        "impactos" if ids
        else "para_extractor" if leido.para_extractor
        else leido.motivo or "sin_lugar"
    )  # fmt: skip
    fuente_id = f"{canal.canal}-{publicacion['id']}"
    for viejo in set(anterior.get("impactos", [])) - set(ids):
        if anterior.get("metodo") != "extractor":
            quitar_fuente(almacen, viejo, fuente_id, ahora)
    documento: Documento = {
        "id": publicacion["id"],
        "canal_id": canal.id,
        "impactos": ids,
        "prioridad": leido.prioridad,
        "metodo": "parser",
    }
    for campo in ("derribados", "heridos", "fallecidos"):
        valor = getattr(leido, campo)
        if valor is not None:
            documento[campo] = valor
    if canal.region:
        documento["region"] = canal.region
    if leido.sin_resolver:
        documento["sin_resolver"] = sorted({h.texto for h in leido.sin_resolver})[:10]
    almacen.guardar_mensaje_guerra(
        enlace, canal.id, publicacion["fecha"], huella_mensaje, resultado, documento
    )
    return resultado


def procesar(
    almacen: Almacen,
    datos: Datos,
    canales: list[Canal],
    nomenclator: Nomenclator,
    ahora: datetime,
    plazo: Plazo | None = None,
    todo: bool = False,
) -> Resumen:
    resumen = Resumen()
    ataques = Ataques(almacen.ataques_ucrania())
    for canal in canales:
        cursor = almacen.cursor(f"guerra:{canal.id}") or {"ultimo_id": 0}
        ultimo = int(cursor["ultimo_id"])
        maximo = ultimo
        for publicacion in sorted(datos.ultimas(canal.canal).values(), key=lambda p: p["id"]):
            publicado = _fecha(publicacion["fecha"])
            if not todo and publicacion["id"] <= ultimo and ahora - publicado > RELECTURA:
                continue
            if plazo is not None and plazo.agotado():
                resumen.pendientes = True
                break
            maximo = max(maximo, publicacion["id"])
            enlace = f"https://t.me/{canal.canal}/{publicacion['id']}"
            huella_mensaje = huella(publicacion["texto"])
            anterior = almacen.mensaje_guerra(enlace)
            if anterior is not None and anterior["huella"] == huella_mensaje:
                continue
            resumen.mensajes += 1
            if canal.grupo == "rosaviatsia":
                anuncio = restricciones.leer(publicacion["texto"], publicado)
                if anuncio is not None:
                    resumen.restricciones += restricciones.incorporar(
                        almacen, nomenclator, ataques, publicacion["id"], publicado,
                        publicacion.get("responde_a"), anuncio,
                    )  # fmt: skip
                almacen.guardar_mensaje_guerra(
                    enlace, canal.id, publicacion["fecha"], huella_mensaje,
                    "restriccion" if anuncio else "sin_restriccion", {"id": publicacion["id"]},
                )  # fmt: skip
                continue
            leido = analizar(
                publicacion["texto"], publicado, nomenclator, regiones_del_canal(canal),
                raices_regiones(), reivindicacion=canal.grupo == "estado_mayor_ua",
            )  # fmt: skip
            hecho = impactos_guerra.incorporar(
                almacen, ataques, canal, publicacion["id"], publicado, leido, ahora
            )
            resumen.impactos_nuevos += hecho.nuevos
            resumen.impactos_actualizados += hecho.actualizados
            ids = [
                d["id"]
                for impacto in leido.impactos
                for d in almacen.impactos_guerra_en(impacto.lugar.id)
                if any(f["id"] == f"{canal.canal}-{publicacion['id']}" for f in d["fuentes"])
                and "fusionado_en" not in d
            ]  # fmt: skip
            resultado = registrar(almacen, canal, publicacion, leido, ids, huella_mensaje, ahora)
            resumen.con_impactos += resultado == "impactos"
            resumen.para_extractor += resultado == "para_extractor"
            resumen.motivos[resultado] = resumen.motivos.get(resultado, 0) + 1
        if maximo > ultimo:
            almacen.guardar_cursor(f"guerra:{canal.id}", {"ultimo_id": maximo})
        if resumen.pendientes:
            break
    enlazados = impactos_guerra.reenlazar(almacen, ataques, ahora)
    registro.info(
        "guerra: reenlazados=%d fusionados=%d", enlazados.reenlazados, enlazados.fusionados
    )
    return resumen


# --- Corrección de lo ya guardado (una vez por versión) ----------------------------------------

CURSOR_CORRECCION = "guerra:correccion"
VERSION_CORRECCION = "victimas-homenajes/1"
# Lo que el mensaje, vuelto a leer, dice que no es un ataque con dron sobre un lugar.
NO_ES_IMPACTO = {
    "homenaje": "homenaje, obituario o memoria de un militar caído: no describe un ataque con "
    "dron sobre un lugar",
    "retrospectivo": "recuerda un ataque pasado (visita, condecoración, aniversario): no es un "
    "ataque nuevo",
    "sin_dron": "el mensaje no habla de un ataque con drones",
    "aviso": "aviso de alarma, no un ataque",
    "sin_impacto": "el mensaje no describe ningún impacto",
}
MOTIVO_VICTIMAS = (
    "víctimas leídas frase a frase: un año escrito como fecha no es una cifra de víctimas y más "
    "de 100 por impacto solo con la cifra pegada al verbo"
)


@dataclass
class Correccion:
    revisados: int = 0
    retirados: int = 0
    fuentes_quitadas: int = 0
    victimas_cambiadas: int = 0
    sin_texto: int = 0
    motivos: dict[str, int] = field(default_factory=dict)

    def documento(self, ahora: datetime) -> dict[str, Any]:
        return {
            "version": VERSION_CORRECCION, "fecha": instante(ahora)["valor"],
            "revisados": self.revisados, "retirados": self.retirados,
            "fuentes_quitadas": self.fuentes_quitadas,
            "victimas_cambiadas": self.victimas_cambiadas, "sin_texto": self.sin_texto,
            "motivos": self.motivos,
        }  # fmt: skip


def corregir(
    almacen: Almacen,
    datos: Datos,
    canales: list[Canal],
    nomenclator: Nomenclator,
    ahora: datetime,
    forzar: bool = False,
) -> Correccion | None:
    """Vuelve a leer, con las reglas de ahora, el mensaje de cada fuente de los impactos
    vigentes, desde los textos guardados por el lector (sin descargar nada ni llamar al
    extractor). Una fuente cuyo mensaje no describe un ataque con dron sobre un lugar
    (homenajes y obituarios de militares, memoria, avisos) se quita; un impacto sin fuentes
    queda retirado con su motivo. Las víctimas de cada fuente se vuelven a leer (solo si el
    mensaje da un único lugar) y el impacto lleva la mayor. Cada cambio es una versión nueva
    con su motivo en el historial. Una vez por versión (cursor CURSOR_CORRECCION); None si ya
    estaba aplicada."""
    hecho = almacen.cursor(CURSOR_CORRECCION) or {}
    if hecho.get("version") == VERSION_CORRECCION and not forzar:
        return None
    por_nombre = {c.canal.lower(): c for c in canales}
    textos: dict[str, dict[int, dict[str, Any]]] = {}
    vigentes = impactos_guerra.vigentes(almacen)
    # Cuántos impactos da cada mensaje: las víctimas solo se asignan si da uno solo.
    por_fuente: dict[str, int] = {}
    for documento in vigentes:
        for fuente in documento["fuentes"]:
            por_fuente[fuente["id"]] = por_fuente.get(fuente["id"], 0) + 1
    leidos: dict[str, MensajeLeido | None] = {}
    focos = almacen.focos_termicos()
    resultado = Correccion()
    for documento in vigentes:
        resultado.revisados += 1
        fuentes = []
        lecturas = {x["fuente_id"]: x for x in documento.get("lecturas", [])}
        quitadas: list[str] = []
        for fuente in documento["fuentes"]:
            partes = fuente["enlace"].split("/")
            canal = por_nombre.get(partes[3].lower()) if len(partes) > 4 else None
            if fuente["id"] not in leidos:
                leido = None
                if canal is not None and canal.grupo != "rosaviatsia":
                    if canal.canal not in textos:
                        textos[canal.canal] = datos.ultimas(canal.canal)
                    publicacion = textos[canal.canal].get(int(partes[4]))
                    if publicacion is not None:
                        leido = analizar(
                            publicacion["texto"], _fecha(publicacion["fecha"]), nomenclator,
                            regiones_del_canal(canal), raices_regiones(),
                            reivindicacion=canal.grupo == "estado_mayor_ua",
                        )  # fmt: skip
                leidos[fuente["id"]] = leido
            leido = leidos[fuente["id"]]
            if leido is None:
                resultado.sin_texto += 1
                fuentes.append(fuente)
                continue
            if leido.motivo in NO_ES_IMPACTO:
                quitadas.append(leido.motivo)
                lecturas.pop(fuente["id"], None)
                continue
            fuentes.append(fuente)
            unico = por_fuente.get(fuente["id"]) == 1
            victimas = {
                c: getattr(leido, c) for c in ("heridos", "fallecidos")
                if unico and getattr(leido, c) is not None
            }  # fmt: skip
            if fuente["id"] in lecturas:
                lecturas[fuente["id"]] = {**lecturas[fuente["id"]], "victimas": victimas}
        nuevo = copy.deepcopy(documento)
        motivos = []
        if not fuentes:
            motivo = NO_ES_IMPACTO[quitadas[0]]
            nuevo["retirado"] = {"fecha": instante(ahora), "motivo": motivo}
            resultado.retirados += 1
            resultado.motivos[quitadas[0]] = resultado.motivos.get(quitadas[0], 0) + 1
            motivos.append(motivo)
        else:
            if quitadas:
                resultado.fuentes_quitadas += len(quitadas)
                motivos.append("fuente quitada: " + NO_ES_IMPACTO[quitadas[0]])
            nuevo["fuentes"] = fuentes
            nuevo["lecturas"] = sorted(lecturas.values(), key=lambda x: x["fuente_id"])
            impactos_guerra.victimas_por_lecturas(nuevo, documento)
            if any(nuevo.get(c) != documento.get(c) for c in ("heridos", "fallecidos")):
                resultado.victimas_cambiadas += 1
                motivos.append(MOTIVO_VICTIMAS)
            foco = focos.get(documento["id"], {}).get("resultado")
            impactos_guerra._recalcular(
                nuevo, foco == "detectado" and impactos_guerra.con_firms(nuevo)
            )
        if nuevo == documento:
            continue
        nuevo["control"] = {**documento["control"], "ultima_actualizacion": instante(ahora)}
        almacen.guardar_impacto_guerra(nuevo)
        cambios = {
            c: nuevo.get(c) for c in ("heridos", "fallecidos", "retirado", "credibilidad")
            if nuevo.get(c) != documento.get(c)
        }  # fmt: skip
        almacen.anotar_motivo(
            "impactos_guerra", documento["id"],
            {c: documento.get(c) for c in cambios}, cambios, "; ".join(motivos),
        )  # fmt: skip
    almacen.guardar_cursor(CURSOR_CORRECCION, resultado.documento(ahora))
    return resultado


def estado_fuentes(datos: Datos, canales: list[Canal]) -> dict[str, dict[str, Any]]:
    """Por grupo de fuentes: si el último paso del lector leyó todos sus canales y la hora de
    la última lectura correcta de alguno (para estado.json)."""
    control = datos.control()
    grupos: dict[str, dict[str, Any]] = {}
    for grupo in GRUPOS:
        del_grupo = [c for c in canales if c.grupo == grupo]
        estados = [control.get("canales", {}).get(c.id, {}) for c in del_grupo]
        correctas = [e["ultima_correcta"] for e in estados if e.get("ultima_correcta")]
        leidos = sum(e.get("resultado") == "leido" for e in estados)
        grupos[grupo] = {
            "estado": "leida" if del_grupo and leidos == len(del_grupo)
            else "con_aviso" if leidos else "no_leida",
            "ultimo_dato": max(correctas) if correctas else None,
        }  # fmt: skip
    return grupos


def paso_horario(almacen: Almacen, ahora: datetime) -> tuple[dict[str, dict[str, Any]], Resumen]:
    """Lo que hace la recogida horaria. Nada de lo que falle sale de aquí."""
    datos = Datos(directorio_datos())
    canales = cargar_canales()
    try:
        estados = estado_fuentes(datos, canales)
    except (OSError, ValueError) as error:
        registro.warning("guerra: no se lee el control del lector: %s", error)
        estados = {g: {"estado": "no_leida", "ultimo_dato": None} for g in GRUPOS}
    if not (datos.raiz / "control.json").exists():
        registro.info("guerra: el lector de canales aún no ha dejado datos")
        return estados, Resumen()
    nomenclator = cargar()
    correccion = corregir(almacen, datos, canales, nomenclator, ahora)
    if correccion is not None:
        registro.info("guerra: corrección de lo guardado %s", correccion.documento(ahora))
    plazo = Plazo(TOPE_S)
    resumen = procesar(almacen, datos, canales, nomenclator, ahora, plazo)
    registro.info("guerra: %s", resumen.texto())
    return estados, resumen


def opciones_base(descripcion: str | None) -> argparse.ArgumentParser:
    """Dónde está la base: un db.age local (pruebas) o la rama estado (--remoto, en el servidor,
    con el cerrojo de la recogida: servidor/guerra_reproceso.sh)."""
    opciones = argparse.ArgumentParser(description=descripcion)
    opciones.add_argument("--base", type=Path, help="db.age local")
    opciones.add_argument("--remoto", action="store_true", help="la base de la rama estado")
    opciones.add_argument("--correo", help="correo del autor del commit de la base (--remoto)")
    opciones.add_argument("--repositorio", default=remoto.REPOSITORIO)
    opciones.add_argument("--datos", type=Path)
    opciones.add_argument("--guardar", action="store_true", help="vuelve a cifrar la base local")
    return opciones


@contextmanager
def con_base(args: argparse.Namespace) -> Iterator[Almacen]:
    """Abre la base y, al terminar sin error, la guarda: la local con --guardar; la de la rama
    estado, siempre que haya cambiado."""
    from almacen.cifrado import abrir_cifrada, cargar_clave_local, guardar_cifrada

    if not args.remoto and args.base is None:
        raise SystemExit("hace falta --base o --remoto")
    if not args.remoto:
        cargar_clave_local()
    with TemporaryDirectory() as temporal:
        ruta = args.base
        if args.remoto:
            if not args.correo:
                raise SystemExit("con --remoto hace falta --correo")
            ruta = Path(temporal) / remoto.FICHERO
            if not remoto.descargar(ruta, args.repositorio):
                raise SystemExit("no hay base en la rama estado")
        almacen = Almacen(abrir_cifrada(ruta))
        antes = almacen.conexion.serialize()
        yield almacen
        if almacen.conexion.serialize() == antes:
            registro.info("base sin cambios")
        elif args.remoto:
            guardar_cifrada(almacen.conexion, ruta)
            remoto.subir(ruta, args.correo, args.repositorio)
            registro.info("base subida a la rama %s", remoto.RAMA)
        elif args.guardar:
            guardar_cifrada(almacen.conexion, ruta)
        almacen.cerrar()


def principal(argumentos: list[str] | None = None) -> int:
    opciones = opciones_base(__doc__)
    opciones.add_argument("orden", choices=["procesar", "corregir"])
    opciones.add_argument("--todo", action="store_true")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ahora = datetime.now(UTC)
    datos = Datos(args.datos or directorio_datos())
    with con_base(args) as almacen:
        if args.orden == "corregir":
            hecho = corregir(almacen, datos, cargar_canales(), cargar(), ahora, forzar=True)
            registro.info("corrección: %s", hecho.documento(ahora) if hecho else None)
            return 0
        resumen = procesar(almacen, datos, cargar_canales(), cargar(), ahora, None, args.todo)
        registro.info("guerra: %s", resumen.texto())
        registro.info(
            "impactos: %s", impactos_guerra.resumen_por_sentido(impactos_guerra.vigentes(almacen))
        )
    return 0


if __name__ == "__main__":
    sys.exit(principal())
