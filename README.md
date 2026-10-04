# Observatorio Europeo de Incidentes con Drones (EODI)

*European Observatory of Drone Incidents* · [droneobservatory.eu](https://droneobservatory.eu)

Registra cada incidente con drones en Europa, incluida la guerra entre Ucrania
y Rusia en los dos sentidos, para una web pública de una sola pantalla con el mapa de Europa y para un conjunto de
datos interno más detallado destinado al sistema de detección AEGIS.

Principios: cada dato guarda quién lo dice; la ubicación es un área (punto más
radio); Ucrania va en una capa aparte agregada por ataque; nada se borra; lo
interno nunca llega a lo público; de cada fuente se guarda el hecho, una frase
breve de origen y el enlace, nunca el texto completo.

Fases hechas: cimientos; recogida automática de la capa de guerra con el canal
oficial de la Fuerza Aérea de Ucrania (RU_UA) y el del Ministerio de Defensa
ruso (UA_RU), las dos marcadas como reivindicación de parte, con sus
históricos desde octubre de 2022; y recogida de noticias europeas sobre drones
en los ficheros GKG de GDELT, filtradas, deduplicadas y agrupadas en
candidatos internos; el extractor que los convierte en incidentes europeos,
con fusión, episodios y presencia_dron; y la web pública de una sola pantalla
en [droneobservatory.eu](https://droneobservatory.eu), en español e inglés.

## Estructura

| Carpeta | Contenido |
| --- | --- |
| `esquema/` | JSON Schema versionados (1.11.0; `esquema/exportacion/` para la exportación semanal), con marca de visibilidad por campo |
| `configuracion/` | Fuentes con su fiabilidad, vocabularios de modelos de dron y de regiones, nomenclátor de lugares europeos, cajas de coordenadas de los países, vocabulario de noticias, medios europeos de GDELT y la lista de referencia de 2025 |
| `proceso/` | Validaciones, máquina de estados, regla de credibilidad, ataques, tramos solapados, noticias (filtro, réplicas y agrupación), extracción, validación de fichas, incidentes, fusión y episodios; y el motor de deducción por descarte físico (`proceso/deduccion/`, catálogo de prestaciones en `configuracion/catalogo_drones.json`, [`docs/informe_deduccion.md`](docs/informe_deduccion.md)) |
| `modelo/` | Extractor: cliente HTTP del servicio (configurado por secretos), ficha con salida obligada por esquema, coste y límites, lectura de las primeras frases |
| `almacen/` | Base de datos SQLite con historial, cifrado con age y rama `estado` del repositorio de datos |
| `exportacion/` | `incidentes.geojson`, `incidentes_sin_ubicacion.json` y `ucrania.json` para la web, cada uno con su lista cerrada de campos; y la exportación semanal interna y cifrada para AEGIS, con el origen de cada dato y el nivel de detalle de cada incidente ([`docs/informe_exportacion_aegis.md`](docs/informe_exportacion_aegis.md)) |
| `recogida/` | Descarga educada, caché, fuentes de partes (Fuerza Aérea y Ministerio de Defensa ruso), GDELT, anomalías térmicas de NASA FIRMS, tráfico aéreo de adsb.lol, detección en directo de cierres de aeropuerto con las posiciones en tiempo real y mapa diario de interferencia GPS ([`docs/informe_europa_directo.md`](docs/informe_europa_directo.md)), meteorología de Open-Meteo y METAR, ejecución horaria, histórico y auditoría de cobertura |
| `publicacion/` | Ficheros públicos generados: `ucrania.json`, `incidentes.geojson` (incidentes con punto, para el mapa) e `incidentes_sin_ubicacion.json` (incidentes cuyo lugar solo se sabe a nivel de país o de región) |
| `web/` | Web pública de una sola pantalla: mapa, fichas, línea de tiempo, metodología y datos abiertos ([`web/README.md`](web/README.md)) |
| `tests/` | Tests |

## Ejecutar los tests

Requiere Python 3.13.

```sh
python -m venv .venv
. .venv/bin/activate          # en Windows: .venv\Scripts\activate
pip install -r requirements-desarrollo.txt

pytest
ruff check .
ruff format --check .
mypy
```

`mypy` usa la configuración estricta de `pyproject.toml`. Los tests no usan la
red y los de cifrado generan una clave efímera; para cifrar datos reales, la
identidad age se pasa en la variable de entorno `EODI_CLAVE_AGE` y nunca se
guarda en el repositorio.

## Recogida

- `python -m recogida.horaria --correo <correo>`: lo que ejecuta cada hora, en el
  minuto 17, el servidor de recogida ([`docs/servidor.md`](docs/servidor.md)); el
  workflow `recogida` queda para lanzarla a mano en una emergencia. Descarga `db.age` de la rama `estado`,
  recoge lo nuevo desde el cursor de cada fuente (con relectura de las últimas
  48 horas) y de GDELT, regenera `publicacion/` y sube la base si ha cambiado.
- `python -m recogida.historico --fuente <id> --correo <correo> [--solo-cache]`:
  histórico de una fuente de partes, en local y reanudable, incorporado a la
  base de la rama `estado`, con la auditoría de cobertura por días. Las páginas
  en bruto quedan en `data/cache/`, fuera de git.
- `python -m recogida.lugares_osm`: regenera el nomenclátor de lugares desde
  OpenStreetMap; se ejecuta a mano y el resultado se revisa.
- Workflow `historico-gdelt`: histórico de noticias desde los ficheros GKG,
  repartido en hasta 20 trabajos; los parciales van cifrados a la rama
  `historico-gdelt` del repositorio de datos y un trabajo final los incorpora.
- `python -m recogida.extractor estimar | lote`: coste previsto del histórico
  con una muestra de llamadas, y extracción del histórico por lotes dentro del
  límite de gasto.
- `python -m recogida.comparacion [--candidatos]`: cobertura frente a la lista
  de referencia de 2025.

## Web

`vercel.json` define el build (`cd web && npm run build`), las cabeceras de
seguridad y las direcciones propias de cada incidente y ataque. Cada push a `main`
que cambia `web/`, `publicacion/` o `vercel.json` se despliega con la integración
de Vercel con GitHub, también los commits de datos de la recogida. Detalle en
[`web/README.md`](web/README.md) y [`docs/informe_web.md`](docs/informe_web.md).

Decisiones, valores y cobertura en [`docs/informe_recogida.md`](docs/informe_recogida.md),
[`docs/informe_gdelt_mindef.md`](docs/informe_gdelt_mindef.md),
[`docs/informe_gkg_partes.md`](docs/informe_gkg_partes.md) y
[`docs/informe_extractor_europa.md`](docs/informe_extractor_europa.md).

## Licencia

- Código: [Apache-2.0](LICENSE).
- Datos publicados (`incidentes.geojson`, `incidentes_sin_ubicacion.json`, `ucrania.json`):
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Detalle en
  [LICENSE-DATOS](LICENSE-DATOS). Las frases de origen citadas pertenecen a sus
  autores y se reproducen como cita breve junto al enlace.
- `configuracion/lugares_europa.json` contiene datos © colaboradores de
  OpenStreetMap, bajo licencia [ODbL](https://www.openstreetmap.org/copyright).
- `configuracion/medios_europa.json` sale de la lista de dominios por país que
  publica GDELT.
- `configuracion/paises_europa.json` contiene datos © colaboradores de
  OpenStreetMap (Nominatim), bajo licencia ODbL.
- `configuracion/instalaciones_europa.json` contiene datos © colaboradores de
  OpenStreetMap, bajo licencia ODbL.
- `configuracion/fronteras_europa.json` sale de
  [Natural Earth](https://www.naturalearthdata.com), de dominio público.
- `configuracion/localidades_pequenas.json.gz` contiene datos de
  [GeoNames](https://www.geonames.org), bajo licencia
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- `configuracion/regiones_localidades.json` contiene datos de
  [GeoNames](https://www.geonames.org), bajo licencia
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- `configuracion/localidades_europa.json` contiene datos de
  [GeoNames](https://www.geonames.org), bajo licencia
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- El foco térmico de cada impacto sale de las anomalías térmicas de NASA FIRMS, que se
  descargan en el servidor y no se redistribuyen. We acknowledge the use of data and/or
  imagery from NASA's Fire Information for Resource Management System (FIRMS)
  (https://www.earthdata.nasa.gov/firms), part of NASA's Earth Science Data and Information
  System (ESDIS).
- El tráfico aéreo medido sale del archivo diario de [adsb.lol](https://adsb.lol/)
  (© adsb.lol contributors, [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/)), que se
  procesa en el servidor; el bloque `trafico_aereo` de los datos publicados se ofrece con la
  misma licencia (`LICENSE-DATOS`). `configuracion/aeropuertos_trafico.json` sale de
  [OurAirports](https://ourairports.com/data/) (dominio público). Meteorología: «Weather data
  by Open-Meteo.com» (CC BY 4.0) y METAR del Iowa Environmental Mesonet. Código y modelos de
  terceros (traffic, skylight, gods-eye-view): `docs/licencias_terceros.md`.
- El horizonte de radar del motor de deducción se calcula en el servidor con Copernicus DEM
  GLO-90: produced using Copernicus WorldDEM-90 © DLR e.V. 2010-2014 and © Airbus Defence and
  Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights
  reserved. Las teselas no se redistribuyen; el resultado es interno.
