"""El conjunto de referencia (proceso/referencia.py, docs/control_fichas.md): las fichas cuyo valor
correcto de cada dato está comprobado contra el texto completo de sus fuentes.

Las copias guardadas de cada ficha (tests/referencia/fichas/) pasan por las funciones que deciden
cada dato al publicar y se comparan con la referencia. Falla una discrepancia nueva, una conocida
que ya está corregida (se quita de la lista; si vuelve, falla como nueva) y una lista de conocidas
más larga que el tope: la lista solo puede encoger."""

import copy
import json

from esquema import Documento
from proceso import auditoria_fichas, referencia

# Discrepancias conocidas el 21 de octubre de 2026. Solo puede bajar.
TOPE_DISCREPANCIAS = 5
PRESENCIAS = {"confirmada", "no_confirmada", "no_acreditada", "descartada"}
ESTADOS = {"notificado", "confirmado", "atribuido", "desmentido"}
TIPOS = {"incursion", "interrupcion_aeroportuaria", "sobrevuelo"}
PAISES = {"ES", "NL", "DK", "DE", "PL", "RO", "BG", "LT", "LV", "BE", "NO"}
OBLIGATORIAS = {
    "EODI-2025-00066", "EODI-2025-00228", "EODI-2025-00238", "EODI-2025-00157",
    "EODI-2025-00203", "EODI-2025-00357", "EODI-2026-00648", "EODI-2026-00131",
    "EODI-2026-00322", "EODI-2026-00488", "EODI-2026-00152", "EODI-2026-00512",
    "EODI-2026-00515", "EODI-2025-00154",
}  # fmt: skip


def _copias() -> dict[str, Documento]:
    fichas, _ = referencia.cargar()
    return {
        f["id"]: json.loads(
            (referencia.DIRECTORIO / "fichas" / f"{f['id']}.json").read_text(encoding="utf-8")
        )
        for f in fichas
    }


def test_cada_valor_de_la_referencia_lleva_su_cita_y_su_fuente() -> None:
    fichas, _ = referencia.cargar()
    assert len(fichas) >= 50
    assert len({f["id"] for f in fichas}) == len(fichas)
    for ficha in fichas:
        assert ficha["por_que"], ficha["id"]
        # Un dato que ninguna fuente legible dice queda sin comprobar, con su motivo.
        assert set(ficha["valores"]) | set(ficha.get("sin_comprobar", {})) == set(
            referencia.CAMPOS
        ), ficha["id"]
        assert all(ficha.get("sin_comprobar", {}).values()), ficha["id"]
        for campo, valor in ficha["valores"].items():
            assert {"valor", "cita", "enlace"} <= set(valor), (ficha["id"], campo)
            if valor["cita"] == "sin fuente":
                assert valor["enlace"] is None, (ficha["id"], campo)
            else:
                assert str(valor["enlace"]).startswith("http"), (ficha["id"], campo)


def test_los_ficheros_de_la_referencia_van_en_ascii() -> None:
    for ruta in sorted(referencia.DIRECTORIO.rglob("*.json")):
        assert ruta.read_bytes().isascii(), ruta.name


def test_la_referencia_cubre_cada_valor_y_las_fichas_obligatorias() -> None:
    fichas, _ = referencia.cargar()
    valores = [{c: v["valor"] for c, v in f["valores"].items()} for f in fichas]
    assert {v.get("presencia_dron") for v in valores} >= PRESENCIAS
    # Ningún «desmentido» de las 50 resiste sus fuentes: EODI-2026-00007 y EODI-2025-00357 solo
    # negaban el dron, y desde el 21 de octubre de 2026 ya no lo son (tests/test_decidir.py).
    hoy = {referencia.valores(d)["estado"] for d in _copias().values()}
    assert {v.get("estado") for v in valores} | hoy >= ESTADOS - {"desmentido"}
    assert {v.get("tipo") for v in valores} >= TIPOS
    assert {v.get("pais") for v in valores} >= PAISES
    assert {"frontera", "interior"} <= {v.get("zona") for v in valores}
    categorias = {(v.get("objetivo") or {}).get("categoria") for v in valores}
    assert {None, "aeropuerto", "base_militar", "puerto", "energia"} <= categorias
    assert {f["id"] for f in fichas} >= OBLIGATORIAS


def test_ninguna_ficha_de_la_referencia_tiene_una_discrepancia_nueva() -> None:
    resultado = referencia.comparar(_copias())
    assert resultado["ausentes"] == []
    assert resultado["nuevas"] == [], (
        "Una ficha de la referencia ya no da el valor comprobado contra sus fuentes. Arregla el "
        "código; la referencia solo se cambia con una cita nueva de una fuente "
        "(docs/control_fichas.md)."
    )


def test_una_discrepancia_corregida_sale_de_la_lista() -> None:
    resultado = referencia.comparar(_copias())
    assert resultado["corregidas"] == [], (
        "Estas discrepancias ya dan el valor correcto: quítalas de "
        "tests/referencia/discrepancias.json y baja TOPE_DISCREPANCIAS."
    )


def test_la_lista_de_discrepancias_solo_encoge() -> None:
    fichas, conocidas = referencia.cargar()
    ids = {f["id"] for f in fichas}
    assert len(conocidas) <= TOPE_DISCREPANCIAS
    claves = [(d["id"], d["campo"]) for d in conocidas]
    assert len(set(claves)) == len(claves)
    for discrepancia in conocidas:
        assert discrepancia["id"] in ids
        assert discrepancia["campo"] in referencia.CAMPOS
        assert discrepancia["motivo"] and discrepancia["cita"], discrepancia


def test_la_auditoria_avisa_si_una_ficha_de_la_referencia_cambia() -> None:
    copias = _copias()
    assert referencia.fallos(copias.values()) == []
    # Una regla que dejara de confirmar Sofía (EODI-2025-00157, la confirma la autoridad que lo
    # atribuye a un dron) sale en la comprobación R: sin autoridad que lo diga ni pruebas, la
    # presencia que decide el guardado ya no es la correcta.
    cambiada = copy.deepcopy(copias["EODI-2025-00157"])
    cambiada["afirmaciones"] = []
    cambiada["fuentes"] = [{**f, "es_autoridad": False} for f in cambiada["fuentes"]]
    cambiada.pop("pruebas", None)
    otras = [d for i, d in copias.items() if i != "EODI-2025-00157"]
    assert referencia.fallos([*otras, cambiada]) == ["EODI-2025-00157 presencia_dron"]
    fundida = {**copias["EODI-2025-00157"], "fusionado_en": "EODI-2025-00444"}
    assert referencia.fallos([*otras, fundida]) == ["EODI-2025-00157 ausente"]
    assert auditoria_fichas.auditar([cambiada])["R"] == ["EODI-2025-00157 presencia_dron"]
    # Las fichas que no vienen no cuentan (las pruebas de la auditoría con fichas inventadas).
    assert referencia.fallos([]) == []
