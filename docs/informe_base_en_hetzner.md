# La base de datos, de GitHub al disco del servidor

Informe del cambio de dónde y cómo se guarda la base de datos del European Observatory of Drone
Incidents. En uso desde el 5 de octubre de 2026 a las 01:42 UTC (modo `disco`). Código: [`almacen/sitio.py`](../almacen/sitio.py) y
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

Después del ensayo, antes de fusionar, se repitió el ensayo del paso c2 de
[`fusiones.md`](fusiones.md) con el código ya rebasado sobre `main` (20:40 a 20:52 UTC, base de la
rama en `a53a9b9`, modo disco, `--ensayo`, 1 GB): código 0, «ficheros publicados con cambios: 3»,
11 min 35 s, 1 GB de pico y la copia de trabajo borrada al terminar.

## Lo ocurrido en cada fase (horas UTC)

**Espera.** La sesión de corrección de errores de datos terminó el 4 de octubre: su informe final
con la comprobación en producción se fusionó a las 19:43 (#123), no le quedaba ningún PR abierto
ni ningún trabajo en el servidor, y la lectura del histórico del canal de Mykoláiv, que empezó con
su #121, acabó a las 19:50; las recogidas de las 19:17 y las 20:17 terminaron bien, publicaron y
procesaron todo lo leído (`pendientes=False`). Mientras se esperaba, la recogida de las 16:17 falló
por una ficha con fecha futura (no por el tamaño); lo arregló esa sesión (#118) y no se intervino.

**Fase B: lo nuevo al lado de lo viejo.**

- 20:55: fusión del código (#122, `42adfa7`), sin interruptor en el servidor. La recogida de las
  21:17, la primera con el código nuevo en modo `github`, terminó bien en 13 min 32 s (5,0 GB) y
  publicó; los incidentes de la web se quedaron en 508.
- 21:40: interruptor en `doble`.

| Recogida | Resultado | Duración | Pico (systemd) | Disco frente a rama (huella del contenido) | Incidentes en la web |
| --- | --- | --- | --- | --- | ---: |
| 22:17 | Correcta, publicó | 12 min 59 s | 5,0 GB | Iguales (`522eba59…`) | 508 |
| 23:17 | Correcta, publicó | 12 min 57 s | 5,1 GB | Iguales (`1c5fed07…`) | 508 |
| 00:17 | Correcta, publicó (5 incidentes del extractor) | 16 min 49 s | 5,6 GB | Iguales (`cdb1384f…`) | 510 |
| 01:17 | Correcta, publicó | 14 min 24 s | 5,1 GB | Iguales (`4c6d080f…`) | 510 |

La copia en disco tardó 1 s y la de seguridad 2 s en cada una; la de las 22:17 creó también la
primera diaria y la primera semanal, y la de las 00:17, las del nuevo día y la nueva semana.

**Fase C: el cambio.** A las 01:42:13, con la recogida de las 01:17 terminada a las 01:31, el
cerrojo libre y la rama sin cambios desde la comparación, el interruptor pasó a `disco`.

| Recogida | Resultado | Duración | Pico (systemd, con caché) | Memoria anónima máxima | Copia secundaria frente a disco | Incidentes en la web |
| --- | --- | --- | --- | --- | --- | ---: |
| 02:17 | Correcta, publicó | 13 min 15 s | 3,7 GB | — | Iguales (`1d8673d5…`) | 511 |
| 03:17 | Correcta, publicó | 12 min 46 s | 3,3 GB | 0,85 GB (desde las 03:22) | Iguales (`0c0c6008…`) | 511 |
| 04:17 | Correcta, publicó | 12 min 59 s | 3,3 GB | 0,87 GB | Iguales (`1bac0bc8…`) | 511 |
| 05:17 | Correcta, publicó | 12 min 53 s | 3,3 GB | 0,84 GB | Iguales (`0b075e9a…`) | 511 |

Guardar la base en disco tarda 1 o 2 s; cifrarla y subir la copia de seguridad, unos 55 s, y la
copia secundaria a la rama, unos 10 s más. El pico que da systemd incluye la caché de los
ficheros que se escriben (la copia de trabajo, la base nueva y su versión comprimida, de más de
1 GB cada una), que el sistema libera cuando necesita memoria; la memoria propia del proceso
(anónima, medida cada 10 s en el grupo de la unidad) no pasa de 0,9 GB. Con la base en memoria,
la recogida llegaba a 5,0 a 5,6 GB.

Los lectores también bajan: el motor de deducción, de 2,3 GB a 1,6 GB de pico (01:05 frente a
02:05, y más rápido: 67 s frente a 77 s); el catálogo vivo, de 1,9 GB (4 de octubre) a 1,2 GB
(5 de octubre). La exportación semanal de las 03:47 leyó la base del disco, pero no publicó la
versión 2026.10.05 por un fallo anterior a este cambio (apartado de pendientes).

## Prueba de restauración

El 5 de octubre a las 05:42, la última copia del almacén (`base/horaria/2026-10-05T052842Z.db.age`,
55,4 MB cifrada) se restauró en una carpeta aparte con `servidor/base.sh copias restaurar
--huella`: comprobación de su SHA-256, descifrado, integridad de SQLite correcta, 1 190 711 296
bytes (el mismo tamaño que la base en uso) y la misma huella de contenido que
`/home/eodi/base/eodi.sqlite`: `0b075e9a5bf7f63f0b01f90278404038ae2341c64687ed7874f9ca206be88f3e`.
Tardó 29 s con 0,2 GB de memoria.

## Cómo volver atrás

Desde el modo `disco`, con una orden, justo después de una recogida terminada y fuera de los
minutos 12 a 40:

```
echo github | sudo -u eodi tee /home/eodi/.eodi/base_modo
```

La recogida siguiente vuelve a descargar la base de la rama `estado`, que está al día mientras la
copia secundaria funcione (en el diario de cada recogida: «copia secundaria subida a la rama
estado»). Si no lo estuviera, antes de cambiar el interruptor:
`sudo -u eodi bash /home/eodi/droneobservatory/servidor/base.sh a-github`. Si la base del disco
se hubiera estropeado: restaurar la última copia buena (apartado anterior) o usar
`/home/eodi/base/eodi.anterior.sqlite`, subirla con `a-github` y cambiar el interruptor. El código
de antes no hace falta: en el modo `github` hace exactamente lo de antes.

## Lo lanzado en el servidor

Todo con `systemd-run` y retirado al terminar, salvo lo que debe quedar:

- Carpetas `/home/eodi/base` y `/home/eodi/base/trabajo` (quedan) y el interruptor
  `/home/eodi/.eodi/base_modo`, hoy `disco` (queda).
- Bucket privado `droneobservatory-base` (queda), con las copias de `base/`; las tres del ensayo
  (`ensayo/`) se borraron.
- `eodi-ensayo-base`, `eodi-ensayo-republicar`, `eodi-ensayo-restaurar`, `eodi-ensayo-c2`,
  `eodi-ensayo-exportacion` (con `--sin-subir`): ensayos con 1 GB, en `/home/eodi/ensayo-base`,
  borrada después (11 GB).
- `eodi-base-comparar-22` a `-05` y `eodi-restauracion-real`: comprobaciones de solo lectura con
  1 GB.
- `eodi-medir-0317`, `eodi-medir-0417`, `eodi-medir-0517` (y un primer intento fallido,
  `eodi-medir-recogida`): lectura de la memoria del grupo de la recogida cada 10 s. Sus
  temporizadores se pararon y el script y sus ficheros se borraron.

No queda nada de esto en marcha: solo las unidades de siempre.

## Pendientes, con su arreglo

- **La exportación semanal no validaba desde el 4 de octubre**: resuelto el 5 de octubre de 2026
  (#125). El cierre de pista ya tiene regla de origen y la versión 2026.10.05 se generó a mano a
  las 08:40 UTC con la base del disco; detalle en
  [`informe_exportacion_aegis.md`](informe_exportacion_aegis.md), apartado 9.
- **Retirar la base de GitHub** cuando lleve una semana funcionando en disco (desde el 12 de
  octubre de 2026). Planteado, sin hacer: dejar de subir la copia secundaria (quitar la llamada a
  `remoto.subir` de `sitio.guardar_base` en modo disco), cambiar el workflow de emergencia
  `recogida.yml` para que restaure la última copia del almacén en vez de leer la rama (o
  retirarlo), y el workflow `historico-gdelt` para que su `incorporar` trabaje sobre la base del
  servidor; después, borrar la rama `estado` con el acuerdo de quien lleva el proyecto, porque es
  irreversible.
- **Llevar al almacén de Hetzner los datos publicados cada hora.** Planteado, sin hacer: hoy son
  commits «Actualiza los datos publicados» en `main` (unos 38 MB por hora; la web los toma al
  desplegarse). Arreglo propuesto: subirlos al almacén público como `estado.json` (con
  `recogida/almacen_publico.py`), que la web los lea de allí y dejar de hacer el commit; cambia la
  web y su CSP, por eso queda para un encargo propio.
- **Llevar la exportación semanal al almacén.** Planteado, sin hacer: hoy va cifrada a `main` del
  repositorio de datos con su etiqueta, y AEGIS la importa de allí. Arreglo propuesto: un bucket
  privado o un prefijo del de copias, con el mismo cifrado y el manifiesto, y cambiar el
  importador de AEGIS a la vez.
- **Pico de memoria con caché.** systemd sigue dando unos 3,3 GB de pico por la caché de los
  ficheros grandes que se escriben al final. No es memoria que falte, pero si se quisiera bajar
  la cifra: escribir la base nueva y su versión comprimida con `posix_fadvise(DONTNEED)` o poner a
  la unidad `MemoryHigh` para que el sistema recupere antes esa caché.
- **`instalar.sh` crea la carpeta de la base** para un servidor nuevo; en el actual se creó a mano
  el 4 de octubre con los mismos permisos. Se aplica en la próxima `reconstruir.sh`, sin nada más
  que hacer.
