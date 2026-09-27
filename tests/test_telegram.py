from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from recogida.cache import CachePaginas
from recogida.recorrido import (
    Progreso,
    clave_pagina,
    pagina,
    publicaciones_en_cache,
    recorrer_historico,
)
from recogida.telegram import es_pagina_de_canal, leer_pagina, url_pagina
from tests.telegram_falso import CanalFalso, descargador

FIXTURE = Path(__file__).parent / "fixtures" / "canal.html"
INICIO = datetime(2026, 1, 1, tzinfo=UTC)


def canal(n: int) -> CanalFalso:
    return CanalFalso({i: (INICIO + timedelta(hours=i), f"texto {i}") for i in range(1, n + 1)})


def test_lee_cabecera_publicaciones_y_enlace_anterior() -> None:
    leida = leer_pagina(FIXTURE.read_text(encoding="utf-8"))
    assert leida.canal is not None
    assert leida.canal.titulo.startswith("Повітряні Сили")
    assert leida.canal.verificado
    assert leida.canal.enlaces_descripcion == ("https://sites.google.com/view/uaairforce",)
    assert leida.anterior == 100
    # La publicación sin texto (solo imagen) se conserva con texto vacío.
    assert [p.id for p in leida.publicaciones] == [100, 101, 102]
    assert leida.publicaciones[2].texto == ""


def test_texto_con_saltos_sin_respuesta_citada_y_fecha_utc() -> None:
    publicacion = leer_pagina(FIXTURE.read_text(encoding="utf-8")).publicaciones[1]
    assert publicacion.texto.startswith("⚡️ ЗБИТО/ПОДАВЛЕНО 10 ВОРОЖИХ БПЛА\n\nУ ніч на 27")
    assert "відповіді" not in publicacion.texto
    assert '"мобільні"' in publicacion.texto
    assert publicacion.fecha == datetime(2026, 9, 27, 4, 30, 2, tzinfo=UTC)
    assert publicacion.enlace == "https://t.me/kpszsu/101"


def test_pagina_sin_cabecera_no_es_contenido_real() -> None:
    assert es_pagina_de_canal(FIXTURE.read_text(encoding="utf-8"))
    assert not es_pagina_de_canal("<html>Too Many Requests</html>")
    assert leer_pagina("<html></html>").canal is None


def test_url_de_pagina() -> None:
    assert url_pagina("kpszsu") == "https://t.me/s/kpszsu"
    assert url_pagina("kpszsu", 80) == "https://t.me/s/kpszsu?before=80"


def test_cache_guarda_y_lee_comprimido(tmp_path: Path) -> None:
    cache = CachePaginas(tmp_path)
    assert cache.leer("kpszsu/antes-5") is None
    cache.guardar("kpszsu/antes-5", "<html>ñ</html>")
    assert cache.leer("kpszsu/antes-5") == "<html>ñ</html>"
    assert cache.ruta("kpszsu/antes-5").name == "antes-5.html.gz"
    with pytest.raises(ValueError, match="clave"):
        cache.ruta("../fuera")


def test_la_portada_nunca_sale_de_la_cache(tmp_path: Path) -> None:
    falso = canal(5)
    cache = CachePaginas(tmp_path)
    d = descargador(falso)
    pagina(d, cache, "kpszsu", None, usar_cache=True)
    pagina(d, cache, "kpszsu", 3, usar_cache=True)
    pagina(d, cache, "kpszsu", 3, usar_cache=True)
    assert len(falso.pedidas) == 2
    assert cache.leer(clave_pagina("kpszsu", 3)) is not None


def test_recorrido_del_historico_se_reanuda(tmp_path: Path) -> None:
    falso = canal(10)
    cache = CachePaginas(tmp_path / "cache")
    ruta = tmp_path / "progreso.json"
    desde = INICIO + timedelta(hours=4)
    # Un corte a mitad: el progreso guardado apunta a la página siguiente.
    Progreso(inicio=11, siguiente=8, paginas=1).guardar(ruta)
    cache.guardar(clave_pagina("kpszsu", 11), falso.html(11))
    progreso = recorrer_historico(descargador(falso), cache, "kpszsu", desde, ruta)
    assert progreso.siguiente is None
    assert Progreso.leer(ruta) == progreso
    assert falso.pedidas == ["https://t.me/s/kpszsu?before=8", "https://t.me/s/kpszsu?before=5"]
    ids = sorted(p.id for p in publicaciones_en_cache(cache, "kpszsu", 11, desde))
    assert ids == [4, 5, 6, 7, 8, 9, 10]


def test_recorrido_nuevo_empieza_en_la_portada(tmp_path: Path) -> None:
    falso = canal(4)
    ruta = tmp_path / "progreso.json"
    progreso = recorrer_historico(
        descargador(falso), CachePaginas(tmp_path), "kpszsu", INICIO, ruta
    )
    assert progreso.inicio == 5
    assert falso.pedidas[0] == "https://t.me/s/kpszsu"


def test_falta_una_pagina_en_la_cache(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list(publicaciones_en_cache(CachePaginas(tmp_path), "kpszsu", 11, INICIO))
