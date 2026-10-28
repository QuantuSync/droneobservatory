"""Coste de cada llamada al extractor y límites de gasto duros.

Cada llamada se cobra con la tarifa del modelo que la hizo (modelo/modelos.py: el base, el
experto o el de antes), con su tramo de más de 100.000 tokens, sus precios de caché y el
descuento de los lotes.

Límites, compartidos por todo lo que llama al extractor:
- 5 dólares para todo el histórico (modo «historico»);
- 0,30 dólares al día para la recogida horaria (modo «horario»);
- 5 dólares para la revisión de todo lo publicado con las reglas de calidad de los
  datos (modo «revision», `python -m recogida.extractor revision`);
- 3 dólares para el histórico de las fuentes oficiales de detalle (modo «detalle»,
  `python -m recogida.detalle historico`), por lotes.
- 0,20 dólares al día para los mensajes de la capa de guerra que el código no resuelve
  (modo «guerra», en la recogida horaria), aparte del límite horario;
- 5 dólares para el histórico de esos mensajes desde el 1 de enero de 2025 (modo
  «guerra_historico», `python -m proceso.extraccion_guerra lote`);
- 2 dólares, una sola vez, para la tercera revisión de la calidad de los datos (modo
  «calidad», `python -m recogida.calidad`): candidatos separados por suceso, artículos que
  ahora se sitúan, candidatos de la búsqueda dirigida y los prioritarios nunca extraídos.
- 3 dólares, una sola vez, para el barrido dirigido desde enero de 2025 (modo «dirigida»,
  `python -m recogida.barrido_dirigido incorporar`): incidentes en España y en puertos y presas.

- 0,15 dólares al día para el control de calidad de las fichas (modo «control», en la recogida
  horaria y en la revisión de madrugada: duplicados, respaldo de cada dato y traducción de las
  citas, recogida/control_fichas.py);
- 4 dólares, una sola vez, para el repaso de todo lo publicado con ese control (modo
  «control_repaso», `python -m recogida.control_fichas repaso`).
- 2 dólares, una sola vez, para traducir por lote las citas que quedaban sin traducir el 14 de
  octubre de 2026 (unas 8.600 de la capa de Ucrania y 440 de Europa) con el modelo base (modo
  «traducciones», `python -m recogida.control_fichas traducir-pendientes`).

El barrido del catálogo vivo (recogida/catalogo_vivo.py) lleva su propio registro de gasto
fuera de la base: 0,30 dólares al día y 3 dólares una vez para su primera pasada.

El modelo experto lleva su propio gasto, aparte de todos los modos (docs/modelos.md): lo que
gasta cuenta solo contra su tope, nunca contra el de la recogida horaria ni el de otro modo. Su
tope normal del día es 1,50 dólares (LIMITE_EXPERTO_DIARIO_USD) mientras su parte del mes deje al
menos MINIMO_EXPERTO_DIARIO_USD a cada día que queda (tope_experto), y aparte tiene una reserva
crítica de 0,50 dólares al día (RESERVA_CRITICA_DIARIA_USD) que solo usan los casos críticos
(proceso/escalado.es_critico) cuando el tope normal ya no da. Lo que el experto gasta en un día por
encima de su tope normal es de la reserva. Un caso que no cabe espera: el normal, hasta la misma
hora del día siguiente (su tope se renueva a las 00:00 UTC, y así las esperas no vencen todas a
medianoche); el crítico, a la recogida siguiente, y se reintenta en cada una.

Tope mensual (desde el 19 de octubre de 2026): todo lo que se gasta en la API en el mes (UTC),
también lo de las sesiones, cuenta contra TOPE_MENSUAL_USD (150 dólares desde el 28 de octubre de
2026, 60 desde el 20, con los créditos mensuales de la API incluidos en el plan; la variable
EODI_TOPE_MENSUAL_USD lo cambia), repartido entre el experto y los modos de cada día
(REPARTO_MENSUAL_USD). Cada modo de cada día y el experto gastan como mucho lo que queda de su parte
del mes entre los días que quedan (tope_del_dia). Al 80 % se avisa una vez (recogida/gasto_api.py);
al 100 % solo siguen la recogida horaria con el modelo base (sin ella no se sabe qué es crítico) y
los casos críticos con la reserva del experto; los demás modos de cada día esperan al mes
siguiente.

Filtro de entrada (desde el 28 de octubre de 2026, recogida/entrada.py): cada ficha nueva pasa
por el experto antes de publicarse, comparada con todas las que pueden contar el mismo suceso, y 24
horas después otra vez (la medida). Modo «entrada»: 3 dólares al día (LIMITE_ENTRADA_DIARIO_USD),
solo con el experto y con su cupo propio: no cuenta contra el tope diario del experto, ni contra su
reserva crítica, ni contra el control; sí dentro de su parte del mes (90 de los 150). Lo que no
cabe espera a la recogida siguiente, sin publicarse.

La segunda lectura (docs/segunda_lectura.md) usa un servicio secundario gratuito; lo único que
cuesta es el experto al revisar lo que marca (modo «segunda_lectura»): como mucho 0,30 dólares al
día (LIMITE_SEGUNDA_EXPERTO_DIARIO_USD), dentro del tope normal del experto y nunca de la reserva
crítica. Lo que no cabe espera al día siguiente.

Antes de cada llamada se suma lo gastado y el peor caso de la llamada (sus
tokens de entrada estimados y el máximo de salida); si pasa del límite, no se
llama.
"""

import calendar
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from modelo import modelos

DESCUENTO_LOTE = modelos.DESCUENTO_LOTE
LIMITE_HISTORICO_USD = 5.00
LIMITE_DIARIO_USD = 0.30
LIMITE_REVISION_USD = 5.00
# Histórico de las fuentes oficiales de detalle (respuestas parlamentarias, informes de
# investigación, sentencias), procesado una sola vez por lotes: presupuesto propio, aparte del
# límite diario. Lo nuevo de cada día entra en el límite diario de la recogida horaria.
LIMITE_DETALLE_USD = 3.00
LIMITE_GUERRA_DIARIO_USD = 0.20
LIMITE_GUERRA_HISTORICO_USD = 5.00
LIMITE_CALIDAD_USD = 2.00
LIMITE_DIRIGIDA_USD = 3.00
# 0,25 desde el 20 de octubre de 2026 (era 0,15; lo medido, 0,04-0,12 al día).
LIMITE_CONTROL_DIARIO_USD = 0.25
# Repaso del control sobre todo lo publicado: 4 USD el 14 de octubre de 2026 de madrugada (se
# gastaron 3,46) y 6 USD más ese mismo día para las fichas que quedaron sin verificar.
LIMITE_CONTROL_REPASO_USD = 9.46
# Repaso de todo lo publicado con el experto y las reglas del 20 de octubre de 2026 (buques, fechas
# relativas, nombres propios, titulares, lugar, duplicados), por lote y de madrugada
# (recogida/control_fichas.repaso_experto): 15 USD en total, con los créditos del plan. Va aparte
# del tope diario del experto, de su reserva crítica, de su parte del mes y del tope mensual
# (almacen/base.py, CUPOS_PROPIOS y FUERA_DEL_MES): no quita nada a la recogida.
LIMITE_REPASO_EXPERTO_USD = 15.00
# Repaso de todo lo publicado con la pregunta del filtro de entrada (28 de octubre de 2026,
# recogida/repaso_entrada.py): 40 USD en total, con llamadas directas (no por lotes). Va aparte,
# como el repaso con el experto: fuera del tope diario del experto, de su reserva crítica, del modo
# «entrada» y del reparto y el tope del mes (CUPOS_PROPIOS y FUERA_DEL_MES en almacen/base.py).
LIMITE_REPASO_ENTRADA_USD = 40.00
# Traducción de una sola vez de las citas atrasadas (14 de octubre de 2026), por lote.
LIMITE_TRADUCCIONES_USD = 2.00
# Búsqueda mensual de rectificaciones oficiales con el modelo base (recogida/rectificaciones.py):
# una pasada al mes, con su tope por día (el de la pasada). Las preguntas al experto van aparte,
# con su tope.
LIMITE_RECTIFICACIONES_USD = 0.30
# Tope diario del modelo experto, en todos los modos juntos y aparte de ellos. Fue 1 dólar hasta el
# 19 de octubre de 2026 y 0,30 del 19 al 20: con 0,30 casi todo lo decidió el modelo base y salieron
# fichas mal publicadas (un buque como lugar, un suceso de la semana anterior como nuevo). Desde el
# 20 de octubre, con los créditos mensuales del plan, 1,50.
LIMITE_EXPERTO_DIARIO_USD = 1.50
# Lo que el tope del experto deja siempre a cada día que queda del mes: si su parte del mes va tan
# deprisa que no daría para esto, el tope de hoy baja (tope_experto).
MINIMO_EXPERTO_DIARIO_USD = 0.50
# Lo que el experto deja libre de su tope del día para los escalados que no pueden esperar cuando
# hace lo opcional (comprobar_al_ritmo): un margen fijo, no un reparto por horas que deje la mañana
# sin experto (el 20 de octubre de 2026 a las 11:45 Chelsea 3 se quedó sin él por ese reparto).
MARGEN_ESCALADOS_USD = 0.30
# Reserva crítica del experto, aparte del tope: solo para los casos críticos.
RESERVA_CRITICA_DIARIA_USD = 0.50
# Lo que el experto gasta cada día en revisar lo que marca la segunda lectura: cuenta dentro de su
# tope normal (nunca de la reserva crítica).
# Era 0,30 hasta el 19 de octubre de 2026 (de 30 candidatos revisados, 2 cambiaron algo) y 0,10
# hasta el 25: con 0,10 el experto se paraba cada día con candidatos esperando.
LIMITE_SEGUNDA_EXPERTO_DIARIO_USD = 0.30
# Cupo propio de la segunda lectura para las dos búsquedas de lo que falta (declaraciones oficiales
# e incidentes que faltan, docs/segunda_lectura.md): su extracción con el experto, como mucho
# configuracion/segunda_lectura.json (busqueda.cupo_experto.por_dia, 20 casos al día desde el 20 de
# octubre de 2026; antes 2) y estos
# dólares al día, dentro de su parte del mes (sin repartirla por días: el peor caso de una
# extracción, unos 0,06, no cabría en lo que le toca de un día). No cuenta contra el tope normal del
# experto, no va al ritmo de su tope y nunca sale de la reserva crítica (desde el 20 de octubre de
# 2026: con la regla del ritmo esas búsquedas casi nunca llegaban al experto, y las que llegaban
# como críticas gastaban la reserva).
# 0,80 desde el 20 de octubre de 2026 (era 0,12, para 2 casos): 20 casos y el peor caso del último.
LIMITE_SEGUNDA_BUSQUEDA_DIARIO_USD = 0.80
# Cupo propio del experto en el control de las fichas (duplicados dudosos y verificaciones que
# contradicen la ficha, recogida/control_fichas.py), aparte de su tope normal: desde el 20 de
# octubre de 2026, porque ese día el control (0,07 USD) y las esperas que vencen a medianoche
# gastaron de 00:00 a 06:00 UTC los 0,30 del experto, y la recogida horaria se quedó sin él durante
# el día. Cuenta dentro de la parte del mes del control; los casos críticos del control siguen con
# el tope del experto y su reserva crítica. De madrugada va por lote (escalar_lote). 0,25 desde el
# 20 de octubre de 2026 (era 0,06): el control manda al experto los fallos de las fichas.
LIMITE_CONTROL_EXPERTO_DIARIO_USD = 0.25
# Cupo propio del experto en el filtro de entrada de las fichas nuevas y en su medida a las 24 horas
# (recogida/entrada.py), desde el 28 de octubre de 2026: aparte del tope normal del experto, de su
# reserva crítica y del control; dentro de su parte del mes.
LIMITE_ENTRADA_DIARIO_USD = 3.00
# Tope del experto antes del 15 de octubre de 2026: una espera anotada sin su tope es de entonces.
LIMITE_EXPERTO_ANTERIOR_USD = 0.30
# Un caso que espera al experto por un fallo, o crítico con la reserva agotada, vuelve a la
# recogida siguiente (cada hora).
ESPERA_REINTENTO = timedelta(minutes=50)
# Tope mensual de toda la API (todas las llamadas del mes UTC, también las de las sesiones). Lo
# medido del 15 al 19 de octubre de 2026 en funcionamiento normal, por día: base de la recogida
# 0,094; base del control 0,064; guerra 0,002; rectificaciones, una pasada al mes de hasta 0,30.
# 10 USD del 19 al 20 de octubre de 2026; 60 desde el 20, con los créditos mensuales de la API
# incluidos en el plan (caducan cada mes y no se acumulan). 150 desde el 28 de octubre de 2026, con
# el filtro de entrada (3 dólares al día).
TOPE_MENSUAL_USD = 150.00
VARIABLE_TOPE_MENSUAL = "EODI_TOPE_MENSUAL_USD"
EXPERTO = "experto"
OTROS = "otros"
# Al llegar a esta parte del tope mensual se avisa una vez (recogida/gasto_api.py).
AVISO_MENSUAL = 0.80
# Una letra son unos 0,3 tokens en los idiomas europeos; se estima por lo alto con 0,5
# para que el peor caso no se quede corto.
TOKENS_POR_LETRA = 0.5


class Modo(StrEnum):
    HORARIO = "horario"
    HISTORICO = "historico"
    REVISION = "revision"
    DETALLE = "detalle"
    GUERRA = "guerra"
    GUERRA_HISTORICO = "guerra_historico"
    CALIDAD = "calidad"
    DIRIGIDA = "dirigida"
    CONTROL = "control"
    CONTROL_REPASO = "control_repaso"
    TRADUCCIONES = "traducciones"
    RECTIFICACIONES = "rectificaciones"
    SEGUNDA_LECTURA = "segunda_lectura"
    SEGUNDA_BUSQUEDA = "segunda_busqueda"
    REPASO_EXPERTO = "repaso_experto"
    ENTRADA = "entrada"
    REPASO_ENTRADA = "repaso_entrada"


# Lo que le toca a cada uno del tope mensual (suman TOPE_MENSUAL_USD). «otros»: lo que no es de
# ningún modo de cada día (las sesiones, el catálogo vivo), que no se frena aquí pero cuenta. La
# reserva crítica del experto cuenta dentro de su parte: lo que gasta lo resta de su tope normal de
# los días que quedan. Reparto del 20 de octubre de 2026, con lo medido del 15 al 20 de octubre por
# día: base de la recogida 0,068-0,125 (media 0,10); base del control 0,037-0,119 (0,07); guerra
# 0,002; casos críticos de verdad desde el corte del 19 de octubre (22:41 UTC), ninguno (los cuatro
# que usaron la reserva eran entregas de la segunda lectura, que ya no la usan). Reparto de 60 USD
# desde el 20 de octubre: el experto, 40 (1,50 al día y la reserva crítica de lo que pase); la
# recogida horaria, 4 (0,13 al día); el control, 6 (su base y su cupo del experto); la segunda
# búsqueda, 6 (20 casos al día); otros, 3,50 (las sesiones). Desde el 28 de octubre de 2026, 150
# USD: lo mismo y 90 para el filtro de entrada (3 al día durante 30 días).
REPARTO_MENSUAL_USD: dict[str, float] = {
    EXPERTO: 40.00,
    Modo.HORARIO: 4.00,
    Modo.CONTROL: 6.00,
    Modo.GUERRA: 0.20,
    Modo.RECTIFICACIONES: 0.30,
    Modo.SEGUNDA_BUSQUEDA: 6.00,
    Modo.ENTRADA: 90.00,
    OTROS: 3.50,
}
# Los modos de cada día que paran al llegar al tope mensual. La recogida horaria sigue con el
# modelo base: sin ella no se sabe qué caso es crítico.
PARAN_AL_TOPE_MENSUAL = frozenset(
    {Modo.CONTROL, Modo.GUERRA, Modo.RECTIFICACIONES, Modo.SEGUNDA_LECTURA, Modo.SEGUNDA_BUSQUEDA}
)


class LimiteGasto(RuntimeError):
    pass


@dataclass(frozen=True)
class Mes:
    """Lo gastado en el mes (UTC) del momento: en total, con hoy, y antes de hoy por modo (sin las
    llamadas al experto) y del experto (Almacen.gasto_del_mes)."""

    momento: datetime
    total: float = 0.0
    modos_antes: dict[str, float] = field(default_factory=dict)
    experto_antes: float = 0.0


def del_mes(almacen: Any, momento: datetime, prefijo_experto: str = "") -> Mes:
    """Lo gastado en el mes del momento, de la base (Almacen.gastos_del_mes)."""
    total, modos, experto = almacen.gastos_del_mes(mes(momento), dia(momento), prefijo_experto)
    return Mes(momento, total, modos, experto)


def tope_mensual() -> float:
    """El tope mensual de la API: TOPE_MENSUAL_USD, o el de EODI_TOPE_MENSUAL_USD si se da."""
    try:
        return float(os.environ.get(VARIABLE_TOPE_MENSUAL) or TOPE_MENSUAL_USD)
    except ValueError:
        return TOPE_MENSUAL_USD


def parte_del_mes(nombre: str) -> float:
    """Lo que le toca a un modo (o al experto) del tope mensual; en proporción si se cambió."""
    return REPARTO_MENSUAL_USD.get(nombre, 0.0) * tope_mensual() / TOPE_MENSUAL_USD


def dias_que_quedan(momento: datetime) -> int:
    """Los días que quedan del mes (UTC), con el de hoy."""
    utc = momento.astimezone(UTC)
    return calendar.monthrange(utc.year, utc.month)[1] - utc.day + 1


def tope_del_dia(
    limite_diario: float, parte: float, gastado_antes: float, momento: datetime
) -> float:
    """El tope de hoy: lo que queda de la parte del mes entre los días que quedan, como mucho el
    límite diario. Lo que un día no se gasta queda para los siguientes."""
    queda = max(0.0, parte - gastado_antes) / dias_que_quedan(momento)
    return round(min(limite_diario, queda), 6)


def mes_agotado(mes: Mes | None, previsto: float = 0.0) -> bool:
    """Si lo gastado en el mes llega al tope mensual, o lo pasa con lo previsto."""
    if mes is None:
        return False
    tope = tope_mensual()
    return mes.total >= tope or mes.total + previsto > tope


def tope_experto(mes: Mes | None) -> float:
    """El tope normal del experto hoy: el límite diario mientras lo que queda de su parte del mes
    deje al menos MINIMO_EXPERTO_DIARIO_USD a cada uno de los días que quedan después de hoy; si
    no, lo que sobre de eso (y como poco lo que le toca de cada día). Sin mes, el límite diario."""
    if mes is None:
        return LIMITE_EXPERTO_DIARIO_USD
    queda = max(0.0, parte_del_mes(EXPERTO) - mes.experto_antes)
    dias = dias_que_quedan(mes.momento)
    libre = max(queda / dias, queda - MINIMO_EXPERTO_DIARIO_USD * (dias - 1))
    return round(min(LIMITE_EXPERTO_DIARIO_USD, libre), 6)


@dataclass(frozen=True)
class Uso:
    entrada: int
    salida: int
    escritura_cache: int = 0
    lectura_cache: int = 0
    # El modelo que hizo la llamada (el campo «model» de la respuesta); vacío, el base.
    modelo: str = ""

    @classmethod
    def de_respuesta(cls, usage: dict[str, Any], modelo: str | None = None) -> "Uso":
        return cls(
            entrada=int(usage.get("input_tokens", 0)),
            salida=int(usage.get("output_tokens", 0)),
            escritura_cache=int(usage.get("cache_creation_input_tokens") or 0),
            lectura_cache=int(usage.get("cache_read_input_tokens") or 0),
            modelo=modelo or "",
        )

    @classmethod
    def de_mensaje(cls, respuesta: dict[str, Any]) -> "Uso":
        """El uso de una respuesta del servicio, con el modelo que la dio."""
        return cls.de_respuesta(respuesta.get("usage", {}), respuesta.get("model"))

    def coste(self, lote: bool = False) -> float:
        return modelos.coste(
            self.modelo or None, self.entrada, self.salida, self.escritura_cache,
            self.lectura_cache, lote,
        )  # fmt: skip


def peor_caso(
    letras_entrada: int, max_salida: int, lote: bool = False, modelo: str | None = None,
    esfuerzo: str | None = None,
) -> float:  # fmt: skip
    """Coste máximo de una llamada: toda la entrada sin caché y toda la salida permitida, con el
    margen del razonamiento del modelo (el base si no se dice)."""
    nombre = modelo or modelos.base()
    salida = modelos.max_salida(nombre, max_salida, esfuerzo)
    return Uso(int(letras_entrada * TOKENS_POR_LETRA), salida, modelo=nombre).coste(lote)


class Tramo(StrEnum):
    NORMAL = "normal"
    RESERVA = "reserva"


def comprobar_experto(
    gastado_hoy: float, previsto: float, critico: bool = False, mes: Mes | None = None
) -> Tramo:
    """El tramo del experto que paga la llamada: el tope normal de hoy si cabe y, si no, la
    reserva crítica, solo para un caso crítico. Con el tope mensual agotado, solo la reserva.
    Lanza LimiteGasto si no cabe en ninguno."""
    tope = tope_experto(mes)
    agotado = mes_agotado(mes, previsto)
    if not agotado and gastado_hoy + previsto <= tope:
        return Tramo.NORMAL
    if critico and gastado_hoy + previsto <= tope + RESERVA_CRITICA_DIARIA_USD:
        return Tramo.RESERVA
    maximo = tope + (RESERVA_CRITICA_DIARIA_USD if critico else 0.0)
    raise LimiteGasto(
        f"experto{' (reserva crítica)' if critico else ''}: gastado {gastado_hoy:.4f} + "
        f"previsto {previsto:.4f} > {maximo:.2f} USD"
        + (f" (tope mensual de {tope_mensual():.2f} USD agotado)" if agotado else "")
    )


def margen_escalados(momento: datetime, tope: float = LIMITE_EXPERTO_DIARIO_USD) -> float:
    """Lo que hay que dejar libre del tope normal del experto para los escalados de lo que queda
    del día (UTC): MARGEN_ESCALADOS_USD, o lo que corresponda a lo que queda del día a ritmo
    constante si es menos (nada a las 24:00). Sin reparto por horas que deje la mañana sin
    experto."""
    utc = momento.astimezone(UTC)
    transcurrido = utc.hour * 3600 + utc.minute * 60 + utc.second
    return min(MARGEN_ESCALADOS_USD, tope * (1 - transcurrido / 86400))


def comprobar_al_ritmo(
    gastado_experto_hoy: float, previsto: float, momento: datetime, mes: Mes | None = None,
    que: str = EXPERTO,
) -> None:  # fmt: skip
    """Lo que el experto hace si le sobra (la segunda lectura, los motivos opcionales): solo con
    lo que no necesitan los escalados que no pueden esperar. El gasto del experto en el día tiene
    que ir por debajo del ritmo de su tope (margen_escalados), nunca en la reserva crítica ni con
    el tope mensual agotado. Lanza LimiteGasto si no."""
    tope = tope_experto(mes)
    margen = margen_escalados(momento, tope)
    if mes_agotado(mes, previsto) or gastado_experto_hoy + previsto > tope - margen:
        raise LimiteGasto(
            f"{que}: experto gastado {gastado_experto_hoy:.4f} + previsto {previsto:.4f} > "
            f"{tope - margen:.2f} USD (margen de {margen:.2f} para los escalados del resto del "
            "día, o tope mensual agotado)"
        )
    comprobar_experto(gastado_experto_hoy, previsto, critico=False, mes=mes)


def comprobar_segunda(
    gastado_experto_hoy: float, gastado_segunda_hoy: float, previsto: float,
    momento: datetime | None = None, mes: Mes | None = None,
) -> None:  # fmt: skip
    """La revisión por el experto de lo que marca la segunda lectura: cabe en su modo (0,30 al
    día) y en el tope normal del experto, nunca en la reserva crítica, y solo al ritmo de su tope
    (comprobar_al_ritmo). Lanza LimiteGasto si no."""
    if gastado_segunda_hoy + previsto > LIMITE_SEGUNDA_EXPERTO_DIARIO_USD:
        raise LimiteGasto(
            f"{Modo.SEGUNDA_LECTURA}: gastado {gastado_segunda_hoy:.4f} + previsto "
            f"{previsto:.4f} > {LIMITE_SEGUNDA_EXPERTO_DIARIO_USD:.2f} USD"
        )
    comprobar_al_ritmo(
        gastado_experto_hoy, previsto, momento or datetime.now(UTC), mes, Modo.SEGUNDA_LECTURA
    )


def comprobar_cupo(gastado_hoy: float, previsto: float, modo: Modo, mes: Mes | None = None) -> None:
    """El cupo propio del experto de un modo (la segunda búsqueda): su límite del día y lo que
    queda de su parte del mes, sin repartirla por días; nunca con el tope mensual agotado ni de la
    reserva crítica. Lanza LimiteGasto si no cabe."""
    if gastado_hoy + previsto > limite(modo):
        raise LimiteGasto(
            f"{modo}: gastado {gastado_hoy:.4f} + previsto {previsto:.4f} > {limite(modo):.2f} USD"
        )
    if mes is None:
        return
    queda = parte_del_mes(modo) - mes.modos_antes.get(modo, 0.0) - gastado_hoy
    if previsto > queda:
        raise LimiteGasto(
            f"{modo}: previsto {previsto:.4f} > {max(0.0, queda):.4f} USD de su parte del mes"
        )
    if mes_agotado(mes, previsto):
        raise LimiteGasto(f"{modo}: tope mensual de {tope_mensual():.2f} USD agotado")


def comprobar_control_experto(gastado_hoy: float, previsto: float, mes: Mes | None = None
                              ) -> None:  # fmt: skip
    """El cupo propio del experto en el control (lo no crítico): su límite del día, nunca con el
    tope mensual agotado ni de la reserva crítica. Lanza LimiteGasto si no cabe."""
    if gastado_hoy + previsto > LIMITE_CONTROL_EXPERTO_DIARIO_USD:
        raise LimiteGasto(
            f"experto del {Modo.CONTROL}: gastado {gastado_hoy:.4f} + previsto {previsto:.4f} > "
            f"{LIMITE_CONTROL_EXPERTO_DIARIO_USD:.2f} USD"
        )
    if mes_agotado(mes, previsto):
        raise LimiteGasto(
            f"experto del {Modo.CONTROL}: tope mensual de {tope_mensual():.2f} USD agotado"
        )


def reparto_experto(
    gastado_hoy: float, tope: float = LIMITE_EXPERTO_DIARIO_USD
) -> dict[str, float]:
    """Lo que el experto gastó en el día, repartido entre su tope normal del día (`tope`) y la
    reserva crítica (lo que pasa de él)."""
    return {
        "normal": round(min(gastado_hoy, tope), 6),
        "reserva": round(max(0.0, gastado_hoy - tope), 6),
    }


def espera_experto(ahora: datetime, critico: bool) -> str:
    """Hasta cuándo espera un caso que no cabe en el gasto del experto: el crítico (sin reserva),
    hasta la recogida siguiente; el normal, hasta la misma hora del día siguiente (su tope ya se
    renovó a las 00:00 UTC): así las esperas no vencen todas a medianoche y no se comen el tope
    de la madrugada (20 de octubre de 2026)."""
    if critico:
        return (ahora + ESPERA_REINTENTO).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (ahora.astimezone(UTC) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def espera_vencida(hasta: str, ahora: str, tope: Any = None) -> bool:
    """Una espera al experto ya vencida: llegó su hora, o se anotó con un tope (`tope`, el normal
    de entonces; sin él, el de antes del 15 de octubre de 2026) menor que el de ahora."""
    try:
        anotado = float(tope) if tope is not None else LIMITE_EXPERTO_ANTERIOR_USD
    except (TypeError, ValueError):
        anotado = LIMITE_EXPERTO_ANTERIOR_USD
    return anotado < LIMITE_EXPERTO_DIARIO_USD or ahora >= str(hasta)


def limite(modo: Modo) -> float:
    return {
        Modo.HORARIO: LIMITE_DIARIO_USD,
        Modo.HISTORICO: LIMITE_HISTORICO_USD,
        Modo.REVISION: LIMITE_REVISION_USD,
        Modo.DETALLE: LIMITE_DETALLE_USD,
        Modo.GUERRA: LIMITE_GUERRA_DIARIO_USD,
        Modo.GUERRA_HISTORICO: LIMITE_GUERRA_HISTORICO_USD,
        Modo.CALIDAD: LIMITE_CALIDAD_USD,
        Modo.DIRIGIDA: LIMITE_DIRIGIDA_USD,
        Modo.CONTROL: LIMITE_CONTROL_DIARIO_USD,
        Modo.CONTROL_REPASO: LIMITE_CONTROL_REPASO_USD,
        Modo.TRADUCCIONES: LIMITE_TRADUCCIONES_USD,
        Modo.RECTIFICACIONES: LIMITE_RECTIFICACIONES_USD,
        Modo.SEGUNDA_LECTURA: LIMITE_SEGUNDA_EXPERTO_DIARIO_USD,
        Modo.SEGUNDA_BUSQUEDA: LIMITE_SEGUNDA_BUSQUEDA_DIARIO_USD,
        Modo.REPASO_EXPERTO: LIMITE_REPASO_EXPERTO_USD,
        Modo.ENTRADA: LIMITE_ENTRADA_DIARIO_USD,
        Modo.REPASO_ENTRADA: LIMITE_REPASO_ENTRADA_USD,
    }[modo]


def diario(modo: Modo) -> bool:
    """Los modos con límite diario (lo gastado se cuenta solo en el día UTC)."""
    return modo in {
        Modo.HORARIO, Modo.GUERRA, Modo.CONTROL, Modo.RECTIFICACIONES, Modo.SEGUNDA_LECTURA,
        Modo.SEGUNDA_BUSQUEDA, Modo.ENTRADA,
    }  # fmt: skip


def limite_de_hoy(modo: Modo, mes: Mes | None = None) -> float:
    """El límite del modo; en los de cada día con parte del mes, lo que les toca hoy. El modelo
    base de la recogida horaria nunca para: como poco tiene su parte media de cada día, también
    con su parte o el tope del mes gastados."""
    if mes is None or not diario(modo) or modo not in REPARTO_MENSUAL_USD:
        return limite(modo)
    tope = tope_del_dia(
        limite(modo), parte_del_mes(modo), mes.modos_antes.get(modo, 0.0), mes.momento
    )
    if modo is Modo.HORARIO:
        utc = mes.momento.astimezone(UTC)
        media = parte_del_mes(modo) / calendar.monthrange(utc.year, utc.month)[1]
        tope = max(tope, round(min(limite(modo), media), 6))
    return tope


def comprobar(gastado: float, previsto: float, modo: Modo, mes: Mes | None = None) -> None:
    """Lanza LimiteGasto si lo gastado más lo previsto pasa del límite del modo (con `mes`, el de
    hoy según su parte del mes) o, en los modos que paran, del tope mensual."""
    tope = limite_de_hoy(modo, mes)
    if gastado + previsto > tope:
        raise LimiteGasto(
            f"{modo}: gastado {gastado:.4f} + previsto {previsto:.4f} > {tope:.2f} USD"
        )
    if modo in PARAN_AL_TOPE_MENSUAL and mes_agotado(mes, previsto):
        raise LimiteGasto(f"{modo}: tope mensual de {tope_mensual():.2f} USD agotado")


def mes(momento: datetime) -> str:
    """El mes (UTC) del momento, AAAA-MM."""
    return momento.astimezone(UTC).strftime("%Y-%m")


def dia(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%d")
