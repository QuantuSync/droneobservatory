# La base de datos, de GitHub al disco del servidor

Informe del cambio de dónde y cómo se guarda la base de datos del European Observatory of Drone
Incidents. Código: [`almacen/sitio.py`](../almacen/sitio.py) y
[`almacen/copias.py`](../almacen/copias.py); operación: [`servidor.md`](servidor.md), apartado
«Base de datos».

## Cómo estaba

La base (SQLite) vivía cifrada con age en la rama `estado` del repositorio privado de datos, un
único commit que la recogida sustituía cada hora con un push forzado. Cada proceso que la
necesitaba clonaba la rama, descifraba la base y la cargaba entera en memoria; los que la
cambiaban la serializaban entera, la comprimían, la cifraban y la volvían a subir. El 4 de
octubre de 2026 rompió la recogida dos veces:

- **12:17 UTC.** La base cifrada pasó de los 100 MB por fichero que admite GitHub y no se pudo
  subir: la recogida no publicó. Se parcheó con compresión xz (#106) y partiéndola en trozos de
  50 MB (#107).
- **15:17 UTC.** La base pasó de 1 GiB, el tope de las bases deserializadas en memoria de
  SQLite, y dejó de admitir escrituras («database or disk is full»). Se parcheó copiándola a una
  base en memoria sin ese tope (#114).

La recogida horaria tenía en memoria, a la vez, la base (más de 1 GB), una copia serializada
entera para saber al final si había cambiado (otro tanto) y, al guardar, otra serialización más
su versión comprimida. De ahí venían buena parte de sus picos de 3,1 a 3,6 GB.

## Cómo queda

| Qué | Dónde |
| --- | --- |
| Código | GitHub, como antes |
| Base de datos | `/home/eodi/base/eodi.sqlite` en el disco del servidor, carpeta con permisos 700 del usuario `eodi`. Se abre desde disco |
| Copias de seguridad | Bucket privado `droneobservatory-base` de Hetzner Object Storage: una por guardado durante 48 horas, una diaria durante 30 días, una semanal durante un año, cifradas con age |
| Copia secundaria | La rama `estado`, mientras siga funcionando; si falla, solo deja un aviso |
| Datos publicados cada hora | Sin cambios |
| Exportación semanal | Sin cambios (lee la base de donde mande) |

**El interruptor.** Un fichero, `/home/eodi/.eodi/base_modo`, con una palabra:

- `github` (o sin fichero): como antes. Es el modo de cualquier equipo sin el fichero: GitHub
  Actions, el equipo local.
- `doble`: manda la rama `estado`, como antes; además, al guardar, copia en el disco y copia de
  seguridad. Un fallo de esa parte solo deja un aviso.
- `disco`: manda el fichero del disco; al guardar, copia de seguridad y copia secundaria en la
  rama.

Se cambia con una orden y vale desde la sesión siguiente, sin reiniciar nada.

**Escritura segura en disco.** Cada sesión copia la base a `base/trabajo/` (con la API de copia de
SQLite, consistente aunque otra sesión la esté sustituyendo) y trabaja sobre esa copia en modo
WAL. Al terminar bien, vuelca la copia a `eodi.sqlite.nuevo`, la sincroniza en disco y la pone en
el sitio de `eodi.sqlite` con un `rename`, que es atómico: en ningún momento falta la base ni hay
una a medio escribir. La versión sustituida queda como `eodi.anterior.sqlite`. Así se mantiene lo
que ya hacía la rama: una recogida que falla a medias no deja nada. Si dos sesiones se solaparan
sin el cerrojo, la segunda en guardar no pisa a la primera: falla. Los ficheros temporales de
SQLite van junto a la copia, no a `/tmp`, que en el servidor está en memoria (tmpfs).

**Saber si ha cambiado, sin leer la base entera.** En disco, la recogida compara el recuento de
cambios de la conexión y la versión del esquema, en vez de serializar la base al principio y al
final. En los modos `github` y `doble` se sigue haciendo como antes.

## Puntos que abren la base

Todos pasan ahora por `almacen/sitio.py` (`abrir_base` y `guardar_base`). Con `--base` (un
`db.age` local) siguen abriendo ese fichero, como antes.

| Proceso | Lanzado por | Uso |
| --- | --- | --- |
| `recogida.horaria` | `eodi-recogida` (minuto 17) | Lee y escribe |
| `recogida.guerra procesar --remoto`, `proceso.extraccion_guerra lote --remoto` | `guerra_reproceso.sh` (a mano) | Lee y escribe |
| `recogida.extractor` (`estimar`, `lote`, `recuperar`, `reconstruir`) y quien usa su `con_base`: `recogida.revision`, `recogida.calidad`, `recogida.barrido_dirigido incorporar` | `revision.sh`, `calidad.sh`, `dirigido.sh` (a mano) | Lee y escribe |
| `recogida.historico` | A mano (histórico de un canal) | Lee y escribe |
| `recogida.historico_gdelt incorporar` | Workflow `historico-gdelt` (a mano, en GitHub) | Lee y escribe |
| `recogida.deduccion calcular` | `eodi-deduccion` (minuto 5) | Solo lee |
| `recogida.catalogo_vivo barrer` | `eodi-catalogo` (05:23) | Solo lee |
| `recogida.satelite` (órdenes con la base) | A mano; el servicio `eodi-satelite` usa los objetivos que deja la recogida | Solo lee |
| `recogida.detalle historico` | `detalle_historico.sh` (a mano) | Solo lee |
| `recogida.exportacion` | `eodi-exportacion` (lunes 03:47) | Solo lee |
| `recogida.busqueda_dirigida pendientes` | A mano | Solo lee |
| `recogida.historico_gdelt tramos` | Workflow `historico-gdelt` | Solo lee (un cursor) |
| `recogida.comparacion`, `recogida.informe_gdelt` | A mano, en local | Solo lee |
| `recogida.localidades_pequenas` | A mano, en local | Solo con `--base` |

No abren la base, e intercambian ficheros en `/home/eodi/datos/` con la recogida horaria: el
tráfico aéreo (`eodi-trafico`), la lectura de la búsqueda dirigida (`eodi-busqueda`), el lector
de canales de guerra (`eodi-guerra`), la recogida de las fuentes de detalle (`eodi-detalle`), la
detección en directo (`eodi-directo`), la captura del seguimiento (`eodi-seguimiento` y su
archivo), la luz nocturna (`eodi-luces`), los focos en vivo (`eodi-focos-vivo`), las imágenes de
satélite (`eodi-satelite`) y el histórico de FIRMS.

Los lectores, en disco, también trabajan sobre una copia propia en `base/trabajo/` que se borra al
cerrar: algunos escriben en la base abierta sin guardarla, y así siguen sin poder tocar la de
verdad.

## Ensayo fuera de producción (4 de octubre de 2026)

En una carpeta aparte del servidor (`/home/eodi/ensayo-base`), como `eodi`, con `systemd-run`, un
tope de 1 GB de memoria, `Nice=19` y E/S en reposo, después del minuto 40 y con el cerrojo de la
recogida libre (mirado sin quedárselo). Nada salía a producción: rama `estado` en un repositorio
git local, publicación en la carpeta del ensayo, copias de seguridad con el prefijo `ensayo/`, sin
extractor y con copias propias de los datos de entrada (`/home/eodi/datos`). Un primer intento en
el equipo local (WSL, las dos versiones a la vez) se paró al quedarse el equipo con poca memoria
libre, antes de que arrancara ninguna recogida.

**La base de partida** fue la misma que la recogida real de las 17:17: la rama `estado` en el
commit `a56b52f`, el mismo antes y después de que esa recogida la descargara (foto con la misma
huella SHA-256 en el servidor y en local).

| | Recogida real 17:17 (base en memoria) | Ensayo 17:40 (base en disco) |
| --- | --- | --- |
| Resultado | Correcta, publicó | Correcta (código 0), publicó en su carpeta |
| Duración | 16 min 55 s | 16 min 23 s (con `Nice=19`) |
| Pico de memoria (systemd, incluye caché) | **5,2 GB** | **1 GB** (con un tope de 1 GB) |
| Memoria residente máxima | — | 1,04 GB |
| Guardar la base | Comparar con la copia inicial, serializar, comprimir, cifrar y subir: 71 s | Volcar a disco y sustituir: 3 s; cifrar, copia de seguridad (3 objetos de 51,9 MB) y copia secundaria: 65 s |

**Igualdad de los datos publicados.** El ensayo y la recogida real no leen exactamente lo mismo,
porque corren con 23 minutos de diferencia. Lo publicado por el ensayo difiere del real solo en:

- la hora de actualización de cada registro (17:40 frente a 17:17);
- lo nuevo entre las dos horas: un parte más del Ministerio de Defensa ruso (el ataque
  EODI-UA-2026-1029, que enlaza un impacto) y cuatro franjas más de GDELT;
- lo que avanzan los pasos con tope de tiempo: el histórico de guerra (150 s; 5 292 mensajes en el
  ensayo frente a 5 962) y las mediciones de tráfico aéreo (150 s; 36 incidentes evaluados frente
  a 46), y una llamada al extractor de guerra que el ensayo no hace.

`incidentes_sin_ubicacion.json` salió idéntico. Para comprobar la igualdad sin esas diferencias de
entrada, la base que dejó la recogida real de las 17:17 en la rama (`5b67d00`) se abrió **desde
disco** con el código nuevo y se publicó con la hora de esa recogida: los tres ficheros salieron
**idénticos byte a byte** a los que publicó la recogida real (commit `182804d`):

| Fichero | SHA-256 (real y desde disco) |
| --- | --- |
| `incidentes.geojson` | `276c2954…285604` |
| `incidentes_sin_ubicacion.json` | `682ed50d…2d2228` |
| `ucrania.json` | `8e50fde2…5197bf` |

Esa publicación desde disco tardó 38 s con 0,73 GB de memoria residente.

**Copia y restauración del ensayo.** La copia `ensayo/horaria/2026-10-04T175604Z.db.age` se
restauró en otra carpeta (25 s, 0,2 GB de memoria): 1 109 729 280 bytes, integridad correcta y la
misma huella de contenido que la base del ensayo (`976db535…4cc1b49`).
