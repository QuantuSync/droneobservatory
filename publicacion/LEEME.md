# Datos publicados

Desde el 8 de octubre de 2026 los datos que publica el European Observatory of Drone Incidents ya
no se guardan en este repositorio. Las versiones anteriores siguen en su historial de git.

**Descargas** (licencia en [`LICENSE-DATOS`](../LICENSE-DATOS)), en la web, con las mismas
direcciones de siempre:

- <https://droneobservatory.eu/datos/incidentes.geojson> y `incidentes.csv`
- <https://droneobservatory.eu/datos/incidentes_sin_ubicacion.json>
- <https://droneobservatory.eu/datos/ucrania.json> y `ucrania.csv`
- <https://droneobservatory.eu/datos/prevision.json>

**Dónde viven.** La recogida horaria los sube al almacén público de Hetzner
(<https://droneobservatory-almacen.nbg1.your-objectstorage.com/publicacion/>), con un manifiesto
(`publicacion/manifiesto.json`: tamaño y huella SHA-256 de cada fichero) y, cada día, una instantánea
fechada que no se sobrescribe (`publicacion/historial/AAAA-MM-DD/`), que sustituye al historial de
git de esta carpeta. La web se reconstruye con ellos cada vez que cambian.

Cómo funciona y cómo volver a publicarlos aquí: [`docs/servidor.md`](../docs/servidor.md),
«Datos publicados», y [`docs/operacion.md`](../docs/operacion.md).
