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

Dos modelos (docs/modelos.md): cada llamada la hace el modelo base. Un par dudoso (o cuya
decisión no casa con el día y el sitio) y una verificación que contradice un dato clave de la
ficha se repiten con el experto (proceso/escalado.py) y vale lo suyo; también, siempre, la unión
que retiraría una ficha ya publicada (nada publicado se retira sin el experto). Si el experto ha
agotado su tope del día, el par o la verificación esperan al día siguiente y la ficha nueva sigue
retenida hasta entonces (sin el límite de 6 horas: no se publica mal); lo publicado se queda
como estaba; lo demás sigue. Las traducciones
nunca se escalan. Cada decisión guarda el modelo que la tomó, y cada dato que corrige la
verificación, en control.modelos del incidente.

De madrugada, las traducciones atrasadas van en un lote (a mitad de precio, `noche`): se envía
y la recogida siguiente (o la madrugada siguiente) recoge el resultado (cursor
`control_fichas:lote`).

Gasto: modo «control», 0,15 dólares al día (horaria y madrugada); el repaso de todo lo publicado,
modo «control_repaso», 4 dólares y después 6 más (el 14 de octubre de 2026). Uso:

    python -m recogida.control_fichas noche|repaso|estado|traducir-pendientes [--base DB.age]
        [--ensayo CARPETA]
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
from modelo import coste, ficha, paginas
from modelo.cliente import ErrorTemporal, LlamadaFallida
from proceso import (
    atribucion,
    autoridades,
    buques,
    escalado,
    incidentes,
    lugar_preciso,
    no_es_suceso,
    presencia,
    rectificaciones,
    titulares,
)
from proceso import control_fichas as reglas
from proceso.noticias import Nomenclator
from proceso.presencia import TABLA_MOTIVOS
from recogida import revisados
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger(__name__)

CURSOR = "control_fichas"
ESPERA = timedelta(hours=6)
# En la recogida horaria, una ficha ya verificada que recibe fuentes nuevas se vuelve a verificar
# como mucho cada 6 horas (y siempre de madrugada): el tope diario es para lo nuevo.
ESPERA_REVERIFICAR = timedelta(hours=6)
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
# La pasada de madrugada gasta como mucho esto del día en revisar lo publicado (pares y
# verificaciones por lote, con su escalado al experto).
TOPE_NOCHE_USD = 0.08
# Y aparte, esto en las citas sin traducir: lo nuevo de cada día (unas 15 a 30 citas de la capa
# de Ucrania y lo que no recogieron los lotes de cada hora, medido el 14 de octubre de 2026) cabe
# de sobra (unas 500 citas en el peor caso con el modelo base por lote; con el de antes, una
# petición al menos) y el resto del tope se come lo atrasado. Lo que gaste la revisión no le
# quita sitio.
TOPE_NOCHE_CITAS_USD = 0.05
# Y como mucho este tiempo: tiene que acabar antes de la recogida siguiente.
TOPE_NOCHE_S = 25 * 60.0
# Repaso por lotes: espera entre consultas del estado del lote y tope de espera.
ESPERA_LOTE_S = 60
TOPE_LOTE_S = 12 * 3600
# La madrugada espera su lote como mucho esto (sin el cerrojo); lo que no termina se recoge en la
# recogida siguiente como los lotes de cada hora.
TOPE_LOTE_NOCHE_S = 3 * 3600
# Lotes enviados y aún sin recoger (las citas de cada hora): se recogen en la recogida siguiente.
CURSOR_LOTES = "control_fichas:lotes"
# Un lote termina casi siempre en minutos y como mucho en 24 horas; pasado ese tiempo se olvida y
# sus citas vuelven a quedar pendientes.
CADUCIDAD_LOTE = timedelta(hours=25)
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
    # Llamadas repetidas con el experto, y lo que espera al experto (tope del día o fallo).
    escaladas: int = 0
    esperan_experto: list[str] = field(default_factory=list)
    # Llamadas y gasto de cada modelo en esta pasada.
    por_modelo: dict[str, list[float]] = field(default_factory=dict)

    def resumen(self) -> str:
        return (
            f"llamadas {self.llamadas} ({self.gasto:.4f} USD; escaladas {self.escaladas}, "
            f"esperan al experto {len(self.esperan_experto)}), unidos {len(self.unidos)}, "
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
        # De la última llamada: el modelo que dio la respuesta que vale, los motivos del
        # escalado, si el caso era crítico y, si esperaba al experto y no pudo ser, hasta cuándo
        # espera.
        self.ultimo_modelo = ""
        self.ultimos_motivos: list[str] = []
        self.ultimo_critico = False
        self.ultima_espera: str | None = None

    @property
    def parado(self) -> bool:
        return self.resultado.parada is not None

    @property
    def solo_criticos(self) -> bool:
        """Parado por el tope del modo: aún pasan los casos críticos, directos al experto."""
        return self.resultado.parada == "limite_gasto" and self.fabrica is not None

    def servicio(self) -> Servicio:
        """El servicio de esta pasada (se crea la primera vez)."""
        if self._servicio is None:
            if self.fabrica is None:
                raise RuntimeError("sin servicio")
            self._servicio = self.fabrica()
        return self._servicio

    def llamar(
        self, cuerpo: dict[str, Any], max_salida: int, clave: str,
        escalar: Callable[[dict[str, Any]], list[str]] | None = None, critico: bool = False,
    ) -> dict[str, Any] | None:  # fmt: skip
        """La respuesta leída, o None si no se puede llamar (y queda la parada).

        Con `escalar` (los motivos para escalar una respuesta leída del base), la llamada se
        repite con el experto si hay motivos y vale la suya; si el experto no puede ahora,
        devuelve None sin parar nada y deja en `ultima_espera` hasta cuándo espera. El experto
        paga con su tope (y con la reserva crítica si el caso es `critico` o sus motivos lo
        hacen crítico), nunca con el del modo. Un caso `critico` que ya no cabe en el tope del modo
        va directo al experto, sin el base (lo crítico no espera por los topes normales).
        """
        self.ultimo_modelo, self.ultimos_motivos, self.ultima_espera = "", [], None
        self.ultimo_critico = False
        leida = self._llamar_base(cuerpo, max_salida, clave)
        sin_base = escalar is not None and critico and leida is None and self.solo_criticos
        if sin_base and self._servicio is None:
            try:
                self._servicio = self.servicio()
            except Exception as error:
                self.resultado.errores.append(f"{clave}: {str(error)[:150]}")
                return None
        if escalar is None or self._servicio is None:
            return leida
        if sin_base:
            motivos = [f"{escalado.CRITICO_SIN_BASE}: tope de {self.modo} agotado"]
        else:
            motivos = escalar(leida) if leida is not None else (
                ["respuesta_invalida"] if not self.parado else []
            )  # fmt: skip
        if not motivos:
            return leida
        experto = getattr(self._servicio, "experto", None)
        cliente_experto = experto() if callable(experto) else None
        if cliente_experto is None:
            return leida
        self.ultimos_motivos = motivos
        self.ultimo_critico = critico = critico or escalado.es_critico(motivos)
        modelo_experto = str(getattr(cliente_experto, "modelo", ""))
        esfuerzo = (cuerpo.get("output_config") or {}).get("effort")
        previsto = coste.peor_caso(peticiones.letras(cuerpo), max_salida, modelo=modelo_experto,
                                   esfuerzo=esfuerzo)  # fmt: skip
        dia = coste.dia(self.ahora)
        mes = coste.del_mes(self.almacen, self.ahora, modelo_experto)
        try:
            if not critico and self.modo is coste.Modo.CONTROL:
                # Lo no crítico del control, con su cupo propio del experto (no con su tope).
                coste.comprobar_control_experto(
                    self.almacen.gastado_experto_en(self.modo.value, dia), previsto, mes
                )
            else:
                # Para la reserva crítica cuenta todo lo que el experto gastó hoy, también en el
                # cupo del control.
                gastado = self.almacen.gastado_modelo(modelo_experto, dia)
                if self.modo is coste.Modo.CONTROL:
                    gastado += self.almacen.gastado_experto_en(self.modo.value, dia)
                coste.comprobar_experto(gastado, previsto, critico, mes)
        except coste.LimiteGasto:
            self._esperar(clave, coste.espera_experto(self.ahora, critico))
            return None
        try:
            respuesta = cliente_experto.mensaje(cuerpo)
        except LlamadaFallida as error:
            self.resultado.errores.append(f"{clave}: experto: {str(error)[:150]}")
            self._esperar(clave, _iso(self.ahora + timedelta(minutes=50)))
            return None
        self.resultado.escaladas += 1
        return self._anotar(respuesta, clave, escalada=True)

    def _esperar(self, clave: str, hasta: str) -> None:
        self.ultima_espera = hasta
        self.resultado.esperan_experto.append(clave)
        registro.info("%s espera al experto hasta %s: %s", clave, hasta,
                      "; ".join(self.ultimos_motivos[:3]))  # fmt: skip
        return None

    def _anotar(self, respuesta: dict[str, Any], clave: str, escalada: bool = False
                ) -> dict[str, Any] | None:  # fmt: skip
        uso = coste.Uso.de_mensaje(respuesta)
        gasto = uso.coste()
        self.almacen.registrar_llamada({
            "fecha": _iso(self.ahora), "modo": self.modo.value, "candidato": clave[:200],
            "lote": False, "entrada": uso.entrada, "salida": uso.salida,
            "escritura_cache": uso.escritura_cache, "lectura_cache": uso.lectura_cache,
            "coste": gasto, "modelo": uso.modelo, "escalada": escalada,
        })  # fmt: skip
        self.resultado.llamadas += 1
        self.resultado.gasto += gasto
        cuenta = self.resultado.por_modelo.setdefault(uso.modelo or "?", [0, 0.0])
        cuenta[0] += 1
        cuenta[1] += gasto
        self.ultimo_modelo = uso.modelo
        try:
            return peticiones.leer(respuesta)
        except peticiones.RespuestaInvalida as error:
            self.resultado.errores.append(f"{clave}: {error}")
            return None

    def _llamar_base(self, cuerpo: dict[str, Any], max_salida: int, clave: str
                     ) -> dict[str, Any] | None:  # fmt: skip
        if self.parado:
            return None
        if self.fabrica is None:
            self.resultado.parada = "sin_servicio"
            return None
        dia = coste.dia(self.ahora) if coste.diario(self.modo) else None
        gastado = self.almacen.gastado(self.modo.value, dia)
        esfuerzo = (cuerpo.get("output_config") or {}).get("effort")
        previsto = coste.peor_caso(peticiones.letras(cuerpo), max_salida, esfuerzo=esfuerzo)
        try:
            if self.plazo is not None:
                self.plazo.comprobar()
            coste.comprobar(gastado, previsto, self.modo, coste.del_mes(self.almacen, self.ahora))
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
        return self._anotar(respuesta, clave)


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


def paginas_de(enlaces: list[str], plazo: Plazo | None) -> dict[str, paginas.Pagina]:
    """Las primeras frases y las marcas de cada noticia, en memoria (nunca se guardan)."""
    from recogida.descarga import Descargador

    def uno(enlace: str) -> tuple[str, paginas.Pagina]:
        try:
            return enlace, paginas.leer_pagina(Descargador(plazo=plazo, reintentos=1), enlace)
        except Exception:
            return enlace, paginas.Pagina("")

    if not enlaces:
        return {}
    with ThreadPoolExecutor(max_workers=6) as hilos:
        return dict(hilos.map(uno, enlaces))


def descargar(enlaces: list[str], plazo: Plazo | None) -> dict[str, str]:
    """Las primeras frases de cada noticia, en memoria (nunca se guardan)."""
    return {enlace: pagina.texto for enlace, pagina in paginas_de(enlaces, plazo).items()}


def no_es_suceso_de(
    almacen: Almacen, incidente: Documento, leidas: dict[str, paginas.Pagina]
) -> no_es_suceso.Veredicto | None:
    """Si ninguna fuente de la ficha cuenta un suceso (proceso/no_es_suceso.py): todas sus
    fuentes públicas son noticias, se han leído y su página, su dirección o su titular dicen que
    son contenido patrocinado, opinión, análisis, explicativo, entrevista o resumen. Con una
    fuente oficial, nunca."""
    publicas = _publicas(incidente)
    if not publicas or any(reglas.oficial(f) for f in publicas):
        return None
    enlaces = list(dict.fromkeys(str(f.get("enlace") or "") for f in publicas))
    if "" in enlaces or any(e not in leidas for e in enlaces):
        return None
    titulares_ = _titulares(almacen, publicas)
    medios = {str(f.get("enlace")): str(f.get("medio", "")) for f in publicas}
    return no_es_suceso.de_fuentes(
        ficha.FuenteTexto(medios[e], "", None, titulares_.get(e, ""), "", e, leidas[e].marcas)
        for e in enlaces
    )  # fmt: skip


def senalar_no_suceso(
    ctx: "Contexto", incidente: Documento, veredicto: no_es_suceso.Veredicto
) -> bool:
    """La ficha publicada cuyas fuentes no cuentan un suceso se repite con el experto, que
    decide si se retira (nada publicado se retira sin él). True si se anota."""
    from proceso import extraccion

    candidato = (incidente.get("control") or {}).get("candidato")
    if not candidato or extraccion.esperan_experto(ctx.almacen).get(candidato, {}).get("revision"):
        return False
    # El experto ya la vio con este motivo y la mantuvo: no se le vuelve a mandar cada vez que el
    # control verifica la ficha.
    anteriores = ctx.almacen.extracciones(candidato)
    if anteriores and any(
        no_es_suceso.PREFIJO_MOTIVO in m for m in anteriores[-1].get("escalado") or []
    ):
        return False
    extraccion.anotar_espera(ctx.almacen, candidato, [veredicto.motivo_escalado()], ctx.ahora,
                             False, revision=True)  # fmt: skip
    registro.warning("%s: %s; se repite con el experto", incidente["id"],
                     veredicto.motivo_escalado())  # fmt: skip
    return True


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


def conservar_la_mas_antigua(
    almacen: Almacen, decisiones: dict[str, Documento], ahora: datetime, modelos: frozenset[str]
) -> dict[str, Documento]:
    """Las uniones del control conservan la ficha más antigua (reglas.mas_antiguo). Las que
    conservaron la más nueva (hasta el 14 de octubre de 2026 se miraba la fecha de alta) cambian de
    número: la ficha publicada sigue igual (su lugar, sus fuentes y lo que el control verificó y
    corrigió, cada valor con su afirmación de origen) pero con el identificador de la más antigua;
    la más nueva pasa a llevar a ella, y también las demás que se habían unido a la nueva. Devuelve
    las decisiones corregidas (para guardarlas, con la verificación copiada al número que queda);
    sin nada que corregir, no toca nada."""
    corregidas: dict[str, Documento] = {}
    vigentes = {**decisiones}
    for clave in sorted(vigentes):
        decision = vigentes[clave]
        if decision.get("decision") != "mismo" or "conserva" not in decision:
            continue
        nuevo_id, viejo_id = decision["conserva"], decision["une"]
        if reglas.orden_registro(viejo_id) >= reglas.orden_registro(nuevo_id):
            continue
        conserva = almacen.incidente(nuevo_id)
        une = almacen.incidente(viejo_id)
        if (
            conserva is None or une is None or not incidentes.activo(conserva)
            or une.get("fusionado_en") != nuevo_id
        ):  # fmt: skip
            continue
        otros = [
            f for f in almacen.fusiones()
            if not f["revertida"] and f["destino"] == nuevo_id and f["absorbido"] != viejo_id
        ]  # fmt: skip
        fecha = ahora.strftime("%Y-%m-%dT%H:%MZ")
        queda = {**copy.deepcopy(conserva), "id": viejo_id}
        altas = sorted((une["control"]["alta"], conserva["control"]["alta"]),
                       key=lambda a: str(a["valor"]))  # fmt: skip
        queda["control"]["alta"] = altas[0]
        fundido = {**copy.deepcopy(conserva), "fusionado_en": viejo_id}
        fundido.pop("episodio", None)
        almacen.guardar_incidente(queda, ahora, modelos)
        almacen.guardar_incidente(fundido, ahora, modelos)
        propias = {f["id"] for f in une.get("fuentes", [])}
        aportadas = [f["id"] for f in conserva["fuentes"] if f["id"] not in propias]
        almacen.revertir_fusion(viejo_id)
        almacen.registrar_fusion(
            fecha, nuevo_id, viejo_id,
            incidentes.PREFIJO_REVISADA + PREFIJO_UNION + str(decision.get("motivo_es", "")),
            aportadas,
        )  # fmt: skip
        for fusion in otros:
            otro = almacen.incidente(fusion["absorbido"])
            if otro is None or otro.get("fusionado_en") != nuevo_id:
                continue
            almacen.guardar_incidente({**otro, "fusionado_en": viejo_id}, ahora, modelos)
            almacen.revertir_fusion(fusion["absorbido"])
            almacen.registrar_fusion(
                fecha, fusion["absorbido"], viejo_id, fusion["motivo"], fusion["fuentes"]
            )
        nota = f"se conserva la ficha más antigua ({viejo_id}), no {nuevo_id}"
        corregidas[clave] = {**decision, "conserva": viejo_id, "une": nuevo_id, "corregida": nota}
        verificada = vigentes.get(reglas.clave_verificacion(nuevo_id))
        if verificada is not None:
            corregidas[reglas.clave_verificacion(viejo_id)] = {**verificada, "corregida": nota}
        for otra, d in vigentes.items():
            if otra != clave and d.get("conserva") == nuevo_id:
                corregidas[otra] = {**d, "conserva": viejo_id, "corregida": nota}
        vigentes.update(corregidas)
        registro.info("control de fichas: %s (y %d unidas a ella)", nota, len(otros))
    return corregidas


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


def espera_vigente(clave: str, activos: dict[str, Documento]) -> bool:
    """Lo que espera al experto sigue en juego: sus fichas siguen activas y, si es un par, aún son
    candidatas al mismo suceso. Si una se unió a otra o se retiró (o el par ya no lo es), no queda
    nada que decidir: no retiene ninguna ficha ni cuenta como caso crítico que espera (el 20 de
    octubre de 2026, el par EODI-2025-00438|00444 siguió esperando después de que la regla de
    fusión uniera 00438 a 00444, retuvo 00444 y abrió la incidencia del experto)."""
    tipo, _, ids = clave.partition(":")
    fichas = [activos.get(i) for i in ids.split("|")]
    if not fichas or any(f is None for f in fichas):
        return False
    if tipo == "par" and len(fichas) == 2:
        a, b = fichas
        return a is not None and b is not None and reglas.candidatos(a, b)
    return True


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


def esperas_vencidas(ctx: Contexto) -> set[str]:
    """Las fichas de los pares y verificaciones que esperaban al experto y ya pueden volver
    (venció su espera o subió el tope del experto)."""
    ahora = _iso(ctx.ahora)
    fichas: set[str] = set()
    activos = {d["id"]: d for d in _activos(ctx.almacen)}
    for clave, decision in ctx.decisiones.items():
        if not decision.get("espera_experto") or "datos" in decision:
            continue
        if not espera_vigente(clave, activos):
            continue
        if decision.get("decision", "dudoso") != "dudoso":
            continue
        if coste.espera_vencida(str(decision["espera_experto"]), ahora,
                                decision.get("tope_experto")):  # fmt: skip
            fichas |= set(clave.split(":", 1)[1].split("|"))
    return fichas


def pares_por_decidir(
    ctx: Contexto, foco: set[str], revisar_decididos: bool = True, forzar: bool = False
) -> list[tuple[Documento, Documento, str]]:
    """Los pares candidatos que hay que comparar (con la huella de sus fuentes). Resuelve los
    dudosos que llevan 6 horas como distintos y deja en dudosos los que no han cambiado. Sin
    `revisar_decididos` (la recogida horaria), un par ya decidido no se vuelve a comparar aunque
    lleguen fuentes nuevas: lo hace la pasada de madrugada. Con `forzar` (el repaso con el
    experto), todos salvo los que ese repaso ya decidió con las mismas fuentes."""
    activos = _activos(ctx.almacen)
    resultado = []
    for a, b in reglas.pares_candidatos(activos, foco):
        clave = reglas.clave_par(a["id"], b["id"])
        huella = reglas.huella_fuentes(a) + reglas.huella_fuentes(b)
        previa = ctx.decision(clave)
        if forzar:
            if not _hecho_en_repaso(previa, huella):
                resultado.append((a, b, huella))
            continue
        if previa is not None:
            if previa["decision"] in {"mismo", "distinto"} and (
                previa.get("huella") == huella or not revisar_decididos
            ):
                continue
            if previa["decision"] == "dudoso" and previa.get("espera_experto"):
                # Espera al experto: no se resuelve solo a las 6 horas; se vuelve a comparar
                # cuando el experto puede (el día siguiente, la recogida siguiente si es crítico
                # o en cuanto sube su tope).
                if not coste.espera_vencida(
                    str(previa["espera_experto"]), _iso(ctx.ahora), previa.get("tope_experto")
                ):
                    ctx.resultado.dudosos.append(clave)
                    continue
                resultado.append((a, b, huella))
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
    # La que se uniría a la otra, si ya está publicada: esa unión solo la decide el experto.
    une = reglas.mas_antiguo(a, b)[1]["id"]
    une_publicada = une if une not in retenidos(ctx.almacen) else None
    # Crítico para el gasto del experto: la unión retiraría una publicada, o una de las dos es
    # un caso crítico.
    es_critico = une_publicada is not None or critico(a) or critico(b)
    return Peticion("par", clave, cuerpo, peticiones.MAX_SALIDA_COMPARAR,
                    {"a": a["id"], "b": b["id"], "huella": huella,
                     "une_publicada": une_publicada, "critico": es_critico})  # fmt: skip


def motivos_par(peticion: Peticion) -> Callable[[dict[str, Any]], list[str]]:
    """Los motivos para escalar la comparación (proceso/escalado.py): el par dudoso o que no
    casa, y la unión que retiraría una ficha ya publicada."""

    def motivos(respuesta: dict[str, Any]) -> list[str]:
        return escalado.motivos_comparacion(respuesta) or escalado.motivos_union(
            respuesta, peticion.datos.get("une_publicada")
        )

    return motivos


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


def decision_comprobada(respuesta: dict[str, Any]) -> str:
    """«mismo» solo con el mismo día, el mismo sitio y ninguna ficha que resuma varios sucesos;
    si la respuesta dice «mismo» sin eso, queda dudoso."""
    decision = str(respuesta.get("decision"))
    if decision != "mismo":
        return decision
    if (
        respuesta.get("mismo_dia") is True
        and respuesta.get("mismo_sitio") is True
        and (respuesta.get("varios_sucesos") is False)
    ):
        return "mismo"
    return "dudoso"


def procesar_par(ctx: Contexto, peticion: Peticion, respuesta: dict[str, Any] | None) -> None:
    """La decisión del par y, si son el mismo suceso, la unión (se conserva el más antiguo)."""
    clave = peticion.clave
    if respuesta is None and ctx.llamador.ultima_espera:
        anterior = ctx.decision(clave) or {}
        ctx.nuevas[clave] = {
            "decision": "dudoso", "huella": peticion.datos["huella"], "fecha": _iso(ctx.ahora),
            "desde": anterior.get("desde", _iso(ctx.ahora)), "version": peticiones.VERSION,
            "espera_experto": ctx.llamador.ultima_espera,
            "tope_experto": coste.LIMITE_EXPERTO_DIARIO_USD,
            "escalado": ctx.llamador.ultimos_motivos,
        }  # fmt: skip
        if ctx.llamador.ultimo_critico:
            ctx.nuevas[clave]["critico"] = True
        ctx.resultado.dudosos.append(clave)
        return
    if respuesta is None or respuesta.get("decision") not in peticiones.DECISIONES:
        ctx.resultado.dudosos.append(clave)
        return
    from recogida.revisados import _vivo

    a = _vivo(ctx.almacen, peticion.datos["a"])
    b = _vivo(ctx.almacen, peticion.datos["b"])
    previa = ctx.decision(clave)
    decision: Documento = {
        "decision": decision_comprobada(respuesta), "huella": peticion.datos["huella"],
        "fecha": _iso(ctx.ahora), "motivo_es": str(respuesta.get("motivo_es", ""))[:500],
        "motivo_en": str(respuesta.get("motivo_en", ""))[:500], "version": peticiones.VERSION,
        **{k: bool(respuesta.get(k)) for k in ("mismo_dia", "mismo_sitio", "varios_sucesos")},
    }  # fmt: skip
    if ctx.llamador.ultimo_modelo:
        decision["modelo"] = ctx.llamador.ultimo_modelo
    if ctx.llamador.ultimos_motivos:
        decision["escalado"] = ctx.llamador.ultimos_motivos
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


def comparar_pares(ctx: Contexto, foco: set[str], revisar_decididos: bool = True) -> None:
    textos: dict[str, str] = {}
    for a, b, huella in pares_por_decidir(ctx, foco, revisar_decididos):
        a2, b2 = ctx.almacen.incidente(a["id"]), ctx.almacen.incidente(b["id"])
        if a2 is None or b2 is None or not incidentes.activo(a2) or not incidentes.activo(b2):
            continue
        clave = reglas.clave_par(a["id"], b["id"])
        if ctx.llamador.parado and not ctx.llamador.solo_criticos:
            ctx.resultado.dudosos.append(clave)
            continue
        peticion = peticion_par(ctx, a2, b2, huella, textos)
        if ctx.llamador.parado and not peticion.datos.get("critico"):
            ctx.resultado.dudosos.append(clave)
            continue
        respuesta = ctx.llamador.llamar(peticion.cuerpo, peticion.max_salida, clave,
                                        motivos_par(peticion),
                                        bool(peticion.datos.get("critico")))  # fmt: skip
        procesar_par(ctx, peticion, respuesta)


def por_verificar(
    ctx: Contexto, foco: set[str], espera: timedelta | None = None, forzar: bool = False
) -> list[Documento]:
    """Las fichas del foco con fuentes que aún no se verificaron, las más recientes primero. Con
    `espera` (la recogida horaria), una ficha ya verificada con fuentes nuevas se vuelve a
    verificar como mucho una vez en ese tiempo; las nuevas, siempre. Con `forzar` (el repaso con
    el experto), todas las del foco salvo las que ese repaso ya verificó con las mismas fuentes."""
    resultado = []
    for incidente in sorted(_activos(ctx.almacen), key=lambda d: d["control"]["alta"]["valor"],
                            reverse=True):  # fmt: skip
        if incidente["id"] not in foco or not _publicas(incidente):
            continue
        previa = ctx.decision(reglas.clave_verificacion(incidente["id"]))
        if forzar:
            if not _hecho_en_repaso(previa, reglas.huella_fuentes(incidente)):
                resultado.append(incidente)
            continue
        if previa is not None and previa.get("espera_experto"):
            # Espera al experto: se vuelve a verificar cuando puede.
            if coste.espera_vencida(
                str(previa["espera_experto"]), _iso(ctx.ahora), previa.get("tope_experto")
            ):
                resultado.append(incidente)
            continue
        fallos = reglas.fallos_de_ficha(incidente)
        if fallos and (previa is None or previa.get("fallos") != fallos):
            # Un fallo conocido de la ficha (buque como lugar, fecha de publicación con «la
            # semana pasada»…): se verifica con el experto aunque sus fuentes no cambien.
            resultado.append(incidente)
            continue
        if previa is not None and previa.get("huella") == reglas.huella_fuentes(incidente):
            continue
        if (
            previa is not None
            and espera is not None
            and ctx.ahora - _leer(str(previa["fecha"])) < espera
        ):
            continue
        resultado.append(incidente)
    return resultado


def peticion_verificacion(ctx: Contexto, incidente: Documento) -> Peticion:
    publicas = _publicas(incidente)
    leidas = paginas_de(
        list(dict.fromkeys(f["enlace"] for f in publicas if f.get("enlace")))[:8], ctx.plazo
    )
    textos = {enlace: pagina.texto for enlace, pagina in leidas.items()}
    # Lo que no cuenta un suceso no se mantiene como ficha: lo decide el experto.
    if (veredicto := no_es_suceso_de(ctx.almacen, incidente, leidas)) is not None:
        senalar_no_suceso(ctx, incidente, veredicto)
    fuentes = fuentes_de_ficha(ctx.almacen, incidente, textos)
    vista = reglas.vista(incidente)
    cuerpo = peticiones.cuerpo_verificar(vista, fuentes.bloques)
    return Peticion("verificacion", reglas.clave_verificacion(incidente["id"]), cuerpo,
                    peticiones.MAX_SALIDA_VERIFICAR,
                    {"huella": reglas.huella_fuentes(incidente), "vista": vista,
                     "comprobar": fuentes.comprobar,
                     "critico": critico(incidente),
                     "autoridad": presencia.atribuida_por_autoridad(incidente),
                     "fallos": reglas.fallos_de_ficha(incidente)})  # fmt: skip


def critico(incidente: Documento) -> bool:
    """Un caso crítico para el escalado y la reserva crítica del experto: confirmado o
    atribuido, incursión o suceso en una base militar de un país de la OTAN o de Moldavia,
    cierre de aeropuerto, o con víctimas, heridos o daños."""
    pais = str(incidente.get("pais") or (incidente.get("lugar") or {}).get("pais") or "")
    consecuencias = incidente.get("consecuencias") or {}
    cierre = (consecuencias.get("cierre") or {}).get("valor")
    danos = (consecuencias.get("danos") or {}).get("nivel")
    personas = [consecuencias.get(c) for c in ("heridos", "fallecidos")]
    lugar = incidente.get("lugar") or {}
    titulos = tuple(str(t) for t in (incidente.get("titulo") or {}).values())
    nombres = tuple(str(lugar.get(c) or "") for c in ("nombre", "suceso", "sitio"))
    return (
        incidente.get("presencia_dron") == "confirmada"
        or incidente.get("estado", {}).get("actual") in {"confirmado", "atribuido"}
        or (incidente.get("tipo") == "incursion" and escalado.critico_otan(pais))
        or cierre == "si"
        or danos in {"menores", "graves"}
        or any(_con_personas(p) for p in personas)
        or escalado.es_critico([], (*titulos, *nombres), pais)
    )  # fmt: skip


def _con_personas(rango: Any) -> bool:
    """Un número de heridos o fallecidos que no es cero ni desconocido."""
    if isinstance(rango, int | float):
        return rango > 0
    if isinstance(rango, dict):
        return any(isinstance(v, int | float) and v > 0 for v in rango.values())
    return False


# La presencia que lee la verificación frente a la de la ficha: lo que la contradice.
_PRESENCIA_CONTRARIA = {
    "confirmada": {"no_hallado", "desmentido", "posible"},
    "no_confirmada": {"no_hallado", "desmentido"},
    "descartada": {"confirmada"},
    # Atribuida a drones por una autoridad: no encontrarlos no la contradice; un desmentido, sí
    # (va a las rectificaciones oficiales, proceso/control_fichas._presencia).
    "atribuida": {"desmentido"},
    # Rectificada por una autoridad oficial (proceso/rectificaciones.py): la cambia solo otra
    # rectificación, nunca la verificación de sus fuentes.
    "no_acreditada": set(),
}


def contradice(vista: dict[str, Any], respuesta: dict[str, Any],
               autoridad: bool = False) -> list[str]:  # fmt: skip
    """Los datos clave en que la verificación del modelo contradice la ficha (los dos con
    valor y distintos): presencia del dron, número de drones y cierre. Con `autoridad` (una
    autoridad atribuye el suceso a drones), la presencia confirmada solo la contradice un
    desmentido."""

    def valor(clave: str) -> Any:
        dato = respuesta.get(clave)
        return dato.get("valor") if isinstance(dato, dict) else None

    contra = []
    actual_presencia = str(vista.get("presencia_dron"))
    if autoridad and actual_presencia == "confirmada":
        actual_presencia = "atribuida"
    if valor("presencia") in _PRESENCIA_CONTRARIA.get(actual_presencia, set()):
        contra.append("presencia")
    drones = str(valor("drones") or "").replace(" ", "")
    actual = str(vista.get("drones") or "")
    if drones and actual not in {"", "sin dato"} and drones != actual.replace(" ", ""):
        contra.append("drones")
    cierre = valor("cierre")
    if cierre in {"si", "no"} and vista.get("cierre") in {"si", "no"} and cierre != vista["cierre"]:
        contra.append("cierre")
    return contra


def procesar_verificacion(ctx: Contexto, peticion: Peticion,
                          respuesta: dict[str, Any] | None) -> None:  # fmt: skip
    if respuesta is None and ctx.llamador.ultima_espera:
        # Contradice la ficha y el experto no puede ahora: se espera, sin aplicar nada.
        anterior = ctx.decision(peticion.clave) or {}
        ctx.nuevas[peticion.clave] = {
            "huella": peticion.datos["huella"], "fecha": _iso(ctx.ahora),
            "version": peticiones.VERSION, "espera_experto": ctx.llamador.ultima_espera,
            "tope_experto": coste.LIMITE_EXPERTO_DIARIO_USD,
            "desde": anterior.get("desde") if anterior.get("espera_experto") else _iso(ctx.ahora),
            "escalado": ctx.llamador.ultimos_motivos,
        }  # fmt: skip
        if ctx.llamador.ultimo_critico:
            ctx.nuevas[peticion.clave]["critico"] = True
        return
    if respuesta is None:
        return
    comprobada = reglas.comprobar(respuesta, peticion.datos["comprobar"])
    ctx.nuevas[peticion.clave] = {
        "huella": peticion.datos["huella"], "fecha": _iso(ctx.ahora),
        "vista": peticion.datos["vista"], "version": peticiones.VERSION,
        "datos": {k: list(v) for k, v in comprobada.datos.items()},
        "sin_comprobar": sorted(set(respuesta) - set(comprobada.datos)),
    }  # fmt: skip
    if peticion.datos.get("fallos"):
        ctx.nuevas[peticion.clave]["fallos"] = peticion.datos["fallos"]
    if ctx.llamador.ultimo_modelo:
        ctx.nuevas[peticion.clave]["modelo"] = ctx.llamador.ultimo_modelo
    if ctx.llamador.ultimos_motivos:
        ctx.nuevas[peticion.clave]["escalado"] = ctx.llamador.ultimos_motivos
    ctx.resultado.verificadas += 1


def motivos_verificacion(peticion: Peticion) -> Callable[[dict[str, Any]], list[str]]:
    """Los motivos para escalar la verificación (proceso/escalado.py): que contradiga la ficha
    en un dato clave (si además es un caso crítico, se anota) o que la ficha tenga un fallo
    conocido (proceso/control_fichas.fallos_de_ficha): esa va siempre al experto."""

    def motivos(respuesta: dict[str, Any]) -> list[str]:
        return escalado.motivos_verificacion(
            contradice(peticion.datos["vista"], respuesta, bool(peticion.datos.get("autoridad"))),
            bool(peticion.datos.get("critico")),
        ) + [f"{escalado.MOTIVO_FALLO_FICHA}: {f}" for f in peticion.datos.get("fallos", [])]

    return motivos


def verificar(ctx: Contexto, foco: set[str], espera: timedelta | None = None) -> None:
    for incidente in por_verificar(ctx, foco, espera):
        if ctx.llamador.parado and not ctx.llamador.solo_criticos:
            break
        if ctx.llamador.parado and not critico(incidente):
            continue
        peticion = peticion_verificacion(ctx, incidente)
        respuesta = ctx.llamador.llamar(peticion.cuerpo, peticion.max_salida, peticion.clave,
                                        motivos_verificacion(peticion),
                                        bool(peticion.datos.get("critico")))  # fmt: skip
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
    inicios = revisados.inicios_revisados()
    for incidente in _activos(ctx.almacen):
        decision = decisiones.get(reglas.clave_verificacion(incidente["id"]))
        if decision is not None and decision.get("espera_experto") and "datos" not in decision:
            # Espera al experto: todavía no hay verificación que aplicar.
            continue
        if decision is None or decision.get("anulada"):
            # Una verificación anulada al revisarla (su corrección no era buena) no se aplica;
            # la ficha se vuelve a verificar cuando llegan fuentes nuevas.
            continue
        verificada = _verificada_vigente(decision, incidente)
        conservar: set[str] = set()
        if decision.get("huella") != reglas.huella_fuentes(incidente):
            # Fuentes nuevas aún sin verificar: un valor que ninguna fuente daba solo se quita si
            # es el mismo que se comprobó (lo nuevo puede traerlo).
            actual, vista = reglas.vista(incidente), decision.get("vista", {})
            conservar = {c for c in ("drones", "cierre", "duracion_min", "inicio")
                         if actual.get(c) != vista.get(c)}  # fmt: skip
        if _inicio_revisado_vigente(incidente, inicios.get(str(incidente["id"]))):
            # La hora revisada a mano con su cita (incidentes_revisados.json, titulares.inicio)
            # no la quita la verificación: el verificador puede no leer «entre las 07:00 y las
            # 08:10» como la hora del suceso (EODI-2025-00365).
            conservar |= {"inicio", "duracion_min"}
        fuentes_regla, titular_regla = presencia.respaldo_cierre_de_pista(incidente)
        enlaces = {f.get("enlace") or f["id"] for f in _publicas(incidente)}
        correccion = reglas.aplicar(
            incidente,
            verificada,
            bool(fuentes_regla or titular_regla),
            ctx.nom,
            frozenset(conservar),
            completa=len(enlaces) <= peticiones.MAX_FUENTES,
        )
        if correccion.dudas:
            ctx.resultado.dudas[incidente["id"]] = correccion.dudas
        if correccion.rectificar is not None:
            _a_rectificaciones(ctx.almacen, incidente, *correccion.rectificar)
        if not correccion.cambios:
            continue
        nuevo = incidentes.aplicar_reglas(correccion.incidente)
        nuevo = titulares.ajustar_incidente(nuevo)
        nuevo["titulo"] = atribucion.titulo_segun_atribucion(nuevo)
        if decision.get("modelo"):
            nuevo = anotar_modelos(nuevo, correccion.cambios, str(decision["modelo"]))
        _guardar(ctx, incidente, nuevo, "; ".join(correccion.cambios))


def _a_rectificaciones(almacen: Almacen, incidente: Documento, fuente_id: str, frase: str) -> None:
    """Lo que desmiente una autoridad en una ficha que otra atribuyó a drones, a la cola de las
    rectificaciones oficiales: lo decide el experto (recogida/rectificaciones.py)."""
    from recogida import rectificaciones as seguimiento

    fuente = next((f for f in incidente["fuentes"] if f["id"] == fuente_id), None)
    if fuente is None or not fuente.get("enlace"):
        return
    elegido = {"incidente": incidente["id"], "titular": frase, "url": fuente["enlace"],
               "medio": fuente.get("medio") or "", "fecha": fuente["fecha"]["valor"],
               "idioma": fuente.get("idioma") or "und"}  # fmt: skip
    seguimiento.encolar(almacen, [elegido], seguimiento.ORIGEN_VERIFICACION)


def _inicio_revisado_vigente(incidente: Documento, revisado: Documento | None) -> bool:
    """El inicio del incidente es el revisado a mano (mismo valor y precisión)."""
    inicio = incidente.get("tiempo", {}).get("inicio", {})
    return revisado is not None and (inicio.get("valor"), inicio.get("precision")) == (
        revisado.get("valor"),
        revisado.get("precision"),
    )


# Comienzo de cada corrección de la verificación y el dato de la ficha que corrige.
_CAMPO_CORREGIDO = (
    ("presencia", "presencia_dron"), ("drones", "drones"), ("cierre", "cierre"),
    ("duración", "cierre_minutos"), ("hora", "inicio"), ("día", "inicio"),
    ("lugar", "lugar_suceso"),
)  # fmt: skip


def anotar_modelos(incidente: Documento, cambios: list[str], modelo: str) -> Documento:
    """Anota en control.modelos el modelo que decidió cada dato corregido."""
    campos = {c for cambio in cambios for p, c in _CAMPO_CORREGIDO if cambio.startswith(p)}
    if not campos:
        return incidente
    modelos = {**incidente["control"].get("modelos", {}), **dict.fromkeys(campos, modelo)}
    return {
        **incidente,
        "control": {**incidente["control"], "modelos": dict(sorted(modelos.items()))},
    }


def _guardar(ctx: Contexto, antes: Documento, despues: Documento, motivo: str) -> bool:
    # Lo que el guardado conservaría de las rectificaciones oficiales (Almacen.guardar_incidente)
    # se conserva ya aquí: una corrección que se iba a deshacer no se anota ni se cuenta, y no
    # vuelve en cada pasada.
    despues = rectificaciones.mantener(despues, antes)
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
        sin_nombre = lugar_preciso.nota_sin_nombre(nuevo)
        if sin_nombre is not None:
            nuevo = sin_nombre
            motivos.append("nota del lugar sin el nombre en otro idioma")
        if ctx.nom is not None:
            preciso = lugar_preciso.precisar(nuevo, ctx.nom, ctx.ahora)
            if preciso is not None:
                nuevo = preciso
                motivos.append(f"lugar en {preciso['lugar']['suceso']}, la instalación de la ficha")
        sin_buque = incidentes.lugar_sin_buque(nuevo["lugar"], buques.textos_de(nuevo))
        if sin_buque is not nuevo["lugar"]:
            nuevo = {**nuevo, "lugar": sin_buque}
            motivos.append(f"lugar {sin_buque['suceso']}: el nombre de un buque no es un lugar")
        if nuevo.get("tipo") == "sobrevuelo" and incidentes.alcanzado_en_el_mar(nuevo):
            motivos.append("buque alcanzado por un dron en el mar: no es un sobrevuelo")
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
    las de la verificación; y las autoridades que no están en la tabla, con la marca de nombre
    (proceso/autoridades.py), para que la ficha no salga con una sin traducir."""
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
        visibles = {**documento, "fuentes": _publicas(documento)}
        for nombre, idioma in autoridades.por_traducir(visibles):
            citas.setdefault(huella_texto(nombre), (idioma, autoridades.MARCA + nombre))
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
        texto = texto.removeprefix(autoridades.MARCA)
        es, en = str(entrada.get("es") or "").strip(), str(entrada.get("en") or "").strip()
        if idioma == "es":
            es = texto
        if idioma == "en":
            en = texto
        if es and en:
            nuevas[huella] = {"idioma": idioma, "es": es, "en": en,
                              "version": peticiones.VERSION}  # fmt: skip
    if len(nuevas) < len(tanda):
        # Lo que llega sin una de las dos traducciones no se guarda: se vuelve a pedir otro día.
        registro.warning("traducción %s: %d de %d citas sin las dos traducciones",
                         peticion.clave, len(tanda) - len(nuevas), len(tanda))  # fmt: skip
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
    # Lo que espera al experto se retiene hasta que decida, sin el límite de 6 horas, mientras
    # siga en juego (espera_vigente).
    por_id = {d["id"]: d for d in activos}
    esperan = {
        id_ for clave, d in decisiones.items() if d.get("espera_experto") and "datos" not in d
        and d.get("decision") in {None, "dudoso"} and espera_vigente(clave, por_id)
        for id_ in clave.split(":", 1)[1].split("|")
    }  # fmt: skip
    nuevos_retenidos: dict[str, Documento] = {}
    for incidente in activos:
        id_ = incidente["id"]
        if id_ in vistos:
            continue
        desde = retenidos.get(id_, {}).get("desde", _iso(ctx.ahora))
        motivos = []
        if id_ in pendientes_par:
            motivos.append("posible duplicado sin decidir")
        verificacion = decisiones.get(reglas.clave_verificacion(id_))
        if verificar_nuevos and (
            verificacion is None
            or (verificacion.get("espera_experto") and "datos" not in verificacion)
        ):
            motivos.append("verificación pendiente")
        if id_ in esperan:
            motivos.append("espera al modelo experto")
        if motivos and (id_ in esperan or ctx.ahora - _leer(desde) < ESPERA):
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
    últimas 48 horas) o «repaso» (todo lo publicado, con su propio tope).

    De madrugada, aquí solo se hace lo que no llama al servicio (uniones, reglas, verificaciones
    ya decididas, retención): las llamadas van por lote en `noche`. En la recogida horaria, las
    citas nuevas van en un lote que recoge la recogida siguiente (`enviar_traducciones`)."""
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
    corregidas = conservar_la_mas_antigua(almacen, ctx.decisiones, ahora, modelos)
    if corregidas:
        almacen.guardar_controles(corregidas, _iso(ahora))
        ctx.decisiones = {**ctx.decisiones, **corregidas}
        # La ficha que queda ya estaba publicada (con otro número): no se retiene como nueva.
        if "vistos" in cursor:
            quedan = {d["conserva"] for d in corregidas.values() if "conserva" in d}
            cursor = {
                **cursor,
                "vistos": {**cursor["vistos"], **dict.fromkeys(quedan, _iso(ahora))},
            }
            vistos |= quedan
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
    horaria = alcance == "horaria"
    if horaria:
        recoger_lotes(ctx)
        # Lo que esperaba al experto vuelve en cuanto puede (venció su espera o subió su tope),
        # aunque sus fichas ya no estén entre las nuevas: no espera a la pasada de madrugada.
        foco = foco | esperas_vencidas(ctx)
    try:
        if alcance != "noche":
            comparar_pares(ctx, foco, revisar_decididos=not horaria)
            verificar(ctx, foco, ESPERA_REVERIFICAR if horaria else None)
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
    if horaria:
        enviar_traducciones(ctx, citas_de(en_foco, decisiones_foco), hechas)
    elif alcance == "repaso":
        traducir(ctx, citas_de(en_foco, decisiones_foco), hechas)
    if alcance == "repaso" and not llamador.parado:
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
    # Con el escalado: llamadas directas al experto ya hechas (se anotan con el cerrojo), y por
    # clave, el modelo que dio la respuesta que vale, los motivos y la espera.
    llamadas_experto: list[Documento] = field(default_factory=list)
    # Llamadas directas del modelo base (los casos críticos de madrugada, que no esperan al lote).
    llamadas_directas: list[Documento] = field(default_factory=list)
    modelos: dict[str, str] = field(default_factory=dict)
    motivos: dict[str, list[str]] = field(default_factory=dict)
    esperas: dict[str, str] = field(default_factory=dict)
    criticos: set[str] = field(default_factory=set)


def _peor_lote(peticion: Peticion, modelo: str | None = None) -> float:
    esfuerzo = (peticion.cuerpo.get("output_config") or {}).get("effort")
    return coste.peor_caso(peticiones.letras(peticion.cuerpo), peticion.max_salida, lote=True,
                           modelo=modelo, esfuerzo=esfuerzo)  # fmt: skip


def elegir_para_lote(lista: list[Peticion], disponible: float, modelo: str | None = None
                     ) -> tuple[dict[str, Peticion], float, int]:  # fmt: skip
    """Las peticiones que caben en `disponible` dólares en el peor caso (con el precio de
    `modelo`; sin él, el del base), con su identificador en el lote; el peor caso total y cuántas
    quedan fuera."""
    elegidas: dict[str, Peticion] = {}
    previsto = 0.0
    for numero, peticion in enumerate(lista):
        peor = _peor_lote(peticion, modelo)
        if previsto + peor > disponible:
            return elegidas, previsto, len(lista) - numero
        previsto += peor
        elegidas[f"c{numero:06d}"] = peticion
    return elegidas, previsto, 0


def leer_resultados(servicio: ServicioLotes, estado: dict[str, Any],
                    elegidas: dict[str, Peticion], respuestas: Respuestas) -> None:  # fmt: skip
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
        respuestas.usos[peticion.clave] = coste.Uso.de_mensaje(mensaje)
        respuestas.modelos[peticion.clave] = str(mensaje.get("model") or "")
        try:
            respuestas.leidas[peticion.clave] = peticiones.leer(mensaje)
        except peticiones.RespuestaInvalida:
            respuestas.leidas[peticion.clave] = None


def por_lote(
    servicio: ServicioLotes, lista: list[Peticion], disponible: float,
    dormir: Callable[[float], None], reloj: Callable[[], float], tope_s: float = TOPE_LOTE_S,
    modelo: str | None = None,
) -> Respuestas:  # fmt: skip
    """Manda las peticiones en un lote (a mitad de precio) hasta el peor caso de `disponible`
    dólares y espera a que termine. Lo que no cabe queda fuera."""
    respuestas = Respuestas()
    elegidas, previsto, respuestas.fuera_de_tope = elegir_para_lote(lista, disponible, modelo)
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
        if reloj() - inicio > tope_s:
            raise TimeoutError(f"el lote {creado['id']} no terminó")
        dormir(ESPERA_LOTE_S)
        estado = servicio.lote(creado["id"])
    leer_resultados(servicio, estado, elegidas, respuestas)
    return respuestas


def escalar_lote(
    servicio: Any, almacen: Almacen, lista: list[Peticion], respuestas: Respuestas,
    ahora: datetime, modo: coste.Modo, dormir: Callable[[float], None] | None = None,
    reloj: Callable[[], float] | None = None, tope_s: float = TOPE_LOTE_NOCHE_S,
) -> None:  # fmt: skip
    """Las respuestas del lote (del modelo base) que piden escalado se repiten con el experto
    dentro de su tope del día (los críticos, también de la reserva crítica); lo que no cabe espera
    al día siguiente, o a la recogida siguiente si es crítico. Los críticos van en llamadas
    directas; los demás, con `dormir` y `reloj`, en un lote del experto (a mitad de precio) que se
    espera como el del base. Se hace sin el cerrojo, sobre una copia: las llamadas al experto
    quedan en `respuestas.llamadas_experto` para anotarlas después en la base."""
    experto = getattr(servicio, "experto", None)
    cliente_experto = experto() if callable(experto) else None
    if cliente_experto is None:
        return
    modelo_experto = str(getattr(cliente_experto, "modelo", ""))
    dia = coste.dia(ahora)
    gastado_experto = almacen.gastado_modelo(modelo_experto, dia)
    # Lo no crítico del control va con su cupo propio del experto (coste.comprobar_control_experto).
    gastado_cupo = almacen.gastado_experto_en(modo.value, dia)
    mes = coste.del_mes(almacen, ahora, modelo_experto)
    por_lote_experto = (
        dormir is not None
        and reloj is not None
        and callable(getattr(cliente_experto, "crear_lote", None))
    )
    al_lote: dict[str, Peticion] = {}
    for peticion in lista:
        if peticion.tipo not in {"par", "verificacion"} or peticion.clave not in respuestas.leidas:
            continue
        leida = respuestas.leidas[peticion.clave]
        sin_leer = respuestas.motivos.get(peticion.clave) or ["respuesta_invalida"]
        if peticion.tipo == "par":
            motivos = motivos_par(peticion)(leida) if leida else sin_leer
        else:
            motivos = motivos_verificacion(peticion)(leida) if leida else sin_leer
        if not motivos:
            continue
        respuestas.motivos[peticion.clave] = motivos
        es_critico = bool(peticion.datos.get("critico")) or escalado.es_critico(motivos)
        if es_critico:
            respuestas.criticos.add(peticion.clave)
        esfuerzo = (peticion.cuerpo.get("output_config") or {}).get("effort")
        en_lote = por_lote_experto and not es_critico
        previsto = coste.peor_caso(peticiones.letras(peticion.cuerpo), peticion.max_salida,
                                   lote=en_lote, modelo=modelo_experto,
                                   esfuerzo=esfuerzo)  # fmt: skip
        try:
            if not es_critico and modo is coste.Modo.CONTROL:
                coste.comprobar_control_experto(gastado_cupo, previsto, mes)
            else:
                gastado = gastado_experto + (gastado_cupo if modo is coste.Modo.CONTROL else 0.0)
                coste.comprobar_experto(gastado, previsto, es_critico, mes)
        except coste.LimiteGasto:
            respuestas.esperas[peticion.clave] = coste.espera_experto(ahora, es_critico)
            respuestas.leidas[peticion.clave] = None
            continue
        if en_lote:
            # Lo que no es crítico no tiene prisa de madrugada: va al lote, con su peor caso ya
            # contado.
            if modo is coste.Modo.CONTROL:
                gastado_cupo += previsto
            else:
                gastado_experto += previsto
            al_lote[f"e{len(al_lote):06d}"] = peticion
            continue
        try:
            mensaje = cliente_experto.mensaje(peticion.cuerpo)
        except LlamadaFallida:
            respuestas.esperas[peticion.clave] = _iso(ahora + timedelta(minutes=50))
            respuestas.leidas[peticion.clave] = None
            continue
        uso = coste.Uso.de_mensaje(mensaje)
        if es_critico or modo is not coste.Modo.CONTROL:
            gastado_experto += uso.coste()
        else:
            gastado_cupo += uso.coste()
        respuestas.llamadas_experto.append({
            "fecha": _iso(ahora), "modo": modo.value, "candidato": peticion.clave[:200],
            "lote": False, "entrada": uso.entrada, "salida": uso.salida,
            "escritura_cache": uso.escritura_cache, "lectura_cache": uso.lectura_cache,
            "coste": uso.coste(), "modelo": uso.modelo, "escalada": True,
        })  # fmt: skip
        respuestas.modelos[peticion.clave] = uso.modelo
        try:
            respuestas.leidas[peticion.clave] = peticiones.leer(mensaje)
        except peticiones.RespuestaInvalida:
            respuestas.leidas[peticion.clave] = None
    if al_lote and dormir is not None and reloj is not None:
        lote_experto(cliente_experto, al_lote, respuestas, ahora, modo, dormir, reloj, tope_s)


def directas_criticas(
    servicio: Any, lista: list[Peticion], respuestas: Respuestas, ahora: datetime,
    modo: coste.Modo, disponible: float,
) -> float:  # fmt: skip
    """Los casos críticos de la pasada de madrugada no esperan a un lote: el modelo base los lee en
    llamadas directas, dentro de `disponible` dólares; si no caben o el base falla, van al experto
    sin él (escalar_lote, con su tope o la reserva crítica). Devuelve lo gastado. Se hace sin el
    cerrojo: las llamadas quedan en `respuestas.llamadas_directas` para anotarlas con él."""
    gastado = 0.0
    for peticion in lista:
        esfuerzo = (peticion.cuerpo.get("output_config") or {}).get("effort")
        previsto = coste.peor_caso(peticiones.letras(peticion.cuerpo), peticion.max_salida,
                                   esfuerzo=esfuerzo)  # fmt: skip
        respuestas.leidas[peticion.clave] = None
        if gastado + previsto > disponible:
            respuestas.motivos[peticion.clave] = [
                f"{escalado.CRITICO_SIN_BASE}: tope de {modo} agotado"
            ]
            continue
        try:
            mensaje = servicio.mensaje(peticion.cuerpo)
        except LlamadaFallida as error:
            respuestas.motivos[peticion.clave] = [
                f"{escalado.CRITICO_SIN_BASE}: {str(error)[:150]}"
            ]
            continue
        uso = coste.Uso.de_mensaje(mensaje)
        gastado += uso.coste()
        respuestas.llamadas_directas.append({
            "fecha": _iso(ahora), "modo": modo.value, "candidato": peticion.clave[:200],
            "lote": False, "entrada": uso.entrada, "salida": uso.salida,
            "escritura_cache": uso.escritura_cache, "lectura_cache": uso.lectura_cache,
            "coste": uso.coste(), "modelo": uso.modelo,
        })  # fmt: skip
        respuestas.modelos[peticion.clave] = uso.modelo
        try:
            respuestas.leidas[peticion.clave] = peticiones.leer(mensaje)
        except peticiones.RespuestaInvalida:
            respuestas.leidas[peticion.clave] = None
    return gastado


def lote_experto(
    cliente_experto: Any, elegidas: dict[str, Peticion], respuestas: Respuestas, ahora: datetime,
    modo: coste.Modo, dormir: Callable[[float], None], reloj: Callable[[], float], tope_s: float,
) -> None:  # fmt: skip
    """Las peticiones no críticas que escala el control de madrugada, en un lote con el experto
    (a mitad de precio). Si el lote falla o no termina a tiempo, cada una espera a la recogida
    siguiente, como con un fallo del experto."""
    try:
        creado = cliente_experto.crear_lote(
            [{"custom_id": i, "params": p.cuerpo} for i, p in elegidas.items()]
        )
        registro.info("lote con el experto %s: %d peticiones", creado["id"], len(elegidas))
        inicio = reloj()
        estado = creado
        while estado.get("processing_status") != "ended":
            if reloj() - inicio > tope_s:
                raise TimeoutError(f"el lote con el experto {creado['id']} no terminó")
            dormir(ESPERA_LOTE_S)
            estado = cliente_experto.lote(creado["id"])
        resultados = cliente_experto.resultados_lote(estado)
    except (LlamadaFallida, TimeoutError) as error:
        registro.warning("lote con el experto sin terminar: %s", str(error)[:200])
        resultados = []
    vistas: set[str] = set()
    for resultado in resultados:
        peticion = elegidas.get(str(resultado.get("custom_id", "")))
        cuerpo = resultado.get("result", {})
        if peticion is None or cuerpo.get("type") != "succeeded":
            continue
        vistas.add(peticion.clave)
        mensaje = cuerpo["message"]
        uso = coste.Uso.de_mensaje(mensaje)
        respuestas.llamadas_experto.append({
            "fecha": _iso(ahora), "modo": modo.value, "candidato": peticion.clave[:200],
            "lote": True, "entrada": uso.entrada, "salida": uso.salida,
            "escritura_cache": uso.escritura_cache, "lectura_cache": uso.lectura_cache,
            "coste": uso.coste(lote=True), "modelo": uso.modelo, "escalada": True,
        })  # fmt: skip
        respuestas.modelos[peticion.clave] = uso.modelo
        try:
            respuestas.leidas[peticion.clave] = peticiones.leer(mensaje)
        except peticiones.RespuestaInvalida:
            respuestas.leidas[peticion.clave] = None
    for peticion in elegidas.values():
        if peticion.clave not in vistas:
            respuestas.esperas[peticion.clave] = _iso(ahora + timedelta(minutes=50))
            respuestas.leidas[peticion.clave] = None


def procesar_respuestas(ctx: Contexto, lista: list[Peticion], respuestas: Respuestas) -> None:
    """Aplica las respuestas de un lote (con el cerrojo tomado), con el modelo que dio cada una
    y lo que espera al experto."""
    for llamada in respuestas.llamadas_experto:
        ctx.almacen.registrar_llamada(llamada)
        ctx.resultado.llamadas += 1
        ctx.resultado.gasto += float(llamada["coste"])
        ctx.resultado.escaladas += 1
    for peticion in lista:
        if peticion.clave not in respuestas.leidas:
            continue
        respuesta = respuestas.leidas[peticion.clave]
        ctx.llamador.ultimo_modelo = respuestas.modelos.get(peticion.clave, "")
        ctx.llamador.ultimos_motivos = respuestas.motivos.get(peticion.clave, [])
        ctx.llamador.ultimo_critico = peticion.clave in respuestas.criticos
        ctx.llamador.ultima_espera = respuestas.esperas.get(peticion.clave)
        if ctx.llamador.ultima_espera:
            ctx.resultado.esperan_experto.append(peticion.clave)
        if peticion.tipo == "par":
            procesar_par(ctx, peticion, respuesta)
        elif peticion.tipo == "separado":
            procesar_separado(ctx, peticion, respuesta)
        elif peticion.tipo == "verificacion":
            procesar_verificacion(ctx, peticion, respuesta)
        else:
            procesar_traduccion(ctx, peticion, respuesta)
    ctx.llamador.ultimo_modelo, ctx.llamador.ultimos_motivos = "", []
    ctx.llamador.ultima_espera = None


# --- Citas de cada hora por lote, recogidas en la recogida siguiente ------------------------


def lotes_pendientes(almacen: Almacen) -> list[Documento]:
    cursor = almacen.cursor(CURSOR_LOTES) or {}
    return list(cursor.get("lotes", [])) if isinstance(cursor, dict) else []


def citas_en_lote(almacen: Almacen) -> set[str]:
    """Las huellas de las citas que ya van en un lote sin recoger."""
    return {h for lote in lotes_pendientes(almacen) for tanda in lote.get("tandas", {}).values()
            for h, _, _ in tanda}  # fmt: skip


def enviar_traducciones(ctx: Contexto, citas: dict[str, tuple[str, str]], hechas: set[str]
                        ) -> int:  # fmt: skip
    """Manda en un lote las citas sin traducir (que no vayan ya en otro) dentro del tope del día;
    se recogen en la recogida siguiente. Devuelve cuántas citas van. Sin servicio de lotes, se
    traducen con llamadas directas como antes."""
    lista = peticiones_traduccion(citas, hechas | citas_en_lote(ctx.almacen))
    if not lista or ctx.llamador.parado or ctx.llamador.fabrica is None:
        return 0
    try:
        servicio: Any = ctx.llamador.servicio()
    except Exception as error:
        ctx.resultado.errores.append(f"lote de citas: {str(error)[:150]}")
        return 0
    if not callable(getattr(servicio, "crear_lote", None)):
        traducir(ctx, citas, hechas)
        return 0
    dia = coste.dia(ctx.ahora) if coste.diario(ctx.llamador.modo) else None
    disponible = (
        coste.limite(ctx.llamador.modo)
        - ctx.almacen.gastado(ctx.llamador.modo.value, dia)
        - gasto_reservado(ctx.almacen)
    )
    elegidas, previsto, _fuera = elegir_para_lote(lista, disponible)
    if not elegidas:
        return 0
    try:
        creado = servicio.crear_lote(
            [{"custom_id": i, "params": p.cuerpo} for i, p in elegidas.items()]
        )
    except LlamadaFallida as error:
        ctx.resultado.errores.append(f"lote de citas: {str(error)[:150]}")
        return 0
    lotes = lotes_pendientes(ctx.almacen)
    lotes.append({
        "id": creado["id"], "enviado": _iso(ctx.ahora), "peor_caso": round(previsto, 6),
        "tandas": {i: p.datos["tanda"] for i, p in elegidas.items()},
    })  # fmt: skip
    ctx.almacen.guardar_cursor(CURSOR_LOTES, {"lotes": lotes})
    enviadas = sum(len(p.datos["tanda"]) for p in elegidas.values())
    registro.info("lote de citas %s enviado: %d citas, peor caso %.4f USD", creado["id"],
                  enviadas, previsto)  # fmt: skip
    return enviadas


def gasto_reservado(almacen: Almacen) -> float:
    """El peor caso de los lotes enviados y sin recoger, que todavía no está en el gasto."""
    return sum(float(lote.get("peor_caso", 0)) for lote in lotes_pendientes(almacen))


def recoger_lotes(ctx: Contexto) -> int:
    """Recoge los lotes de citas terminados: guarda las traducciones y anota su gasto (a mitad
    de precio, con la tarifa del modelo). Devuelve cuántas citas se tradujeron."""
    lotes = lotes_pendientes(ctx.almacen)
    if not lotes or ctx.llamador.fabrica is None:
        return 0
    try:
        servicio: Any = ctx.llamador.servicio()
    except Exception as error:
        ctx.resultado.errores.append(f"lotes de citas: {str(error)[:150]}")
        return 0
    quedan, antes = [], ctx.resultado.traducidas
    for lote in lotes:
        try:
            estado = servicio.lote(lote["id"])
        except LlamadaFallida as error:
            ctx.resultado.errores.append(f"lote {lote['id']}: {str(error)[:150]}")
            quedan.append(lote)
            continue
        if estado.get("processing_status") != "ended":
            if ctx.ahora - _leer(lote["enviado"]) < CADUCIDAD_LOTE:
                quedan.append(lote)
            continue
        elegidas = {
            i: Peticion("traduccion", f"traducir:{lote['id']}:{i}", {}, 0,
                        {"tanda": [tuple(c) for c in tanda]})
            for i, tanda in lote["tandas"].items()
        }  # fmt: skip
        respuestas = Respuestas()
        try:
            leer_resultados(servicio, estado, elegidas, respuestas)
        except LlamadaFallida as error:
            ctx.resultado.errores.append(f"lote {lote['id']}: {str(error)[:150]}")
            quedan.append(lote)
            continue
        _anotar_lote(ctx.almacen, respuestas, ctx.ahora, ctx.resultado, ctx.llamador.modo)
        for peticion in elegidas.values():
            if peticion.clave in respuestas.leidas:
                procesar_traduccion(ctx, peticion, respuestas.leidas[peticion.clave])
    ctx.almacen.guardar_cursor(CURSOR_LOTES, {"lotes": quedan})
    return ctx.resultado.traducidas - antes


def _anotar_lote(
    almacen: Almacen,
    respuestas: Respuestas,
    ahora: datetime,
    resultado: Resultado,
    modo: coste.Modo = coste.Modo.CONTROL_REPASO,
) -> None:
    for clave, uso in respuestas.usos.items():
        gasto = uso.coste(lote=True)
        almacen.registrar_llamada({
            "fecha": _iso(ahora), "modo": modo.value, "candidato": clave[:200],
            "lote": True, "entrada": uso.entrada, "salida": uso.salida,
            "escritura_cache": uso.escritura_cache, "lectura_cache": uso.lectura_cache,
            "coste": gasto, "modelo": uso.modelo,
        })  # fmt: skip
        resultado.llamadas += 1
        resultado.gasto += gasto
        cuenta = resultado.por_modelo.setdefault(uso.modelo or "?", [0, 0.0])
        cuenta[0] += 1
        cuenta[1] += gasto
    for llamada in respuestas.llamadas_directas:
        almacen.registrar_llamada(llamada)
        resultado.llamadas += 1
        resultado.gasto += float(llamada["coste"])
        cuenta = resultado.por_modelo.setdefault(str(llamada.get("modelo") or "?"), [0, 0.0])
        cuenta[0] += 1
        cuenta[1] += float(llamada["coste"])


@dataclass
class Base:
    """Cómo abrir la base, guardarla y tomar el cerrojo de la recogida (en el servidor)."""

    abrir: Callable[[], Almacen]
    guardar: Callable[[Almacen], None]
    cerrojo: Callable[[], Any]
    # Cierra una copia que ya no se usa. En el servidor cada copia es la base entera en disco con
    # su caché de SQLite (256 MB): sin cerrarlas, la revisión de madrugada llegaba a los 2 GB de su
    # unidad y el sistema la paraba (del 15 al 19 de octubre de 2026, casi cada noche).
    soltar: Callable[[Almacen], None] = lambda almacen: None


def repaso(base: Base, fabrica: Callable[[], Any], nom: Nomenclator | None = None,
           dormir: Callable[[float], None] | None = None,
           reloj: Callable[[], float] | None = None, alcance: str = "repaso",
           resultado: Resultado | None = None) -> Resultado:  # fmt: skip
    """El control por lotes y en dos rondas: primero los pares (y las uniones), después la
    verificación de cada ficha y las citas (las de Europa y, con lo que quede del tope, las de
    la capa de Ucrania, las más recientes primero). Las peticiones se preparan sobre una copia
    de la base, sin el cerrojo; las respuestas del base que piden escalado se repiten con el
    experto (también sin el cerrojo), y todo se aplica con el cerrojo tomado sobre la base del
    momento.

    «repaso»: todo lo publicado, con su tope propio. «noche»: lo publicado en las últimas 48
    horas, sin citas (van aparte), con lo que quede del día hasta TOPE_NOCHE_USD."""
    import time

    dormir = dormir or time.sleep
    reloj = reloj or time.monotonic
    if nom is None:
        from proceso.noticias import nomenclator

        nom = nomenclator()
    resultado = resultado or Resultado()
    noche_ = alcance == "noche"
    modo = coste.Modo.CONTROL if noche_ else coste.Modo.CONTROL_REPASO
    tope_s = TOPE_LOTE_NOCHE_S if noche_ else TOPE_LOTE_S
    servicio = fabrica()
    from recogida.extractor import modelos_base

    for ronda in ("pares", "fichas"):
        ahora = datetime.now(UTC)
        copia = base.abrir()
        modelos = modelos_base() | frozenset(copia.vocabulario("modelo_dron"))
        llamador = Llamador(copia, None, modo, ahora, None, resultado)
        ctx = Contexto(copia, ahora, modelos, llamador, resultado, nom, None, copia.controles())
        if ronda == "pares":
            # El lugar que nombra el titular, antes de buscar pares (en la copia, sin guardar).
            reglas_deterministas(ctx)
        todos = {d["id"] for d in _activos(copia)
                 if not noche_ or _reciente(d, ahora - VENTANA_NOCHE)}  # fmt: skip
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
            if not noche_:
                hechas = set(copia.traducciones())
                europa = {**citas_pendientes(copia, "europa"),
                          **citas_de(_activos(copia), ctx.decisiones)}  # fmt: skip
                lista += peticiones_traduccion(europa, hechas)
                lista += peticiones_traduccion(citas_pendientes(copia, "ucrania"), hechas)
        if noche_:
            hoy = coste.dia(ahora)
            disponible = min(
                TOPE_NOCHE_USD - resultado.gasto,
                coste.limite(modo) - copia.gastado(modo.value, hoy) - gasto_reservado(copia),
            )
        else:
            disponible = coste.limite(modo) - copia.gastado(modo.value)
        registro.info("repaso, ronda %s: %d peticiones, %.4f USD disponibles", ronda, len(lista),
                      disponible)  # fmt: skip
        # De madrugada, los casos críticos no esperan al lote: van en llamadas directas.
        criticas = [
            p for p in lista
            if noche_ and p.tipo in {"par", "verificacion"} and p.datos.get("critico")
        ]  # fmt: skip
        respuestas = Respuestas()
        directo = directas_criticas(servicio, criticas, respuestas, ahora, modo, disponible)
        directas = {p.clave for p in criticas}
        al_lote = [p for p in lista if p.clave not in directas]
        del_lote = por_lote(servicio, al_lote, disponible - directo, dormir, reloj, tope_s)
        respuestas.leidas.update(del_lote.leidas)
        respuestas.usos.update(del_lote.usos)
        respuestas.fuera_de_tope = del_lote.fuera_de_tope
        registro.info("%s, ronda %s: %d respuestas, %d fuera del tope", alcance, ronda,
                      len(respuestas.leidas), respuestas.fuera_de_tope)  # fmt: skip
        escalar_lote(servicio, copia, lista, respuestas, datetime.now(UTC), modo, dormir, reloj,
                     tope_s)  # fmt: skip
        with base.cerrojo():
            almacen = base.abrir()
            ahora = datetime.now(UTC)
            ctx = Contexto(almacen, ahora, modelos, Llamador(almacen, None, modo, ahora, None,
                           resultado), resultado, nom, None, almacen.controles())  # fmt: skip
            _anotar_lote(almacen, respuestas, ahora, resultado, modo)
            procesar_respuestas(ctx, lista, respuestas)
            almacen.guardar_controles(ctx.nuevas, _iso(ahora))
            ctx.decisiones = {**ctx.decisiones, **ctx.nuevas}
            ctx.nuevas = {}
            reglas_deterministas(ctx)
            aplicar_verificaciones(ctx)
            base.guardar(almacen)
        base.soltar(copia)
        base.soltar(almacen)
    registro.info("repaso: %s", resultado.resumen())
    return resultado


# --- Repaso de todo lo publicado con el experto (docs/control_fichas.md, «Repaso con el experto»)

RUTA_GRUPOS = Path(__file__).resolve().parent.parent / "configuracion" / "repaso_experto.json"
# Dentro de un grupo de fichas que pueden contar el mismo suceso, se comparan las de 3 días.
DIAS_GRUPO = 3
TOPE_REPASO_EXPERTO_S = 6 * 3600.0
# Peticiones por lote: lo que no cabe en el lote va en el siguiente, con el gasto ya anotado.
PETICIONES_POR_LOTE = 400


def _hecho_en_repaso(previa: Documento | None, huella: str) -> bool:
    """El repaso con el experto ya decidió esto con las mismas fuentes."""
    return (
        previa is not None
        and bool(previa.get("repaso_experto"))
        and (previa.get("huella") == huella)
    )


@dataclass
class Grupo:
    """Una serie de fichas que el repaso compara de dos en dos: las de `dias` días como mucho, o
    todas si `dias` es None (las fichas de una serie con la fecha de noticias posteriores, como la
    explosión del 5 de junio de 2026 en el puerto de Constanza)."""

    fichas: list[str]
    dias: int | None = DIAS_GRUPO


def grupos_del_repaso(ruta: Path = RUTA_GRUPOS) -> list[Grupo]:
    """Las series de fichas que el repaso compara entre sí aunque no sean candidatas al mismo
    suceso por las reglas (la serie de Constanza): configuracion/repaso_experto.json. Con
    «sin_ventana», todas las de la serie, sea cual sea su fecha."""
    if not ruta.exists():
        return []
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return [Grupo(list(g["fichas"]), None if g.get("sin_ventana") else DIAS_GRUPO)
            for g in datos.get("grupos", [])]  # fmt: skip


def pares_de_grupos(ctx: Contexto, grupos: list[Grupo]
                    ) -> list[tuple[Documento, Documento, str]]:  # fmt: skip
    """Los pares de cada grupo activos, con fuentes y dentro de su ventana, que el repaso aún no
    decidió con las mismas fuentes."""
    activos = {d["id"]: d for d in _activos(ctx.almacen)}
    pares = []
    for grupo in grupos:
        fichas = sorted((activos[i] for i in grupo.fichas
                         if i in activos and _publicas(activos[i])),
                        key=lambda d: d["id"])  # fmt: skip
        for n, a in enumerate(fichas):
            for b in fichas[n + 1 :]:
                if grupo.dias is not None and abs(
                    reglas.instante(a) - reglas.instante(b)
                ) > timedelta(days=grupo.dias):
                    continue
                huella = reglas.huella_fuentes(a) + reglas.huella_fuentes(b)
                if not _hecho_en_repaso(ctx.decision(reglas.clave_par(a["id"], b["id"])), huella):
                    pares.append((a, b, huella))
    return pares


def _primero_con_fallos(incidente: Documento) -> int:
    """Primero las fichas con un fallo conocido o con el lugar en el país a secas."""
    pais = (incidente.get("lugar") or {}).get("nivel") == "pais"
    return 0 if reglas.fallos_de_ficha(incidente) or pais else 1


def repaso_experto(base: Base, fabrica: Callable[[], Any], nom: Nomenclator | None = None,
                   dormir: Callable[[float], None] | None = None,
                   reloj: Callable[[], float] | None = None,
                   grupos: list[Grupo] | None = None) -> Resultado:  # fmt: skip
    """El repaso de todo lo publicado con el experto, por lotes (a mitad de precio) y dentro de
    su presupuesto aparte (coste.LIMITE_REPASO_EXPERTO_USD, modo «repaso_experto»: fuera del
    tope diario del experto, de su reserva crítica, de su parte del mes y del tope mensual).

    Dos rondas, como el repaso: los pares (los candidatos de las reglas, ya decididos o no, y los
    de las series de configuracion/repaso_experto.json) y la verificación de cada ficha
    publicada, las que tienen un fallo conocido o el lugar en el país a secas primero. Cada
    respuesta es del experto y va por el camino normal: las uniones, las correcciones con su
    cita y el motivo en el historial (TABLA_MOTIVOS). Lo que el repaso ya decidió con las mismas
    fuentes no se repite: si se para (el presupuesto o el tiempo), sigue donde lo dejó."""
    import time

    dormir = dormir or time.sleep
    reloj = reloj or time.monotonic
    if nom is None:
        from proceso.noticias import nomenclator

        nom = nomenclator()
    grupos = grupos_del_repaso() if grupos is None else grupos
    resultado = Resultado()
    modo = coste.Modo.REPASO_EXPERTO
    experto = getattr(fabrica(), "experto", None)
    cliente = experto() if callable(experto) else None
    if cliente is None or not callable(getattr(cliente, "crear_lote", None)):
        resultado.errores.append("sin experto por lotes")
        return resultado
    modelo_experto = str(getattr(cliente, "modelo", "")) or None
    from recogida.extractor import modelos_base

    inicio = reloj()
    # Lo ya preguntado en esta pasada no se repite aunque la respuesta no valga.
    hechas: set[str] = set()
    for ronda in ("pares", "fichas"):
        while reloj() - inicio < TOPE_REPASO_EXPERTO_S:
            ahora = datetime.now(UTC)
            copia = base.abrir()
            modelos = modelos_base() | frozenset(copia.vocabulario("modelo_dron"))
            llamador = Llamador(copia, None, modo, ahora, None, resultado)
            ctx = Contexto(copia, ahora, modelos, llamador, resultado, nom, None, copia.controles())
            reglas_deterministas(ctx)
            todos = {d["id"] for d in _activos(copia)}
            if ronda == "pares":
                textos: dict[str, str] = {}
                vistos: set[str] = set()
                lista: list[Peticion] = []
                for a, b, h in [*pares_por_decidir(ctx, todos, forzar=True),
                                *pares_de_grupos(ctx, grupos)]:  # fmt: skip
                    clave = reglas.clave_par(a["id"], b["id"])
                    if clave not in vistos | hechas and len(lista) < PETICIONES_POR_LOTE:
                        vistos.add(clave)
                        lista.append(peticion_par(ctx, a, b, h, textos))
            else:
                fichas = sorted((d for d in por_verificar(ctx, todos, forzar=True)
                                 if reglas.clave_verificacion(d["id"]) not in hechas),
                                key=_primero_con_fallos)  # fmt: skip
                lista = [peticion_verificacion(ctx, d) for d in fichas[:PETICIONES_POR_LOTE]]
            disponible = coste.limite(modo) - copia.gastado(modo.value)
            registro.info("repaso con el experto, ronda %s: %d peticiones, %.4f USD disponibles",
                          ronda, len(lista), disponible)  # fmt: skip
            base.soltar(copia)
            if not lista:
                break
            try:
                respuestas = por_lote(cliente, lista, disponible, dormir, reloj,
                                      TOPE_REPASO_EXPERTO_S, modelo_experto)  # fmt: skip
            except (TimeoutError, LlamadaFallida) as error:
                resultado.errores.append(f"repaso con el experto: {str(error)[:200]}")
                resultado.parada = "error"
                return resultado
            hechas |= set(respuestas.leidas)
            if not respuestas.leidas:
                resultado.parada = "limite_gasto" if respuestas.fuera_de_tope else "sin_respuestas"
                break
            with base.cerrojo():
                almacen = base.abrir()
                ahora = datetime.now(UTC)
                ctx = Contexto(almacen, ahora, modelos, Llamador(almacen, None, modo, ahora, None,
                               resultado), resultado, nom, None, almacen.controles())  # fmt: skip
                _anotar_lote(almacen, respuestas, ahora, resultado, modo)
                procesar_respuestas(ctx, lista, respuestas)
                for peticion in lista:
                    if peticion.clave in respuestas.leidas and peticion.clave in ctx.nuevas:
                        ctx.nuevas[peticion.clave]["repaso_experto"] = _iso(ahora)
                almacen.guardar_controles(ctx.nuevas, _iso(ahora))
                ctx.decisiones = {**ctx.decisiones, **ctx.nuevas}
                ctx.nuevas = {}
                reglas_deterministas(ctx)
                aplicar_verificaciones(ctx)
                base.guardar(almacen)
            # Lo que no cupo en el peor caso va en la vuelta siguiente, con lo gastado de verdad.
            base.soltar(almacen)
        if resultado.parada == "limite_gasto":
            break
    registro.info("repaso con el experto: %s", resultado.resumen())
    return resultado


def noche(base: Base, fabrica: Callable[[], Any] | None, ruta_estado: Path,
          dormir: Callable[[float], None] | None = None,
          reloj: Callable[[], float] | None = None) -> Resultado:  # fmt: skip
    """La pasada de madrugada, todo por lotes (a mitad de precio): con el cerrojo, lo que no llama
    al servicio; sin el cerrojo mientras espera, los pares y la verificación de lo publicado en
    las últimas 48 horas (repaso con alcance «noche»), con el escalado al experto; y después las
    citas sin traducir de cada capa (las de Europa y las de Ucrania, las más recientes primero),
    con lo que sobra del día hasta TOPE_NOCHE_CITAS_USD. Cada resultado se guarda con el
    cerrojo."""
    import time

    from recogida.extractor import modelos_base

    with base.cerrojo():
        almacen = base.abrir()
        ahora = datetime.now(UTC)
        modelos = modelos_base() | frozenset(almacen.vocabulario("modelo_dron"))
        resultado = ejecutar(almacen, ahora, modelos, "noche", fabrica, Plazo(TOPE_NOCHE_S))
        if fabrica is not None:
            recoger_lotes(Contexto(almacen, ahora, modelos, Llamador(
                almacen, fabrica, coste.Modo.CONTROL, ahora, None, resultado), resultado, None,
                None))  # fmt: skip
        base.guardar(almacen)
    if fabrica is None:
        escribir_estado(ruta_estado, resultado, almacen, ahora)
        base.soltar(almacen)
        return resultado
    base.soltar(almacen)
    try:
        repaso(base, fabrica, None, dormir, reloj, alcance="noche", resultado=resultado)
    except (TimeoutError, LlamadaFallida) as error:
        resultado.errores.append(f"revisión por lote: {str(error)[:200]}")
    copia = base.abrir()
    hechas = set(copia.traducciones())
    lista = peticiones_traduccion(citas_pendientes(copia, "europa"), hechas)
    lista += peticiones_traduccion(citas_pendientes(copia, "ucrania"), hechas)
    hoy = coste.dia(datetime.now(UTC))
    disponible = min(
        TOPE_NOCHE_CITAS_USD,
        coste.limite(coste.Modo.CONTROL) - copia.gastado(coste.Modo.CONTROL.value, hoy),
    )
    disponible -= gasto_reservado(copia)
    almacen, ahora = copia, datetime.now(UTC)
    if lista and disponible > 0:
        base.soltar(copia)
        respuestas = por_lote(fabrica(), lista, disponible, dormir or time.sleep,
                              reloj or time.monotonic, TOPE_LOTE_NOCHE_S)  # fmt: skip
        with base.cerrojo():
            almacen = base.abrir()
            ahora = datetime.now(UTC)
            ctx = Contexto(almacen, ahora, frozenset(), Llamador(almacen, None, coste.Modo.CONTROL,
                           ahora, None, resultado), resultado, None, None)  # fmt: skip
            _anotar_lote(almacen, respuestas, ahora, resultado, coste.Modo.CONTROL)
            for peticion in lista:
                if peticion.clave in respuestas.leidas:
                    procesar_traduccion(ctx, peticion, respuestas.leidas[peticion.clave])
            base.guardar(almacen)
    escribir_estado(ruta_estado, resultado, almacen, ahora)
    base.soltar(almacen)
    return resultado


def traducir_pendientes(base: Base, fabrica: Callable[[], Any],
                        dormir: Callable[[float], None] | None = None,
                        reloj: Callable[[], float] | None = None) -> Resultado:  # fmt: skip
    """Traduce de una vez, por lote y con el modelo base, todas las citas publicadas sin traducir
    (las de Europa primero y después las de la capa de Ucrania, las más recientes primero),
    dentro del tope de una sola vez del modo «traducciones». Prepara y espera sin el cerrojo;
    guarda con el cerrojo."""
    import time

    resultado = Resultado()
    copia = base.abrir()
    hechas = set(copia.traducciones())
    europa = {**citas_pendientes(copia, "europa"), **citas_de(_activos(copia), copia.controles())}
    lista = peticiones_traduccion(europa, hechas)
    lista += peticiones_traduccion(citas_pendientes(copia, "ucrania"), hechas)
    modo = coste.Modo.TRADUCCIONES
    disponible = coste.limite(modo) - copia.gastado(modo.value)
    registro.info("traducciones pendientes: %d peticiones, %.4f USD disponibles", len(lista),
                  disponible)  # fmt: skip
    respuestas = por_lote(fabrica(), lista, disponible, dormir or time.sleep,
                          reloj or time.monotonic)  # fmt: skip
    with base.cerrojo():
        almacen = base.abrir()
        ahora = datetime.now(UTC)
        ctx = Contexto(almacen, ahora, frozenset(), Llamador(almacen, None, modo, ahora, None,
                       resultado), resultado, None, None)  # fmt: skip
        _anotar_lote(almacen, respuestas, ahora, resultado, modo)
        for peticion in lista:
            if peticion.clave in respuestas.leidas:
                procesar_traduccion(ctx, peticion, respuestas.leidas[peticion.clave])
        base.guardar(almacen)
    registro.info("traducciones pendientes: %d citas traducidas, %d peticiones fuera del tope",
                  resultado.traducidas, respuestas.fuera_de_tope)  # fmt: skip
    return resultado


# --- Estado para el resumen diario y la vigilancia ------------------------------------------


def escribir_estado(ruta: Path, resultado: Resultado | None, almacen: Almacen,
                    ahora: datetime, segunda: Documento | None = None) -> None:  # fmt: skip
    """~/.eodi/control.json: lo que hizo el control en cada pasada del día, para el resumen de
    las 08:00 y para la vigilancia. Con `segunda`, también la segunda lectura
    (recogida/segunda_lectura.estado_para_control), que nadie vigila: no es vital."""
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
            "errores": resultado.errores[:5], "escaladas": resultado.escaladas,
            "esperan_experto": resultado.esperan_experto[:20],
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
        "modelos": gasto_por_modelo(almacen, ahora, anterior.get("modelos") or {}),
        "experto": gasto_experto(almacen, ahora, anterior.get("experto") or {}),
        "api": gasto_api(almacen, ahora, anterior.get("api") or {}),
        "criticos_esperando": criticos_esperando(almacen),
    }
    if segunda is not None:
        datos["segunda_lectura"] = segunda
    elif "segunda_lectura" in anterior:
        datos["segunda_lectura"] = anterior["segunda_lectura"]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(ruta)


# Días (de Madrid) que se guardan del gasto por modelo.
DIAS_MODELOS = 10


def papel(modelo: str) -> str:
    """El papel de un modelo en el esquema de dos (docs/modelos.md): «base», «experto» o
    «anterior» (el único modelo de antes). Los nombres de los modelos no salen de aquí."""
    from modelo import modelos

    base, experto = modelos.base(), modelos.experto()
    if experto and modelo.startswith(experto):
        return "experto"
    if modelo and base and modelo.startswith(base):
        return "base"
    return "anterior"


def gasto_por_modelo(almacen: Almacen, ahora: datetime, anterior: Documento) -> Documento:
    """Llamadas, escaladas y gasto de cada papel (base, experto, anterior) por día de Madrid: el
    de hoy y el de ayer se recalculan con la base; los anteriores se conservan."""
    from zoneinfo import ZoneInfo

    madrid = ZoneInfo("Europe/Madrid")
    hoy = ahora.astimezone(madrid).date()
    dias: Documento = {d: v for d, v in anterior.items()
                       if d >= (hoy - timedelta(days=DIAS_MODELOS)).isoformat()}  # fmt: skip
    for dia in (hoy - timedelta(days=1), hoy):
        inicio = datetime.combine(dia, datetime.min.time(), madrid).astimezone(UTC)
        fin = datetime.combine(dia + timedelta(days=1), datetime.min.time(), madrid).astimezone(UTC)
        papeles: Documento = {}
        for fila in almacen.llamadas_por_modelo(_iso(inicio), _iso(fin)):
            cuenta = papeles.setdefault(papel(fila["modelo"]),
                                        {"llamadas": 0, "escaladas": 0, "coste": 0.0})  # fmt: skip
            cuenta["llamadas"] += fila["llamadas"]
            cuenta["escaladas"] += fila["escaladas"]
            cuenta["coste"] = round(cuenta["coste"] + fila["coste"], 6)
        dias[dia.isoformat()] = papeles
    return dias


def gasto_experto(almacen: Almacen, ahora: datetime, anterior: Documento) -> Documento:
    """Lo que gastó el experto cada día UTC, repartido entre su tope normal y la reserva crítica
    (modelo/coste.py), con los dos topes: hoy y ayer se recalculan con la base."""
    from modelo import modelos

    experto = modelos.experto()
    hoy = ahora.astimezone(UTC).date()
    dias: Documento = {d: v for d, v in anterior.items()
                       if d >= (hoy - timedelta(days=DIAS_MODELOS)).isoformat()}  # fmt: skip
    for dia in (hoy - timedelta(days=1), hoy):
        gastado = almacen.gastado_modelo(experto, dia.isoformat()) if experto else 0.0
        # El tope normal de ese día: el de su parte del mes, como mucho el límite diario.
        momento = datetime(dia.year, dia.month, dia.day, 12, tzinfo=UTC)
        tope = coste.LIMITE_EXPERTO_DIARIO_USD
        if experto:
            tope = coste.tope_experto(coste.del_mes(almacen, momento, experto))
        dias[dia.isoformat()] = {
            **coste.reparto_experto(gastado, tope), "limite": tope,
            "reserva_limite": coste.RESERVA_CRITICA_DIARIA_USD,
        }  # fmt: skip
    return dias


def gasto_api(almacen: Almacen, ahora: datetime, anterior: Documento) -> Documento:
    """Lo gastado en la API cada día UTC (todas las llamadas) y lo acumulado en su mes hasta el
    final de ese día, con el tope mensual (coste.tope_mensual): hoy y ayer se recalculan con la
    base. El resumen diario lo cuenta (recogida/visitas.py, lineas_api)."""
    hoy = ahora.astimezone(UTC).date()
    dias: Documento = {d: v for d, v in anterior.items()
                       if d >= (hoy - timedelta(days=DIAS_MODELOS)).isoformat()}  # fmt: skip
    for dia in (hoy - timedelta(days=1), hoy):
        dias[dia.isoformat()] = {
            "dia": round(almacen.gasto_entre(dia.isoformat(), dia.isoformat()), 4),
            "mes": round(almacen.gasto_entre(dia.replace(day=1).isoformat(), dia.isoformat()), 4),
            "tope": coste.tope_mensual(),
        }
    return dias


def criticos_esperando(almacen: Almacen) -> list[Documento]:
    """Los casos críticos que esperan al experto ahora (candidatos, pares y verificaciones), con
    desde cuándo (la reserva crítica se agotó o el experto falló): se reintentan en cada
    recogida. Un par o una verificación que ya no está en juego (espera_vigente) no cuenta."""
    from proceso import extraccion

    casos = [
        {"clave": clave, "desde": str(e.get("desde") or "")}
        for clave, e in extraccion.esperan_experto(almacen).items()
        if isinstance(e, dict) and e.get("critico")
    ]
    activos = {d["id"]: d for d in _activos(almacen)}
    casos += [
        {"clave": clave, "desde": str(d.get("desde") or d.get("fecha") or "")}
        for clave, d in almacen.controles().items()
        if d.get("espera_experto") and d.get("critico") and "datos" not in d
        and d.get("decision", "dudoso") == "dudoso" and espera_vigente(clave, activos)
    ]  # fmt: skip
    return sorted(casos, key=lambda c: c["desde"])


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

    return Base(abrir, lambda a: sitio.guardar_base(a, temporal, correo), tomar,
                lambda a: a.cerrar())  # fmt: skip


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("alcance", choices=("noche", "repaso", "estado", "traducir-pendientes",
                                              "repaso-experto"))  # fmt: skip
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
        if args.alcance in {"repaso", "traducir-pendientes", "repaso-experto"}:
            fabrica = _fabrica()
            if fabrica is None:
                return 1
            if args.alcance == "repaso":
                resultado = repaso(base, fabrica)
            elif args.alcance == "repaso-experto":
                resultado = repaso_experto(base, fabrica)
            else:
                resultado = traducir_pendientes(base, fabrica)
            print(resultado.resumen())
            return 0
        if args.alcance == "noche":
            try:
                resultado = noche(base, None if args.sin_servicio else _fabrica(), args.estado)
            except Exception:
                registro.exception("control de fichas fallido")
                escribir_estado(args.estado, None, base.abrir(), ahora)
                return 1
            print(resultado.resumen())
            return 0
        almacen = base.abrir()
        if args.alcance == "estado":
            print(json.dumps({
                "gasto_control_hoy": almacen.gastado(coste.Modo.CONTROL.value, coste.dia(ahora)),
                "gasto_repaso": almacen.gastado(coste.Modo.CONTROL_REPASO.value),
                "gasto_repaso_experto": almacen.gastado(coste.Modo.REPASO_EXPERTO.value),
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
