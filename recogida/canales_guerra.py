"""Lectura de los canales de la capa de guerra en el servidor: administraciones militares
regionales de Ucrania, Estado Mayor ucraniano, gobernadores rusos (y autoridades instaladas
por Rusia que dan lugar concreto) y Rosaviatsia.

Los canales y la prueba de que son oficiales están en `configuracion/canales_guerra.json`
(docs/informe_capa_guerra.md). Se leen por su vista pública web (t.me/s/<canal>) con la
identificación del observatorio y una petición cada 3 segundos, y lo leído se guarda en el
disco del servidor, fuera del repositorio y de la base: un fichero JSONL por canal y mes
con las publicaciones que pasan el filtro de la fuente (palabras de dron, o de aeropuerto en
Rosaviatsia), con su número, su hora, su texto y la publicación a la que responden. La
recogida horaria (`recogida/guerra.py`) lee esos ficheros y escribe la base en segundos.

Antes de leer un canal se comprueba que sigue siendo el oficial:

1. la página trae la cabecera del canal (y no una de bloqueo o de canal sin vista previa);
2. el título contiene el nombre oficial;
3. lleva la insignia de verificado, si la llevaba al identificarlo;
4. la descripción sigue enlazando lo que enlazaba al identificarlo (la web de la
   institución, el canal hermano, sus redes);
5. la web oficial de la institución sigue enlazando el canal. Tras una comprobación correcta
   no se vuelve a mirar en un día; tras un fallo, en la lectura siguiente. Si la web carga y
   ya no lo enlaza, el canal deja de leerse. Si no carga (muchas
   webs oficiales ucranianas y rusas bloquean las direcciones de centros de datos), vale la
   última comprobación correcta mientras no tenga más de 30 días; después, el canal deja
   de leerse hasta que vuelva a comprobarse. Los canales cuya web nunca ha cargado desde el
   servidor (lo dice la configuración, con la fecha y el sitio desde donde se comprobó) se
   leen con las comprobaciones 1 a 4.

Si algo falla, el canal no se lee y el motivo queda en `control.json`; los demás siguen.

Uso (como eodi en el servidor):
    python -m recogida.canales_guerra recoger [--datos DIR]
    python -m recogida.canales_guerra historico --desde 2025-01-01 [--minutos 40]
    python -m recogida.canales_guerra resumen
"""

import argparse
import json
import logging
import os
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from recogida.descarga import AGENTE_EODI, Descargador, DescargaFallida
from recogida.plazo import Plazo, TiempoAgotado
from recogida.telegram import Pagina, Publicacion, es_pagina_de_canal, leer_pagina, url_pagina

registro = logging.getLogger("recogida.canales_guerra")

RAIZ = Path(__file__).resolve().parent.parent
CONFIGURACION = RAIZ / "configuracion" / "canales_guerra.json"
VARIABLE_DATOS = "EODI_GUERRA_DATOS"
DATOS_POR_DEFECTO = Path.home() / "datos" / "guerra"
CONTROL = "control.json"
# Cada lectura vuelve a mirar las últimas 12 horas: las administraciones corrigen cifras y
# añaden daños a lo largo de la mañana. Bastan 1 o 2 páginas por canal.
RELECTURA = timedelta(hours=12)
# La web oficial se comprueba como mucho una vez al día; si no carga, vale la última
# comprobación correcta durante 30 días.
COMPROBAR_WEB_CADA = timedelta(hours=24)
VIGENCIA_WEB = timedelta(days=30)
LIMITE_WEB_S = 20.0
# Tope de páginas de un canal en una lectura incremental: 30 páginas son unas 600
# publicaciones, más de diez días de la administración más activa. Si no alcanza el cursor,
# el resto lo recoge el histórico.
MAX_PAGINAS_RECOGER = 30
# Tope de tiempo de una lectura incremental de todos los canales: unos 60 canales a 1 o 2
# páginas, 3 s por página, son de 3 a 6 minutos.
TOPE_RECOGER_S = 20 * 60.0

# Filtro de la fuente: palabras de dron (ucraniano y ruso) o, en Rosaviatsia, de aeropuerto.
PALABRAS_DRON = re.compile(
    r"БпЛА|БПЛА|безпілотн|беспилотн|дрон|шахед|shahed|герань|гербер|ударн\w*\s+БпЛА|"
    r"\bFPV\b|ФПВ|коптер|ланцет|молні|молни|самол[её]тн\w+\s+тип|uav|drone",
    re.IGNORECASE,
)
PALABRAS_AEROPUERTO = re.compile(r"аэропорт|аеропорт|ограничени|ковер|«ковёр»", re.IGNORECASE)


@dataclass(frozen=True)
class Canal:
    id: str
    canal: str
    grupo: str
    pais: str
    region: str | None
    sentido: str
    idioma: str
    titulo: str
    insignia: bool
    descripcion_enlaza: tuple[str, ...]
    web_oficial: str | None
    web_enlaza: str | None
    web_desde_servidor: bool
    fiabilidad: str
    origen: str
    medio: str
    autoridad_ocupacion: bool
    identificado: dict[str, Any]
    # Institución del canal: dos canales de la misma institución (el institucional y el de su
    # jefe) no son fuentes independientes.
    institucion: str = ""
    # Canales intermedios de la cadena oficial: la web enlaza el primero y la descripción de
    # cada uno enlaza el siguiente (favt.gov.ru → @favt_ru → @favt_info).
    cadena: tuple[tuple[str, str], ...] = ()

    @property
    def filtro(self) -> re.Pattern[str]:
        return PALABRAS_AEROPUERTO if self.grupo == "rosaviatsia" else PALABRAS_DRON


def cargar_canales(ruta: Path = CONFIGURACION) -> list[Canal]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    canales = []
    for c in datos["canales"]:
        canales.append(
            Canal(
                id=c["id"],
                canal=c["canal"],
                grupo=c["grupo"],
                pais=c["pais"],
                region=c.get("region"),
                sentido=c["sentido"],
                idioma=c["idioma"],
                titulo=c["titulo"],
                insignia=c["insignia"],
                descripcion_enlaza=tuple(c.get("descripcion_enlaza", [])),
                web_oficial=c.get("web_oficial"),
                web_enlaza=c.get("web_enlaza"),
                web_desde_servidor=c.get("web_desde_servidor", False),
                fiabilidad=c["fiabilidad"],
                origen=c["origen"],
                medio=c["medio"],
                autoridad_ocupacion=c.get("autoridad_ocupacion", False),
                identificado=c["identificado"],
                institucion=c.get("institucion", c["id"]),
                cadena=tuple((x["canal"], x["titulo"]) for x in c.get("cadena", [])),
            )
        )
    return canales


def directorio_datos() -> Path:
    return Path(os.environ.get(VARIABLE_DATOS) or DATOS_POR_DEFECTO)


def _instante(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _leer_instante(texto: str | None) -> datetime | None:
    if not texto:
        return None
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(UTC)


# --- Almacén en disco ---------------------------------------------------------------------


class Datos:
    """Publicaciones guardadas por canal y mes, y el control de lectura de cada canal."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        # Último texto guardado de cada publicación, por canal: se lee una vez.
        self._textos: dict[str, dict[int, str]] = {}

    def _vistas(self, canal: str) -> dict[int, str]:
        if canal not in self._textos:
            self._textos[canal] = {p["id"]: p["texto"] for p in self.publicaciones(canal)}
        return self._textos[canal]

    def _control_ruta(self) -> Path:
        return self.raiz / CONTROL

    def control(self) -> dict[str, Any]:
        ruta = self._control_ruta()
        if not ruta.exists():
            return {"canales": {}}
        datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
        return datos

    def guardar_control(self, control: dict[str, Any]) -> None:
        self.raiz.mkdir(parents=True, exist_ok=True)
        temporal = self._control_ruta().with_suffix(".tmp")
        temporal.write_text(
            json.dumps(control, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8"
        )
        temporal.replace(self._control_ruta())

    def anadir(self, canal: str, publicaciones: list[Publicacion]) -> int:
        """Añade las publicaciones nuevas o cambiadas (otra hora o texto que la última versión
        guardada de ese número). Devuelve cuántas ha añadido."""
        vistas = self._vistas(canal)
        por_mes: dict[str, list[dict[str, Any]]] = {}
        for p in sorted(publicaciones, key=lambda x: x.id):
            documento = {
                "id": p.id, "fecha": _instante(p.fecha), "texto": p.texto,
                **({"responde_a": p.responde_a} if p.responde_a else {}),
            }  # fmt: skip
            if vistas.get(p.id) == p.texto:
                continue
            vistas[p.id] = p.texto
            por_mes.setdefault(p.fecha.strftime("%Y-%m"), []).append(documento)
        for mes, lista in por_mes.items():
            ruta = self.raiz / "canales" / canal / f"{mes}.jsonl"
            ruta.parent.mkdir(parents=True, exist_ok=True)
            with ruta.open("a", encoding="utf-8", newline="\n") as fichero:
                for documento in lista:
                    fichero.write(json.dumps(documento, ensure_ascii=False) + "\n")
        return sum(len(x) for x in por_mes.values())

    def publicaciones(self, canal: str) -> Iterator[dict[str, Any]]:
        """Todas las versiones guardadas, en el orden en que se guardaron."""
        directorio = self.raiz / "canales" / canal
        if not directorio.exists():
            return
        for ruta in sorted(directorio.glob("*.jsonl")):
            with ruta.open(encoding="utf-8") as fichero:
                for linea in fichero:
                    if linea.strip():
                        yield json.loads(linea)

    def ultimas(self, canal: str) -> dict[int, dict[str, Any]]:
        """La última versión de cada publicación del canal."""
        return {p["id"]: p for p in self.publicaciones(canal)}


# --- Verificación ---------------------------------------------------------------------


class NoVerificado(RuntimeError):
    pass


def verificar_cabecera(canal: Canal, portada: Pagina) -> None:
    if portada.canal is None:
        raise NoVerificado("la página no trae la cabecera del canal")
    if canal.titulo.lower() not in portada.canal.titulo.lower():
        raise NoVerificado("el título no contiene el nombre oficial")
    if canal.insignia and not portada.canal.verificado:
        raise NoVerificado("falta la insignia de verificado")
    enlaces = " ".join(portada.canal.enlaces_descripcion).lower()
    for esperado in canal.descripcion_enlaza:
        if esperado.lower() not in enlaces:
            raise NoVerificado(f"la descripción ya no enlaza {esperado}")


def verificar_cadena(canal: Canal, descargador: Descargador) -> None:
    """Cada canal intermedio de la cadena oficial sigue con su título y enlazando el siguiente."""
    if not canal.cadena:
        return
    siguientes = [c for c, _ in canal.cadena[1:]] + [canal.canal]
    for (intermedio, titulo), siguiente in zip(canal.cadena, siguientes, strict=True):
        portada = pagina(descargador, intermedio, None)
        if portada.canal is None or titulo.lower() not in portada.canal.titulo.lower():
            raise NoVerificado(f"el canal intermedio {intermedio} no es el esperado")
        enlaces = " ".join(portada.canal.enlaces_descripcion).lower()
        if f"t.me/{siguiente.lower()}" not in enlaces:
            raise NoVerificado(f"{intermedio} ya no enlaza {siguiente}")


def enlaza_canal(html: str, canal: str) -> bool:
    patron = re.compile(r"t\.me(?:/|%2F)(?:s/)?" + re.escape(canal) + r"(?![A-Za-z0-9_])", re.I)
    return bool(patron.search(html))


def verificar_web(
    canal: Canal, descargador: Descargador, estado: dict[str, Any], ahora: datetime
) -> None:
    """Comprobación 5 (cabecera del módulo). Actualiza `estado` con lo comprobado."""
    if canal.web_oficial is None or canal.web_enlaza is None:
        return
    correcta = _leer_instante(estado.get("web_ultima_correcta"))
    ultima = _leer_instante(estado.get("web_ultima_comprobacion"))
    # Tras una comprobación correcta se espera un día; tras un fallo se reintenta en la
    # lectura siguiente (hay webs oficiales que alternan respuestas y cortes). Las webs que no
    # cargan desde el servidor se intentan una vez al día.
    referencia = correcta if canal.web_desde_servidor else ultima
    if referencia is None or ahora - referencia >= COMPROBAR_WEB_CADA:
        estado["web_ultima_comprobacion"] = _instante(ahora)
        # Muchas webs oficiales bloquean las direcciones extranjeras o no responden: un solo
        # reintento y 20 s, para no gastar en ellas el tiempo de la lectura.
        web = descargador.con_limites(reintentos=1, limite_s=LIMITE_WEB_S)
        try:
            html = web.texto(canal.web_oficial, lambda t: "<html" in t.lower())
        except (DescargaFallida, TiempoAgotado) as error:
            estado["web_resultado"] = f"no carga: {str(error)[:120]}"
        else:
            if enlaza_canal(html, canal.web_enlaza):
                estado["web_resultado"] = "enlaza"
                estado["web_ultima_correcta"] = _instante(ahora)
                correcta = ahora
            else:
                estado["web_resultado"] = "no_enlaza"
                raise NoVerificado("la web oficial ya no enlaza el canal")
    if estado.get("web_resultado") == "no_enlaza":
        raise NoVerificado("la web oficial ya no enlaza el canal")
    if not canal.web_desde_servidor:
        # La web no carga desde el servidor: valen las comprobaciones 1 a 4.
        return
    if correcta is None or ahora - correcta > VIGENCIA_WEB:
        raise NoVerificado("la web oficial no se ha podido comprobar en 30 días")


# --- Lectura ------------------------------------------------------------------------------


def pagina(descargador: Descargador, canal: str, antes: int | None) -> Pagina:
    return leer_pagina(descargador.texto(url_pagina(canal, antes), es_pagina_de_canal))


def recoger_canal(
    canal: Canal,
    descargador: Descargador,
    datos: Datos,
    estado: dict[str, Any],
    ahora: datetime,
    portada: Pagina | None = None,
) -> int:
    """Lectura incremental: desde el cursor y las últimas 12 horas. Devuelve las guardadas."""
    portada = portada or pagina(descargador, canal.canal, None)
    verificar_cabecera(canal, portada)
    verificar_cadena(canal, descargador)
    verificar_web(canal, descargador, estado, ahora)
    ultimo = int(estado.get("ultimo_id", 0))
    desde = ahora - RELECTURA
    vistas = {p.id: p for p in portada.publicaciones}
    leida, paginas = portada, 1

    def falta(p: Pagina) -> bool:
        if not p.publicaciones:
            return False
        primera = min(p.publicaciones, key=lambda x: x.id)
        return primera.id > ultimo or primera.fecha >= desde

    while falta(leida) and paginas < MAX_PAGINAS_RECOGER and ultimo > 0:
        antes = min(p.id for p in leida.publicaciones)
        leida = pagina(descargador, canal.canal, antes)
        paginas += 1
        vistas.update((p.id, p) for p in leida.publicaciones)
    elegidas = [p for p in vistas.values() if p.id > ultimo or p.fecha >= desde]
    guardadas = datos.anadir(canal.canal, [p for p in elegidas if canal.filtro.search(p.texto)])
    if vistas:
        estado["ultimo_id"] = max(ultimo, max(vistas))
        estado["ultima_publicacion"] = _instante(max(vistas.values(), key=lambda p: p.id).fecha)
    return guardadas


def recoger(
    canales: list[Canal], descargador: Descargador, datos: Datos, ahora: datetime, plazo: Plazo
) -> dict[str, Any]:
    """Lee todos los canales; uno que falla no para a los demás. Devuelve el control."""
    control = datos.control()
    for canal in canales:
        estado = control["canales"].setdefault(canal.id, {})
        estado["ultimo_intento"] = _instante(ahora)
        try:
            plazo.comprobar()
            guardadas = recoger_canal(canal, descargador, datos, estado, ahora)
        except NoVerificado as error:
            estado.update(resultado="no_verificado", motivo=str(error))
            registro.warning("%s no se lee: %s", canal.id, error)
        except (DescargaFallida, TiempoAgotado) as error:
            estado.update(resultado="no_leido", motivo=str(error)[:200])
            registro.warning("%s no se lee: %s", canal.id, error)
        else:
            estado.update(resultado="leido", motivo=None, ultima_correcta=_instante(ahora))
            registro.info("%s: %d publicaciones guardadas", canal.id, guardadas)
        datos.guardar_control(control)
    control["ultima_recogida"] = _instante(ahora)
    datos.guardar_control(control)
    return control


# El histórico recorre antes los canales que sitúan impactos en Rusia, que no tienen otra
# fuente con lugar, y después las administraciones regionales de Ucrania.
ORDEN_HISTORICO = ("estado_mayor_ua", "gobernadores_ru", "rosaviatsia", "ova_ua")


def orden_historico(canales: list[Canal]) -> list[Canal]:
    """Los canales en el orden del histórico; dentro de cada grupo, el de la configuración."""
    return sorted(
        canales,
        key=lambda c: ORDEN_HISTORICO.index(c.grupo) if c.grupo in ORDEN_HISTORICO else 99,
    )


def historico(
    canales: list[Canal],
    descargador: Descargador,
    datos: Datos,
    desde: date,
    plazo: Plazo,
    ahora: datetime,
) -> bool:
    """Baja por cada canal hasta `desde`, guardando lo que pasa el filtro. Reanudable: el
    avance de cada canal queda en el control tras cada página. True si ha terminado todo."""
    control = datos.control()
    limite = datetime.combine(desde, datetime.min.time(), tzinfo=UTC)
    terminado = True
    for canal in orden_historico(canales):
        estado = control["canales"].setdefault(canal.id, {})
        avance = estado.setdefault("historico", {})
        if avance.get("terminado") and avance.get("desde") == desde.isoformat():
            continue
        if avance.get("desde") != desde.isoformat():
            avance.clear()
            avance["desde"] = desde.isoformat()
        try:
            if "siguiente" not in avance:
                portada = pagina(descargador, canal.canal, None)
                verificar_cabecera(canal, portada)
                verificar_cadena(canal, descargador)
                verificar_web(canal, descargador, estado, ahora)
                datos.anadir(canal.canal, [p for p in portada.publicaciones
                                           if canal.filtro.search(p.texto)])  # fmt: skip
                avance["siguiente"] = min((p.id for p in portada.publicaciones), default=None)
                avance["paginas"] = 1
                datos.guardar_control(control)
            while avance.get("siguiente"):
                plazo.comprobar()
                leida = pagina(descargador, canal.canal, avance["siguiente"])
                datos.anadir(canal.canal, [p for p in leida.publicaciones
                                           if canal.filtro.search(p.texto)])  # fmt: skip
                avance["paginas"] = avance.get("paginas", 0) + 1
                antigua = min((p.fecha for p in leida.publicaciones), default=None)
                avance["siguiente"] = (
                    None if antigua is None or antigua < limite
                    else min(p.id for p in leida.publicaciones)
                )  # fmt: skip
                if antigua is not None:
                    avance["hasta"] = _instante(antigua)
                datos.guardar_control(control)
            avance["terminado"] = True
            datos.guardar_control(control)
            registro.info("histórico de %s terminado: %d páginas", canal.id, avance["paginas"])
        except NoVerificado as error:
            registro.warning("%s no se lee: %s", canal.id, error)
            estado.update(resultado="no_verificado", motivo=str(error))
            datos.guardar_control(control)
        except TiempoAgotado:
            return False
        except DescargaFallida as error:
            registro.warning("histórico de %s cortado: %s", canal.id, error)
            terminado = False
    return terminado


def resumen(canales: list[Canal], datos: Datos) -> dict[str, Any]:
    control = datos.control()
    filas = {}
    for canal in canales:
        estado = control["canales"].get(canal.id, {})
        guardadas = len(datos.ultimas(canal.canal))
        filas[canal.id] = {
            "resultado": estado.get("resultado"),
            "ultima_correcta": estado.get("ultima_correcta"),
            "web": estado.get("web_resultado"),
            "guardadas": guardadas,
            "historico": estado.get("historico", {}),
        }
    return {"ultima_recogida": control.get("ultima_recogida"), "canales": filas}


def descargador(plazo: Plazo | None = None) -> Descargador:
    return Descargador(agente=AGENTE_EODI, plazo=plazo)


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("orden", choices=["recoger", "historico", "resumen"])
    opciones.add_argument("--datos", type=Path, default=None)
    opciones.add_argument("--desde", type=date.fromisoformat, default=date(2025, 1, 1))
    opciones.add_argument("--minutos", type=float, default=40.0)
    opciones.add_argument("--canal", action="append", default=[])
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    datos = Datos(args.datos or directorio_datos())
    canales = [c for c in cargar_canales() if not args.canal or c.id in args.canal]
    ahora = datetime.now(UTC)
    if args.orden == "resumen":
        print(json.dumps(resumen(canales, datos), ensure_ascii=False, indent=1))
        return 0
    if args.orden == "recoger":
        plazo = Plazo(TOPE_RECOGER_S)
        control = recoger(canales, descargador(plazo), datos, ahora, plazo)
        fallidos = [c for c, e in control["canales"].items() if e.get("resultado") != "leido"]
        registro.info("canales sin leer: %d de %d", len(fallidos), len(canales))
        return 0
    plazo = Plazo(args.minutos * 60)
    terminado = historico(canales, descargador(plazo), datos, args.desde, plazo, ahora)
    registro.info("histórico %s", "terminado" if terminado else "pendiente")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
