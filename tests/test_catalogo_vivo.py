"""Catálogo 1.1.0 y catálogo vivo: aceleraciones derivadas con su fórmula, clase de aeromodelo,
lectores de War&Sanctions y de fichas de fabricante, reglas de entrada, historial versionado,
tácticas, incorporación a la base y exportación. Sin red: las páginas son de prueba."""

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from proceso import catalogo_vivo as cv
from proceso.deduccion import aceleraciones, catalogo
from recogida import catalogo_vivo
from recogida.descarga import DescargaFallida

G = 9.80665
AHORA = datetime(2026, 10, 5, 5, 23, tzinfo=UTC)


@pytest.fixture(scope="module")
def real() -> catalogo.Catalogo:
    return catalogo.cargar()


# --- Aceleraciones derivadas ------------------------------------------------------------


def _modelo(tipo: str, **campos: list[dict[str, Any]]) -> dict[str, Any]:
    return {"id": "m", "tipo_aeronave": tipo,
            "campos": {c: {"datos": d, "sin_fuente": False}
                       for c, d in campos.items()}}  # fmt: skip


def test_multirrotor_aceleracion_horizontal_es_g_por_tangente_del_angulo() -> None:
    angulo = {"valor": 35, "unidad": "°", "fuente": "D19", "cita": "Ángulo máx. de cabeceo 35°"}
    derivadas = aceleraciones.derivar(_modelo("multirrotor", angulo_inclinacion=[angulo]))
    horizontal = derivadas["aceleracion_horizontal"][0]
    assert horizontal["valor"] == pytest.approx(G * math.tan(math.radians(35)), abs=1e-4)
    assert horizontal["unidad"] == "m/s2" and horizontal["fuente"] == "D19"
    assert horizontal["derivada"]["formula"] == "a = g·tan(θ)"
    assert horizontal["derivada"]["datos"] == [
        {"campo": "angulo_inclinacion", "fuente": "D19", "valor": 35, "unidad": "°"}
    ]
    # La vertical, sin relación empuje/peso, solo como cota inferior: el máximo no se sabe.
    vertical = derivadas["aceleracion_vertical"][0]
    assert (
        set(vertical) >= {"min", "derivada"} and "max" not in vertical and "valor" not in vertical
    )
    assert vertical["min"] == pytest.approx(G * (1 / math.cos(math.radians(35)) - 1), abs=1e-4)


def test_con_modo_manual_sin_angulo_el_angulo_publicado_es_solo_cota_inferior() -> None:
    derivadas = aceleraciones.derivar(_modelo(
        "multirrotor",
        angulo_inclinacion=[{"valor": 25, "unidad": "°", "fuente": "C13", "nota": "Modo: N."}],
        velocidad_maxima=[{"valor": 27, "unidad": "m/s", "fuente": "C13", "nota": "Modo: M."}],
    ))  # fmt: skip
    entrada = derivadas["aceleracion_horizontal"][0]
    assert "valor" not in entrada and "max" not in entrada
    assert entrada["min"] == pytest.approx(G * math.tan(math.radians(25)), abs=1e-4)
    assert entrada["derivada"]["formula"] == "a ≥ g·tan(θ)"


def test_con_empuje_peso_la_vertical_es_g_por_r_menos_uno() -> None:
    derivadas = aceleraciones.derivar(_modelo(
        "multirrotor",
        angulo_inclinacion=[{"valor": 30, "unidad": "°", "fuente": "X1"}],
        relacion_empuje_peso=[{"valor": 2.5, "unidad": "n", "fuente": "X2"}],
    ))  # fmt: skip
    assert [v["valor"] for v in derivadas["aceleracion_vertical"]] == [round(G * 1.5, 4)]


def test_tiempo_de_0_a_100_da_una_cota_inferior() -> None:
    derivadas = aceleraciones.derivar(_modelo(
        "multirrotor", tiempo_0_100=[{"valor": 2, "unidad": "s", "fuente": "C1"}]
    ))  # fmt: skip
    entrada = derivadas["aceleracion_horizontal"][0]
    assert entrada["min"] == pytest.approx(100 / 3.6 / 2, abs=1e-4) and "max" not in entrada


def test_ala_fija_por_factor_de_carga_alabeo_y_radio_de_viraje() -> None:
    derivadas = aceleraciones.derivar(_modelo(
        "ala_fija",
        factor_carga=[{"valor": 2, "unidad": "n", "fuente": "T1"}],
        angulo_alabeo=[{"valor": 45, "unidad": "°", "fuente": "T2"}],
        radio_viraje=[{"valor": 100, "unidad": "m", "fuente": "T3"}],
        velocidad_crucero=[{"valor": 72, "unidad": "km/h", "fuente": "T3"}],
    ))  # fmt: skip
    valores = sorted(v["valor"] for v in derivadas["aceleracion_horizontal"])
    assert valores == pytest.approx(sorted([G * math.sqrt(3), G, 20 * 20 / 100]), abs=1e-3)
    assert not derivadas["aceleracion_vertical"]


def test_el_catalogo_lleva_las_derivadas_al_dia_con_sus_fuentes(real: catalogo.Catalogo) -> None:
    crudo = json.loads(catalogo.CATALOGO.read_text(encoding="utf-8"))
    assert aceleraciones.con_derivadas(crudo) == crudo
    for modelo in crudo["modelos"]:
        for campo in aceleraciones.DERIVADOS:
            for dato in modelo.get("campos", {}).get(campo, {}).get("datos", []):
                if "derivada" in dato:
                    assert dato["fuente"] in real.fuentes
                    assert {d["fuente"] for d in dato["derivada"]["datos"]} == {dato["fuente"]}


def test_la_envolvente_de_aceleracion_sale_de_los_modelos(real: catalogo.Catalogo) -> None:
    sub250 = real.envolvente("multirrotor_consumo_sub250", "aceleracion_horizontal")
    angulos = real.envolvente("multirrotor_consumo_sub250", "angulo_inclinacion")
    assert angulos.maximo is not None and sub250.maximo is not None
    assert sub250.maximo == pytest.approx(G * math.tan(math.radians(angulos.maximo)), abs=1e-3)
    # Una clase con un modelo sin ángulo (el Agras T50 no lo publica) queda sin cota.
    assert real.envolvente("multirrotor_pesado_carga", "aceleracion_horizontal").maximo is None


def test_la_clase_fpv_tiene_velocidad_con_fuente(real: catalogo.Catalogo) -> None:
    velocidad = real.envolvente("fpv", "velocidad_maxima")
    assert velocidad.maximo is not None and not velocidad.debil
    assert {"dji_fpv", "dji_avata", "iflight_nazgul_eco_dc5"} <= set(real.clases["fpv"].modelos)


def test_clase_nueva_de_aeromodelo_pequeno_de_ala_fija(real: catalogo.Catalogo) -> None:
    clase = real.clases["aeromodelo_ala_fija_pequeno"]
    assert clase.tipo_aeronave == "ala_fija" and clase.corto_alcance
    assert clase.clase_esquema == "ala_fija" and clase.aegis == ()
    assert len(clase.modelos) == 4
    # La altura de la categoría abierta, con su norma como fuente.
    altura = real.envolvente("aeromodelo_ala_fija_pequeno", "altura_tipica")
    assert altura.maximo == 120
    assert any(real.fuentes[f]["tipo"] == "normativa" for f in altura.fuentes)


# --- War&Sanctions y fichas de fabricante ----------------------------------------------

FICHA_WS = """<html><h1>Ovod</h1><div>FPV kamikaze</div><div>Total number:</div>
<div>Updated: 04.05.2026</div><div>Declared characteristics</div>
<div>Take-off weight, max.</div><div><span>5.4 kg</span></div>
<div>Flight time</div><div>8-12 min</div>
<div>Maximum speed</div><div>100–140 km/h</div>
<div>Maximum flight altitude</div><div>5 000 m</div>
<div>Control fiber optic cable up to 20 km long</div><div>yes</div>
<div>Provide additional information</div></html>"""


def test_ficha_de_war_and_sanctions() -> None:
    ficha = cv.ficha_war_sanctions("https://war-sanctions.gur.gov.ua/en/uav/486", FICHA_WS)
    assert ficha is not None
    assert (ficha.nombre, ficha.proposito, ficha.fecha) == ("Ovod", "FPV kamikaze", "2026-05-04")
    assert ficha.cifras["mtow"] == [
        {"valor": 5.4, "unidad": "kg", "cita": "Take-off weight, max. 5.4 kg"}
    ]
    assert ficha.cifras["autonomia"][0] == {"min": 8.0, "max": 12.0, "unidad": "min",
                                            "cita": "Flight time 8-12 min"}  # fmt: skip
    assert ficha.cifras["velocidad_maxima"][0]["max"] == 140.0
    assert ficha.cifras["techo"][0]["valor"] == 5000.0
    assert cv.fibra(ficha)


def test_la_clase_de_un_modelo_nuevo_por_su_proposito_y_sus_cifras() -> None:
    def ficha(proposito: str, alcance: float | None, velocidad: float | None) -> cv.Ficha:
        nueva = cv.Ficha("u", "X", proposito)
        if alcance is not None:
            nueva.cifras["alcance"] = [{"valor": alcance, "unidad": "km", "cita": "c"}]
        if velocidad is not None:
            nueva.cifras["velocidad_maxima"] = [{"valor": velocidad, "unidad": "km/h", "cita": "c"}]
        return nueva

    assert cv.clase_por_proposito(ficha("FPV kamikaze", 5, 180))[0] == cv.FPV
    assert cv.clase_por_proposito(ficha("False target", 600, 160))[0] == cv.SENUELO
    assert cv.clase_por_proposito(ficha("Strike", 950, 550))[0] == cv.REACCION
    assert cv.clase_por_proposito(ficha("Barrage", 1500, 180))[0] == cv.PISTON
    assert cv.clase_por_proposito(ficha("Barrage", 40, 110))[0] == cv.MERODEADORA
    # Un dron de reconocimiento puede ser un multirrotor o un ala fija: no se decide.
    assert cv.clase_por_proposito(ficha("Reconnaissance", 100, 120))[0] is None
    # El nodriza que lleva drones FPV no es un FPV.
    assert cv.clase_por_proposito(ficha("Carrier of FPV drones", 70, None))[0] is None
    assert (
        cv.clase_por_proposito(ficha("Reconnaissance / Carrier of FPV drones", 300, None))[0]
        is None
    )


def test_una_cifra_con_una_unidad_que_no_es_la_del_campo_no_entra(real: catalogo.Catalogo) -> None:
    from recogida.catalogo_vivo import unidad_del_campo

    crudo = json.loads(catalogo.CATALOGO.read_text(encoding="utf-8"))
    assert unidad_del_campo(crudo, "autonomia", {"valor": 31, "unidad": "min"})
    assert unidad_del_campo(crudo, "autonomia", {"valor": 4, "unidad": "h"})
    assert not unidad_del_campo(crudo, "autonomia", {"valor": 10, "unidad": "km"})
    assert unidad_del_campo(crudo, "alcance", {"valor": 900, "unidad": "m"})
    assert unidad_del_campo(crudo, "clase_ue", {"texto": "C1"})


def test_ficha_de_fabricante_por_etiquetas() -> None:
    pagina = ("<div>Peso de despegue</div><div>720 g</div><div>Velocidad máx. de ascenso</div>"
              "<div>10 m/s</div><div>Velocidad horizontal máx.</div><div>21 m/s</div>"
              "<div>Tiempo máx. de vuelo</div><div>46 minutos</div>"
              "<div>Ángulo máx. de cabeceo</div><div>35°</div>")  # fmt: skip
    ficha = cv.ficha_fabricante("u", "DJI Air 3", pagina)
    assert ficha.cifras["velocidad_ascenso"][0]["valor"] == 10.0
    assert ficha.cifras["velocidad_maxima"][0]["valor"] == 21.0
    assert ficha.cifras["autonomia"][0] == {"valor": 46.0, "unidad": "min",
                                            "cita": "Tiempo máx. de vuelo 46 minutos"}  # fmt: skip
    assert ficha.cifras["angulo_inclinacion"][0]["unidad"] == "°"


def test_nombres_de_modelo_con_marcas_comerciales(real: catalogo.Catalogo) -> None:
    nombres = cv.nombres_de(json.loads(catalogo.CATALOGO.read_text(encoding="utf-8")))
    assert cv.modelo_de("DJI MAVIC 3T EU", nombres) == "dji_mavic_3t"
    assert cv.modelo_de("DJI Mini 4 Pro Fly More Combo", nombres) == "dji_mini_4_pro"
    assert cv.modelo_de("Izdeliye-52 (Lancet)", nombres) == "lancet_52"
    assert cv.modelo_de("DJI Mini 9", nombres) is None


# --- Tácticas --------------------------------------------------------------------------


def test_tacticas_en_un_texto() -> None:
    texto = (
        "Russia launched Shahed drones along a new route over Belarus. "
        "The fiber-optic FPV drones are immune to jamming. "
        "Gerbera decoys flew at an altitude of 150 m to exhaust air defence."
    )
    tipos = {t for t, _, _ in cv.tacticas(texto)}
    assert {"ruta", "fibra_optica", "senuelo", "altura"} <= tipos
    ruta = next(p for t, _, p in cv.tacticas(texto) if t == "ruta")
    assert ruta == ["RU", "BY"]


# --- Catálogo vivo: aplicar lo admitido --------------------------------------------------


def _base() -> tuple[dict[str, Any], dict[str, Any]]:
    return (json.loads(catalogo.CATALOGO.read_text(encoding="utf-8")),
            json.loads(catalogo.FUENTES.read_text(encoding="utf-8")))  # fmt: skip


def test_aplicar_vivo_solo_anade_y_versiona() -> None:
    base, fuentes = _base()
    vivo = {
        "version": 3,
        "fuentes": {"V1": {"titulo": "W&S", "url": "https://war-sanctions.gur.gov.ua/en/uav/999",
                           "fecha": None, "consultada": "2026-10-05", "tipo": "inteligencia",
                           "prioridad": "normal"}},
        "datos": [{"modelo": "geran_1", "campo": "viento_maximo", "alta": "2026-10-05",
                   "dato": {"fuente": "V1", "valor": 15, "unidad": "m/s", "cita": "Wind 15 m/s"}}],
    }  # fmt: skip
    nuevo, nuevas_fuentes = catalogo.aplicar_vivo(base, fuentes, vivo)
    assert nuevo["version"] == f"{base['version']}+vivo.3"
    assert "V1" in nuevas_fuentes["fuentes"]
    geran = next(m for m in nuevo["modelos"] if m["id"] == "geran_1")
    assert geran["campos"]["viento_maximo"]["datos"][-1]["fuente"] == "V1"
    assert geran["vivo"] == {"alta": "2026-10-05", "fuentes": ["V1"]}
    # El catálogo de la configuración no cambia y el vivo se construye y valida.
    assert base == _base()[0]
    construido = catalogo.construir(nuevo, nuevas_fuentes, json.loads(
        catalogo.ZONAS.read_text(encoding="utf-8")))  # fmt: skip
    assert construido.version.endswith("+vivo.3")


def test_una_cifra_nueva_solo_ensancha_la_envolvente(real: catalogo.Catalogo) -> None:
    base, fuentes = _base()
    antes = real.envolvente("multirrotor_consumo", "velocidad_maxima")
    vivo = {"version": 1, "datos": [{"modelo": "dji_air_3", "campo": "velocidad_maxima",
            "alta": "2026-10-05",
            "dato": {"fuente": "D20", "valor": 30, "unidad": "m/s"}}]}  # fmt: skip
    nuevo = catalogo.construir(*catalogo.aplicar_vivo(base, fuentes, vivo), json.loads(
        catalogo.ZONAS.read_text(encoding="utf-8")))  # fmt: skip
    despues = nuevo.envolvente("multirrotor_consumo", "velocidad_maxima")
    assert despues.maximo is not None and antes.maximo is not None
    assert despues.maximo >= antes.maximo and despues.minimo == antes.minimo


# --- Barrido: reglas de entrada e historial --------------------------------------------


RSS_PRENSA = """<rss><channel><item><title>New Geran variant flies at an altitude of 50 m</title>
<link>https://prensa.example/a</link><pubDate>Mon, 05 Oct 2026 06:00:00 GMT</pubDate>
<description>Geran-2 drones flew at an altitude of 50 m along a new route.</description></item>
</channel></rss>"""
RSS_OTRA = RSS_PRENSA.replace("prensa.example/a", "otro.example/b")
LISTA_WS = """<a href="https://war-sanctions.gur.gov.ua/en/uav/999"><div>Name</div><div>Nuevo-1</div>
<div>Purpose</div><div>False target</div></a>"""
FICHA_NUEVA = """<h1>Nuevo-1</h1><div>False target</div><div>Updated: 04.05.2026</div>
<div>Declared characteristics</div><div>Maximum speed</div><div>180 km/h</div>
<div>Flight range</div><div>500 km</div><div>Provide additional information</div>"""


class Paginas:
    """Descargador de prueba: dirección → página; robots.txt lo permite todo."""

    def __init__(self, paginas: dict[str, str]) -> None:
        self.paginas = paginas
        self.pedidas: list[str] = []

    def texto(self, url: str, _valido: Any) -> str:
        self.pedidas.append(url)
        if url.endswith("/robots.txt"):
            return "User-agent: *\nAllow: /\n"
        for clave, pagina in self.paginas.items():
            if url.startswith(clave):
                return pagina
        raise DescargaFallida(f"{url}: 404")


def _configuracion(*fuentes: dict[str, Any]) -> dict[str, Any]:
    return {"version": "1.0.0", "descripcion": "prueba", "fuentes": list(fuentes)}


def test_inteligencia_entra_directo_y_prensa_espera_una_segunda_fuente(tmp_path: Path) -> None:
    ws = {"id": "war_sanctions", "nombre": "W&S", "tipo": "inteligencia", "ritmo": "diario",
          "lector": "war_sanctions", "url": "https://war-sanctions.gur.gov.ua/en/uav",
          "paginas_max": 1}  # fmt: skip
    prensa = {"id": "prensa", "nombre": "Prensa", "tipo": "prensa_tecnica", "ritmo": "semanal",
              "lector": "rss", "url": "https://prensa.example/feed", "solo_dron": True}  # fmt: skip
    paginas = Paginas({
        "https://war-sanctions.gur.gov.ua/en/uav?page=1": LISTA_WS,
        "https://war-sanctions.gur.gov.ua/en/uav/999": FICHA_NUEVA,
        "https://prensa.example/feed": RSS_PRENSA,
    })  # fmt: skip
    resumen = catalogo_vivo.barrer(tmp_path, AHORA, paginas, None, None, False, None,  # type: ignore[arg-type]
                                   _configuracion(ws, prensa))  # fmt: skip
    novedades = catalogo_vivo.leer_novedades(tmp_path)
    modelo = next(n for n in novedades if n["tipo"] == cv.MODELO_NUEVO)
    assert modelo["estado"] == cv.ADMITIDA and modelo["clase"] == cv.SENUELO
    tactica = next(n for n in novedades if n["tipo"] == cv.TACTICA)
    assert tactica["estado"] == cv.CANDIDATA
    # Lo admitido entra en el catálogo vivo, versionado, con su historial.
    vivo = json.loads((tmp_path / catalogo_vivo.CATALOGO).read_text(encoding="utf-8"))
    assert vivo["version"] == 1 and vivo["modelos"][0]["nombre"] == "Nuevo-1"
    assert vivo["modelos"][0]["clase"] == cv.SENUELO
    historial = (tmp_path / catalogo_vivo.HISTORIAL).read_text(encoding="utf-8").splitlines()
    assert json.loads(historial[0])["version"] == 1
    assert resumen["aplicadas"] == len(json.loads(historial[0])["novedades"])
    # La misma táctica en otro sitio la confirma; volver a leer lo mismo no añade nada.
    paginas.paginas["https://prensa.example/feed"] = RSS_OTRA
    control = json.loads((tmp_path / catalogo_vivo.CONTROL).read_text(encoding="utf-8"))
    control["fuentes"]["prensa"]["ultima_lectura"] = "2026-09-01T00:00Z"
    (tmp_path / catalogo_vivo.CONTROL).write_text(json.dumps(control), encoding="utf-8")
    catalogo_vivo.barrer(tmp_path, AHORA, paginas, None, None, False, None,  # type: ignore[arg-type]
                         _configuracion(ws, prensa))  # fmt: skip
    tacticas = [n for n in catalogo_vivo.leer_novedades(tmp_path) if n["tipo"] == cv.TACTICA]
    assert tacticas and all(t["estado"] == cv.ADMITIDA for t in tacticas)
    assert any(t.get("confirmada_por") for t in tacticas)
    vivo2 = json.loads((tmp_path / catalogo_vivo.CATALOGO).read_text(encoding="utf-8"))
    assert vivo2["version"] == 1  # nada nuevo que aplicar al catálogo


def test_una_candidata_del_mismo_sitio_no_se_confirma() -> None:
    def novedad(id_: str, url: str) -> dict[str, Any]:
        return {"id": id_, "clave": "tactica|ruta||BY", "estado": cv.CANDIDATA,
                "fuente": {"url": url}}  # fmt: skip

    mismas = [novedad("a", "https://p.example/1"), novedad("b", "https://www.p.example/2")]
    assert cv.confirmar_candidatos(mismas) == []
    otras = [novedad("a", "https://p.example/1"), novedad("b", "https://q.example/2")]
    assert len(cv.confirmar_candidatos(otras)) == 2


def test_el_robots_txt_que_no_permite_no_se_lee(tmp_path: Path) -> None:
    class Prohibido(Paginas):
        def texto(self, url: str, _valido: Any) -> str:
            if url.endswith("/robots.txt"):
                return "User-agent: *\nDisallow: /\n"
            return super().texto(url, _valido)

    prensa = {"id": "prensa", "nombre": "Prensa", "tipo": "prensa_tecnica", "ritmo": "semanal",
              "lector": "rss", "url": "https://prensa.example/feed"}  # fmt: skip
    paginas = Prohibido({"https://prensa.example/feed": RSS_PRENSA})
    resumen = catalogo_vivo.barrer(tmp_path, AHORA, paginas, None, None, False, None,  # type: ignore[arg-type]
                                   _configuracion(prensa))  # fmt: skip
    assert resumen["fuentes"]["prensa"] == "no_leida"
    assert "https://prensa.example/feed" not in paginas.pedidas


def test_el_extractor_respeta_el_presupuesto_y_valida_cada_cifra(tmp_path: Path) -> None:
    class Extractor:
        def __init__(self) -> None:
            self.llamadas = 0

        def mensaje(self, _cuerpo: Any) -> dict[str, Any]:
            self.llamadas += 1
            texto = json.dumps({"cifras": [
                {"modelo": "Gerbera", "campo": "alcance", "valor": 700, "unidad": "km",
                 "frase": "The Gerbera can fly up to 700 km."},
                {"modelo": "Gerbera", "campo": "techo", "valor": 9000, "unidad": "m",
                 "frase": "una frase que no está en el texto"},
            ]})  # fmt: skip
            return {"stop_reason": "end_turn", "content": [{"type": "text", "text": texto}],
                    "usage": {"input_tokens": 1000, "output_tokens": 100}}  # fmt: skip

    extractor = Extractor()
    barrido = catalogo_vivo.Barrido(tmp_path, AHORA, *_base(), Paginas({}), extractor)  # type: ignore[arg-type]
    cifras = catalogo_vivo.extraer_cifras(
        barrido, ["The Gerbera can fly up to 700 km."], cv.nombres_de(_base()[0])
    )
    assert [c["dato"]["valor"] for c in cifras] == [700]
    assert barrido.gasto["dias"][AHORA.date().isoformat()] > 0
    # Sin presupuesto no se llama.
    barrido.gasto["dias"][AHORA.date().isoformat()] = catalogo_vivo.LIMITE_DIARIO_USD
    assert catalogo_vivo.extraer_cifras(barrido, ["The Gerbera can fly 700 km."], {}) == []
    assert extractor.llamadas == 1


def test_incorporacion_a_la_base_y_exportacion_por_semana(tmp_path: Path) -> None:
    from exportacion import semanal

    novedad = {"id": "n1", "fecha": "2026-10-05", "semana": "2026-W41", "estado": "admitida",
               "tipo": "cifra_nueva", "clave": "cifra|geran_1|viento_maximo|x",
               "fuente": {"id": "war_sanctions", "tipo": "inteligencia", "url": "https://w/1",
                          "titulo": "Geran-1", "fecha": None}}  # fmt: skip
    (tmp_path / catalogo_vivo.NOVEDADES).write_text(json.dumps(novedad) + "\n", encoding="utf-8")
    (tmp_path / catalogo_vivo.CATALOGO).write_text(json.dumps({"version": 2}), encoding="utf-8")
    (tmp_path / catalogo_vivo.TACTICAS).write_text(json.dumps({"tactica|ruta||BY": {
        "tactica": "ruta", "modelos": [], "paises": ["BY"], "primera": "2026-10-05",
        "ultima": "2026-10-05", "veces": 1, "estado": "candidata", "ejemplos": []}}),
        encoding="utf-8")  # fmt: skip
    almacen = Almacen.abrir()
    assert catalogo_vivo.incorporar(almacen, tmp_path) == {"catalogo": 1, "novedades": 1,
                                                           "tacticas": 1}  # fmt: skip
    assert catalogo_vivo.incorporar(almacen, tmp_path) == {}
    datos = semanal.novedades_catalogo(almacen, "1.1.0+vivo.2", {"version": 2})
    assert datos["semanas"] == [{"semana": "2026-W41", "novedades": [novedad]}]
    assert semanal.tacticas_catalogo(almacen)["tacticas"][0]["clave"] == "tactica|ruta||BY"
