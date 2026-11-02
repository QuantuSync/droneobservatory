"""Las declaraciones oficiales citadas y una extracción nueva de los mismos artículos
(proceso/extraccion.conservar_oficiales y sin_oficiales_del_filtro):

- EODI-2026-00356 (2 de noviembre de 2026): la extracción de las 05:23 no volvió a leer la
  declaración del ΓΕΕΘΑ con los cuatro drones en inewsgr.com, aunque la ficha seguía teniendo el
  artículo, y la presencia bajó de confirmada a no confirmada (auditoría X). Llevaba así desde
  octubre: según la extracción encontrara o no esa declaración, la presencia iba y volvía.
- Lo que la medida a las 24 horas deja como no oficial no vuelve con una extracción nueva de los
  mismos artículos (el mismo camino que el filtro de entrada en EODI-2026-00694), solo con una
  fuente nueva que trae su frase.
"""

import copy
from datetime import UTC, datetime
from typing import Any

from almacen.base import Almacen
from proceso import decidir, extraccion
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS

AHORA = datetime(2026, 11, 2, 5, 23, tzinfo=UTC)
ARTICULO = "gdelt-62c9a4ff879f1f92"
OTRO = "gdelt-f740e996e2430aed"
DRONES = (
    "Σύμφωνα με τα στοιχεία του ΓΕΕΘΑ, στην περιοχή κινήθηκαν ένας σχηματισμός δύο F-16 "
    "και πέντε μεμονωμένα αεροσκάφη. Ένα ATR-72 και τέσσερα μη επανδρωμένα αεροσκάφη (UAV)."
)
SIN_DRONES = "όπως ανακοίνωσε το ΓΕΕΘΑ, συνολικά 7 τουρκικά αεροσκάφη έκαναν σήμερα παραβάσεις"


def _articulo(id_: str, medio: str) -> dict[str, Any]:
    return {**ejemplos.fuente(id_, "C"), "medio": medio, "idioma": "el",
            "frase_origen": "Έξι παραβιάσεις του ελληνικού εθνικού εναέριου χώρου"}  # fmt: skip


def _declaracion(articulo: str, numero: int, frase: str, medio: str = "inewsgr.com",
                 autoridad: str = "ΓΕΕΘΑ", **otros: Any) -> dict[str, Any]:  # fmt: skip
    return {
        **ejemplos.fuente(f"{articulo}-declaracion-{numero}", "B", es_autoridad=True),
        "medio": f"{autoridad} (declaración oficial citada en {medio})",
        "frase_origen": frase, "idioma": "el", "campos_respaldados": ["estado", "presencia_dron"],
        **otros,
    }  # fmt: skip


def _ficha(*fuentes: dict[str, Any]) -> dict[str, Any]:
    ficha = copy.deepcopy(ejemplos.incidente_minimo())
    paso = {"estado": "notificado", "fecha": ejemplos.instante("2025-10-02T06:00Z"),
            "fuente_id": fuentes[0]["id"]}  # fmt: skip
    ficha.update(id="EODI-2026-00356", fuentes=list(fuentes),
                 estado={"actual": "notificado", "historial": [paso]})  # fmt: skip
    return ficha


def test_la_declaracion_que_la_extraccion_nueva_no_trae_se_conserva() -> None:
    anterior = _ficha(_articulo(ARTICULO, "inewsgr.com"), _articulo(OTRO, "newsit.gr"),
                      _declaracion(OTRO, 1, SIN_DRONES, "newsit.gr"),
                      _declaracion(ARTICULO, 2, DRONES))  # fmt: skip
    nueva = _ficha(_articulo(ARTICULO, "inewsgr.com"), _articulo(OTRO, "newsit.gr"),
                   _declaracion(OTRO, 1, SIN_DRONES, "newsit.gr"))  # fmt: skip
    rehecha = extraccion.conservar_oficiales(nueva, anterior)
    ids = [f["id"] for f in rehecha["fuentes"]]
    assert f"{ARTICULO}-declaracion-2" in ids
    # Con ella, la presencia sigue confirmada por la autoridad que nombra los drones.
    decision = decidir.decidir_presencia(rehecha)
    assert decision.valor == "confirmada"
    assert decision.regla == "autoridad_atribuye"
    # Sin conservarla, era lo que pasó el 2 de noviembre a las 05:23.
    assert decidir.decidir_presencia(nueva).valor == "no_confirmada"


def test_no_se_conserva_si_el_articulo_ya_no_esta_ni_si_viene_repetida() -> None:
    declaracion = _declaracion(ARTICULO, 2, DRONES)
    anterior = _ficha(_articulo(ARTICULO, "inewsgr.com"), declaracion)
    # Tras una separación el artículo se fue con su suceso: la declaración se va con él.
    sin_articulo = _ficha(_articulo(OTRO, "newsit.gr"))
    assert extraccion.declaraciones_que_siguen(sin_articulo, anterior) == []
    # La extracción nueva trae la misma frase con otro número: no se repite.
    renumerada = _ficha(_articulo(ARTICULO, "inewsgr.com"), _declaracion(ARTICULO, 1, DRONES))
    assert extraccion.declaraciones_que_siguen(renumerada, anterior) == []
    # Una no oficial (la quitó el filtro o la medida) no vuelve como oficial.
    quitada = {**declaracion, "es_autoridad": False, "publica": False, "fiabilidad": "C"}
    nueva = _ficha(_articulo(ARTICULO, "inewsgr.com"))
    assert extraccion.declaraciones_que_siguen(nueva, _ficha(nueva["fuentes"][0], quitada)) == []
    # La de una revisión a mano la vuelve a poner proceso/revisados, no la extracción.
    revisada = {**declaracion, "id": "revisada-89fb9b68779f3f22-declaracion-1"}
    assert extraccion.declaraciones_que_siguen(nueva, _ficha(nueva["fuentes"][0], revisada)) == []


def _base(*fichas: dict[str, Any]) -> Almacen:
    almacen = Almacen.abrir()
    for ficha in fichas:
        almacen.guardar_incidente(ficha, AHORA, VOCABULARIO_MODELOS)
    return almacen


def _medida(**campos: Any) -> dict[str, Any]:
    return {"version": "medida/2", "fecha": "2026-11-01T18:17:03Z", "publicada": "x",
            "errores": [], "corregido": [], **campos}  # fmt: skip


def test_lo_que_quito_la_medida_no_vuelve_con_una_extraccion_nueva() -> None:
    """La medida corre una sola vez: si la extracción siguiente lee otra vez la misma declaración,
    la volvía a hacer oficial (mismo patrón que EODI-2026-00622 con la segunda búsqueda)."""
    centro = "Centrul Operații Aeriene"
    quitada = _declaracion(ARTICULO, 1, f"{centro}: o dronă", autoridad=centro)
    ministerio = _declaracion(OTRO, 1, "Ministerul Apărării: o dronă", "timpul.md",
                              autoridad="Ministerul Apărării")  # fmt: skip
    ficha = _ficha(_articulo(ARTICULO, "moldpres.md"), _articulo(OTRO, "timpul.md"), quitada,
                   ministerio)  # fmt: skip
    almacen = _base(ficha)
    errores = [{"dato": "autoridad", "autoridad": centro.upper(), "correcto": ""}]
    almacen.guardar_controles({"medida:EODI-2026-00356": _medida(
        errores=errores, corregido=[f"declaración no oficial: {quitada['id']}"],
        articulos=[ARTICULO, OTRO])}, "2026-11-01T18:17Z")  # fmt: skip
    rehecha = extraccion.sin_oficiales_del_filtro(almacen, ficha)
    fuentes = {f["id"]: f for f in rehecha["fuentes"]}
    assert fuentes[quitada["id"]]["es_autoridad"] is False
    assert fuentes[quitada["id"]]["publica"] is False
    # La otra autoridad, que la medida no nombra, sigue oficial.
    assert fuentes[ministerio["id"]]["es_autoridad"] is True
    # La misma autoridad con otro número en el mismo artículo tampoco vuelve.
    renumerada = _ficha(*ficha["fuentes"][:2], {**quitada, "id": f"{ARTICULO}-declaracion-2"})
    otra = extraccion.sin_oficiales_del_filtro(almacen, renumerada)
    assert all(not f["es_autoridad"] for f in otra["fuentes"] if "declaracion" in f["id"])
    # Una fuente nueva, que la ficha no tenía al medirla, trae su propia frase: sí es oficial.
    nuevo = "gdelt-0000000000000001"
    con_nueva = _ficha(*ficha["fuentes"], _articulo(nuevo, "agerpres.ro"),
                       _declaracion(nuevo, 1, f"{centro}: a doua dronă", "agerpres.ro",
                                    autoridad=centro))  # fmt: skip
    hecha = extraccion.sin_oficiales_del_filtro(almacen, con_nueva)
    assert {f["id"]: f for f in hecha["fuentes"]}[f"{nuevo}-declaracion-1"]["es_autoridad"]


def test_una_medida_antigua_sin_articulos_ni_nombre() -> None:
    """Las medidas de antes del 2 de noviembre (medida/1) no nombran la autoridad ni apuntan sus
    artículos: valen las declaraciones que quitaron, su autoridad (la de la ficha anterior) y la
    fecha de publicación para saber qué fuente es nueva. Lo revisado a mano no se toca (la cita
    revisada del Ministerul Apărării en EODI-2026-00728)."""
    ministerio = "Ministerul Apărării"
    quitada = _declaracion(OTRO, 1, f"{ministerio}: o dronă", "timpul.md", autoridad=ministerio)
    retirada = {**quitada, "es_autoridad": False, "publica": False, "fiabilidad": "C"}
    revisada = {**quitada, "id": "revisada-bf38ca0a3f505197-declaracion-1"}
    anterior = _ficha(_articulo(OTRO, "timpul.md"), retirada, revisada)
    nueva = _ficha(_articulo(OTRO, "timpul.md"), quitada, revisada)
    almacen = _base(anterior)
    medida = {"version": "medida/1", "fecha": "2026-11-01T18:17:03Z",
              "errores": [{"dato": "autoridad"}],
              "corregido": [f"declaración no oficial: {quitada['id']}"]}  # fmt: skip
    almacen.guardar_controles({"medida:EODI-2026-00356": medida}, "2026-11-01T18:17Z")
    rehecha = extraccion.sin_oficiales_del_filtro(almacen, nueva, anterior)
    fuentes = {f["id"]: f for f in rehecha["fuentes"]}
    assert fuentes[quitada["id"]]["es_autoridad"] is False
    assert fuentes[revisada["id"]]["es_autoridad"] is True
    # Sin medida, nada cambia.
    otra = {**nueva, "id": "EODI-2026-00999"}
    assert extraccion.sin_oficiales_del_filtro(almacen, otra, anterior) is otra
