"""Autoridades sin entrada en la tabla que la traducción ponía en otro país (8/11/2026).

- «Poliția» a secas (EODI-2026-00768, Gordinești, y EODI-2026-00263, Hîrbovăț, las dos de
  Moldavia): la web decía «la Policía de Rumanía». Es la policía de Moldavia y la de Rumanía;
  ahora va en `por_pais` y se escribe con el país que dice la frase, el del medio oficial o el de
  la ficha.
- «Minister van Defensie» (EODI-2025-00072, Bélgica): la web decía «el ministro de Defensa de Países
  Bajos».
"""

from typing import Any

from proceso import autoridades

FRASE_768 = (
    "Poliția precizează: Obiectul suspect descoperit în raionul Rezina este o dronă de "
    "recunoaștere."
)


def _ficha(pais: str, medio: str, frase: str) -> dict[str, Any]:
    return {
        "lugar": {"pais": pais},
        "fuentes": [{"id": "f-declaracion-1", "medio": medio, "frase_origen": frase}],
    }


def test_la_policia_de_una_ficha_de_moldavia_es_la_de_moldavia() -> None:
    documento = autoridades.con_pais(
        _ficha("MD", "Poliția (declaración oficial citada en news.yam.md)", FRASE_768)
    )
    medio = documento["fuentes"][0]["medio"]
    assert medio == "Poliția (MD) (declaración oficial citada en news.yam.md)"
    assert autoridades.de_la_fuente(medio, "es").startswith("la Policía de Moldavia")
    assert autoridades.de_la_fuente(medio, "en").startswith("the Moldovan Police")


def test_la_policia_romana_sigue_rumana() -> None:
    documento = autoridades.con_pais(
        _ficha(
            "MD",
            "Poliția (declaración oficial citada en digi24.ro)",
            "Poliția Română a anunțat că drona a fost găsită",
        )
    )
    assert documento["fuentes"][0]["medio"].startswith("Poliția (RO)")


def test_el_ministro_de_defensa_de_una_ficha_belga_es_el_belga() -> None:
    documento = autoridades.con_pais(
        _ficha(
            "BE",
            "Minister van Defensie (declaración oficial citada en vrt.be)",
            "Minister van Defensie Theo Francken bevestigt dat er drones boven de basis vlogen",
        )
    )
    medio = documento["fuentes"][0]["medio"]
    assert medio.startswith("Minister van Defensie (BE)")
    assert autoridades.de_la_fuente(medio, "es").startswith("el ministro de Defensa de Bélgica")
