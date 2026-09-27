"""Caché local de páginas en bruto, fuera de git, para reprocesar sin volver a descargar.

Las páginas se guardan comprimidas: el histórico ocupa unas diez veces menos.
"""

import gzip
import re
from pathlib import Path

DIRECTORIO = Path(__file__).resolve().parent.parent / "data" / "cache"
# Segmentos que no empiezan por punto: una clave no puede salir del directorio.
_CLAVE_VALIDA = re.compile(r"^[a-z0-9_-][a-z0-9_.-]*(/[a-z0-9_-][a-z0-9_.-]*)*$")


class CachePaginas:
    def __init__(self, directorio: Path = DIRECTORIO) -> None:
        self.directorio = directorio

    def ruta(self, clave: str) -> Path:
        if not _CLAVE_VALIDA.match(clave):
            raise ValueError(f"clave de caché no válida: {clave!r}")
        return self.directorio / f"{clave}.html.gz"

    def leer(self, clave: str) -> str | None:
        ruta = self.ruta(clave)
        if not ruta.exists():
            return None
        return gzip.decompress(ruta.read_bytes()).decode("utf-8")

    def guardar(self, clave: str, texto: str) -> None:
        ruta = self.ruta(clave)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(".tmp")
        # mtime=0: el mismo texto produce siempre los mismos bytes.
        temporal.write_bytes(gzip.compress(texto.encode("utf-8"), mtime=0))
        temporal.replace(ruta)
