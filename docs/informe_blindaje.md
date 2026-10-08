# Blindaje del European Observatory of Drone Incidents

Trabajo del 7 de octubre de 2026 en adelante: que lo que hay aguante, se recupere solo y quede
ordenado, sin añadir funciones. Fase por fase: qué había, qué se ha cambiado, cómo se ha comprobado,
tiempos, costes y pendientes con su arreglo. La operación diaria está en
[`operacion.md`](operacion.md).

## Fase 1. El servidor, firme

### Inventario

Servidor `eodi-recogida` (Hetzner CX33: 4 núcleos, 7,7 GB, disco de 75 GB útiles, Ubuntu 26.04,
`nbg1`). Todas las unidades del observatorio corren como `eodi` (sin privilegios, sin entrada por
SSH), salvo `eodi-reinicio`, que corre como root porque es quien puede reiniciar. Todas tienen tope
de memoria.

| Unidad | Qué hace | Cuándo | Tope de memoria | Arranca sola |
| --- | --- | --- | ---: | --- |
| `eodi-recogida` | Recogida horaria, base, publicación, estado | Minuto 17 | 5 GB | Temporizador |
| `eodi-exportacion` | Exportación semanal cifrada | Lunes 03:47 | 4 GB | Temporizador |
| `eodi-deduccion` | Motor de deducción | Minuto 5 | 4 GB | Temporizador |
| `eodi-catalogo` | Barrido del catálogo vivo | 05:23 | 3 GB | Temporizador |
| `eodi-trafico` | Tráfico aéreo de adsb.lol | Minuto 40 | 3 GB | Temporizador |
| `eodi-detalle` | Fuentes oficiales de detalle | Cada 3 h, minuto 52 | 1,5 GB | Temporizador |
| `eodi-busqueda` | Búsqueda dirigida de noticias | Minuto 2 | 1 GB | Temporizador |
| `eodi-guerra` | Canales de la capa de guerra | Minuto 50 | 1 GB | Temporizador |
| `eodi-satelite` | Imágenes de satélite | 06:43 y 18:43 | 1 GB | Temporizador |
| `eodi-luces` | Luz nocturna | Minuto 41 | 1 GB | Temporizador |
| `eodi-focos-vivo` | Focos de calor de 24 h | Minuto 42 | 1 GB | Temporizador |
| `eodi-rutas` | Rutas de los drones | Minuto 8 | 1 GB | Temporizador |
| `eodi-seguimiento-archivo` | Compresión y copia del archivo del seguimiento | Minuto 3 | 1 GB | Temporizador |
| `eodi-directo` | Detección en directo de cierres | Siempre | 1,5 GB | Sí (`multi-user`) |
| `eodi-seguimiento` | Captura de NEPTUN y de la Fuerza Aérea | Siempre | 150 MB | Sí (`multi-user`) |
| `eodi-vigilancia` (nueva) | salud.json para la vigilancia externa | Cada 5 min | 300 MB | Temporizador |
| `eodi-reinicio` (nueva) | Reinicio tras una actualización, cuando no corta nada | Cada 5 min, 07–16 UTC | 300 MB | Temporizador |

Limpieza: las dos unidades sueltas en fallo (`run-p108193-i110743.service`, de un trabajo del 4 de
octubre, y `eodi-rutaslegibles-comprobar.service`) con `systemctl reset-failed`; las carpetas de
ensayo de sesiones anteriores (`/home/eodi/ensayo-tipo`, `/home/eodi/ensayo-prevision`, 2,2 GB cada
una, con sus scripts), `/var/tmp/eodi-prev` (1,1 GB), `/var/tmp/directo` y los restos de `/tmp`
(un `repo.tgz` de 68 MB, scripts y carpetas temporales de sesiones). El disco pasó del 32 % al
25 %. No se tocó `base/`, `datos/` ni `.eodi/`. Se dejaron los clones de los trabajos de una vez
(`calidad/`, `dirigido/`, `revision/`), que sus scripts reutilizan, y sus informes.

### Acceso

Había: SSH solo con clave, sin contraseña y sin root, solo el usuario `operador`; cortafuegos de
Hetzner con solo SSH; fail2ban (5 intentos en 10 min, veto de 1 h).

Cambios (`servidor/endurecer.sh`):

- **Cortafuegos del propio servidor** con nftables, tabla propia `inet eodi`: entrada cerrada salvo
  SSH, conexiones ya abiertas, el ICMP imprescindible y DHCP; reenvío cerrado. Se aplicó con una
  vuelta atrás programada a los 6 minutos (`systemd-run --on-active=6min`, que quitaba la tabla y
  devolvía la configuración de SSH), se comprobó con una conexión nueva y salida a NEPTUN por IPv4 e
  IPv6, y entonces se anuló la vuelta atrás. Tras el reinicio controlado la tabla se cargó sola.
- **SSH**: además, `MaxAuthTries 3`, `LoginGraceTime 30` y sin reenvíos (X11, TCP, agente,
  túneles), que no se usaban.
- **fail2ban** con vetos crecientes (cada reincidencia dobla el veto, hasta una semana).
- Un informe de un trabajo antiguo que era de root pasó a `eodi`. Los ficheros de credenciales del
  servidor ya eran 600 y de `eodi`, dentro de una carpeta 700.

### Mantenimiento

Había: actualizaciones de seguridad automáticas **con reinicio automático a las 04:45 UTC**, hora
sincronizada (chrony), diario con tope (200 MB, 90 días), logrotate.

El reinicio a hora fija podía cortar un ataque en curso (04:45 UTC son las 07:45 en Kiev; lo que
NEPTUN emite con el servidor apagado se pierde) o un trabajo largo. Ahora las actualizaciones no
reinician solas, y `eodi-reinicio` (cada 5 minutos de 07:00 a 15:55 UTC) reinicia si una
actualización lo pide y, a la vez: no es entre los minutos 12 y 40, no hay ninguna unidad del
observatorio con temporizador en marcha, y no hay un ataque en curso según el último estado del flujo
de NEPTUN (ningún misil ni balístico activo y como mucho 20 drones; si la captura no recibe, no se
sabe y no se reinicia). Los 20 drones salen del archivo del 4 al 7 de octubre: los drones activos no
bajan de 4 en ninguna hora (hay seguimiento de drones casi siempre) y el máximo horario va de 7 a 31.

El aviso de disco va en la vigilancia (al 75 %, antes del 80 %).

### Arranque limpio

Reinicio controlado el 7 de octubre de 2026 a las 15:00:51 UTC, con la misma regla de
`eodi-reinicio`: a las 14:43 no se pudo (21 drones activos según NEPTUN) y después esperó a que
terminaran `eodi-detalle` y `eodi-guerra`.

| Qué | Hora | Desde la orden |
| --- | --- | ---: |
| Orden de reinicio | 15:00:50,9 | 0 s |
| Sistema arrancado (núcleo 1,5 s, initrd 2,5 s, servicios 6,5 s) | 15:00:57 | 6 s |
| Cortafuegos cargado | 15:01:02 | 11 s |
| Temporizadores activos (todos) | 15:01:06 | 15 s |
| fail2ban | 15:01:06 | 15 s |
| `eodi-seguimiento` y `eodi-directo` en marcha | 15:01:07 | 16 s |
| SSH | 15:01:07 | 16 s |
| Primer ciclo de la detección en directo | 15:02 | ~1 min |
| Primer salud.json tras el arranque | 15:05:30 | 4,7 min |

**NEPTUN**: la captura anotó un hueco de 28 s (de la última recepción, 15:00:39,7, a la primera tras
volver, 15:01:07,7). El servicio estuvo parado unos 16 s; los 12 s anteriores son la espera normal
entre latidos. Al reconectar, NEPTUN mandó el estado entero (snapshot, 15:01:07,7): las amenazas
que seguían activas se recuperan; los cambios de esos segundos no.

### Avisos

Había: el workflow `vigia-recogida`, una vez por hora, abría incidencias a partir de `estado.json`
(recogida sin una correcta en 2 horas, exportación, detección en directo, captura del seguimiento con
hasta una hora de retraso). No miraba el disco ni las copias, no fallaba (el dueño solo se enteraba
si miraba las incidencias o le llegaba la notificación de la incidencia) y, de hecho, GitHub lo
lanzaba con mucho retraso (la última ejecución programada antes del cambio fue a las 09:13 en lugar
de a las 09:41).

Ahora:

- El servidor sube cada 5 minutos `salud.json` al almacén público (`recogida/vigilancia.py`,
  unidad `eodi-vigilancia`), sin contenido: última publicación y última recogida (con sus avisos),
  captura del seguimiento, copias, disco, `problemas` y `avisos`.
- `vigia-recogida` pasa cada 10 minutos, lee además `salud.json` (si no llega o tiene más de 20
  minutos, el servidor no da señales), abre la incidencia de cada problema y **falla** cuando
  aparece uno y después una vez por hora mientras siga: GitHub manda al dueño el correo «Run
  failed: vigia-recogida». Una vez al día reactiva su propia programación por la API: sin los
  commits de datos, el repositorio puede pasar semanas sin actividad y GitHub desactiva las
  programaciones a los 60 días.

**Alarma de mentira**, 7 de octubre a las 14:07 UTC: `gh workflow run vigia-recogida.yml -f
prueba=true`. Abrió la incidencia #151 «Alarma de prueba de la vigilancia» y el trabajo falló
(ejecución 37634142426): al dueño le llegan dos correos de GitHub, el de la incidencia nueva y el de
«Run failed». La incidencia se cerró a mano.

### Código 2 y titulares retenidos

En las últimas 30 horas hubo dos recogidas con código 2 (6 de octubre, 15:17 y 19:17), las dos por
«oficiales: tope de 240 s agotado; fuentes sin leer: 2». La barrera de titulares no da código 2:
deja el incidente sin publicar con un aviso en el diario. Ahora mismo retiene dos:

- **EODI-2026-00486** (GB, 6 de octubre, notificado): titular «Posible ataque de posibles drones
  obliga a retirar bombarderos estadounidenses de la base de Fairford». Sus dos fuentes son noticias
  de GDELT cuya frase guardada no nombra Fairford ni el Reino Unido.
- **EODI-2026-00487** (NO, 6 de octubre, notificado): «Drones ilegales cerca del aeropuerto de
  Stavanger incautan dos aparatos». Su fuente no nombra Stavanger ni Noruega.

Los dos titulares, además, están mal formados. La barrera funciona como debe; el arreglo es de
contenido (pendiente: revisarlos y, si la noticia lo sostiene, añadir la cita o el titular
justificado en `configuracion/incidentes_revisados.json`).

En la vigilancia los dos casos salen como **avisos**, no como fallo: en `salud.json` y en el resumen
de cada ejecución del vigía, sin los identificadores (el fichero es público y esos incidentes no
están publicados); los identificadores, en el diario de `eodi-vigilancia`.

### Fusión y comprobación

PR #150, fusionado el 7 de octubre a las 14:07 UTC (main 47f8406). Ensayo antes de fusionar
(`servidor/ensayo.sh`, nuevo: recogida completa sobre copias propias de la base y los datos, con la
exportación semanal entera): código 0 en 19 min, 3 GB de pico (el tope del trabajo; la mayor parte,
caché de la copia de la base). Instalado con `instalar.sh`: ninguna unidad existente cambió; las dos
nuevas, activadas.

Un fallo encontrado al instalar: la unidad `eodi-reinicio` corre como root sin sesión y
`configuracion.sh` necesita `HOME`; se le puso `Environment=HOME=/root` (en el PR de la fase 2).

**El programador de GitHub no basta.** Tras la fusión, el vigía programado cada 10 minutos no se
ejecutó ninguna vez en tres horas y media; antes, la programación horaria salía 5 o 6 veces al
día de 24 (8 ejecuciones programadas entre el 5 y el 7 de octubre). GitHub retrasa o se salta las
ejecuciones programadas de este repositorio, y con eso el aviso podía tardar horas. Por eso se añadió
un disparador fuera de GitHub y fuera del servidor (PR #157): una tarea programada de Vercel cada 10
minutos llama a `api/vigia.ts`, que lee `salud.json` y `directo.json` del almacén y, si hay un
problema o el servidor no da señales, lanza `vigia-recogida` por la API de GitHub. Solo puede
llamarla la tarea programada (variable `CRON_SECRET` del proyecto, creada el 7 de octubre; una
llamada sin ella responde 401). Para lanzar el workflow necesita un token de GitHub que solo pueda
lanzar workflows de este repositorio (`EODI_VIGIA_TOKEN`), que creó el dueño el 7 de octubre.
Prueba a las 22:00, parando solo el temporizador de `salud.json`: la función vio el servidor
«callado» a las 22:20:50 y lanzó el workflow, pero GitHub respondió 403 («Resource not accessible
by personal access token»): al token le falta el permiso *Actions: Read and write* sobre este
repositorio (pendiente 1). Mientras tanto la función deja cada 10 minutos el diagnóstico en su
registro y el aviso depende de la programación de GitHub. El temporizador se volvió a encender a
las 22:22.

Recogidas tras la fusión de la fase 1: 14:17 y 15:17, correctas y publicadas.

## Fase 2. El archivo del seguimiento, a salvo

### Copia cada hora

Había: el trabajo del minuto 3 subía al bucket privado `droneobservatory-archivo` cada día ya
terminado; si el servidor se perdía, se perdía hasta un día de NEPTUN y de la Fuerza Aérea.

Ahora (`recogida/seguimiento_archivo.py`, PR #152) sube cada hora las horas ya comprimidas,
también las del día en curso, y el índice al terminar el día. Lo que se puede perder es la hora en
curso más los 3 minutos hasta la pasada: como mucho, 63 minutos. `eodi-seguimiento` no se tocó ni se
paró (solo se reinicia si cambia su propio código). La primera pasada, a las 15:53, subió las 30
horas del día en curso.

### Rutas en la copia

La carpeta `datos/rutas/` (7 MB: noches estructuradas, publicables, comprobación, ataques) va al
mismo bucket como un tar.gz reproducible: `rutas/ultima.tar.gz` cada vez que cambia y la primera de
cada día en `rutas/diaria/AAAA-MM-DD.tar.gz`, que no se sobrescribe.

### Segunda copia en otra ubicación

Bucket privado `droneobservatory-replica` en Helsinki (`hel1`), otra ubicación de Hetzner, con las
mismas credenciales del proyecto (`almacen/replica.py`, unidad `eodi-replica` en el minuto 47):

- las copias cifradas de la base, tal cual, con la retención de siempre aplicada por su cuenta (nunca
  borra porque falte en el origen: si el bucket de Núremberg se vaciara, Helsinki sigue entero);
- el archivo del seguimiento y las rutas, cifrados con la clave pública age (la unidad no necesita la
  identidad), con la huella del original para comprobarla al restaurar;
- la exportación semanal (fase 3), tal cual.

Sin credenciales los dos buckets nuevos responden 403. Primera pasada: 54 copias de la base y 211
objetos del archivo en 4,7 minutos, con 130 MB de memoria.

**Coste: 0 €.** El precio base del almacenamiento de objetos de Hetzner (6,49 € al mes sin IVA) es
por cuenta, no por bucket ni por ubicación, e incluye 1 TB de almacenamiento y 1 TB de salida; el
tráfico entre ubicaciones de `eu-central` (Núremberg y Helsinki lo son) no se cobra. Ocupación total
tras el cambio: unos 32 GB (teselas 24,6 GB, copias de la base unos 3,5 GB en cada ubicación,
archivo y exportaciones unos cientos de MB).

### Prueba de recuperación

El día 6 de octubre de 2026 entero bajado de la copia con `restaurar-dia` (nuevo): 49 ficheros (24
horas de NEPTUN, 24 de la Fuerza Aérea y el índice), 4,4 MB, en 17 s, idénticos byte a byte a los
del servidor (huellas SHA-256 comparadas una a una). Desde Helsinki, una hora de NEPTUN descifrada
con la identidad age dio la misma huella que el fichero del servidor. `restaurar-todo` baja todo el
archivo y las rutas (lo usa el simulacro de la fase 6: 213 objetos en 13 s).

Fusión: PR #152 (main da82f33), con ensayo previo de recogida y exportación (código 0). Recogidas
siguientes: 16:17 y 17:17, correctas y publicadas.

## Fase 3. Los datos publicados y la exportación, a Hetzner

Había: cada recogida hacía un commit «Actualiza los datos publicados» en `main` con los cuatro
ficheros públicos (unos 42 MB; `ucrania.json` solo, 35 MB), que reconstruía la web; la exportación
semanal iba al repositorio de datos con una etiqueta por versión.

### Diseño

- **Publicación.** La recogida escribe los ficheros en `datos/publicacion/` del servidor (fuera del
  clon) y, según el interruptor `publicacion_modo`, los sube al almacén público, hace el commit o
  las dos cosas (`recogida/publicacion.py`). En el almacén, `publicacion/<fichero>` va con gzip
  (`ucrania.json` pasa de 35 MB a 1,5 MB en tránsito; quien lo pide recibe el JSON tal cual), con su
  huella y `Cache-Control: public, max-age=60`, y `publicacion/manifiesto.json` se sube al final.
- **La web** lee de donde diga `configuracion/publicacion_web.json`. Con `almacen`, el build baja el
  manifiesto y cada fichero, comprueba cada huella (así nunca mezcla dos recogidas) y, si el almacén
  no responde o algo no cuadra, reintenta dos veces y falla: Vercel deja la versión anterior. Las
  direcciones públicas `/datos/…` no cambian porque las sigue sirviendo la web desde su propio
  dominio (las genera el build), sin reglas de reescritura ni problemas de origen cruzado. La bajada
  tarda 1,5 s.
- **Reconstrucción**: con `almacen`, tras publicar algo nuevo, el servidor llama al gancho de
  despliegue de Vercel (`vercel_gancho`, solo en el servidor). El paso de «build ignorado» construye
  siempre un nuevo despliegue del mismo commit. Unas 24 construcciones al día, como antes con los
  commits.
- **Historial**: la primera publicación de cada día deja una instantánea fechada en
  `publicacion/historial/AAAA-MM-DD/` que no se sobrescribe; el historial de git anterior se queda
  donde está.
- **Integración continua**: los trabajos de siempre usan un conjunto fijo de datos de ejemplo
  (`tests/fixtures/publicacion`, 2,4 MB, generado con `generar.py` de los datos reales: un incidente
  de cada ocho, alguno de cada estado, 60 días de Ucrania para tener más de 50 corredores). El
  trabajo nuevo `datos-publicados` baja los datos de verdad de donde los lee la web y pasa la
  barrera de titulares y la validación de la web sobre ellos.
- **Exportación semanal** al bucket privado `droneobservatory-exportaciones` (`nbg1`), con el
  mismo interruptor: `exportaciones/AAAA.MM.DD/` con los mismos ficheros (cifrados con age y el
  manifiesto en claro), el manifiesto al final, nunca se sobrescribe, cada objeto con su huella.
  Entra también en la segunda copia de Helsinki.

**Dónde queda la exportación y cómo se lee.** En
`s3://droneobservatory-exportaciones/exportaciones/AAAA.MM.DD/` (Hetzner Object Storage, `nbg1`,
punto `https://nbg1.your-objectstorage.com`), privada: hacen falta las credenciales S3 del
proyecto (`%USERPROFILE%\.eodi\almacen.env`). Desde un clon de este repositorio:

```
python -m almacen.exportaciones listar
python -m almacen.exportaciones espejo --repositorio C:\dev\eodi-exportaciones
```

`espejo` deja cada versión nueva en un repositorio git local con las mismas carpetas y las mismas
etiquetas `eodi-AAAA.MM.DD` que el repositorio de datos, comprobada fichero a fichero con su
manifiesto. El importador de siempre sigue igual, apuntado a esa carpeta (`--repositorio
C:\dev\eodi-exportaciones`), y se descifra con la misma identidad age (la clave de lectura de
siempre). La clave de despliegue de solo lectura del repositorio de datos deja de hacer falta.

### Cambio con red

| Paso | Cuándo | Comprobación |
| --- | --- | --- |
| Código con el interruptor (PR #153, #154, #155), en `github` | 7 oct, 16:41 | Ensayos de recogida y exportación, código 0 |
| Primera subida a mano y comparación | 16:43 | Almacén idéntico byte a byte a `main` |
| Interruptor en `doble` | 16:43 | — |
| Seis recogidas en `doble` | 17:17 a 22:17 | Las seis: «el almacén es idéntico a main», código 0 |
| La web lee del almacén (PR #158) | 22:43 | Producción entera (abajo) |
| Gancho de despliegue creado y probado | 22:48 | Reconstrucción completa del mismo commit |
| Interruptor en `almacen` | 22:50 | Recogidas siguientes (abajo) |

**Producción con la web leyendo del almacén** (7 de octubre, 22:45–23:00, navegador real a 360×800,
390×844, 412×915 y escritorio, capturas revisadas): el build dice «datos publicados del almacén,
generados el 2026-10-07T22:32:48Z»; 443 incidentes, los mismos que antes; mapa con teselas,
cifras, fichas y capas sin errores de página; cerrar una ficha no mueve el mapa en ningún tamaño;
sin ejecutar código, las páginas de texto (`/incidentes`, `/paises/pl`, `/ucrania`, `/prevision`,
`/metodologia`, `/en/incidents`, una ficha) responden 200; `/EODI-2025-00002` y su versión en
inglés redirigen al incidente que lo absorbió; un identificador inventado da 404; `sitemap.xml` y
las ocho descargas de «Metodología y datos abiertos» responden con su tipo. Primera carga, medida
tres veces: de 5,7 a 6,9 s en los cuatro tamaños, como antes (5,6–5,8 s); una medida suelta de
10,2 s fue una carga en frío. El código de la web no cambió y los datos son los mismos bytes.

**Recogidas en `almacen`**: 23:17 y 00:17, correctas: sin commit en GitHub, datos al almacén,
reconstrucción pedida a Vercel y la web con los datos nuevos unos 2 minutos después de publicarse.

**Vuelta a `doble` probada en real**: un cambio del interruptor tras la recogida de las 00:17; la de
la 01:17 volvió a hacer el commit en `main`, idéntico byte a byte al almacén; vuelta a `almacen` a
las 01:34. Después, `publicacion/` salió de `main` (PR #160) dejando `publicacion/LEEME.md` con
dónde están ahora los datos; la web siguió igual (443 incidentes, descargas y redirecciones bien).

**La base.** La copia secundaria en la rama `estado` sigue hasta el 12 de octubre. El temporizador
de un solo uso `eodi-base-solo-disco` está programado para el martes 13 de octubre a las 10:00 UTC
(apartado «Base de datos» de `servidor.md`); su ensayo, el 7 de octubre a las 16:48, dio «se puede
pasar a solo disco» sin cambiar nada. El primer ensayo, a las 16:42, falló porque exigía que la
última copia estuviera ya en Helsinki y la réplica pasa en el minuto 47: se corrigió (PR #154) para
pedir en Helsinki una copia de menos de 3 horas.

**La exportación del lunes 12 de octubre por el camino nuevo**, ensayada entera el 7 de octubre a
las 17:34: `exportacion.sh` completo con la base real, hacia un prefijo de ensayo del bucket, en
130 s y 2,9 GB de pico (código 0); espejo git local e importación con el importador de siempre en 2
s, misma huella del manifiesto (10bd83a8…), descifrada con la clave age de siempre; los 59 objetos
de ensayo se borraron. El lunes, con el interruptor en `almacen`, irá solo al bucket privado.

**Un fallo tras retirar la carpeta, y su arreglo.** El 8 de octubre a las 02:32 el gancho de la
recogida pidió reconstruir la web y el paso de «build ignorado» lo omitió: entre medias había
entrado en `main` el PR de documentación (#163), que no despliega, y la regla «mismo commit que el
despliegue anterior» ya no se cumplía. La web se quedó una hora con los datos de las 01:17. Lo vio
la comprobación de producción, no la vigilancia. Arreglo (PR #164): con los datos en el almacén,
producción se construye siempre; y el disparador de Vercel avisa si los datos de la web van más de
100 minutos por detrás de la última publicación. Comprobado: a las 02:52 la web estaba con los
datos de las 02:17 y la recogida de las 03:17 llegó a la web por el gancho, sin omitirse.

**Fusiones**: PR #153 (código, en `github`), #154 (comprobaciones de copias), #155 (espejo y
ensayo de la exportación), #158 (la web lee del almacén), #160 (`publicacion/` fuera), cada uno con
su ensayo de recogida y exportación cuando tocaba la recogida o los datos.

## Fase 4. La rama principal, protegida

### Protección

Regla de repositorio «main protegida» (*Settings* → *Rules*), activa desde el 8 de octubre de 2026
a las 02:00 UTC:

- nada entra sin PR (sin aprobaciones obligatorias: el dueño fusiona como siempre, con `gh pr merge
  <n> --rebase`, que deja en `main` el commit único de la rama con su autor anónimo);
- comprobaciones obligatorias en verde, con la rama al día con `main`: `tests`, `web`,
  `datos-publicados` y `ficheros-del-pr`;
- sin empujes forzados ni borrado; historial lineal.

La regla no la salta nadie, tampoco el dueño ni los administradores, salvo una clave de despliegue:
así se puede volver a publicar en el repositorio desde el servidor (modo `doble`) dando de alta su
clave, sin quitar la protección (`operacion.md`). Hoy no hay ninguna clave con escritura en el
repositorio público. Se probó: un push directo a `main` y uno forzado, rechazados («push declined
due to repository rule violations»). Primero se puso con la protección clásica de ramas y se
cambió a la regla porque aquella no deja pasar a ninguna clave de despliegue y rompía la vuelta a
`doble`.

### Ficheros borrados o revertidos sin querer

Comprobación nueva `ficheros-del-pr` (en `tests.yml`, solo en los PR, obligatoria): falla si el PR,
tal como está, deshace en `main` cambios que su rama no hace (el caso de los PR #84 y #87: un squash
sobre una rama desfasada borró un informe y revertía datos) o si borra ficheros de `docs/`,
`esquema/`, `configuracion/` o `tests/fixtures/` sin una línea «Borra a propósito: <ruta>» en la
descripción. Probada con el PR #162, que borraba `docs/informe_reloj.md` sin declararlo: la
comprobación falló y la fusión quedó bloqueada; el PR se cerró sin fusionar.

### Credenciales del servidor contra GitHub

- Repositorio público: la clave de despliegue con escritura del servidor, **retirada** (y su
  fichero `despliegue_web` del servidor): ya no escribe ahí. `reconstruir.sh` ya no la da de alta.
- Repositorio de datos: la clave del servidor con escritura sigue hasta el 13 de octubre (copia
  secundaria de la base); después sobra (decisiones, 2f). La de la recogida de emergencia, que no se
  usaba desde el 27 de septiembre, **retirada**.
- Secretos del repositorio público: los ocho, **retirados** con los workflows que los usaban.

### Comprobaciones automáticas

| Comprobación | Obligatoria | Tarda | Fallos ajenos encontrados | Arreglo |
| --- | --- | --- | --- | --- |
| `tests` (ruff, mypy, pytest, exportación de ensayo) | Sí | 3,5–4 min | Ninguno en los 24 fallos revisados | — |
| `web` (auditoría, lint, tipos, pruebas, build, navegador) | Sí | 3–5,5 min | Prueba de previsión que acababa con una petición de teselas en vuelo (3 ejecuciones) | `unrouteAll` al terminar cada prueba |
| `datos-publicados` (nueva) | Sí | 1 min | — | — |
| `ficheros-del-pr` (nueva) | Sí | 10 s | — | — |
| `salud-recogida` | No (solo informa) | 10 s–2 min | — | — |
| Todas | — | — | GitHub sin máquina 15 min (11 ejecuciones del 5 de octubre; otra el 7 de octubre) | Un push nuevo cancela la ejecución anterior del mismo evento: menos cola. Si aun así pasa, se cancela la atascada (`gh run cancel`) y se relanza |

De los 24 fallos de los 4 días anteriores, 12 eran fallos de verdad (lint, tipos, pruebas, esquema)
y 12 ajenos: los dos tipos de arriba. Con los arreglos, un fallo de `tests` o `web` es un fallo.

## Fase 5. Credenciales y dependencias

### Inventario (sin valores)

**En el servidor** (`/home/eodi/.eodi/`, carpeta 700, cada fichero 600 y de `eodi`):

| Fichero | Para qué | Permisos que da | ¿Sobra? |
| --- | --- | --- | --- |
| `clave_age.txt` | Identidad age: cifra y descifra la base, sus copias y la exportación | Leer todo lo cifrado | No |
| `almacen.env` | Credencial S3 de Hetzner Object Storage del proyecto | Leer y escribir todos los buckets del proyecto (teselas, estado y datos públicos, copias, archivo, exportaciones, réplica) | No; se puede partir (abajo) |
| `extractor.env` | Clave del extractor de textos y clave de NASA FIRMS | Gasto del extractor dentro de sus límites; consultas a FIRMS | No |
| `despliegue_datos` | Clave de despliegue con escritura en `droneobservatory-datos` | Escribir en ese repositorio | Hasta el 13 de octubre (copia secundaria de la base) |
| `despliegue_web` | Clave de despliegue con escritura en `droneobservatory` | Escribir en el repositorio público | Desde el modo `almacen`: retirada (fase 4) |
| `vercel_gancho` | Dirección del gancho de despliegue de Vercel | Pedir una reconstrucción de la web de `main` | No |
| `known_hosts` | Clave de host de GitHub | Ninguno | No |

**En GitHub** (secretos del repositorio público): `EODI_CLAVE_AGE`, `EODI_DATOS_CLAVE_DESPLIEGUE`,
`EODI_EXTRACTOR_CLAVE`, `EODI_EXTRACTOR_URL`, `EODI_EXTRACTOR_URL_LOTES`, `EODI_EXTRACTOR_MODELO`,
`EODI_EXTRACTOR_CABECERAS` y `EODI_FIRMS_MAP_KEY`, que solo usaban los workflows de recogida de
emergencia y del histórico de GDELT. Claves de despliegue: en el repositorio público, «servidor
eodi-recogida» (escritura); en el de datos, «servidor eodi-recogida» (escritura), «droneobservatory:
rama estado» (escritura, la del workflow de emergencia, último uso el 27 de septiembre) y
«aegis-lectura» (solo lectura).

**En Vercel**: `CRON_SECRET` (nueva, para la tarea programada de la vigilancia; recreada como
«sensitive» y solo en producción tras el aviso «Needs Attention» de Vercel, que la marcaba como
legible) y `EODI_VIGIA_TOKEN` (la creó el dueño: «sensitive», solo en producción). El gancho de
despliegue «recogida» del proyecto (su dirección, solo en el servidor).

**En el equipo del dueño** (`%USERPROFILE%\.eodi\`): `hcloud_token.txt` (API de Hetzner Cloud del
proyecto, lectura y escritura), `servidor_ssh` (entrada al servidor como `operador`, con sudo),
`servidor_known_hosts`, `clave_age.txt`, `almacen.env`, `extractor.env`, `firms_map_key.txt`,
`vercel_token.txt` (API de Vercel de la cuenta entera), `vercel_bypass.txt` (saltar la protección de
las vistas previas), `aegis_lectura_ssh` y `github_known_hosts` (la lectura de la exportación desde
el repositorio de datos), `cloudflare_token.txt` y `r2_estado.env` (ya no se usan: la cuenta de
Cloudflare está suspendida y las credenciales de R2 responden 401). La sesión de `gh` de la cuenta
tiene los permisos `repo`, `workflow`, `read:org` y `gist`.

### Búsqueda en historiales, registros, publicados y capturas

- **Credenciales**: ninguna real en el historial completo de los dos repositorios (todas las ramas
  y etiquetas): ni claves privadas, ni identidades age, ni tokens de GitHub, Vercel, Cloudflare o
  Hetzner, ni la clave de FIRMS, ni secretos del almacén, ni ganchos de despliegue, ni ficheros
  `.env`. Lo que aparece son valores de prueba evidentes (identidades age falsas de las pruebas, la
  clave de ejemplo de la documentación de S3) y el nombre de la variable del token de Hetzner en la
  documentación, sin valor.
- **Datos personales**: el correo personal del dueño figura como autor en 11 commits del repositorio
  público (del 27 de septiembre al 7 de octubre de 2026; el último, la fusión del PR #146, hecha desde
  la web de GitHub) y en 2 del de datos, y como valor en una versión antigua de
  `.github/workflows/recogida.yml` (commit ded08ca, ya corregido). Para que no vuelva a pasar, el
  dueño tiene que activar en GitHub la opción de correo privado (decisiones preparadas). Borrarlo del
  historial exige reescribirlo (como el nombre de la decisión 1).
- **Registros del servidor**: el diario no recoge ningún valor de credencial (los scripts pasan las
  credenciales por el entorno, nunca por la línea de órdenes, y solo escriben recuentos).
- **Ficheros publicados**: los números de teléfono que aparecen son de instituciones (oficinas de
  distritos ucranianos citadas de sus canales oficiales, organismos de investigación) y salen de las
  fuentes públicas.
- **Capturas de `docs/capturas/`** (353 imágenes): revisadas las 15 con nombres más sospechosos
  (almacén, credenciales, estados, variantes de prueba, menús); todas enseñan solo la web pública:
  ninguna consola, terminal, panel de cuenta, correo ni dato personal.

### Permisos reducidos sin el dueño

- Retirados los workflows `recogida.yml` (recogida de emergencia) e `historico-gdelt.yml`: los dos
  trabajaban sobre la base de la rama `estado`, que ya no manda, y el primero publicaba en `main`, que
  ahora está protegida. Con ellos sobran y se borraron sus ocho secretos del repositorio público
  (entre ellos la identidad age y la clave de despliegue de la rama `estado`) y la clave de
  despliegue «droneobservatory: rama estado» del repositorio de datos.
- Retirada la clave de despliegue con escritura del servidor en el repositorio público y su fichero
  `despliegue_web`: con la publicación en el almacén, el servidor ya no escribe en GitHub.
- Los buckets privados no son públicos (comprobado sin credenciales: 403 en objeto y en listado).

### Lo que necesita al dueño (paso a paso)

Están en «Decisiones que te tocan», al final, con las pantallas exactas y lo que hay que cambiar
después en el servidor.

### Dependencias

`pip-audit` sobre `requirements.txt`, `requirements-navegador.txt` y `requirements-desarrollo.txt`:
ninguna vulnerabilidad conocida. `npm audit` de la web: ninguna. Todas las dependencias directas de
Python estaban fijadas con `==`; en la web todas salvo `web-vitals` (`^6.2.2`), que se fijó a
`6.2.2` (la del fichero de bloqueo, sin cambiar lo instalado).

### Cabeceras de seguridad de la web

Ya estaban completas y se comprobaron en producción: `Content-Security-Policy` sin código en línea,
con el almacén como único origen externo de imágenes y conexiones y `frame-ancestors 'none'`;
`Strict-Transport-Security` de un año con subdominios y precarga; `X-Content-Type-Options:
nosniff`; `X-Frame-Options: DENY`; `Referrer-Policy` y `Permissions-Policy` restrictivas. El mapa y
las teselas cargan con ellas (comprobado en los cuatro tamaños). No se cambió nada.

## Fase 6. Simulacro de desastre

`servidor/simulacro.sh` (nuevo, PR #156) hace todo de una vez desde el equipo del dueño: crea un
servidor temporal `eodi-simulacro` (mismo tipo, misma clave SSH y mismo cortafuegos, otra IP), lo
endurece e instala con `endurecer.sh` e `instalar.sh` sin dar de alta claves de despliegue, sin las
variables del extractor y sin activar ningún temporizador ni servicio (no captura el seguimiento en
paralelo con el de verdad ni publica nada), lleva la clave age y las credenciales del almacén,
restaura la última copia cifrada de la base y el archivo entero, ejecuta una recogida completa en
ensayo con la exportación semanal, borra el servidor y comprueba que no queda nada suyo.

Segundo intento, 7 de octubre de 2026, 17:14 a 17:31 UTC: **17 minutos**.

| Paso | Duración |
| --- | ---: |
| Servidor creado | 17 s |
| SSH disponible | 19 s |
| `endurecer.sh` | 71 s |
| `instalar.sh` | 80 s |
| Credenciales e interruptor | 9 s |
| Base restaurada (67 MB cifrados, 1,5 GB en disco, huella comprobada) | 27 s |
| Archivo del seguimiento restaurado (213 objetos y las rutas) | 13 s |
| Recogida completa en ensayo con la exportación semanal (código 0) | 13 min 9 s |
| Servidor borrado | 14 s |

Lo que no estaba escrito o falló, y su arreglo:

1. **SSH por socket.** El primer intento se paró en `endurecer.sh`: en una Ubuntu 26.04 recién
   creada `sshd` arranca por socket y `systemctl reload ssh` falla porque el servicio no está en
   marcha. En el servidor de verdad no se veía (el servicio ya estaba activo). Ahora solo se recarga
   si está en marcha.
2. **Restaurar el archivo del seguimiento** no tenía orden: solo había la de un fichero. Ahora
   `restaurar-dia` y `restaurar-todo`.
3. **Pasos tras `reconstruir.sh`** que no estaban escritos: poner los interruptores (`base_modo`,
   `publicacion_modo`, `base_secundaria`), dejar el gancho de Vercel, volver a activar las copias de
   Hetzner y restaurar el archivo. Están en `operacion.md`, «Si hay que levantar un servidor nuevo».
4. **El listado de Hetzner tarda unos segundos** en dejar de ver el servidor borrado; el script lo
   espera antes de comprobar que no queda nada.

Comprobado en Hetzner tras el simulacro: solo queda `eodi-recogida` con su IPv4 y su IPv6; ningún
servidor, IP, volumen ni imagen del simulacro. **Coste**: dos servidores CX33 de menos de una hora
(0,0136 € la hora cada uno, más la IPv4 de esas horas): unos 0,03 € sin IVA.

**Prueba de restauración semanal** (nueva): `eodi-prueba-restauracion`, los martes a las 10:55 UTC,
restaura la última copia horaria que está en los dos sitios, comprueba su huella, su integridad y que
la de Helsinki es idéntica, y avisa por la vigilancia si falla o si pasan 8 días sin una correcta.
Primera ejecución el 7 de octubre: correcta en 25 s.

## Fase 7. La web bajo carga

### Qué se sirve desde dónde

- **Desde la caché de Vercel**: la portada, las fichas, las páginas de texto, `sitemap.xml` y los
  datos `/datos/…` (ficheros estáticos de cada despliegue; los datos llevan `max-age=300`).
- **Funciones**: solo la de los identificadores unidos y los ataques (`api/borde.ts`), con
  `s-maxage=3600`: la caché de Vercel guarda cada respuesta hasta el despliegue siguiente; y la de la
  vigilancia, cada 10 minutos.
- **Desde el almacén de Hetzner, sin pasar por Vercel**: las teselas del mapa (peticiones Range a
  `europa-z14.pmtiles`), `estado.json`, `directo.json` y las capas de satélite, luz, focos y GPS.
  Desde la fase 3, el almacén **no** recibe las visitas a los datos: solo los lee el build.

### Medidas (7 de octubre de 2026)

Prueba breve desde un solo equipo, 20 peticiones en paralelo durante 20 s por dirección:

| Dirección | Peticiones | Por segundo | p50 | p95 | Caché |
| --- | ---: | ---: | ---: | ---: | --- |
| Portada | 8 698 | 435 | 42 ms | 58 ms | HIT (1 MISS) |

A las ~9 000 peticiones desde la misma IP, la protección automática de Vercel la puso en modo
«desafío» (403 con `X-Vercel-Mitigated: challenge`) para todo lo demás: se paró la prueba. Desde el
servidor, con otra IP, la web respondía bien en ese momento, y la IP de prueba volvió a la normalidad
sola en unos minutos. Es lo que haría Vercel con un ataque desde pocas direcciones; una avalancha de
lectores reales viene de muchas IP y la sirve la caché.

Teselas, 40 peticiones Range en paralelo durante 10 s contra el almacén: 342 por segundo, p50 111
ms, p95 144 ms, todas 206. Una primera visita pide de 37 a 57 trozos de teselas (medido con un
navegador real en los cuatro tamaños).

### El primer cuello de botella

Hetzner limita cada bucket a **750 peticiones por segundo**. Con 37 a 57 peticiones de teselas por
visita nueva, el bucket público empezaría a responder «SlowDown» (503) con unas 13 a 20 visitas
nuevas por segundo, y el mapa de fondo cargaría a trozos; los datos y las páginas, servidos por
Vercel, seguirían bien. El tráfico de salida no es el problema: 1 TB incluido es del orden de
200 000 visitas al mes, y cada TB más cuesta 1 € sin IVA.

### Cachés

Las de Vercel ya hacen que una avalancha no llegue al almacén con los datos ni dispare funciones de
más (las redirecciones se guardan una hora en la caché; los datos son estáticos del despliegue). No se
cambió nada. Para las teselas el arreglo queda pendiente (abajo).

### Consumo del plan de Vercel

Cargos de los últimos 30 días (7 de septiembre a 7 de octubre de 2026, API de facturación), todos
dentro de lo incluido en Pro, 0 USD de uso: transferencia rápida 5,5 GB,
peticiones a la CDN 74 217, invocaciones de funciones 4 363, minutos de CPU de construcción
2 212 y unos 25 despliegues de producción al día (el plan admite 6 000).
Con la reconstrucción por el gancho tras cada publicación siguen siendo unas 25 al día (antes las
lanzaba el commit de datos), y la tarea programada añade 144 invocaciones al día. Margen holgado: no
hace falta contratar nada.

## Decisiones que te tocan (preparadas, sin ejecutar)

### 1. El nombre de una persona en el historial público de git

**Dónde está.** El nombre del prefecto de Iasi que se guardó por error como autor de una atribución
(EODI-2026-00015) entró en `publicacion/incidentes.geojson` con el commit 9c5d4f0 (PR #20, 30 de
septiembre de 2026) y salió con f8b04de (4 de octubre de 2026). Entre los dos, 74 commits «Actualiza
los datos publicados» tienen ese fichero con el nombre. Además sigue **en la rama principal de
hoy**, no solo en el historial, en tres ficheros que explican y comprueban su retirada:
`docs/informe_marcador_atribuido.md` (líneas 113–114 y 316), `tests/test_atribucion.py` (líneas 52,
54, 436 y 452) y `web/e2e/atribuido.spec.ts` (líneas 146 y 157), que entraron con los commits
08fd239, 265fb6e y a687b8a.

**Qué habría que hacer.**

1. Sin reescribir nada, con un PR normal: quitar el nombre de los tres ficheros de hoy (en el
   informe, «el propio prefecto de Iasi»; en las pruebas, un nombre inventado con el mismo papel).
   Esto se puede hacer ya y no rompe nada.
2. Para el historial: con `main` congelada (sin fusiones) y la protección de la rama quitada un
   momento, en un clon nuevo `git filter-repo --replace-text <fichero con el nombre y su
   sustituto>` sobre todas las ramas y etiquetas; comprobar con `git log --all -S <apellido>` que no
   queda; `git push --force --all` y `--tags`; volver a poner la protección. Después, pedir a GitHub
   (formulario de soporte de datos sensibles) que borre las vistas en caché de los commits antiguos
   y de los PR, porque GitHub los sigue sirviendo por su identificador aunque ya no estén en ninguna
   rama.

**Qué se rompe.** Cambian los identificadores de todos los commits desde el 30 de septiembre (unos
270 de 301): los enlaces a commits en informes, incidencias y PR dejan de llevar a su commit; los
PR antiguos quedan apuntando a commits que ya no están en la rama; cualquier clon existente
(los del equipo del dueño, el del servidor, el de Vercel) hay que volver a hacerlo o forzarlo
(`git fetch` + `reset --hard`); el servidor lo hace solo en la recogida siguiente. El repositorio no
tiene bifurcaciones ni seguidores, así que no hay copias de terceros que avisar.

**Cuánto se tarda.** Unas 2 horas con las comprobaciones: 30 minutos de preparación y reescritura,
la comprobación, el push, rehacer los clones y vigilar las dos recogidas siguientes.

**Con `publicacion/` fuera de la rama principal**, el paso 2 no cambia: la carpeta sigue en todos
los commits antiguos. Lo que cambia es que ya no entra nada nuevo por ahí. El paso 1 sí hace falta
igual, porque el nombre está también en documentos y pruebas.

### 2. Credenciales que necesitan entrar en una cuenta

**a. Token para el disparador de la vigilancia (lo más urgente).** Creado por el dueño el 7 de
octubre y guardado en Vercel, pero GitHub lo rechaza (403): hay que editarlo y dejar *Actions* en
*Read and write* sobre `droneobservatory` (los pasos 1 a 3 de abajo, con *Edit* en vez de
*Generate*; editar no cambia el valor y no hay que tocar Vercel). Sin eso, el aviso depende del
programador de GitHub, que se salta casi todas las ejecuciones.
1. GitHub → foto de perfil → *Settings* → *Developer settings* → *Personal access tokens* →
   *Fine-grained tokens* → *Generate new token*.
2. Nombre «vigilancia EODI»; caducidad, la más larga que deje (un año); *Resource owner*:
   QuantuSync; *Repository access*: *Only select repositories* → `droneobservatory`.
3. *Permissions* → *Repository permissions* → *Actions*: **Read and write**. Nada más (los metadatos
   de solo lectura los añade GitHub solo).
4. *Generate token* y copiarlo.
5. Vercel → proyecto `droneobservatory` → *Settings* → *Environment Variables* → *Add*: nombre
   `EODI_VIGIA_TOKEN`, valor el token, entornos *Production*; *Save*. Y *Deployments* → el último →
   *Redeploy* (las variables valen desde el despliegue siguiente).
6. En el servidor no hay que cambiar nada. Para probarlo: `gh workflow run vigia-recogida.yml -f
   prueba=true` sigue valiendo, y la función se puede ver en Vercel → *Logs* (filtrar por
   `/api/vigia`).

**b. Correo privado en GitHub.** GitHub → *Settings* → *Emails* → marcar *Keep my email addresses
private* y *Block command line pushes that expose my email*. Después `gh pr merge --squash
--author-email` vuelve a funcionar y nada nuevo saldrá con el correo personal.

**c. Credenciales del almacén separadas por uso.** Hoy una sola credencial S3 del proyecto puede
leer y escribir todos los buckets, y es la misma en el servidor y en el equipo. Hetzner no hace
credenciales de solo lectura ni de un bucket, pero deja limitar cada bucket a unas credenciales con
su política. Paso a paso:
1. Hetzner Console → proyecto EODI → *Security* → *S3 credentials* → *Generate credentials* dos
   veces: «servidor» y «lectura-exportacion». Guardar cada par (el secreto solo se ve una vez).
2. En el equipo: `%USERPROFILE%\.eodi\almacen.env` con el par «servidor»; `%USERPROFILE%\.eodi\
   exportacion_lectura.env` con el otro.
3. En el servidor, el nuevo par: `bash servidor/preparar_almacen.sh` (lleva `almacen.env` al
   servidor) o a mano como `eodi` en `/home/eodi/.eodi/almacen.env` (600). Comprobar la recogida
   siguiente y `eodi-vigilancia`.
4. Pedirme (o a la siguiente sesión) la política de cada bucket: `droneobservatory-exportaciones`
   solo para «servidor» (escritura) y «lectura-exportacion» (`s3:GetObject` y `s3:ListBucket`); los
   demás privados, solo para «servidor». Se aplica con el identificador del proyecto (la cifra de la
   dirección `console.hetzner.com/projects/<id>/…`).
5. Borrar en la consola la credencial antigua.

**d. Token de Vercel.** El de `%USERPROFILE%\.eodi\vercel_token.txt` vale para toda la cuenta.
Vercel → *Account Settings* → *Tokens* → *Create*: ámbito solo el equipo del proyecto, caducidad de
un año; sustituir el fichero y borrar el antiguo. Nada que cambiar en el servidor (no lo usa).

**e. Token de Hetzner Cloud.** Da lectura y escritura del proyecto y solo vive en el equipo. Si se
quiere rotar: Hetzner Console → EODI → *Security* → *API tokens* → *Generate API token* (*Read &
Write*), sustituir `hcloud_token.txt` y borrar el antiguo. Nada que cambiar en el servidor.

**f. Clave de despliegue del repositorio de datos (13 de octubre en adelante).** Cuando el paso a
solo disco haya salido bien (`base_solo_disco.json` correcto y la recogida siguiente con «base solo
en disco»), el servidor ya no escribe en el repositorio de datos: `gh repo deploy-key list --repo
QuantuSync/droneobservatory-datos` y `gh repo deploy-key delete <id> --repo
QuantuSync/droneobservatory-datos` de «servidor eodi-recogida», y en el servidor `sudo -u eodi rm
/home/eodi/.eodi/despliegue_datos*`. Lo dejo escrito porque yo no estaré para hacerlo ese día.

**g. Ficheros que sobran en el equipo.** `cloudflare_token.txt` y `r2_estado.env` (ya no responden)
y, si la importación pasa al espejo del almacén, `aegis_lectura_ssh` con su clave de despliegue de
solo lectura en el repositorio de datos.

### 3. Gasto recurrente

Ninguno nuevo. La segunda copia en Helsinki no cuesta más (el precio base del almacenamiento es por
cuenta). Si un día se quiere quitar el cuello de botella de las teselas (fase 7) con un segundo bucket
de teselas, tampoco: ocupa 24,6 GB del terabyte incluido.

## Costes

| Qué | Coste |
| --- | --- |
| Segunda copia en Helsinki (bucket `droneobservatory-replica`) | 0 €: el precio base del almacenamiento de objetos es por cuenta y todo cabe en el terabyte incluido |
| Bucket privado de la exportación (`droneobservatory-exportaciones`) | 0 €, por lo mismo |
| Datos publicados en el almacén público | 0 €: unos 3 MB comprimidos más una instantánea diaria de unos 3 MB (cerca de 1 GB al año); la web los lee una vez por construcción |
| Simulacros de desastre (dos servidores CX33 de menos de una hora) | Unos 0,03 € sin IVA, una vez |
| Tarea programada y función de Vercel | 0 €: dentro del plan Pro (144 invocaciones al día) |
| **Gasto recurrente nuevo** | **Ninguno**. Total de Hetzner sin cambios: 17,18 € al mes sin IVA (20,78 € con IVA) |

## Pendientes, con su arreglo

1. **El token de la vigilancia no tiene permiso para lanzar el workflow** (403). Arreglo: lo hace el
   dueño, decisiones 2a; después, repetir la prueba (parar `eodi-vigilancia.timer` 25 minutos y ver
   llegar el correo «Run failed» y la incidencia).
2. **Las teselas topan con el límite del bucket** (750 peticiones por segundo; 37 a 57 por visita
   nueva): con una avalancha de más de 13 a 20 visitas nuevas por segundo, el mapa de fondo cargaría
   a trozos. Arreglo, por orden de sencillez: (a) dividir las teselas en dos buckets (por ejemplo,
   el de Helsinki para la mitad de los clientes) sin coste, cambiando `configuracion/almacen_publico.json`
   y la política de seguridad de contenido; (b) servir las teselas a través de Vercel con caché, si
   su CDN guarda bien las respuestas parciales (hay que probarlo en una vista previa antes); medir la
   primera carga antes y después.
3. **Los dos incidentes retenidos por la barrera de titulares** (EODI-2026-00486 y 00487). Arreglo:
   revisar las noticias y, si lo sostienen, añadir la cita o el titular justificado en
   `configuracion/incidentes_revisados.json` con un PR y su ensayo.
4. **Clave de despliegue del repositorio de datos tras el 13 de octubre** (decisiones, 2f).
5. **Credenciales del almacén por uso** (decisiones, 2c): hoy una sola credencial puede con todos los
   buckets.
6. **El correo personal en el historial** y **el nombre del prefecto** (decisiones, 1 y 2b).
7. **El aviso de la vigilancia depende de dos piezas externas** (Vercel para lanzar, GitHub para
   avisar). Si un día faltan las dos, el aviso no llega: el estado sigue en `salud.json` y en el
   diario del servidor (`operacion.md`, «Cómo ver si todo va bien»).
