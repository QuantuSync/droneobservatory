"""Genera los ficheros de la marca que sirve la web a partir del logo original.

Entrada: ``logo_eodi_original.png`` (el logo circular, con el exterior transparente) y la
tipografía Montserrat ExtraBold (licencia SIL OFL 1.1), la más parecida a la del logo, solo
para convertir «EODI» en trazos. Salida, en ``web/public``:

- ``favicon.svg`` y ``marca/eodi-simplificado.svg``: la versión simplificada para tamaños
  pequeños (círculo azul oscuro, anillos claros y «EODI» en blanco, sin mapa, puntos ni
  dron), con el texto ya en trazos para no depender de ninguna fuente;
- ``favicon.ico`` (16, 32 y 48 px) con esa versión;
- ``marca/logo-<n>.webp`` y ``.png``: el logo completo a los tamaños que usa la web;
- ``apple-touch-icon.png`` e ``iconos/icono-<n>.png``: el logo completo sobre azul oscuro,
  y ``iconos/icono-maskable-512.png`` con el margen de seguridad de los iconos adaptables;
- ``manifest.webmanifest``.

Uso (desde ``web/``): ``python marca/generar_marca.py <montserrat-latin-800-normal.woff2>``.
Necesita Pillow, fontTools y brotli; no forma parte de la web ni de sus tests.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fontTools.pens.basePen import BasePen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageChops, ImageDraw

WEB = Path(__file__).resolve().parent.parent
ORIGINAL = WEB / "marca" / "logo_eodi_original.png"
PUBLICO = WEB / "public"

# Colores tomados del logo: el fondo del círculo, el anillo exterior claro y los interiores.
AZUL_OSCURO = "#021c3e"
ANILLO_CLARO = "#92f4ff"
ANILLO_INTERIOR = "#3d8fc4"
BLANCO = "#ffffff"

# Geometría de la versión simplificada, en un lienzo de 64 × 64 unidades.
LADO = 64
CENTRO = LADO / 2
RADIO_CIRCULO = 31.5
RADIO_ANILLO_EXTERIOR = 28.6
GROSOR_ANILLO_EXTERIOR = 1.9
RADIO_ANILLO_INTERIOR = 25.8
GROSOR_ANILLO_INTERIOR = 0.9
ANCHO_TEXTO = 47.0
TEXTO = "EODI"
# Montserrat va algo más abierta que el logo: se aprieta el espacio entre letras.
APRIETE = 0.04

TAMANOS_ICO = (16, 32, 48)
TAMANOS_LOGO = (96, 192, 384, 640)
TAMANOS_ICONO = (192, 512)
LADO_APPLE = 180
# Icono de los avisos de ntfy (recogida/avisos.py): 256 px, el logo completo sobre fondo.
LADO_AVISO = 256
# Los iconos adaptables se recortan hasta un círculo del 80 % del lado.
ZONA_SEGURA = 0.8
# El logo completo sobre fondo ocupa este tanto del icono.
OCUPACION_ICONO = 0.92
SUPERMUESTREO = 16
CALIDAD_WEBP = 90
TEMA = AZUL_OSCURO


def trazo_del_texto(fuente: Path) -> tuple[str, list[list[tuple[float, float]]]]:
    """«EODI» en trazos: la ruta SVG y los contornos como polígonos, ya colocados."""
    tipo = TTFont(fuente)
    glifos = tipo.getGlyphSet()
    mapa = tipo.getBestCmap()
    unidades = tipo["head"].unitsPerEm
    nombres = [mapa[ord(letra)] for letra in TEXTO]
    avances = [glifos[n].width for n in nombres]
    apriete = APRIETE * unidades
    ancho = sum(avances) - apriete * (len(nombres) - 1)
    # Se escala para que las cuatro letras ocupen ANCHO_TEXTO unidades del lienzo.
    escala = ANCHO_TEXTO / ancho
    alto_mayusculas = tipo["OS/2"].sCapHeight * escala
    x0 = CENTRO - ANCHO_TEXTO / 2
    base = CENTRO + alto_mayusculas / 2
    svg = SVGPathPen(glifos)
    poligonos: list[list[tuple[float, float]]] = []
    x = 0.0
    for nombre, avance in zip(nombres, avances, strict=True):
        transformacion = (escala, 0, 0, -escala, x0 + x * escala, base)
        glifos[nombre].draw(TransformPen(svg, transformacion))
        plano = Aplanador(glifos)
        glifos[nombre].draw(TransformPen(plano, transformacion))
        poligonos.extend(plano.contornos)
        x += avance - apriete
    return svg.getCommands(), poligonos


class Aplanador(BasePen):  # type: ignore[misc]
    """Convierte los contornos de un glifo en polígonos (las curvas, en tramos cortos).

    Los nombres de los métodos son los que exige la interfaz de plumas de fontTools.
    """

    PASOS = 12

    def __init__(self, glifos: object) -> None:
        super().__init__(glifos)
        self.contornos: list[list[tuple[float, float]]] = []
        self._actual: list[tuple[float, float]] = []

    def _moveTo(self, p: tuple[float, float]) -> None:  # noqa: N802
        self._actual = [p]

    def _lineTo(self, p: tuple[float, float]) -> None:  # noqa: N802
        self._actual.append(p)

    def _curveToOne(  # noqa: N802
        self, a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]
    ) -> None:
        p0 = self._actual[-1]
        for i in range(1, self.PASOS + 1):
            t = i / self.PASOS
            u = 1 - t
            self._actual.append(
                (
                    u**3 * p0[0] + 3 * u * u * t * a[0] + 3 * u * t * t * b[0] + t**3 * c[0],
                    u**3 * p0[1] + 3 * u * u * t * a[1] + 3 * u * t * t * b[1] + t**3 * c[1],
                )
            )

    def _qCurveToOne(self, a: tuple[float, float], b: tuple[float, float]) -> None:  # noqa: N802
        p0 = self._actual[-1]
        for i in range(1, self.PASOS + 1):
            t = i / self.PASOS
            u = 1 - t
            self._actual.append(
                (
                    u * u * p0[0] + 2 * u * t * a[0] + t * t * b[0],
                    u * u * p0[1] + 2 * u * t * a[1] + t * t * b[1],
                )
            )

    def _closePath(self) -> None:  # noqa: N802
        if len(self._actual) > 2:
            self.contornos.append(self._actual)
        self._actual = []

    _endPath = _closePath  # noqa: N815


def svg_simplificado(ruta_texto: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {LADO} {LADO}" '
        f'role="img" aria-label="EODI">'
        f'<circle cx="{CENTRO}" cy="{CENTRO}" r="{RADIO_CIRCULO}" fill="{AZUL_OSCURO}"/>'
        f'<circle cx="{CENTRO}" cy="{CENTRO}" r="{RADIO_ANILLO_EXTERIOR}" fill="none" '
        f'stroke="{ANILLO_CLARO}" stroke-width="{GROSOR_ANILLO_EXTERIOR}"/>'
        f'<circle cx="{CENTRO}" cy="{CENTRO}" r="{RADIO_ANILLO_INTERIOR}" fill="none" '
        f'stroke="{ANILLO_INTERIOR}" stroke-width="{GROSOR_ANILLO_INTERIOR}"/>'
        f'<path fill="{BLANCO}" fill-rule="nonzero" d="{ruta_texto}"/>'
        "</svg>\n"
    )


def anillo(dibujo: ImageDraw.ImageDraw, radio: float, grosor: float, color: str, k: float) -> None:
    caja = [(CENTRO - radio) * k, (CENTRO - radio) * k, (CENTRO + radio) * k, (CENTRO + radio) * k]
    dibujo.ellipse(caja, outline=color, width=round(grosor * k))


def raster_simplificado(lado: int, poligonos: list[list[tuple[float, float]]]) -> Image.Image:
    """La versión simplificada dibujada a `lado` píxeles, con supermuestreo y relleno par-impar."""
    k = lado * SUPERMUESTREO / LADO
    grande = lado * SUPERMUESTREO
    imagen = Image.new("RGBA", (grande, grande), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(imagen)
    r = RADIO_CIRCULO
    dibujo.ellipse(
        [(CENTRO - r) * k, (CENTRO - r) * k, (CENTRO + r) * k, (CENTRO + r) * k], fill=AZUL_OSCURO
    )
    anillo(dibujo, RADIO_ANILLO_EXTERIOR, GROSOR_ANILLO_EXTERIOR, ANILLO_CLARO, k)
    anillo(dibujo, RADIO_ANILLO_INTERIOR, GROSOR_ANILLO_INTERIOR, ANILLO_INTERIOR, k)
    # Cada contorno invierte la máscara: así los huecos de la O y la D quedan abiertos.
    mascara = Image.new("L", (grande, grande), 0)
    for contorno in poligonos:
        capa = Image.new("L", (grande, grande), 0)
        ImageDraw.Draw(capa).polygon([(x * k, y * k) for x, y in contorno], fill=255)
        mascara = ImageChops.logical_xor(mascara.convert("1"), capa.convert("1")).convert("L")
    imagen.paste(Image.new("RGBA", (grande, grande), BLANCO), (0, 0), mascara)
    return imagen.resize((lado, lado), Image.Resampling.LANCZOS)


def sobre_fondo(logo: Image.Image, lado: int, ocupacion: float) -> Image.Image:
    """El logo completo centrado sobre un cuadrado azul oscuro, opaco."""
    fondo = Image.new("RGBA", (lado, lado), AZUL_OSCURO)
    medida = round(lado * ocupacion)
    reducido = logo.resize((medida, medida), Image.Resampling.LANCZOS)
    fondo.alpha_composite(reducido, ((lado - medida) // 2, (lado - medida) // 2))
    return fondo.convert("RGB")


def principal(fuente: Path) -> None:
    ruta_texto, poligonos = trazo_del_texto(fuente)
    svg = svg_simplificado(ruta_texto)
    (PUBLICO / "marca").mkdir(exist_ok=True)
    (PUBLICO / "iconos").mkdir(exist_ok=True)
    (PUBLICO / "favicon.svg").write_text(svg, encoding="utf-8")
    (PUBLICO / "marca" / "eodi-simplificado.svg").write_text(svg, encoding="utf-8")

    mayor = raster_simplificado(max(TAMANOS_ICO), poligonos)
    iconos = [raster_simplificado(n, poligonos) for n in TAMANOS_ICO]
    mayor.save(
        PUBLICO / "favicon.ico",
        sizes=[(n, n) for n in TAMANOS_ICO],
        append_images=iconos,
    )

    logo = Image.open(ORIGINAL).convert("RGBA")
    for n in TAMANOS_LOGO:
        reducido = logo.resize((n, n), Image.Resampling.LANCZOS)
        reducido.save(PUBLICO / "marca" / f"logo-{n}.png", optimize=True)
        reducido.save(PUBLICO / "marca" / f"logo-{n}.webp", quality=CALIDAD_WEBP, method=6)

    sobre_fondo(logo, LADO_APPLE, OCUPACION_ICONO).save(
        PUBLICO / "apple-touch-icon.png", optimize=True
    )
    sobre_fondo(logo, LADO_AVISO, OCUPACION_ICONO).save(
        PUBLICO / "marca" / f"aviso-{LADO_AVISO}.png", optimize=True
    )
    for n in TAMANOS_ICONO:
        sobre_fondo(logo, n, OCUPACION_ICONO).save(
            PUBLICO / "iconos" / f"icono-{n}.png", optimize=True
        )
    sobre_fondo(logo, max(TAMANOS_ICONO), ZONA_SEGURA).save(
        PUBLICO / "iconos" / "icono-maskable-512.png", optimize=True
    )

    manifiesto = {
        "name": "European Observatory of Drone Incidents",
        "short_name": "EODI",
        "start_url": "/",
        "display": "browser",
        "background_color": AZUL_OSCURO,
        "theme_color": TEMA,
        "icons": [
            *(
                {"src": f"/iconos/icono-{n}.png", "sizes": f"{n}x{n}", "type": "image/png"}
                for n in TAMANOS_ICONO
            ),
            {
                "src": "/iconos/icono-maskable-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
            {"src": "/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
    }
    (PUBLICO / "manifest.webmanifest").write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    principal(Path(sys.argv[1]))
