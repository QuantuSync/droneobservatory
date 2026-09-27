# Observatorio Europeo de Incidentes con Drones (EODI)

*European Observatory of Drone Incidents* · [droneobservatory.eu](https://droneobservatory.eu)

Registra cada incidente con drones en Europa, incluida la guerra entre Ucrania
y Rusia en los dos sentidos, para una web pública de una sola pantalla con el mapa de Europa y para un conjunto de
datos interno más detallado destinado al sistema de detección AEGIS.

Principios: cada dato guarda quién lo dice; la ubicación es un área (punto más
radio); Ucrania va en una capa aparte agregada por ataque; nada se borra; lo
interno nunca llega a lo público; de cada fuente se guarda el hecho, una frase
breve de origen y el enlace, nunca el texto completo.

Fases hechas: cimientos y recogida automática con la primera fuente, el canal
oficial de la Fuerza Aérea de Ucrania, con su histórico desde octubre de 2022.
La web está pendiente.

## Estructura

| Carpeta | Contenido |
| --- | --- |
| `esquema/` | JSON Schema versionados (1.0.0), con marca de visibilidad por campo |
| `configuracion/` | Fuentes con su fiabilidad y vocabulario de modelos de dron |
| `proceso/` | Validaciones, máquina de estados y regla de credibilidad |
| `modelo/` | Extractor: interfaz, implementación nula y caché en disco |
| `almacen/` | Base de datos SQLite con historial, cifrado con age y rama `estado` del repositorio de datos |
| `exportacion/` | `incidentes.geojson` y `ucrania.json` para la web, cada uno con su lista cerrada de campos |
| `recogida/` | Descarga educada, caché, fuente de la Fuerza Aérea, parser de partes, ejecución horaria e histórico |
| `publicacion/` | Ficheros públicos generados: `ucrania.json` e `incidentes.geojson` |
| `web/` | Reservado para la fase siguiente |
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

- `python -m recogida.horaria --correo <correo>`: lo que ejecuta el workflow
  `recogida` cada hora en el minuto 17. Descarga `db.age` de la rama `estado`,
  recoge lo nuevo desde el cursor de cada fuente, regenera `publicacion/` y
  sube la base si ha cambiado.
- `python -m recogida.historico --correo <correo>`: recuperación única del
  histórico, en local y reanudable. Las páginas en bruto quedan en
  `data/cache/`, fuera de git.

Decisiones, valores y cobertura en [`docs/informe_recogida.md`](docs/informe_recogida.md).

## Licencia

- Código: [Apache-2.0](LICENSE).
- Datos publicados (`incidentes.geojson`, `ucrania.json`):
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Detalle en
  [LICENSE-DATOS](LICENSE-DATOS). Las frases de origen citadas pertenecen a sus
  autores y se reproducen como cita breve junto al enlace.
