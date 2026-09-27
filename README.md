# Observatorio Europeo de Incidentes con Drones (EODI)

*European Observatory of Drone Incidents* · [droneobservatory.eu](https://droneobservatory.eu)

Registra cada incidente con drones en Europa, incluida la guerra entre Ucrania
y Rusia en los dos sentidos, para una web pública de una sola pantalla con el mapa de Europa y para un conjunto de
datos interno más detallado destinado al sistema de detección AEGIS.

Principios: cada dato guarda quién lo dice; la ubicación es un área (punto más
radio); Ucrania va en una capa aparte agregada por ataque; nada se borra; lo
interno nunca llega a lo público; de cada fuente se guarda el hecho, una frase
breve de origen y el enlace, nunca el texto completo.

Esta fase contiene solo los cimientos: sin fuentes, sin recogida y sin web.

## Estructura

| Carpeta | Contenido |
| --- | --- |
| `esquema/` | JSON Schema versionados (1.0.0), con marca de visibilidad por campo |
| `configuracion/` | Fuentes con su fiabilidad y vocabulario de modelos de dron |
| `proceso/` | Validaciones, máquina de estados y regla de credibilidad |
| `modelo/` | Extractor: interfaz, implementación nula y caché en disco |
| `almacen/` | Base de datos SQLite con historial y cifrado con age |
| `exportacion/` | `incidentes.geojson` para la web, con lista cerrada de campos |
| `recogida/`, `web/` | Reservados para fases siguientes |
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

`mypy` usa la configuración estricta de `pyproject.toml`. Los tests de cifrado
generan una clave efímera; para cifrar datos reales, la identidad age se pasa
en la variable de entorno `EODI_CLAVE_AGE` y nunca se guarda en el
repositorio.
