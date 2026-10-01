"""Extractor para los mensajes de la capa de guerra que el código no resuelve.

Primero código (`proceso/mensajes_guerra.py`); el extractor solo para los mensajes que quedan
como «para_extractor»: frases que mezclan drones con otras armas o lugares que el
nomenclátor no resuelve solo. Se le pasa el texto mínimo (las frases con un arma o un daño,
como mucho 1500 letras) y cada lugar que devuelve se valida por código:

- el arma tiene que ser un dron;
- la confianza, llegar al umbral de la validación de fichas (0,5);
- la frase de origen tiene que estar en el texto del mensaje;
- el lugar tiene que resolverse en el nomenclátor dentro de la región del canal (o de la que
  nombra la frase, en los canales de todo el país), con las mismas reglas que el código.

Lo que no pasa se descarta con su motivo, que queda en el registro del mensaje. Gasto:
límite diario propio de 0,20 dólares en la recogida horaria (modo «guerra», aparte del de las
noticias) y un presupuesto único de 5 dólares para el histórico (modo «guerra_historico», por
lotes, con prioridad a los objetivos de combustible, energía e industria, que FIRMS puede
comprobar). Cada llamada queda en `llamadas_extractor` con su coste.

El lote del histórico lo envía la recogida horaria una sola vez, cuando el histórico de los
canales está completo y todo lo leído procesado, y lo incorpora una recogida posterior cuando
el servicio lo termina; ninguna espera con el cerrojo tomado. `lote` lo envía a mano.

Uso: python -m proceso.extraccion_guerra estimar|lote (--base local.age [--guardar] | --remoto
    --correo <autor>) [--datos DIR] [--maximo N]
"""

import logging
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from almacen.base import Almacen
from esquema import Documento
from modelo import coste, guerra
from modelo.cliente import ErrorTemporal, LlamadaFallida
from proceso import impactos_guerra
from proceso.impactos_guerra import Ataques
from proceso.lugares_guerra import TIPOS_INSTALACION, Lugar, Nomenclator, normalizar
from proceso.mensajes_guerra import (
    DRON,
    IMPACTO,
    OTRA_ARMA,
    ImpactoLeido,
    MensajeLeido,
    analizar,
    frase_breve,
)
from proceso.validacion_ficha import UMBRAL_CONFIANZA
from recogida.canales_guerra import Canal, Datos, historico_terminado
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger("proceso.extraccion_guerra")
MAX_LETRAS = 1500
PENDIENTE = "para_extractor"
# En la recogida horaria, solo los mensajes de los últimos 3 días: lo anterior es del histórico.
VENTANA_HORARIA = timedelta(days=3)
# Tope del extractor de guerra en la ejecución horaria: unos 10 s por llamada.
TOPE_S = 120.0
# Marca del lote del histórico en la base (tabla de cursores): se envía una sola vez.
CURSOR_LOTE = "guerra:lote_historico"


class Servicio(Protocol):
    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]: ...


class ServicioLotes(Protocol):
    def crear_lote(self, peticiones: list[dict[str, Any]]) -> dict[str, Any]: ...

    def lote(self, id_: str) -> dict[str, Any]: ...

    def resultados_lote(self, lote: dict[str, Any]) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class Peticion:
    enlace: str
    canal: Canal
    publicacion: Documento
    texto: str

    @property
    def fecha(self) -> datetime:
        return datetime.fromisoformat(self.publicacion["fecha"].replace("Z", "+00:00"))

    def cuerpo(self) -> dict[str, Any]:
        return guerra.cuerpo(self.texto, self.publicacion["fecha"][:16], self.canal.region)

    def letras(self) -> int:
        return len(self.texto) + len(guerra.INSTRUCCIONES)

    @property
    def id_lote(self) -> str:
        return re.sub(r"[^A-Za-z0-9_-]", "_", self.enlace.removeprefix("https://t.me/"))[:64]


def texto_minimo(texto: str) -> str:
    """Las frases con un arma o un daño, en orden, hasta 1500 letras."""
    frases = [f.strip() for f in re.split(r"(?<=[.!?\n])\s+", texto) if f.strip()]
    utiles = [f for f in frases if DRON.search(f) or OTRA_ARMA.search(f) or IMPACTO.search(f)]
    resultado = ""
    for frase in utiles:
        if len(resultado) + len(frase) + 1 > MAX_LETRAS:
            break
        resultado += (" " if resultado else "") + frase
    return resultado or texto[:MAX_LETRAS]


def pendientes(
    almacen: Almacen, datos: Datos, canales: dict[str, Canal], desde: datetime | None = None
) -> list[Peticion]:
    """Los mensajes para el extractor aún sin extraer, de mayor a menor prioridad y del más
    reciente al más antiguo."""
    registros = [
        r for r in almacen.mensajes_guerra(PENDIENTE)
        if r.get("extraido", {}).get("version") != guerra.VERSION
        and (desde is None or r["fecha"] >= desde.strftime("%Y-%m-%dT%H:%M:%SZ"))
        and r["canal"] in canales
    ]  # fmt: skip
    # Orden estable: del más reciente al más antiguo y, por encima, la prioridad.
    registros.sort(key=lambda r: r["fecha"], reverse=True)
    registros.sort(key=lambda r: -r.get("prioridad", 0))
    textos: dict[str, dict[int, Documento]] = {}
    peticiones = []
    for r in registros:
        canal = canales[r["canal"]]
        if canal.canal not in textos:
            textos[canal.canal] = datos.ultimas(canal.canal)
        publicacion = textos[canal.canal].get(int(r["id"]))
        if publicacion is None:
            continue
        peticiones.append(
            Peticion(r["enlace"], canal, publicacion, texto_minimo(publicacion["texto"]))
        )
    return peticiones


def _en_texto(frase: str, texto: str) -> bool:
    return normalizar(frase) in normalizar(texto)


def _resolver(
    lugar: dict[str, Any], nomenclator: Nomenclator, regiones: frozenset[str] | None
) -> Lugar | None:
    """El lugar que da el extractor, resuelto en el nomenclátor con las reglas del código."""
    nombre = str(lugar.get("nombre", ""))
    localidad_texto = str(lugar.get("localidad") or "")
    if lugar.get("nivel") == "instalacion":
        categoria = next((c for patron, c in TIPOS_INSTALACION if patron.search(nombre)), None)
        cerca = None
        if localidad_texto:
            hallados = [h for h in nomenclator.localidades_en(localidad_texto, regiones) if h.lugar]
            cerca = hallados[0].lugar if len(hallados) == 1 else None
        if categoria is not None:
            comillas = re.search(r"[«\"“]([^»\"”]+)[»\"”]", nombre)
            resto = comillas.group(1) if comillas else re.sub(
                r"\b(?:НПЗ|ТЕЦ|ТЕС|ТЭЦ|нафтобаза|нефтебаза)\b", "", nombre
            ).strip() or None  # fmt: skip
            instalacion = nomenclator.instalacion(categoria, regiones, cerca, resto)
            if instalacion is not None:
                return instalacion
        return cerca
    hallados = [h for h in nomenclator.localidades_en(nombre[:1].upper() + nombre[1:], regiones)
                if h.lugar]  # fmt: skip
    return hallados[0].lugar if len(hallados) == 1 else None


@dataclass
class Validacion:
    impactos: list[ImpactoLeido] = field(default_factory=list)
    descartes: list[str] = field(default_factory=list)


def validar(
    lugares: list[dict[str, Any]],
    texto: str,
    nomenclator: Nomenclator,
    regiones: frozenset[str] | None,
    raices: tuple[tuple[str, str], ...],
) -> Validacion:
    from proceso.mensajes_guerra import regiones_en_texto

    resultado = Validacion()
    vistos: set[str] = set()
    for lugar in lugares:
        nombre = str(lugar.get("nombre", ""))[:60]
        if lugar.get("arma") != "dron":
            resultado.descartes.append(f"{nombre}: arma {lugar.get('arma')}")
            continue
        confianza = float(lugar.get("confianza") or 0)
        if confianza < UMBRAL_CONFIANZA:
            resultado.descartes.append(f"{nombre}: confianza baja")
            continue
        frase = str(lugar.get("frase", ""))
        if not frase or not _en_texto(frase, texto):
            resultado.descartes.append(f"{nombre}: frase que no está en el texto")
            continue
        ambito = regiones or regiones_en_texto(frase, raices) or regiones_en_texto(texto, raices)
        if not ambito:
            resultado.descartes.append(f"{nombre}: sin región")
            continue
        resuelto = _resolver(lugar, nomenclator, ambito)
        if resuelto is None:
            resultado.descartes.append(f"{nombre}: no se resuelve en el nomenclátor")
            continue
        if resuelto.id in vistos:
            continue
        vistos.add(resuelto.id)
        categorias = tuple(c for c in lugar.get("categorias", []) if c in guerra.CATEGORIAS)
        tipo = str(lugar["tipo"]) if lugar.get("tipo") in guerra.TIPOS else "impacto"
        resultado.impactos.append(ImpactoLeido(resuelto, tipo, categorias, frase_breve(frase)))
    return resultado


def procesar_respuesta(
    almacen: Almacen,
    ataques: Ataques,
    peticion: Peticion,
    respuesta: dict[str, Any],
    nomenclator: Nomenclator,
    raices: tuple[tuple[str, str], ...],
    ahora: datetime,
    modo: coste.Modo,
    lote: bool,
) -> int:
    """Anota el coste, valida los lugares y da de alta los impactos. Devuelve cuántos."""
    uso = coste.Uso.de_respuesta(respuesta.get("usage", {}))
    almacen.registrar_llamada({
        "fecha": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), "modo": modo.value,
        "candidato": peticion.enlace, "lote": lote, "entrada": uso.entrada, "salida": uso.salida,
        "escritura_cache": uso.escritura_cache, "lectura_cache": uso.lectura_cache,
        "coste": uso.coste(lote),
    })  # fmt: skip
    registro_previo = almacen.mensaje_guerra(peticion.enlace) or {}
    documento = {k: v for k, v in registro_previo.items() if k not in {"huella", "resultado"}}
    regiones = frozenset({peticion.canal.region}) if peticion.canal.region else None
    lugares: list[dict[str, Any]] = []
    try:
        lugares = guerra.leer_respuesta(respuesta)
    except guerra.RespuestaInvalida as error:
        validacion = Validacion(descartes=[str(error)])
    else:
        validacion = validar(lugares, peticion.publicacion["texto"], nomenclator, regiones, raices)
    base = analizar(
        peticion.publicacion["texto"], peticion.fecha, nomenclator, regiones, raices,
        reivindicacion=peticion.canal.grupo == "estado_mayor_ua",
    )  # fmt: skip
    leido_parte = base.parte_diario
    leido = MensajeLeido(
        impactos=validacion.impactos, noche=base.noche, es_noche=base.es_noche, dia=base.dia,
        heridos=base.heridos, fallecidos=base.fallecidos, derribados=base.derribados,
        parte_diario=leido_parte,
    )  # fmt: skip
    if len(leido.impactos) == 1:
        unico = leido.impactos[0]
        leido.impactos = [ImpactoLeido(unico.lugar, unico.tipo, unico.categorias, unico.frase,
                                       base.heridos, base.fallecidos)]  # fmt: skip
    confianza = max(
        (float(x.get("confianza") or 0) for x in lugares if x.get("arma") == "dron"), default=None
    )
    impactos_guerra.incorporar(
        almacen, ataques, peticion.canal, int(peticion.publicacion["id"]), peticion.fecha, leido,
        ahora, metodo="extractor", confianza=confianza, version=guerra.VERSION,
    )  # fmt: skip
    fuente_id = f"{peticion.canal.canal}-{peticion.publicacion['id']}"
    ids = sorted({
        d["id"] for i in leido.impactos for d in almacen.impactos_guerra_en(i.lugar.id)
        if any(f["id"] == fuente_id for f in d["fuentes"]) and "fusionado_en" not in d
    })  # fmt: skip
    documento.update(
        impactos=sorted(set(documento.get("impactos", [])) | set(ids)),
        metodo="extractor",
        extraido={
            "version": guerra.VERSION, "fecha": ahora.strftime("%Y-%m-%dT%H:%MZ"),
            "validos": len(validacion.impactos), "descartes": validacion.descartes[:10],
        },
    )  # fmt: skip
    almacen.guardar_mensaje_guerra(
        peticion.enlace, registro_previo.get("canal", peticion.canal.id),
        peticion.publicacion["fecha"], registro_previo.get("huella", ""),
        PENDIENTE, documento,
    )  # fmt: skip
    return len(ids)


@dataclass
class Resultado:
    llamadas: int = 0
    impactos: int = 0
    parada: str | None = None


def extraer(
    almacen: Almacen,
    cliente: Servicio,
    peticiones: list[Peticion],
    nomenclator: Nomenclator,
    raices: tuple[tuple[str, str], ...],
    ahora: datetime,
    modo: coste.Modo,
    plazo: Plazo | None = None,
) -> Resultado:
    """Una llamada por mensaje hasta la primera parada (límite de gasto, plazo, error)."""
    resultado = Resultado()
    ataques = Ataques(almacen.ataques_ucrania())
    for peticion in peticiones:
        gastado = almacen.gastado(modo.value, coste.dia(ahora) if coste.diario(modo) else None)
        previsto = coste.peor_caso(peticion.letras(), guerra.MAX_TOKENS_SALIDA)
        try:
            if plazo is not None:
                plazo.comprobar()
            coste.comprobar(gastado, previsto, modo)
            respuesta = cliente.mensaje(peticion.cuerpo())
        except TiempoAgotado:
            resultado.parada = "tiempo"
            break
        except coste.LimiteGasto:
            resultado.parada = "limite_gasto"
            break
        except ErrorTemporal:
            resultado.parada = "servicio_caido"
            break
        except LlamadaFallida:
            resultado.parada = "error"
            break
        resultado.llamadas += 1
        resultado.impactos += procesar_respuesta(
            almacen, ataques, peticion, respuesta, nomenclator, raices, ahora, modo, False
        )
    return resultado


def horaria(
    almacen: Almacen,
    datos: Datos,
    canales: list[Canal],
    nomenclator: Nomenclator,
    raices: tuple[tuple[str, str], ...],
    ahora: datetime,
    fabrica: Callable[[], Servicio],
    plazo: Plazo | None = None,
) -> Resultado:
    """Paso de la recogida horaria: los pendientes de los últimos 3 días, con el límite diario."""
    por_id = {c.id: c for c in canales if c.grupo != "rosaviatsia"}
    peticiones = pendientes(almacen, datos, por_id, ahora - VENTANA_HORARIA)
    if not peticiones:
        return Resultado()
    return extraer(
        almacen, fabrica(), peticiones, nomenclator, raices, ahora, coste.Modo.GUERRA, plazo
    )


def elegir_para_lote(almacen: Almacen, peticiones: list[Peticion]) -> tuple[list[Peticion], float]:
    """Las peticiones que caben, en su orden, en lo que queda del presupuesto del histórico
    (peor caso, a mitad de precio por ir en lote)."""
    queda = coste.limite(coste.Modo.GUERRA_HISTORICO) - almacen.gastado(
        coste.Modo.GUERRA_HISTORICO.value
    )
    elegidas: list[Peticion] = []
    previsto = 0.0
    for peticion in peticiones:
        caso = coste.peor_caso(peticion.letras(), guerra.MAX_TOKENS_SALIDA, lote=True)
        if previsto + caso > queda:
            break
        elegidas.append(peticion)
        previsto += caso
    return elegidas, previsto


def enviar_lote(
    almacen: Almacen, cliente: ServicioLotes, peticiones: list[Peticion], ahora: datetime
) -> dict[str, Any]:
    """Envía el lote del histórico, una sola vez, y deja su marca en la base. No espera: la
    recogida horaria lo incorpora cuando termina (`incorporar_lote`), así nunca se retiene el
    cerrojo de la recogida mientras el servicio lo procesa."""
    if almacen.cursor(CURSOR_LOTE) is not None:
        return {"enviadas": 0, "motivo": "el lote del histórico ya se envió"}
    elegidas, previsto = elegir_para_lote(almacen, peticiones)
    if not elegidas:
        return {"enviadas": 0, "fuera_de_limite": len(peticiones)}
    creado = cliente.crear_lote([{"custom_id": p.id_lote, "params": p.cuerpo()} for p in elegidas])
    almacen.guardar_cursor(CURSOR_LOTE, {
        "id": creado["id"], "estado": "enviado", "enviado": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "peticiones": len(elegidas), "peor_caso_usd": round(previsto, 4),
    })  # fmt: skip
    registro.info("lote %s enviado: %d peticiones, peor caso %.4f USD",
                  creado["id"], len(elegidas), previsto)  # fmt: skip
    return {
        "enviadas": len(elegidas), "lote": creado["id"],
        "fuera_de_limite": len(peticiones) - len(elegidas),
    }  # fmt: skip


def incorporar_lote(
    almacen: Almacen,
    cliente: ServicioLotes,
    datos: Datos,
    canales: list[Canal],
    nomenclator: Nomenclator,
    raices: tuple[tuple[str, str], ...],
    ahora: datetime,
) -> dict[str, Any] | None:
    """Si el lote enviado ya terminó, incorpora sus respuestas con las mismas reglas que una
    llamada directa y anota el resultado en su marca. None si no hay lote pendiente."""
    marca = almacen.cursor(CURSOR_LOTE)
    if marca is None or marca.get("estado") != "enviado":
        return None
    estado = cliente.lote(marca["id"])
    if estado.get("processing_status") != "ended":
        return {"lote": marca["id"], "estado": "en_proceso"}
    por_id = {
        p.id_lote: p
        for p in pendientes(almacen, datos, {c.id: c for c in canales if c.grupo != "rosaviatsia"})
    }
    ataques = Ataques(almacen.ataques_ucrania())
    impactos = fallidas = ya_extraidas = 0
    for resultado in cliente.resultados_lote(estado):
        peticion = por_id.get(resultado.get("custom_id", ""))
        if peticion is None:
            # Lo extrajo entretanto la recogida horaria, o ya no está pendiente.
            ya_extraidas += 1
            continue
        if resultado.get("result", {}).get("type") != "succeeded":
            fallidas += 1
            continue
        impactos += procesar_respuesta(
            almacen, ataques, peticion, resultado["result"]["message"], nomenclator, raices,
            ahora, coste.Modo.GUERRA_HISTORICO, True,
        )  # fmt: skip
    marca.update({
        "estado": "incorporado", "incorporado": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "impactos": impactos, "fallidas": fallidas, "ya_extraidas": ya_extraidas,
        "gastado_usd": round(almacen.gastado(coste.Modo.GUERRA_HISTORICO.value), 4),
    })  # fmt: skip
    almacen.guardar_cursor(CURSOR_LOTE, marca)
    return marca


def paso_lote(
    almacen: Almacen,
    fabrica: Callable[[], ServicioLotes],
    datos: Datos,
    canales: list[Canal],
    nomenclator: Nomenclator,
    raices: tuple[tuple[str, str], ...],
    ahora: datetime,
    al_dia: bool,
) -> dict[str, Any] | None:
    """Paso horario del lote del histórico: lo incorpora si terminó y, si aún no se envió,
    lo envía en cuanto el histórico de los canales está completo y todo lo leído procesado
    (`al_dia`)."""
    marca = almacen.cursor(CURSOR_LOTE)
    if marca is not None:
        if marca.get("estado") != "enviado":
            return None
        return incorporar_lote(almacen, fabrica(), datos, canales, nomenclator, raices, ahora)
    if not al_dia or not historico_terminado(datos, canales):
        return None
    peticiones = pendientes(almacen, datos, {c.id: c for c in canales if c.grupo != "rosaviatsia"})
    if not peticiones:
        return None
    return enviar_lote(almacen, fabrica(), peticiones, ahora)


def principal(argumentos: list[str] | None = None) -> int:
    from modelo import cliente as servicio
    from recogida.canales_guerra import cargar_canales, directorio_datos
    from recogida.guerra import con_base, opciones_base

    opciones = opciones_base(__doc__)
    opciones.add_argument("orden", choices=["estimar", "lote"])
    opciones.add_argument("--maximo", type=int, default=0, help="como mucho tantos mensajes")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    servicio.cargar_local()
    datos = Datos(args.datos or directorio_datos())
    canales = {c.id: c for c in cargar_canales() if c.grupo != "rosaviatsia"}
    with con_base(args) as almacen:
        peticiones = pendientes(almacen, datos, canales)
        if args.maximo:
            peticiones = peticiones[: args.maximo]
        peor = sum(
            coste.peor_caso(p.letras(), guerra.MAX_TOKENS_SALIDA, lote=True) for p in peticiones
        )
        prioridades = {m["enlace"]: m.get("prioridad") for m in almacen.mensajes_guerra(PENDIENTE)}
        registro.info(
            "pendientes: %d (prioridad 3: %d, 2: %d); peor caso en lote %.4f USD; gastado %.4f USD",
            len(peticiones),
            sum(prioridades.get(p.enlace) == 3 for p in peticiones),
            sum(prioridades.get(p.enlace) == 2 for p in peticiones),
            peor, almacen.gastado(coste.Modo.GUERRA_HISTORICO.value),
        )  # fmt: skip
        if args.orden == "lote":
            cliente = servicio.Cliente(servicio.configuracion(), insistencia=servicio.HISTORICO)
            registro.info("lote: %s", enviar_lote(almacen, cliente, peticiones, datetime.now(UTC)))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
