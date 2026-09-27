from pathlib import Path

import pytest

from modelo.extractor import (
    AfirmacionExtraida,
    Extractor,
    ExtractorConCache,
    ExtractorNulo,
    ExtractorRemoto,
    ResultadoExtraccion,
    clave_cache,
)

TEXTO = "Lufthavnen blev lukket efter observation af droner"


class ExtractorFijo(Extractor):
    """Devuelve siempre el mismo resultado y cuenta sus llamadas."""

    def __init__(self, version: str = "fijo-1") -> None:
        super().__init__()
        self._version = version
        self.llamadas = 0

    @property
    def version(self) -> str:
        return self._version

    def _extraer(self, texto: str) -> ResultadoExtraccion:
        self.llamadas += 1
        return ResultadoExtraccion(
            afirmaciones=(AfirmacionExtraida("drones.numero", {"min": 3, "max": 6}, 0.8),),
            tokens_entrada=len(texto.split()),
            tokens_salida=5,
        )


def test_extractor_nulo() -> None:
    extractor = ExtractorNulo()
    resultado = extractor.extraer(TEXTO)
    assert resultado.afirmaciones == ()
    assert extractor.registro.llamadas == 1
    assert extractor.registro.tokens_entrada == 0


def test_registro_de_tokens_acumula() -> None:
    extractor = ExtractorFijo()
    extractor.extraer(TEXTO)
    extractor.extraer(TEXTO)
    assert extractor.registro.llamadas == 2
    assert extractor.registro.tokens_entrada == 2 * len(TEXTO.split())
    assert extractor.registro.tokens_salida == 10


def test_remoto_sin_implementar() -> None:
    extractor = ExtractorRemoto(version="0")
    with pytest.raises(NotImplementedError):
        extractor.extraer(TEXTO)
    assert extractor.registro.llamadas == 0


def test_cache_evita_la_segunda_llamada(tmp_path: Path) -> None:
    interno = ExtractorFijo()
    extractor = ExtractorConCache(interno, tmp_path)
    primero = extractor.extraer(TEXTO)
    segundo = extractor.extraer(TEXTO)
    assert primero == segundo
    assert interno.llamadas == 1
    assert extractor.registro.llamadas == 1
    assert extractor.registro.aciertos_cache == 1
    assert extractor.registro.tokens_salida == 5


def test_cache_persiste_entre_instancias(tmp_path: Path) -> None:
    ExtractorConCache(ExtractorFijo(), tmp_path).extraer(TEXTO)
    interno = ExtractorFijo()
    ExtractorConCache(interno, tmp_path).extraer(TEXTO)
    assert interno.llamadas == 0


def test_cambiar_version_invalida_la_cache(tmp_path: Path) -> None:
    ExtractorConCache(ExtractorFijo("v1"), tmp_path).extraer(TEXTO)
    interno = ExtractorFijo("v2")
    ExtractorConCache(interno, tmp_path).extraer(TEXTO)
    assert interno.llamadas == 1
    assert len(list(tmp_path.iterdir())) == 2


def test_otro_texto_otra_entrada(tmp_path: Path) -> None:
    interno = ExtractorFijo()
    extractor = ExtractorConCache(interno, tmp_path)
    extractor.extraer(TEXTO)
    extractor.extraer(TEXTO + ".")
    assert interno.llamadas == 2


def test_clave_depende_de_texto_y_version() -> None:
    assert clave_cache(TEXTO, "v1") == clave_cache(TEXTO, "v1")
    assert clave_cache(TEXTO, "v1") != clave_cache(TEXTO, "v2")
    assert clave_cache(TEXTO, "v1") != clave_cache(TEXTO + " ", "v1")


def test_la_cache_no_guarda_el_texto(tmp_path: Path) -> None:
    ExtractorConCache(ExtractorFijo(), tmp_path).extraer(TEXTO)
    (fichero,) = tmp_path.iterdir()
    assert TEXTO not in fichero.read_text(encoding="utf-8")
