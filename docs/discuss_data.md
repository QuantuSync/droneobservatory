# Paquete trimestral para Discuss Data

Desde el 19 de octubre de 2026. Los datos abiertos del observatorio se depositan también en
[Discuss Data](https://discuss-data.net), el repositorio de datos de investigación sobre Europa del
Este de la Universidad de Bremen y la Biblioteca Estatal y Universitaria de Gotinga, que da DOI y
admite versiones. Se deposita **una versión fechada cada tres meses** (enero, abril, julio y
octubre); la subida al repositorio la hace a mano el autor.

Código: [`exportacion/discuss_data.py`](../exportacion/discuss_data.py) (el paquete, funciones
puras) y [`recogida/discuss_data.py`](../recogida/discuss_data.py) (bajar los datos, guardar el
paquete y avisar). Pruebas: [`tests/test_discuss_data.py`](../tests/test_discuss_data.py).

## Qué lleva

Un `.zip` fechado, `eodi-incidentes-AAAA-MM-DD.zip`, con una carpeta del mismo nombre:

| Fichero | Contenido |
| --- | --- |
| `data/incidents.csv` | El CSV de la descarga abierta de la web (`/datos/incidentes.csv`), tal cual |
| `data/incidents.geojson` | El GeoJSON de la descarga abierta, sin el bloque `trafico_aereo` |
| `data/incidents_approximate_location.json` | Los incidentes con lugar aproximado (`/datos/incidentes_sin_ubicacion.json`), sin el bloque `trafico_aereo` |
| `data/air_traffic_odbl.json` | El bloque `trafico_aereo` de cada incidente, aparte, con su licencia ODbL 1.0 y la atribución a adsb.lol |
| `README.md` | En inglés: qué es el observatorio, qué contiene el paquete, fecha de corte, número de incidentes y de países, cada campo, los estados y la presencia del dron, la regla de que un estado solo cambia por una declaración oficial, los enlaces a la web y a los datos abiertos, cómo suscribirse a los avisos (ntfy: `drones-europe` y `drones-<país>`, y la página de avisos), las licencias y la cita |
| `METHODOLOGY.md` | La página de metodología en inglés de la web, convertida a Markdown en el momento de generar el paquete |
| `LICENSE.md` | CC BY 4.0 para la compilación, ODbL 1.0 para el tráfico medido y las atribuciones de terceros |
| `CITATION.cff` | El de este repositorio, con la versión y la fecha del paquete |
| `CHANGELOG.md` | Cambios respecto al paquete anterior: incidentes nuevos, unidos o retirados, cambios de estado y de presencia del dron («First version» en el primero) |

Los ficheros de datos salen de la web en una sola versión de los datos (el `resumen.json` antes y
después tiene que dar la misma hora, como en las versiones citables mensuales). Sin el bloque
`trafico_aereo`, cada JSON es el de la web byte a byte. El `.zip` es determinista: los mismos datos
y la misma fecha dan el mismo fichero.

## Licencias

- **Tráfico aéreo medido**: deriva del archivo de adsb.lol (ODbL 1.0) y es una base de datos
  derivada; por eso sale de los ficheros de incidentes y va en un fichero propio con su licencia.
  Así los ficheros de incidentes del paquete solo llevan datos CC BY 4.0.
- **Puntos geocodificados con OpenStreetMap**: el punto de un incidente puede venir de los
  nomenclátores sacados de OpenStreetMap (`configuracion/lugares_europa.json`,
  `configuracion/instalaciones_europa.json`, `configuracion/carceles_europa.json`). Es un resultado de geocodificación suelto, una
  coordenada por incidente: según la [guía de geocodificación de la
  OSMF](https://osmfoundation.org/wiki/Licence/Community_Guidelines/Geocoding_-_Guideline) es un
  extracto no sustancial que puede ir con otros datos y otra licencia, con la atribución a
  OpenStreetMap, que va en el README y en `LICENSE.md`. Los de GeoNames (CC BY 4.0) y OurAirports
  (dominio público) también se atribuyen.
- **Focos térmicos** (`foco_termico`): reconocimiento a NASA FIRMS, como en la web.

## Cómo se genera

- **Cada trimestre, solo**: la exportación semanal del servidor, al terminar, comprueba si el
  paquete del trimestre en curso ya está en el almacén privado. La primera exportación desde el
  día 1 de enero, abril, julio u octubre lo genera con los datos publicados en ese momento, lo
  guarda en el almacén privado y manda **un único aviso** al canal privado del autor con el nombre,
  las cifras y un enlace firmado de descarga que vale 7 días.
- **Sin fallos hacia fuera**: el paso nunca cambia el código de la exportación ni el de la
  recogida. Si falla (la web no responde, el almacén tampoco), lo anota y se reintenta en la
  exportación siguiente; solo avisa del fallo cuando lleva **2 intentos fallidos** en el
  trimestre, y una sola vez.
- **Un paquete guardado no se sobrescribe ni se borra.** El registro de cambios del siguiente se
  calcula frente al último paquete guardado.
- **A mano**:

  ```
  python -m recogida.discuss_data generar --salida <carpeta> [--anterior <zip>] [--fecha AAAA-MM-DD]
  python -m recogida.discuss_data bajar --destino <carpeta> [--nombre eodi-incidentes-AAAA-MM-DD.zip]
  ```

  `generar` baja los datos publicados de la web y deja el paquete en la carpeta (nunca
  sobrescribe); `bajar` trae del almacén privado el último paquete (o el que se diga), con las
  credenciales del almacén.

Como los datos salen de la web, el paquete siempre lleva lo que publica el código de `main`, nunca
lo de una rama.
