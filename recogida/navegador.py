"""Páginas de noticias oficiales que cargan su lista de notas con JavaScript.

Tres fuentes oficiales (configuracion/fuentes_oficiales.json, tipo «pagina_js»: Defensa danesa,
LVNL y Skyguide) no traen los enlaces a sus notas en el HTML: la lista la monta el navegador.
Se leen con un navegador sin interfaz (Chromium con Playwright) en el servidor, fuera de la
recogida horaria: el temporizador de las fuentes de detalle (cada 3 horas, con su propio
cerrojo) renderiza cada lista y la deja en disco; la recogida horaria la lee de ahí y abre las
notas que hablan de drones como las de cualquier página oficial, sin navegador, porque las
notas sí vienen en el HTML.

Las mismas reglas que con el resto de fuentes: robots.txt de la lista, identificación del
observatorio («EODI-bot/1.0»), una página a la vez, sin imágenes, fuentes ni vídeo, tope de
tiempo y comprobación de que lo renderizado trae notas y no una página de bloqueo. Se mide el
tiempo y la memoria de cada render.

Uso, para probar una fuente:  python -m recogida.navegador <id de la fuente> <carpeta>
"""

import importlib
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from esquema import Documento
from recogida import paginas_oficiales
from recogida.descarga import AGENTE_EODI, DescargaFallida, PaginaBloqueada

registro = logging.getLogger(__name__)

TIPO = "pagina_js"
TOPE_S = 30.0
# Lo que no hace falta para leer los enlaces: menos peticiones y menos memoria.
_SIN_CARGAR = frozenset({"image", "font", "media"})
# Un render guardado vale 6 horas: dos ejecuciones del temporizador. Si es más viejo, la
# recogida horaria no lo usa (la fuente queda con aviso).
VIGENCIA_S = 6 * 3600


@dataclass(frozen=True)
class Render:
    id: str
    url: str
    fecha: str
    enlaces: int
    segundos: float
    memoria_mb: float | None


def _memoria_hijos_mb() -> float | None:
    """Memoria residente máxima de los procesos hijos (el navegador), en Linux."""
    if sys.platform == "win32":
        return None
    import resource

    return round(float(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss) / 1024, 1)


def renderizar(url: str, tope_s: float = TOPE_S) -> str:
    """El HTML de la página después de ejecutar su JavaScript."""
    # Solo está instalado en el servidor (requirements-navegador.txt).
    sync_playwright: Any = importlib.import_module("playwright.sync_api").sync_playwright
    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True)
        try:
            contexto = navegador.new_context(user_agent=AGENTE_EODI, java_script_enabled=True)
            pagina = contexto.new_page()
            pagina.route(
                "**/*",
                lambda ruta: (
                    ruta.abort() if ruta.request.resource_type in _SIN_CARGAR else ruta.continue_()
                ),
            )
            respuesta = pagina.goto(url, wait_until="networkidle", timeout=tope_s * 1000)
            if respuesta is None or respuesta.status != 200:
                codigo = respuesta.status if respuesta else "sin respuesta"
                raise DescargaFallida(f"{url}: código {codigo}")
            html: str = pagina.content()
        finally:
            navegador.close()
    return html


def leer(fuente: Documento, carpeta: Path) -> Render:
    """Renderiza la lista de la fuente y la guarda si trae enlaces a notas."""
    inicio = time.monotonic()
    html = renderizar(fuente["url"])
    segundos = round(time.monotonic() - inicio, 2)
    enlaces = paginas_oficiales.enlaces(html, fuente)
    if not enlaces:
        raise PaginaBloqueada(f"{fuente['url']}: la lista renderizada no trae notas")
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / f"{fuente['id']}.html").write_text(html, encoding="utf-8", newline="\n")
    render = Render(
        fuente["id"], fuente["url"], datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        len(enlaces), segundos, _memoria_hijos_mb(),
    )  # fmt: skip
    (carpeta / f"{fuente['id']}.json").write_text(
        json.dumps(asdict(render), ensure_ascii=False), encoding="utf-8", newline="\n"
    )
    return render


def guardado(fuente: Documento, carpeta: Path, ahora: datetime) -> str | None:
    """El último render de la lista si es reciente; None si no hay o es viejo."""
    datos, html = carpeta / f"{fuente['id']}.json", carpeta / f"{fuente['id']}.html"
    if not datos.exists() or not html.exists():
        return None
    render: dict[str, Any] = json.loads(datos.read_text(encoding="utf-8"))
    momento = datetime.fromisoformat(render["fecha"].replace("Z", "+00:00"))
    if (ahora - momento).total_seconds() > VIGENCIA_S:
        return None
    return html.read_text(encoding="utf-8")


def con_javascript(fuentes: tuple[Documento, ...]) -> list[Documento]:
    return [f for f in fuentes if f["tipo"] == TIPO]


def principal(argumentos: list[str] | None = None) -> int:
    from recogida import oficiales

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    argumentos = argumentos if argumentos is not None else sys.argv[1:]
    fuente = next(f for f in oficiales.fuentes() if f["id"] == argumentos[0])
    render = leer(fuente, Path(argumentos[1]))
    registro.info("render %s", re.sub(r"\s+", " ", json.dumps(asdict(render))))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
