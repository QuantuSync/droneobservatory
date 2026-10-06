"""Previsión y tendencias: qué está pasando más de lo normal y qué es probable que pase.

Regla de todo el paquete: solo se publica lo comprobado. Cada número se calcula con los datos
anteriores a una fecha y se compara con lo que pasó después, avanzando en el tiempo; se publica
solo si mejora claramente a una referencia simple (la frecuencia de siempre y «mañana igual que
hoy»), y lleva a la vista su historial de aciertos. Lo que no pasa la comprobación no sale en
`publicacion/prevision.json` (queda en docs/informe_prevision.md como pendiente).

Desde que se publica, cada previsión queda en el registro (tabla `previsiones` de la base, que
no admite cambios ni borrados) con la hora en que se hizo, antes de conocerse el resultado, y
se puntúa cuando el resultado ya se conoce:

- «Esta noche en la frontera»: la de cada país para la noche siguiente, en la primera recogida
  desde las 17:00 UTC (antes de que empiece la noche en Ucrania); se puntúa a los 3 días, cuando
  ya han llegado las noticias de un dron caído;
- «La semana que viene»: la de cada país, en la primera recogida del sábado; se puntúa una
  semana después de acabar la semana;
- «Segunda noche»: cuando sale el aviso.
"""

from datetime import UTC, date, datetime, timedelta

from esquema import Documento
from proceso.prevision import cambios, frontera, segunda_noche, semanal
from proceso.prevision.datos import Datos

VERSION = "prevision-1.0.0"
VERSION_ESQUEMA = "1.0.0"
HORA_REGISTRO_NOCHE = 17
DIAS_PARA_PUNTUAR_NOCHE = 3
DIAS_PARA_PUNTUAR_SEMANA = 13
METODO = {
    "es": (
        "Cada número se calcula solo con datos anteriores y se publica solo si, comprobado hacia "
        "atrás noche a noche o semana a semana, acierta más que la frecuencia de siempre y que "
        "«mañana igual que hoy»."
    ),
    "en": (
        "Each figure is computed only from earlier data and is published only if, checked back "
        "night by night or week by week, it does better than the usual frequency and than "
        "“tomorrow same as today”."
    ),
}


def _instante(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")


def _frontera(datos: Datos, ahora: datetime) -> tuple[Documento, list[Documento]]:
    noche = datos.hasta + timedelta(days=1)
    conocida = datos.hasta - timedelta(days=DIAS_PARA_PUNTUAR_NOCHE)
    por_pais = frontera.calcular(datos, noche, conocida)
    paises = []
    nuevas = []
    for pais, documento in por_pais.items():
        if "probabilidad" not in documento:
            continue
        paises.append({"pais": pais, **documento})
        if ahora.hour >= HORA_REGISTRO_NOCHE:
            nuevas.append({
                "id": f"frontera:{pais}:{noche.isoformat()}", "tipo": "frontera", "pais": pais,
                "objetivo": noche.isoformat(), "emitida": _instante(ahora),
                "probabilidad": documento["probabilidad"], "metodo": frontera.VERSION,
            })  # fmt: skip
    return {
        "version": frontera.VERSION,
        "noche": {"desde": datos.hasta.isoformat(), "hasta": noche.isoformat()},
        "paises": paises,
    }, nuevas


def _semana(datos: Datos, ahora: datetime) -> tuple[Documento, list[Documento]]:
    todas = semanal.series(datos)
    siguiente = semanal.lunes(datos.hasta) + timedelta(days=7)
    paises, marcador, nuevas = [], [], []
    for (pais, grupo), serie in sorted(todas.items()):
        if grupo != "todo":
            continue
        comprobacion, reconstruidas = semanal.comprobar_semana(serie)
        if not comprobacion["publicable"]:
            continue
        # Lo esperado para la semana siguiente, con todas las semanas cerradas (la semana en
        # curso aún no cuenta: está a medias).
        media, minimo, maximo, _ = semanal.prevision(serie.cuentas)
        paises.append({
            "pais": pais, "esperado": round(media, 1), "minimo": minimo, "maximo": maximo,
            "comprobacion": comprobacion,
        })  # fmt: skip
        for r in reconstruidas[-semanal.SEMANAS_EN_MARCADOR :]:
            marcador.append({
                "semana": r.semana.isoformat(), "pais": pais, "esperado": round(r.esperado, 1),
                "minimo": r.minimo, "maximo": r.maximo, "real": r.real,
                "dentro": r.minimo <= r.real <= r.maximo, "tipo": "reconstruida",
            })  # fmt: skip
        if datos.hasta.weekday() >= 5:
            nuevas.append({
                "id": f"semana:{pais}:{siguiente.isoformat()}", "tipo": "semana", "pais": pais,
                "objetivo": siguiente.isoformat(), "emitida": _instante(ahora),
                "esperado": round(media, 1), "minimo": minimo, "maximo": maximo,
                "metodo": semanal.VERSION,
            })  # fmt: skip
    return {
        "version": semanal.VERSION,
        "semana": siguiente.isoformat(),
        "fijada": datos.hasta.weekday() >= 5,
        "paises": paises,
        "marcador": marcador,
    }, nuevas


def _rachas(datos: Datos) -> Documento | None:
    todas = semanal.series(datos)
    juntas = [s for (_, g), s in todas.items() if g == "todo"]
    separadas = [s for (_, g), s in todas.items() if g != "todo"]
    comprobacion_juntas = semanal.comprobar_rachas(juntas)
    comprobacion_separadas = semanal.comprobar_rachas(separadas)
    # La separación frontera/interior se usa si mejora el resultado.
    if (
        comprobacion_separadas["publicable"]
        and comprobacion_separadas["mejora_sobre_normal"]
        > comprobacion_juntas["mejora_sobre_normal"]
    ):
        modo, elegidas, comprobacion = "por_grupo", separadas, comprobacion_separadas
    else:
        modo, elegidas, comprobacion = "todo", juntas, comprobacion_juntas
    if not comprobacion["publicable"]:
        return None
    activas = [r for s in elegidas if (r := semanal.racha_actual(s)) is not None]
    activas.sort(key=lambda r: (-r["veces"], r["pais"]))
    con_racha = {r["pais"] for r in activas}
    terminadas = [
        r
        for s in elegidas
        if (r := semanal.racha_terminada(s)) is not None and r["pais"] not in con_racha
    ]
    terminadas.sort(key=lambda r: (r["hasta"], r["pais"]), reverse=True)
    graficas = {}
    for pais in sorted(con_racha):
        serie = todas.get((pais, "todo"))
        if serie is not None and (g := semanal.grafica(serie)) is not None:
            graficas[pais] = g
    return {
        "version": semanal.VERSION,
        "modo": modo,
        "comprobacion": comprobacion,
        "activas": activas,
        "terminadas": terminadas,
        "graficas": graficas,
    }


def puntuar(entrada: Documento, datos: Datos) -> Documento:
    """La entrada del registro con su resultado, si ya se conoce. La previsión no cambia: el
    resultado se añade al lado."""
    objetivo = date.fromisoformat(entrada["objetivo"])
    if entrada["tipo"] == "frontera":
        if datos.hasta < objetivo + timedelta(days=DIAS_PARA_PUNTUAR_NOCHE):
            return entrada
        return {
            **entrada,
            "con_dron": bool(frontera.resultado_noche(datos, entrada["pais"], objetivo)),
        }
    if entrada["tipo"] == "semana":
        if datos.hasta < objetivo + timedelta(days=DIAS_PARA_PUNTUAR_SEMANA):
            return entrada
        real = semanal.incidentes_de_semana(datos.incidentes, entrada["pais"], objetivo)
        return {**entrada, "real": real, "dentro": entrada["minimo"] <= real <= entrada["maximo"]}
    if entrada["tipo"] == "segunda_noche":
        grande = segunda_noche.grandes(datos)
        if objetivo not in grande:
            return entrada
        return {**entrada, "grande": grande[objetivo]}
    return entrada


def calcular(
    datos: Datos, ahora: datetime, registro: list[Documento]
) -> tuple[Documento, list[Documento]]:
    """El documento de prevision.json y las previsiones nuevas que hay que registrar (las que
    ya están en el registro no se vuelven a registrar ni cambian)."""
    vistas = {e["id"] for e in registro}
    frontera_doc, nuevas_f = _frontera(datos, ahora)
    semana_doc, nuevas_s = _semana(datos, ahora)
    segunda = segunda_noche.calcular(datos, datos.hasta - timedelta(days=1))
    nuevas_n = []
    aviso = segunda.get("aviso")
    if aviso is not None and date.fromisoformat(aviso["tras_noche"]) >= datos.hasta - timedelta(
        days=1
    ):
        objetivo = date.fromisoformat(aviso["tras_noche"]) + timedelta(days=1)
        nuevas_n.append({
            "id": f"segunda_noche:UA:{objetivo.isoformat()}", "tipo": "segunda_noche",
            "pais": "UA", "objetivo": objetivo.isoformat(), "emitida": _instante(ahora),
            "probabilidad": aviso["probabilidad"], "metodo": segunda_noche.VERSION,
        })  # fmt: skip
    else:
        segunda.pop("aviso", None)
    nuevas = [e for e in (*nuevas_f, *nuevas_s, *nuevas_n) if e["id"] not in vistas]
    completo = sorted([*registro, *nuevas], key=lambda e: (e["objetivo"], e["id"]))
    documento: Documento = {
        "version_esquema": VERSION_ESQUEMA,
        "version": VERSION,
        "calculado": _instante(ahora),
        "datos_hasta": datos.hasta.isoformat(),
        "metodo": METODO,
        "frontera": frontera_doc,
        "semana": semana_doc,
        "cajas": {p: list(c) for p, c in sorted(datos.cajas.items())},
        "registro": [puntuar(e, datos) for e in completo],
    }
    if segunda["comprobacion"]["publicable"]:
        documento["segunda_noche"] = segunda
    rachas = _rachas(datos)
    if rachas is not None:
        documento["rachas"] = rachas
    cambiado = cambios.calcular(datos)
    if cambiado is not None:
        documento["cambios"] = cambiado
    return documento, nuevas
