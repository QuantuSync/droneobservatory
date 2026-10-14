"""Control de calidad permanente de las fichas (docs/control_fichas.md).

En cada recogida horaria, antes de publicar, y una vez al día de madrugada sobre las últimas 48
horas:

1. **Duplicados**, también entre idiomas: los pares de fichas candidatos (proceso/
   control_fichas.pares_candidatos) se comparan con lo que dicen sus fuentes (modelo/control.py,
   «comparar»). Mismo suceso: se unen, se conserva el identificador más antiguo y el otro enlace
   lleva al que queda. Distinto: no se vuelven a comparar salvo que lleguen fuentes nuevas.
   Dudoso: se vuelve a comparar con cada fuente nueva y, a las 6 horas, se resuelve como
   distintos.
2. **Lugar**: la instalación que nombra el titular (proceso/lugar_preciso.py) y el sitio que da la
   frase de una fuente para las fichas sin punto (verificación).
3. **Cada dato con su fuente**: la ficha se verifica contra sus fuentes («verificar») y se
   corrige a lo que dicen (proceso/control_fichas.aplicar); el estado, solo con fuente oficial.
4. **Citas**: cada cita de una fuente se traduce una vez al español y al inglés («traducir») y se
   guarda (tabla traducciones); la publicación la añade junto al original.

Una ficha nueva que todavía no ha pasado el control (un par sin decidir, la verificación
pendiente por el tope de gasto o una caída del servicio) se retiene, sin bloquear nada más, como
mucho 6 horas: después se publica con lo que haya. Lo que ya estaba publicado nunca se retiene:
se corrige.

Gasto: modo «control», 0,15 dólares al día (horaria y madrugada); el repaso de todo lo publicado,
modo «control_repaso», 4 dólares una sola vez. Uso:

    python -m recogida.control_fichas noche|repaso|estado [--base DB.age] [--ensayo CARPETA]
"""

import argparse
import copy
import hashlib
import json
import logging
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from modelo import control as peticiones
from modelo import coste
from modelo.cliente import ErrorTemporal, LlamadaFallida
from proceso import atribucion, incidentes, lugar_preciso, presencia, titulares
from proceso import control_fichas as reglas
from proceso.noticias import Nomenclator
from proceso.presencia import TABLA_MOTIVOS
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger(__name__)

CURSOR = "control_fichas"
ESPERA = timedelta(hours=6)
VENTANA_HORARIA = timedelta(hours=72)
VENTANA_NOCHE = timedelta(hours=48)
# Tope de tiempo del paso en la recogida horaria (recogida/plazo.py).
TOPE_S = 300.0
# Un par dudoso se vuelve a comparar como mucho cada hora, y solo con fuentes nuevas.
CITAS_POR_LLAMADA = 30
LETRAS_POR_LLAMADA = 6000
MAX_LETRAS_CITA = 600
# El control falla varias veces seguidas: la vigilancia abre la incidencia.
FALLOS_PARA_AVISAR = 3
PREFIJO_UNION = "control de fichas: "
# La pasada de madrugada gasta como mucho esto del día (lo atrasado de las citas de Ucrania).
TOPE_NOCHE_USD = 0.08
# Y como mucho este tiempo: tiene que acabar antes de la recogida siguiente.
TOPE_NOCHE_S = 25 * 60.0
# Repaso por lotes: espera entre consultas del estado del lote y tope de espera.
ESPERA_LOTE_S = 60
TOPE_LOTE_S = 12 * 3600
RUTA_ESTADO_DEFECTO = Path.home() / ".eodi" / "control.json"
IDIOMAS_WEB = ("es", "en")


class Servicio(Protocol):
    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class Resultado:
    llamadas: int = 0
    gasto: float = 0.0
    unidos: list[str] = field(default_factory=list)
    distintos: int = 0
    dudosos: list[str] = field(default_factory=list)
    corregidos: dict[str, list[str]] = field(default_factory=dict)
    retenidos: dict[str, str] = field(default_factory=dict)
    liberados: dict[str, str] = field(default_factory=dict)
    verificadas: int = 0
    traducidas: int = 0
    dudas: dict[str, list[str]] = field(default_factory=dict)
    parada: str | None = None
    errores: list[str] = field(default_factory=list)

    def resumen(self) -> str:
        return (
            f"llamadas {self.llamadas} ({self.gasto:.4f} USD), unidos {len(self.unidos)}, "
            f"distintos {self.distintos}, dudosos {len(self.dudosos)}, verificadas "
            f"{self.verificadas}, corregidos {len(self.corregidos)}, retenidos "
            f"{len(self.retenidos)}, liberados {len(self.liberados)}, citas traducidas "
            f"{self.traducidas}, parada {self.parada}"
        )


def _instante(ahora: datetime) -> Documento:
    return {"valor": ahora.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"}


def _iso(ahora: datetime) -> str:
    return ahora.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _leer(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def huella_texto(texto: str) -> str:
    return hashlib.sha256(" ".join(texto.split()).encode("utf-8")).hexdigest()


# --- Llamadas con su gasto -----------------------------------------------------------------


class Llamador:
    """Hace las llamadas del control dentro del tope de su modo y anota cada una."""

    def __init__(
        self, almacen: Almacen, fabrica: Callable[[], Servicio] | None, modo: coste.Modo,
        ahora: datetime, plazo: Plazo | None, resultado: Resultado,
    ) -> None:  # fmt: skip
        self.almacen = almacen
        self.fabrica = fabrica
        self.modo = modo
        self.ahora = ahora
        self.plazo = plazo
        self.resultado = resultado
        self._servicio: Servicio | None = None
        # Tope de esta pasada, por debajo del del modo (la de madrugada deja margen para las
        # recogidas horarias del mismo día).
        self.tope: float | None = None

    @property
    def parado(self) -> bool:
        return self.resultado.parada is not None

    def llamar(self, cuerpo: dict[str, Any], max_salida: int, clave: str) -> dict[str, Any] | None:
        """La respuesta leída, o None si no se puede llamar (y queda la parada)."""
        if self.parado:
            return None
        if self.fabrica is None:
            self.resultado.parada = "sin_servicio"
            return None
        dia = coste.dia(self.ahora) if coste.diario(self.modo) else None
        gastado = self.almacen.gastado(self.modo.value, dia)
        previsto = coste.peor_caso(peticiones.letras(cuerpo), max_salida)
        try:
            if self.plazo is not None:
                self.plazo.comprobar()
            coste.comprobar(gastado, previsto, self.modo)
            if self.tope is not None and gastado + previsto > self.tope:
                raise coste.LimiteGasto(f"{self.modo}: tope de la pasada {self.tope:.2f} USD")
            if self._servicio is None:
                self._servicio = self.fabrica()
            respuesta = self._servicio.mensaje(cuerpo)
        except TiempoAgotado:
            self.resultado.parada = "tiempo"
            return None
        except coste.LimiteGasto:
            self.resultado.parada = "limite_gasto"
            return None
        except ErrorTemporal:
            self.resultado.parada = "servicio_caido"
            return None
        except LlamadaFallida as error:
            self.resultado.parada = "error"
            self.resultado.errores.append(str(error)[:200])
            return None
        except Exception as error:
            self.resultado.parada = "error"
            self.resultado.errores.append(repr(error)[:200])
            return None
        uso = coste.Uso.de_respuesta(respuesta.get("usage", {}))
        gasto = uso.coste()
        self.almacen.registrar_llamada({
            "fecha": _iso(self.ahora), "modo": self.modo.value, "candidato": clave[:200],
            "lote": False, "entrada": uso.entrada, "salida": uso.salida,
            "escritura_cache": uso.escritura_cache, "lectura_cache": uso.lectura_cache,
            "coste": gasto,
        })  # fmt: skip
        self.resultado.llamadas += 1
        self.resultado.gasto += gasto
        try:
            return peticiones.leer(respuesta)
        except peticiones.RespuestaInvalida as error:
            self.resultado.errores.append(f"{clave}: {error}")
            return None


# --- Lo que se manda de cada ficha ---------------------------------------------------------


def _titulares(almacen: Almacen, fuentes: list[Documento]) -> dict[str, str]:
    articulos = almacen.articulos_de([f["enlace"] for f in fuentes if f.get("enlace")])
    return {a["url"]: a["titular"] for a in articulos}


def _publicas(incidente: Documento) -> list[Documento]:
    return [
        f for f in incidente.get("fuentes", [])
        if f.get("publica", True) and f.get("fiabilidad") not in {"E", "F"}
    ]  # fmt: skip


@dataclass
class FuentesDeFicha:
    """Lo que se manda de las fuentes de una ficha y cómo se vuelve a cada fuente del incidente:
    una entrada por enlace (la noticia y las declaraciones que cita van juntas)."""

    bloques: list[peticiones.FuenteControl]
    # (id de la fuente a la que se atribuye la frase, texto con que se comprueba)
    comprobar: list[tuple[str, str]]


def fuentes_de_ficha(
    almacen: Almacen, incidente: Documento, textos: dict[str, str]
) -> FuentesDeFicha:
    """Las fuentes públicas de la ficha agrupadas por enlace, las oficiales primero."""
    titulares_ = _titulares(almacen, _publicas(incidente))
    grupos: dict[str, list[Documento]] = {}
    for fuente in _publicas(incidente):
        grupos.setdefault(fuente.get("enlace") or fuente["id"], []).append(fuente)

    def orden(par: tuple[str, list[Documento]]) -> tuple[int, str]:
        oficial = any(reglas.oficial(f) for f in par[1])
        return (0 if oficial else 1, min(f["fecha"]["valor"] for f in par[1]))

    bloques, comprobar = [], []
    for enlace, fuentes in sorted(grupos.items(), key=orden)[: peticiones.MAX_FUENTES]:
        principal = next((f for f in fuentes if "-declaracion-" not in f["id"]), fuentes[0])
        titular = titulares_.get(enlace) or str(principal.get("frase_origen", ""))
        frases = " ".join(dict.fromkeys(str(f.get("frase_origen", "")) for f in fuentes))
        texto = " ".join(t for t in (textos.get(enlace, ""), frases) if t)
        bloques.append(peticiones.FuenteControl(
            medio=str(principal.get("medio", "")), fecha=principal["fecha"]["valor"][:16],
            idioma=str(principal.get("idioma") or ""), titular=titular, texto=texto,
        ))  # fmt: skip
        comprobar.append((principal["id"], f"{titular} {texto}"))
    return FuentesDeFicha(bloques, comprobar)


def descargar(enlaces: list[str], plazo: Plazo | None) -> dict[str, str]:
    """Las primeras frases de cada noticia, en memoria (nunca se guardan)."""
    from modelo import paginas
    from recogida.descarga import Descargador

    def uno(enlace: str) -> tuple[str, str]:
        try:
            return enlace, paginas.leer(Descargador(plazo=plazo, reintentos=1), enlace)
        except Exception:
            return enlace, ""

    if not enlaces:
        return {}
    with ThreadPoolExecutor(max_workers=6) as hilos:
        return dict(hilos.map(uno, enlaces))


# --- Uniones -------------------------------------------------------------------------------


def unir(
    almacen: Almacen, conserva: Documento, une: Documento, motivo: str, ahora: datetime,
    modelos: frozenset[str],
) -> Documento:  # fmt: skip
    """Une `une` en `conserva` (su enlace lleva al que queda) con la fusión anotada como
    revisada: `incidentes.revisar_fusiones` no la deshace."""
    from recogida.revisados import completar

    nuevo, aportadas = incidentes.absorber(conserva, une, ahora)
    nuevo = completar(nuevo, [une])
    fundido = {**copy.deepcopy(une), "fusionado_en": conserva["id"]}
    fundido.pop("episodio", None)
    almacen.guardar_incidente(nuevo, ahora, modelos)
    almacen.guardar_incidente(fundido, ahora, modelos)
    almacen.registrar_fusion(
        ahora.strftime("%Y-%m-%dT%H:%MZ"), une["id"], conserva["id"],
        incidentes.PREFIJO_REVISADA + PREFIJO_UNION + motivo, aportadas,
    )  # fmt: skip
    return nuevo


def reaplicar_uniones(
    almacen: Almacen, decisiones: dict[str, Documento], ahora: datetime, modelos: frozenset[str]
) -> int:
    """Las uniones del control siguen hechas: si el que queda se volvió a extraer y perdió las
    fuentes del unido, las recupera. Devuelve cuántas rehace."""
    rehechas = 0
    for decision in decisiones.values():
        if decision.get("decision") != "mismo" or "conserva" not in decision:
            continue
        conserva = almacen.incidente(decision["conserva"])
        une = almacen.incidente(decision["une"])
        if conserva is None or une is None or not incidentes.activo(conserva):
            continue
        propio = {k: v for k, v in une.items() if k != "fusionado_en"}
        if "fusionado_en" not in une:
            if not incidentes.activo(une):
                continue
            unir(almacen, conserva, propio, decision["motivo_es"], ahora, modelos)
            rehechas += 1
            continue
        tiene = {f["id"] for f in conserva["fuentes"]}
        if any(f["id"] not in tiene for f in propio.get("fuentes", [])):
            nuevo, _ = incidentes.absorber(conserva, propio, ahora)
            almacen.guardar_incidente(nuevo, ahora, modelos)
            rehechas += 1
    return rehechas


# --- El paso -------------------------------------------------------------------------------


@dataclass
class Contexto:
    almacen: Almacen
    ahora: datetime
    modelos: frozenset[str]
    llamador: Llamador
    resultado: Resultado
    nom: Nomenclator | None
    plazo: Plazo | None
    decisiones: dict[str, Documento] = field(default_factory=dict)
    nuevas: dict[str, Documento] = field(default_factory=dict)

    def decision(self, clave: str) -> Documento | None:
        return self.nuevas.get(clave) or self.decisiones.get(clave)


def _activos(almacen: Almacen) -> list[Documento]:
    return [i for i in almacen.incidentes() if incidentes.activo(i)]


def _reciente(incidente: Documento, desde: datetime) -> bool:
    alta = _leer(incidente["control"]["alta"]["valor"])
    ultima = _leer(incidente["control"]["ultima_actualizacion"]["valor"])
    return max(alta, ultima, reglas.instante(incidente)) >= desde


def _ficha_par(d: Documento) -> dict[str, Any]:
    vista = reglas.vista(d)
    return {"id": d["id"], **{k: vista[k] for k in ("titular", "inicio", "lugar", "cierre")}}


@dataclass
class Peticion:
    """Una llamada preparada: su clave, el cuerpo, el tope de salida y lo que hace falta para
    procesar la respuesta (en memoria: las primeras frases de las noticias nunca se guardan)."""

    tipo: str
    clave: str
    cuerpo: dict[str, Any]
    max_salida: int
    datos: dict[str, Any]


def _textos_de(documentos: list[Documento], textos: dict[str, str], plazo: Plazo | None) -> None:
    enlaces = [f["enlace"] for d in documentos for f in _publicas(d)[:8]
               if f.get("enlace") and f["enlace"] not in textos]  # fmt: skip
    textos.update(descargar(list(dict.fromkeys(enlaces)), plazo))


def pares_por_decidir(ctx: Contexto, foco: set[str]) -> list[tuple[Documento, Documento, str]]:
    """Los pares candidatos que hay que comparar (con la huella de sus fuentes). Resuelve los
    dudosos que llevan 6 horas como distintos y deja en dudosos los que no han cambiado."""
    activos = _activos(ctx.almacen)
    resultado = []
    for a, b in reglas.pares_candidatos(activos, foco):
        clave = reglas.clave_par(a["id"], b["id"])
        huella = reglas.huella_fuentes(a) + reglas.huella_fuentes(b)
        previa = ctx.decision(clave)
        if previa is not None:
            if previa["decision"] in {"mismo", "distinto"} and previa.get("huella") == huella:
                continue
            if previa["decision"] == "dudoso":
                desde = _leer(str(previa.get("desde") or previa["fecha"]))
                if ctx.ahora - desde >= ESPERA:
                    ctx.nuevas[clave] = {**previa, "decision": "distinto", "fecha": _iso(ctx.ahora),
                                         "plazo": True, "huella": huella}  # fmt: skip
                    ctx.resultado.distintos += 1
                    continue
                if previa.get("huella") == huella:
                    ctx.resultado.dudosos.append(clave)
                    continue
        resultado.append((a, b, huella))
    return resultado


def peticion_par(ctx: Contexto, a: Documento, b: Documento, huella: str,
                 textos: dict[str, str]) -> Peticion:  # fmt: skip
    _textos_de([a, b], textos, ctx.plazo)
    fa, fb = fuentes_de_ficha(ctx.almacen, a, textos), fuentes_de_ficha(ctx.almacen, b, textos)
    cuerpo = peticiones.cuerpo_comparar(_ficha_par(a), fa.bloques, _ficha_par(b), fb.bloques)
    clave = reglas.clave_par(a["id"], b["id"])
    return Peticion("par", clave, cuerpo, peticiones.MAX_SALIDA_COMPARAR,
                    {"a": a["id"], "b": b["id"], "huella": huella})  # fmt: skip


def pares_separados(ctx: Contexto) -> list[tuple[Documento, Documento]]:
    """Las fichas que una revisión separó (sucesos relacionados, recogida/revisados.separar) y
    que siguen activas: el repaso las vuelve a comparar para revisar la separación. Nunca se
    unen solas: si el control dice que son el mismo suceso, se revisa a mano."""
    activos = {d["id"]: d for d in _activos(ctx.almacen)}
    pares: dict[str, tuple[Documento, Documento]] = {}
    for documento in activos.values():
        for relacionado in documento.get("relacionados", []):
            otro = activos.get(str(relacionado.get("id")))
            if otro is not None:
                uno, dos = sorted((documento, otro), key=lambda d: d["id"])
                pares.setdefault(f"{uno['id']}|{dos['id']}", (uno, dos))
    return list(pares.values())


def procesar_separado(ctx: Contexto, peticion: Peticion,
                      respuesta: dict[str, Any] | None) -> None:  # fmt: skip
    """Solo se anota lo que dice el control de una separación revisada a mano."""
    if respuesta is None or respuesta.get("decision") not in peticiones.DECISIONES:
        return
    ctx.nuevas[peticion.clave] = {
        "decision": respuesta["decision"], "fecha": _iso(ctx.ahora),
        "motivo_es": str(respuesta.get("motivo_es", ""))[:500],
        "motivo_en": str(respuesta.get("motivo_en", ""))[:500], "version": peticiones.VERSION,
    }  # fmt: skip


def procesar_par(ctx: Contexto, peticion: Peticion, respuesta: dict[str, Any] | None) -> None:
    """La decisión del par y, si son el mismo suceso, la unión (se conserva el más antiguo)."""
    clave = peticion.clave
    if respuesta is None or respuesta.get("decision") not in peticiones.DECISIONES:
        ctx.resultado.dudosos.append(clave)
        return
    from recogida.revisados import _vivo

    a = _vivo(ctx.almacen, peticion.datos["a"])
    b = _vivo(ctx.almacen, peticion.datos["b"])
    previa = ctx.decision(clave)
    decision: Documento = {
        "decision": respuesta["decision"], "huella": peticion.datos["huella"],
        "fecha": _iso(ctx.ahora), "motivo_es": str(respuesta.get("motivo_es", ""))[:500],
        "motivo_en": str(respuesta.get("motivo_en", ""))[:500], "version": peticiones.VERSION,
    }  # fmt: skip
    if decision["decision"] == "dudoso":
        decision["desde"] = (previa or {}).get("desde", _iso(ctx.ahora))
        ctx.resultado.dudosos.append(clave)
    elif decision["decision"] == "distinto":
        ctx.resultado.distintos += 1
    elif a is None or b is None or a["id"] == b["id"]:
        # Ya unidos por otro par, o uno retirado entretanto: nada que unir.
        pass
    else:
        conserva, une = reglas.mas_antiguo(a, b)
        decision.update(conserva=conserva["id"], une=une["id"])
        try:
            unir(ctx.almacen, conserva, une, decision["motivo_es"], ctx.ahora, ctx.modelos)
        except DocumentoInvalido as error:
            ctx.resultado.errores.append(f"{clave}: unión sin guardar: {str(error)[:150]}")
            decision["decision"] = "dudoso"
            decision["desde"] = _iso(ctx.ahora)
            ctx.resultado.dudosos.append(clave)
        else:
            ctx.resultado.unidos.append(f"{une['id']} -> {conserva['id']}")
    ctx.nuevas[clave] = decision


def comparar_pares(ctx: Contexto, foco: set[str]) -> None:
    textos: dict[str, str] = {}
    for a, b, huella in pares_por_decidir(ctx, foco):
        a2, b2 = ctx.almacen.incidente(a["id"]), ctx.almacen.incidente(b["id"])
        if a2 is None or b2 is None or not incidentes.activo(a2) or not incidentes.activo(b2):
            continue
        clave = reglas.clave_par(a["id"], b["id"])
        if ctx.llamador.parado:
            ctx.resultado.dudosos.append(clave)
            continue
        peticion = peticion_par(ctx, a2, b2, huella, textos)
        respuesta = ctx.llamador.llamar(peticion.cuerpo, peticion.max_salida, clave)
        procesar_par(ctx, peticion, respuesta)


def por_verificar(ctx: Contexto, foco: set[str]) -> list[Documento]:
    """Las fichas del foco con fuentes que aún no se verificaron, las más recientes primero."""
    resultado = []
    for incidente in sorted(_activos(ctx.almacen), key=lambda d: d["control"]["alta"]["valor"],
                            reverse=True):  # fmt: skip
        if incidente["id"] not in foco or not _publicas(incidente):
            continue
        previa = ctx.decision(reglas.clave_verificacion(incidente["id"]))
        if previa is not None and previa.get("huella") == reglas.huella_fuentes(incidente):
            continue
        resultado.append(incidente)
    return resultado


def peticion_verificacion(ctx: Contexto, incidente: Documento) -> Peticion:
    publicas = _publicas(incidente)
    textos = descargar(
        list(dict.fromkeys(f["enlace"] for f in publicas if f.get("enlace")))[:8], ctx.plazo
    )
    fuentes = fuentes_de_ficha(ctx.almacen, incidente, textos)
    vista = reglas.vista(incidente)
    cuerpo = peticiones.cuerpo_verificar(vista, fuentes.bloques)
    return Peticion("verificacion", reglas.clave_verificacion(incidente["id"]), cuerpo,
                    peticiones.MAX_SALIDA_VERIFICAR,
                    {"huella": reglas.huella_fuentes(incidente), "vista": vista,
                     "comprobar": fuentes.comprobar})  # fmt: skip


def procesar_verificacion(ctx: Contexto, peticion: Peticion,
                          respuesta: dict[str, Any] | None) -> None:  # fmt: skip
    if respuesta is None:
        return
    comprobada = reglas.comprobar(respuesta, peticion.datos["comprobar"])
    ctx.nuevas[peticion.clave] = {
        "huella": peticion.datos["huella"], "fecha": _iso(ctx.ahora),
        "vista": peticion.datos["vista"], "version": peticiones.VERSION,
        "datos": {k: list(v) for k, v in comprobada.datos.items()},
        "sin_comprobar": sorted(set(respuesta) - set(comprobada.datos)),
    }  # fmt: skip
    ctx.resultado.verificadas += 1


def verificar(ctx: Contexto, foco: set[str]) -> None:
    for incidente in por_verificar(ctx, foco):
        if ctx.llamador.parado:
            break
        peticion = peticion_verificacion(ctx, incidente)
        respuesta = ctx.llamador.llamar(peticion.cuerpo, peticion.max_salida, peticion.clave)
        procesar_verificacion(ctx, peticion, respuesta)


def _verificada_vigente(decision: Documento, incidente: Documento) -> reglas.Verificada:
    """Lo comprobado que sigue valiendo para el incidente: las frases de fuentes que aún tiene.
    Con fuentes nuevas, lo que quitaba un valor solo vale si el valor es el mismo que se
    comprobó (hasta la próxima verificación)."""
    tiene = {f["id"] for f in incidente.get("fuentes", [])}
    datos = {k: tuple(v) for k, v in decision.get("datos", {}).items() if v[1] in tiene}
    return reglas.Verificada(datos)


def aplicar_verificaciones(ctx: Contexto) -> None:
    decisiones = {**ctx.decisiones, **ctx.nuevas}
    for incidente in _activos(ctx.almacen):
        decision = decisiones.get(reglas.clave_verificacion(incidente["id"]))
        if decision is None:
            continue
        verificada = _verificada_vigente(decision, incidente)
        conservar: set[str] = set()
        if decision.get("huella") != reglas.huella_fuentes(incidente):
            # Fuentes nuevas aún sin verificar: un valor que ninguna fuente daba solo se quita si
            # es el mismo que se comprobó (lo nuevo puede traerlo).
            actual, vista = reglas.vista(incidente), decision.get("vista", {})
            conservar = {c for c in ("drones", "cierre", "duracion_min", "inicio")
                         if actual.get(c) != vista.get(c)}  # fmt: skip
        fuentes_regla, titular_regla = presencia.respaldo_cierre_de_pista(incidente)
        correccion = reglas.aplicar(
            incidente,
            verificada,
            bool(fuentes_regla or titular_regla),
            ctx.nom,
            frozenset(conservar),
        )
        if correccion.dudas:
            ctx.resultado.dudas[incidente["id"]] = correccion.dudas
        if not correccion.cambios:
            continue
        nuevo = incidentes.aplicar_reglas(correccion.incidente)
        nuevo = titulares.ajustar_incidente(nuevo)
        nuevo["titulo"] = atribucion.titulo_segun_atribucion(nuevo)
        _guardar(ctx, incidente, nuevo, "; ".join(correccion.cambios))


def _guardar(ctx: Contexto, antes: Documento, despues: Documento, motivo: str) -> bool:
    if despues == antes:
        return False
    despues = {**despues, "control": {**despues["control"],
                                      "ultima_actualizacion": _instante(ctx.ahora)}}  # fmt: skip
    try:
        ctx.almacen.guardar_incidente(despues, ctx.ahora, ctx.modelos)
    except DocumentoInvalido as error:
        ctx.resultado.errores.append(f"{antes['id']}: sin guardar: {str(error)[:200]}")
        return False
    campos = ("presencia_dron", "drones", "consecuencias", "tiempo", "lugar", "objetivo",
              "estado", "titulo", "tipo")  # fmt: skip
    cambios = {c: antes.get(c) for c in campos if antes.get(c) != despues.get(c)}
    if cambios:
        ctx.almacen.anotar_motivo(TABLA_MOTIVOS, antes["id"], cambios,
                                  {c: despues.get(c) for c in cambios},
                                  f"{PREFIJO_UNION}{motivo}"[:1000])  # fmt: skip
    ctx.resultado.corregidos.setdefault(antes["id"], []).append(motivo)
    return True


def reglas_deterministas(ctx: Contexto) -> None:
    """El lugar que nombra el titular y el estado sin fuente oficial, sin llamar a nada."""
    for incidente in _activos(ctx.almacen):
        nuevo = incidente
        motivos = []
        if ctx.nom is not None:
            preciso = lugar_preciso.precisar(nuevo, ctx.nom, ctx.ahora)
            if preciso is not None:
                nuevo = preciso
                motivos.append(f"lugar en {preciso['lugar']['suceso']}, que nombra el titular")
        bajado = reglas.bajar_estado(nuevo, _instante(ctx.ahora))
        if bajado is not None:
            nuevo = bajado
            motivos.append("estado sin fuente oficial: notificado")
        if motivos:
            nuevo = incidentes.aplicar_reglas(nuevo)
            _guardar(ctx, incidente, nuevo, "; ".join(motivos))


# --- Citas ---------------------------------------------------------------------------------


def citas_de(
    documentos: list[Documento], decisiones: dict[str, Documento]
) -> dict[str, tuple[str, str]]:
    """Cada cita por traducir: huella -> (idioma, texto). Las frases de las fuentes públicas y
    las de la verificación."""
    citas: dict[str, tuple[str, str]] = {}
    idioma_de: dict[str, str] = {}
    for documento in documentos:
        for fuente in _publicas(documento):
            texto = str(fuente.get("frase_origen") or "").strip()
            idioma_de[fuente["id"]] = str(fuente.get("idioma") or "")
            if texto:
                citas.setdefault(
                    huella_texto(texto), (idioma_de[fuente["id"]], texto[:MAX_LETRAS_CITA])
                )
    for clave, decision in decisiones.items():
        if not clave.startswith("verificacion:"):
            continue
        for _valor, fuente, frase in decision.get("datos", {}).values():
            citas.setdefault(
                huella_texto(frase), (idioma_de.get(fuente, ""), frase[:MAX_LETRAS_CITA])
            )
    return citas


def peticiones_traduccion(citas: dict[str, tuple[str, str]], hechas: set[str]) -> list[Peticion]:
    """Las citas sin traducir en tandas (por número de citas y de letras)."""
    pendientes = [(h, i, t) for h, (i, t) in citas.items() if h not in hechas]
    resultado = []
    while pendientes:
        tanda: list[tuple[str, str, str]] = []
        letras = 0
        while pendientes and len(tanda) < CITAS_POR_LLAMADA and letras < LETRAS_POR_LLAMADA:
            tanda.append(pendientes.pop(0))
            letras += len(tanda[-1][2])
        cuerpo = peticiones.cuerpo_traducir([(i, t) for _, i, t in tanda])
        clave = (
            "traducir:" + hashlib.sha256("".join(h for h, _, _ in tanda).encode()).hexdigest()[:12]
        )
        resultado.append(Peticion("traduccion", clave, cuerpo, peticiones.MAX_SALIDA_TRADUCIR,
                                  {"tanda": tanda}))  # fmt: skip
    return resultado


def procesar_traduccion(ctx: Contexto, peticion: Peticion,
                        respuesta: dict[str, Any] | None) -> None:  # fmt: skip
    if respuesta is None:
        return
    tanda = peticion.datos["tanda"]
    nuevas: dict[str, Documento] = {}
    for entrada in respuesta.get("traducciones", []):
        n = entrada.get("n")
        if not isinstance(n, int) or not 1 <= n <= len(tanda):
            continue
        huella, idioma, texto = tanda[n - 1]
        es, en = str(entrada.get("es") or "").strip(), str(entrada.get("en") or "").strip()
        if idioma == "es":
            es = texto
        if idioma == "en":
            en = texto
        if es and en:
            nuevas[huella] = {"idioma": idioma, "es": es, "en": en,
                              "version": peticiones.VERSION}  # fmt: skip
    ctx.resultado.traducidas += ctx.almacen.guardar_traducciones(nuevas, _iso(ctx.ahora))


def traducir(ctx: Contexto, citas: dict[str, tuple[str, str]], hechas: set[str]) -> None:
    for peticion in peticiones_traduccion(citas, hechas):
        if ctx.llamador.parado:
            break
        respuesta = ctx.llamador.llamar(peticion.cuerpo, peticion.max_salida, peticion.clave)
        if respuesta is None:
            break
        procesar_traduccion(ctx, peticion, respuesta)


CURSOR_CITAS = "control_fichas:citas"


def anotar_pendientes(almacen: Almacen, pendientes: Any) -> None:
    """Las citas que se acaban de publicar sin traducción (exportacion/citas.Pendientes)."""
    almacen.guardar_cursor(CURSOR_CITAS, pendientes.documento())


def citas_pendientes(almacen: Almacen, capa: str) -> dict[str, tuple[str, str]]:
    """Las citas publicadas sin traducción de una capa («europa» o «ucrania»), en orden."""
    cursor = almacen.cursor(CURSOR_CITAS) or {}
    return {h: (str(v[0]), str(v[1])) for h, v in (cursor.get(capa) or {}).items()}


# --- Retención -----------------------------------------------------------------------------


def retener(ctx: Contexto, cursor: Documento, verificar_nuevos: bool) -> Documento:
    """Las fichas nuevas que aún no han pasado el control se retienen como mucho 6 horas.
    Devuelve el cursor nuevo."""
    vistos: dict[str, str] = dict(cursor.get("vistos", {}))
    retenidos: dict[str, Documento] = dict(cursor.get("retenidos", {}))
    decisiones = {**ctx.decisiones, **ctx.nuevas}
    activos = _activos(ctx.almacen)
    if not vistos and "vistos" not in cursor:
        # Primera pasada: lo que ya había se da por visto (se corrige, no se retiene).
        cursor = {**cursor, "vistos": {d["id"]: _iso(ctx.ahora) for d in activos}}
        return cursor
    pendientes_par = {
        id_ for clave in ctx.resultado.dudosos for id_ in clave.removeprefix("par:").split("|")
    }
    nuevos_retenidos: dict[str, Documento] = {}
    for incidente in activos:
        id_ = incidente["id"]
        if id_ in vistos:
            continue
        desde = retenidos.get(id_, {}).get("desde", _iso(ctx.ahora))
        motivos = []
        if id_ in pendientes_par:
            motivos.append("posible duplicado sin decidir")
        if verificar_nuevos and reglas.clave_verificacion(id_) not in decisiones:
            motivos.append("verificación pendiente")
        if motivos and ctx.ahora - _leer(desde) < ESPERA:
            nuevos_retenidos[id_] = {"desde": desde, "motivo": "; ".join(motivos)}
            ctx.resultado.retenidos[id_] = "; ".join(motivos)
            continue
        vistos[id_] = _iso(ctx.ahora)
        if id_ in retenidos:
            nota = "a las 6 horas, con lo que hay" if motivos else "control pasado"
            ctx.resultado.liberados[id_] = nota
    # Lo retenido que ya no está activo (unido a otro o retirado) sale de la lista.
    return {**cursor, "vistos": vistos, "retenidos": nuevos_retenidos}


def retenidos(almacen: Almacen) -> frozenset[str]:
    """Las fichas que la publicación no saca todavía."""
    cursor = almacen.cursor(CURSOR) or {}
    return frozenset(cursor.get("retenidos", {}))


# --- Entrada -------------------------------------------------------------------------------


def ejecutar(
    almacen: Almacen, ahora: datetime, modelos: frozenset[str], alcance: str,
    fabrica: Callable[[], Servicio] | None, plazo: Plazo | None = None,
    nom: Nomenclator | None = None,
) -> Resultado:  # fmt: skip
    """El control: «horaria» (lo nuevo y lo cambiado en 72 horas), «noche» (lo publicado en las
    últimas 48 horas) o «repaso» (todo lo publicado, con su propio tope)."""
    resultado = Resultado()
    modo = coste.Modo.CONTROL_REPASO if alcance == "repaso" else coste.Modo.CONTROL
    llamador = Llamador(almacen, fabrica, modo, ahora, plazo, resultado)
    if nom is None:
        from proceso.noticias import nomenclator

        nom = nomenclator()
    ctx = Contexto(almacen, ahora, modelos, llamador, resultado, nom, plazo, almacen.controles())
    cursor = almacen.cursor(CURSOR) or {}
    # Primera pasada: lo que ya había cuenta como visto (el foco es solo lo reciente).
    vistos = set(cursor["vistos"]) if "vistos" in cursor else {d["id"] for d in _activos(almacen)}
    reaplicar_uniones(almacen, ctx.decisiones, ahora, modelos)
    reglas_deterministas(ctx)
    activos = _activos(almacen)
    if alcance == "repaso":
        foco = {d["id"] for d in activos}
    elif alcance == "noche":
        foco = {d["id"] for d in activos if _reciente(d, ahora - VENTANA_NOCHE)}
    else:
        foco = {
            d["id"]
            for d in activos
            if d["id"] not in vistos or _reciente(d, ahora - VENTANA_HORARIA)
        }
        foco = {i for i in foco if i not in vistos or _cambiado(ctx, i, activos)}
    try:
        comparar_pares(ctx, foco)
        verificar(ctx, foco)
    finally:
        almacen.guardar_controles(ctx.nuevas, _iso(ahora))
    ctx.decisiones = {**ctx.decisiones, **ctx.nuevas}
    ctx.nuevas = {}
    aplicar_verificaciones(ctx)
    hechas = set(almacen.traducciones())
    # Las citas de lo nuevo y lo cambiado; lo atrasado, de madrugada y en el repaso, para que no
    # se coma el gasto del día que necesitan las fichas nuevas.
    en_foco = [d for d in _activos(almacen) if d["id"] in foco]
    decisiones_foco = {
        k: v for k, v in ctx.decisiones.items()
        if k.startswith("verificacion:") and k.removeprefix("verificacion:") in foco
    }  # fmt: skip
    traducir(ctx, citas_de(en_foco, decisiones_foco), hechas)
    if alcance in {"noche", "repaso"} and not llamador.parado:
        if alcance == "noche":
            # Con lo que sobra del día y sin pasar del tope de la madrugada: el resto del día es
            # para las recogidas horarias.
            llamador.tope = TOPE_NOCHE_USD
        atrasadas = {
            **citas_pendientes(almacen, "europa"),
            **citas_de(_activos(almacen), ctx.decisiones),
        }
        traducir(ctx, atrasadas, set(almacen.traducciones()))
        traducir(ctx, citas_pendientes(almacen, "ucrania"), set(almacen.traducciones()))
    if alcance != "repaso":
        nuevo_cursor = retener(ctx, cursor, verificar_nuevos=True)
    else:
        nuevo_cursor = retener(ctx, cursor, verificar_nuevos=False)
    almacen.guardar_cursor(CURSOR, nuevo_cursor)
    registro.info("control de fichas (%s): %s", alcance, resultado.resumen())
    return resultado


def _cambiado(ctx: Contexto, id_: str, activos: list[Documento]) -> bool:
    """El incidente tiene fuentes que no se verificaron."""
    documento = next(d for d in activos if d["id"] == id_)
    decision = ctx.decisiones.get(reglas.clave_verificacion(id_))
    return decision is None or decision.get("huella") != reglas.huella_fuentes(documento)


def _fabrica() -> Callable[[], Servicio] | None:
    try:
        from modelo import cliente as servicio

        configuracion = servicio.configuracion()
    except Exception as error:
        registro.info("control de fichas sin servicio: %s", str(error)[:200])
        return None
    return lambda: servicio.Cliente(configuracion)


def paso_horario(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> Resultado:
    """Paso de la recogida horaria, con su tope de tiempo y de gasto."""
    return ejecutar(almacen, ahora, modelos, "horaria", _fabrica(), Plazo(TOPE_S))


# --- Repaso de todo lo publicado, por lotes -------------------------------------------------


class ServicioLotes(Protocol):
    def crear_lote(self, peticiones: list[dict[str, Any]]) -> dict[str, Any]: ...

    def lote(self, id_: str) -> dict[str, Any]: ...

    def resultados_lote(self, lote: dict[str, Any]) -> list[dict[str, Any]]: ...


@dataclass
class Respuestas:
    """Lo que devuelve un lote: la respuesta leída de cada petición y su uso."""

    leidas: dict[str, dict[str, Any] | None] = field(default_factory=dict)
    usos: dict[str, coste.Uso] = field(default_factory=dict)
    fuera_de_tope: int = 0


def por_lote(
    servicio: ServicioLotes, lista: list[Peticion], disponible: float,
    dormir: Callable[[float], None], reloj: Callable[[], float],
) -> Respuestas:  # fmt: skip
    """Manda las peticiones en un lote (a mitad de precio) hasta el peor caso de `disponible`
    dólares y espera a que termine. Lo que no cabe queda fuera."""
    respuestas = Respuestas()
    elegidas: dict[str, Peticion] = {}
    previsto = 0.0
    for numero, peticion in enumerate(lista):
        peor = coste.peor_caso(peticiones.letras(peticion.cuerpo), peticion.max_salida, lote=True)
        if previsto + peor > disponible:
            respuestas.fuera_de_tope = len(lista) - numero
            break
        previsto += peor
        elegidas[f"c{numero:06d}"] = peticion
    if not elegidas:
        return respuestas
    creado = servicio.crear_lote(
        [{"custom_id": i, "params": p.cuerpo} for i, p in elegidas.items()]
    )
    registro.info("lote %s enviado: %d peticiones, peor caso %.4f USD", creado["id"],
                  len(elegidas), previsto)  # fmt: skip
    inicio = reloj()
    estado = creado
    while estado.get("processing_status") != "ended":
        if reloj() - inicio > TOPE_LOTE_S:
            raise TimeoutError(f"el lote {creado['id']} no terminó")
        dormir(ESPERA_LOTE_S)
        estado = servicio.lote(creado["id"])
    for resultado in servicio.resultados_lote(estado):
        elegida = elegidas.get(resultado.get("custom_id", ""))
        if elegida is None:
            continue
        peticion = elegida
        cuerpo = resultado.get("result", {})
        if cuerpo.get("type") != "succeeded":
            respuestas.leidas[peticion.clave] = None
            continue
        mensaje = cuerpo["message"]
        respuestas.usos[peticion.clave] = coste.Uso.de_respuesta(mensaje.get("usage", {}))
        try:
            respuestas.leidas[peticion.clave] = peticiones.leer(mensaje)
        except peticiones.RespuestaInvalida:
            respuestas.leidas[peticion.clave] = None
    return respuestas


def _anotar_lote(almacen: Almacen, respuestas: Respuestas, ahora: datetime,
                 resultado: Resultado) -> None:  # fmt: skip
    for clave, uso in respuestas.usos.items():
        gasto = uso.coste(lote=True)
        almacen.registrar_llamada({
            "fecha": _iso(ahora), "modo": coste.Modo.CONTROL_REPASO.value, "candidato": clave[:200],
            "lote": True, "entrada": uso.entrada, "salida": uso.salida,
            "escritura_cache": uso.escritura_cache, "lectura_cache": uso.lectura_cache,
            "coste": gasto,
        })  # fmt: skip
        resultado.llamadas += 1
        resultado.gasto += gasto


@dataclass
class Base:
    """Cómo abrir la base, guardarla y tomar el cerrojo de la recogida (en el servidor)."""

    abrir: Callable[[], Almacen]
    guardar: Callable[[Almacen], None]
    cerrojo: Callable[[], Any]


def repaso(base: Base, fabrica: Callable[[], Any], nom: Nomenclator | None = None,
           dormir: Callable[[float], None] | None = None,
           reloj: Callable[[], float] | None = None) -> Resultado:  # fmt: skip
    """El control sobre todo lo publicado, por lotes y en dos rondas: primero los pares (y las
    uniones), después la verificación de cada ficha y las citas (las de Europa y, con lo que
    quede del tope, las de la capa de Ucrania, las más recientes primero). Las peticiones se
    preparan sobre una copia de la base, sin el cerrojo; las respuestas se aplican con el
    cerrojo tomado sobre la base del momento."""
    import time

    dormir = dormir or time.sleep
    reloj = reloj or time.monotonic
    if nom is None:
        from proceso.noticias import nomenclator

        nom = nomenclator()
    resultado = Resultado()
    modo = coste.Modo.CONTROL_REPASO
    servicio = fabrica()
    from recogida.extractor import modelos_base

    for ronda in ("pares", "fichas"):
        ahora = datetime.now(UTC)
        copia = base.abrir()
        modelos = modelos_base() | frozenset(copia.vocabulario("modelo_dron"))
        llamador = Llamador(copia, None, modo, ahora, None, resultado)
        ctx = Contexto(copia, ahora, modelos, llamador, resultado, nom, None, copia.controles())
        todos = {d["id"] for d in _activos(copia)}
        if ronda == "pares":
            textos: dict[str, str] = {}
            lista = [
                peticion_par(ctx, a, b, h, textos) for a, b, h in pares_por_decidir(ctx, todos)
            ]
            for a, b in pares_separados(ctx):
                separado = peticion_par(ctx, a, b, "", textos)
                separado.tipo = "separado"
                separado.clave = "separado:" + separado.clave.removeprefix("par:")
                lista.append(separado)
        else:
            lista = [peticion_verificacion(ctx, d) for d in por_verificar(ctx, todos)]
            hechas = set(copia.traducciones())
            europa = {**citas_pendientes(copia, "europa"),
                      **citas_de(_activos(copia), ctx.decisiones)}  # fmt: skip
            lista += peticiones_traduccion(europa, hechas)
            lista += peticiones_traduccion(citas_pendientes(copia, "ucrania"), hechas)
        disponible = coste.limite(modo) - copia.gastado(modo.value)
        registro.info("repaso, ronda %s: %d peticiones, %.4f USD disponibles", ronda, len(lista),
                      disponible)  # fmt: skip
        respuestas = por_lote(servicio, lista, disponible, dormir, reloj)
        registro.info("repaso, ronda %s: %d respuestas, %d fuera del tope", ronda,
                      len(respuestas.leidas), respuestas.fuera_de_tope)  # fmt: skip
        with base.cerrojo():
            almacen = base.abrir()
            ahora = datetime.now(UTC)
            ctx = Contexto(almacen, ahora, modelos, Llamador(almacen, None, modo, ahora, None,
                           resultado), resultado, nom, None, almacen.controles())  # fmt: skip
            _anotar_lote(almacen, respuestas, ahora, resultado)
            for peticion in lista:
                if peticion.clave not in respuestas.leidas:
                    continue
                respuesta = respuestas.leidas[peticion.clave]
                if peticion.tipo == "par":
                    procesar_par(ctx, peticion, respuesta)
                elif peticion.tipo == "separado":
                    procesar_separado(ctx, peticion, respuesta)
                elif peticion.tipo == "verificacion":
                    procesar_verificacion(ctx, peticion, respuesta)
                else:
                    procesar_traduccion(ctx, peticion, respuesta)
            almacen.guardar_controles(ctx.nuevas, _iso(ahora))
            ctx.decisiones = {**ctx.decisiones, **ctx.nuevas}
            ctx.nuevas = {}
            reglas_deterministas(ctx)
            aplicar_verificaciones(ctx)
            base.guardar(almacen)
    registro.info("repaso: %s", resultado.resumen())
    return resultado


# --- Estado para el resumen diario y la vigilancia ------------------------------------------


def escribir_estado(ruta: Path, resultado: Resultado | None, almacen: Almacen,
                    ahora: datetime) -> None:  # fmt: skip
    """~/.eodi/control.json: lo que hizo el control en cada pasada del día, para el resumen de
    las 08:00 y para la vigilancia."""
    anterior: Documento = {}
    if ruta.exists():
        try:
            anterior = json.loads(ruta.read_text(encoding="utf-8"))
        except ValueError:
            anterior = {}
    dia = ahora.strftime("%Y-%m-%d")
    pasadas = [
        p
        for p in anterior.get("pasadas", [])
        if p.get("fecha", "")[:10] >= coste.dia(ahora - timedelta(days=2))
    ]
    cursor = almacen.cursor(CURSOR) or {}
    # Pasadas seguidas en que el control falló (una excepción o un error del servicio que no es
    # temporal): con FALLOS_PARA_AVISAR, la vigilancia abre la incidencia.
    fallida = resultado is None or resultado.parada == "error"
    fallos = int(anterior.get("fallos_seguidos", 0)) + 1 if fallida else 0
    if resultado is not None:
        pasadas.append({
            "fecha": _iso(ahora), "unidos": resultado.unidos,
            "corregidos": {k: v for k, v in resultado.corregidos.items()},
            "retenidos": resultado.retenidos, "liberados": resultado.liberados,
            "dudosos": len(resultado.dudosos), "verificadas": resultado.verificadas,
            "traducidas": resultado.traducidas, "llamadas": resultado.llamadas,
            "gasto": round(resultado.gasto, 4), "parada": resultado.parada,
            "errores": resultado.errores[:5],
        })  # fmt: skip
    datos = {
        "generado": _iso(ahora),
        "dia": dia,
        "gasto_hoy": round(almacen.gastado(coste.Modo.CONTROL.value, dia), 4),
        "limite_diario": coste.LIMITE_CONTROL_DIARIO_USD,
        "fallos_seguidos": fallos,
        "fallo": resultado is None,
        "retenidos": cursor.get("retenidos", {}),
        "pasadas": pasadas,
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(ruta)


def base_del_servidor(temporal: Path, correo: str, cerrojo: Path | None) -> Base:
    """La base del sitio (en disco en el servidor), con el cerrojo de la recogida."""
    import contextlib

    from almacen import sitio

    def abrir() -> Almacen:
        almacen = sitio.abrir_base(temporal)
        if almacen is None:
            raise RuntimeError("no hay base")
        return almacen

    @contextlib.contextmanager
    def tomar() -> Any:
        if cerrojo is None:
            yield
            return
        import fcntl  # solo en el servidor (Linux)

        with cerrojo.open("a") as fichero:
            registro.info("esperando el cerrojo de la recogida")
            fcntl.flock(fichero, fcntl.LOCK_EX)  # type: ignore[attr-defined,unused-ignore]
            registro.info("cerrojo tomado")
            try:
                yield
            finally:
                fcntl.flock(fichero, fcntl.LOCK_UN)  # type: ignore[attr-defined,unused-ignore]

    return Base(abrir, lambda a: sitio.guardar_base(a, temporal, correo), tomar)


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("alcance", choices=("noche", "repaso", "estado"))
    opciones.add_argument("--estado", type=Path, default=RUTA_ESTADO_DEFECTO)
    opciones.add_argument("--correo", default="", help="correo del autor (solo base en GitHub)")
    opciones.add_argument("--cerrojo", type=Path, help="cerrojo de la recogida (repaso)")
    opciones.add_argument("--sin-servicio", action="store_true",
                          help="solo las reglas que no llaman a nada")  # fmt: skip
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from tempfile import TemporaryDirectory

    from almacen import sitio

    with TemporaryDirectory() as temporal:
        base = base_del_servidor(Path(temporal), args.correo, args.cerrojo)
        ahora = datetime.now(UTC)
        if args.alcance == "repaso":
            fabrica = _fabrica()
            if fabrica is None:
                return 1
            resultado = repaso(base, fabrica)
            print(resultado.resumen())
            return 0
        almacen = base.abrir()
        if args.alcance == "estado":
            print(json.dumps({
                "gasto_control_hoy": almacen.gastado(coste.Modo.CONTROL.value, coste.dia(ahora)),
                "gasto_repaso": almacen.gastado(coste.Modo.CONTROL_REPASO.value),
                "decisiones": len(almacen.controles()),
                "traducciones": len(almacen.traducciones()),
                "cursor": {k: (len(v) if isinstance(v, dict) else v)
                           for k, v in (almacen.cursor(CURSOR) or {}).items()},
            }, ensure_ascii=False, indent=1))  # fmt: skip
            return 0
        from recogida.extractor import modelos_base

        fabrica = None if args.sin_servicio else _fabrica()
        modelos = modelos_base() | frozenset(almacen.vocabulario("modelo_dron"))
        try:
            resultado = ejecutar(almacen, ahora, modelos, args.alcance, fabrica,
                                 Plazo(TOPE_NOCHE_S))  # fmt: skip
        except Exception:
            registro.exception("control de fichas fallido")
            escribir_estado(args.estado, None, almacen, ahora)
            return 1
        escribir_estado(args.estado, resultado, almacen, ahora)
        sitio.guardar_base(almacen, Path(temporal), args.correo)
        print(resultado.resumen())
        return 0


if __name__ == "__main__":
    sys.exit(principal())
