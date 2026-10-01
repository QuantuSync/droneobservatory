# Servidor de recogida

La recogida de cada hora la lanza un servidor propio en Hetzner Cloud, no GitHub Actions.
Todo lo que hay en él sale de los scripts de [`servidor/`](../servidor), que no llevan
ningún secreto: con ellos y con los secretos que se guardan en local se reconstruye desde
cero con una sola orden.

## Qué hay en el servidor

| | |
| --- | --- |
| Servidor | `eodi-recogida`, tipo CX23, Núremberg (`nbg1`), Ubuntu 26.04 LTS |
| Cortafuegos de Hetzner | `eodi-recogida`: solo entra SSH (TCP 22); lo demás, cerrado |
| Usuario `eodi` | Ejecuta el observatorio. Sin privilegios, sin contraseña y sin entrada por SSH |
| Usuario `operador` | Administra: entra por SSH con clave y usa `sudo` |
| SSH | Solo con clave, sin contraseña y sin root |
| Además | fail2ban, actualizaciones de seguridad automáticas con reinicio a las 04:45 si hace falta, zona horaria UTC, hora sincronizada, diario de systemd con tope de tamaño y de antigüedad |

Dos particularidades:

- **Python 3.13.** Ubuntu 26.04 trae Python 3.14; el 3.13 del proyecto se instala del
  archivo de paquetes `ppa:deadsnakes/ppa`, incluido en las actualizaciones automáticas.
- **IPv4 por delante de IPv6** (`/etc/gai.conf`). Desde este centro de datos la conexión
  por IPv6 con Telegram falla casi siempre, y Python agota el tiempo límite de cada
  petición antes de probar con IPv4: sin esta preferencia, la lectura de un canal no cabe
  en su tope de tiempo.

En `/home/eodi`:

- `droneobservatory/`: clon del repositorio en `main` y su entorno virtual (`.venv`) con
  Python 3.13 y `requirements.txt`.
- `.eodi/`, con permisos 600 y propiedad de `eodi`:
  - `clave_age.txt`: la identidad age de la base;
  - `extractor.env`: las variables del extractor, una por línea, y la clave de NASA FIRMS
    (`EODI_FIRMS_MAP_KEY`);
  - `despliegue_datos`: clave de despliegue con escritura solo en `droneobservatory-datos`
    (la usan la recogida, para la rama `estado`, y la exportación semanal, para `main`);
  - `despliegue_web`: clave de despliegue con escritura solo en `droneobservatory`, para
    publicar los ficheros de la web;
  - `known_hosts`: la clave de host publicada por GitHub;
  - `exportacion.json`: la última exportación semanal correcta (versión, hora y huella).
- `datos/detalle/`, con permisos 700 y propiedad de `eodi`: lo que descargan las fuentes
  oficiales de detalle (apartado «Fuentes oficiales de detalle»).
- `datos/guerra/`, con permisos 700 y propiedad de `eodi`: lo que guarda el lector de canales
  de la capa de guerra (apartado «Canales de la capa de guerra con lugar»).
- `datos/firms/`, con permisos 700 y propiedad de `eodi`: los CSV diarios de anomalías
  térmicas de NASA FIRMS, comprimidos, uno por producto y día
  (`<producto>/<año>/<AAAA-MM-DD>.csv.gz`), y `control.json` con la última descarga
  correcta y el estado del histórico. Fuera del repositorio y de la base, que se sube cifrada
  cada hora y no debe crecer con los focos agrícolas. Se pueden volver a descargar.
- `datos/trafico/`, con permisos 700 y propiedad de `eodi`: lo que sale del procesado de cada
  día del archivo de adsb.lol (`dias/<año>/<AAAA-MM-DD>/`: movimientos, aeronaves militares,
  interferencia GNSS por celda y hora y por día, trazas filtradas y `resumen.json`), los METAR
  de cada día (`metar/`), la referencia de EUROCONTROL (`referencia/`), los incidentes que
  necesita el procesado (`zonas.json`, lo escribe la recogida horaria) y `control.json` (último
  día correcto y días que adsb.lol no publicó). Unos 16 MB por día procesado; todo se puede
  volver a calcular desde el archivo de adsb.lol.
- `datos/meteo/`, con permisos 700 y propiedad de `eodi`: la caché de Open-Meteo
  (`openmeteo/<AAAA-MM-DD>/`) y de los METAR del IEM que no estaban en el día procesado.

Las dos claves de despliegue se generan en el servidor y la privada no sale de él. En
GitHub figuran en cada repositorio con el título «servidor eodi-recogida».

## La recogida horaria

`eodi-recogida.timer` lanza `eodi-recogida.service` en el minuto 17 de cada hora (UTC). Si
el servidor estaba apagado a su hora, la ejecución pendiente se lanza al arrancar. La
unidad ejecuta [`servidor/recogida.sh`](../servidor/recogida.sh) como `eodi`, con un tope
de 45 minutos, y el script:

1. toma un cerrojo (`flock`): si hay otra recogida en marcha, no se lanza;
2. deja el clon en la última versión de `main` y reinstala las dependencias solo si ha
   cambiado `requirements.txt`;
3. ejecuta `python -m recogida.horaria`, que descarga la base de la rama `estado`, recoge
   lo nuevo y vuelve a subirla;
   Al final, si han pasado 3 horas o más desde la última descarga correcta, descarga de
   NASA FIRMS los dos últimos días de los productos NRT (VIIRS de Suomi NPP, NOAA-20 y
   NOAA-21 y MODIS) y cruza los focos con los impactos ([`recogida/firms.py`](../recogida/firms.py),
   [`proceso/focos_termicos.py`](../proceso/focos_termicos.py)). Un fallo de FIRMS no cambia
   el resultado de la recogida: queda en el diario («firms no se lee», sin la clave) y en
   `estado.json`, y la siguiente ejecución vuelve a intentarlo;
4. publica en `main` `publicacion/ucrania.json`, `publicacion/incidentes.geojson` y
   `publicacion/incidentes_sin_ubicacion.json` si han cambiado, con autor QuantuSync y la
   dirección anónima. También cuando la recogida
   termina con avisos (código 2); nunca cuando falla con otro código.

Sale con el código de la recogida: con avisos, la unidad queda como fallida en systemd,
igual que el workflow quedaba en rojo, y la hora siguiente se lanza igual.

El script se ejecuta desde el clon, así que un cambio suyo en `main` vale desde la
recogida siguiente (bash lo lee entero al empezar: en realidad, desde la otra). Las unidades de systemd y el endurecimiento, en cambio, se instalan:
si cambian `instalar.sh`, `endurecer.sh` o `configuracion.sh`, hay que volver a ejecutar
`reconstruir.sh`.

## Exportación semanal

`eodi-exportacion.timer` lanza `eodi-exportacion.service` los lunes a las 03:47 UTC (si el
servidor estaba apagado a esa hora, al arrancar). La unidad ejecuta
[`servidor/exportacion.sh`](../servidor/exportacion.sh) como `eodi`, con un tope de 90
minutos, y el script:

1. espera, como mucho una hora, al cerrojo de la recogida horaria (el mismo `flock`): si hay
   una recogida en marcha, la exportación empieza cuando termina; mientras exporta, la
   recogida de esa hora no se lanza (tarda menos de un minuto);
2. ejecuta `python -m recogida.exportacion` con el código del clon tal como lo dejó la última
   recogida, sin actualizarlo: descarga la base de la rama `estado`, genera la versión del
   día (`AAAA.MM.DD`), la valida contra sus esquemas, la cifra con la clave pública de la
   base y la sube a `main` del repositorio de datos como `exportaciones/AAAA.MM.DD/`, con la
   etiqueta `eodi-AAAA.MM.DD`, con la clave de despliegue `despliegue_datos`;
3. si termina bien, deja la versión, la hora y la huella del manifiesto en
   `/home/eodi/.eodi/exportacion.json`, de donde `estado.json` saca `ultima_exportacion`
   en la recogida siguiente.

No escribe en la base, ni en el clon, ni en la rama `estado`, y tiene su propia unidad: si
falla, la recogida horaria sigue igual. Una versión que no valida no se publica, y una que ya
existe (carpeta o etiqueta) no se sobrescribe: se avisa y se sale sin error. Contenido y
formato en [`exportacion/semanal.py`](../exportacion/semanal.py) y
[`docs/informe_exportacion_aegis.md`](informe_exportacion_aegis.md).

Si pasan más de 8 días sin una exportación correcta, el workflow `vigia-recogida` abre la
incidencia «La exportación semanal no se genera» y la cierra cuando vuelve a haberla.

Lanzarla a mano (por ejemplo, tras un fallo), como `operador`:

```
sudo systemctl start eodi-exportacion.service
journalctl -u eodi-exportacion.service -n 40
systemctl list-timers eodi-exportacion.timer
```

## Tráfico aéreo de adsb.lol y condiciones medidas

Informe: [`informe_trafico_aereo.md`](informe_trafico_aereo.md).

**Procesado de cada día.** `eodi-trafico.timer` lanza `eodi-trafico.service` en el minuto 40
de cada hora, como `eodi`, con prioridad baja de CPU y de disco (`Nice=15`,
`IOSchedulingClass=idle`). La unidad ejecuta [`servidor/trafico.sh`](../servidor/trafico.sh),
que toma su propio cerrojo (`/home/eodi/.eodi/trafico.lock`; si la ejecución anterior sigue,
esta no se lanza) y ejecuta `python -m recogida.trafico pendientes --tope-min 50`: procesa días
de la cola mientras quepa otro en 50 minutos. La cola va primero con los 35 últimos días (el
diario, del más nuevo al más viejo) y después con los días de los incidentes europeos y los de
su línea base, con los confirmados y atribuidos delante. Un día se descarga en flujo, sin
guardarlo en disco, y tarda unos 10 minutos de un núcleo y menos de 300 MB de memoria
(medido el 1 de octubre de 2026); adsb.lol lo publica hacia las 03:25 UTC del día siguiente,
así que entra en la ejecución de las 03:40 o en la siguiente. Un día que adsb.lol no ha
publicado se vuelve a mirar cada hora y, tres días después de terminado, se da por perdido
(`control.json`). El procesado no toca el clon (lo pone al día la recogida horaria) ni la base.

**Nunca retiene el cerrojo de la recogida horaria.** Lo que sale del procesado son ficheros
en `datos/trafico/`; la recogida horaria, que ya tiene su cerrojo y la base abierta, los lee
al final y escribe en la base los resultados agregados en segundos
([`recogida/mediciones.py`](../recogida/mediciones.py)): cobertura por aeropuerto y día,
interferencia GNSS diaria por celda, interrupciones (anomalías) y, por incidente, el tráfico
aéreo medido y las condiciones (Open-Meteo y METAR, con su cupo por ejecución). Un fallo de
esa parte no cambia el resultado de la recogida: queda en el diario y en `estado.json`
(fuentes `trafico_aereo` y `condiciones`).

Órdenes:

```
systemctl list-timers eodi-trafico.timer          # cuándo fue la última y cuándo es la siguiente
journalctl -u eodi-trafico.service -n 40          # días procesados, con duración y CPU
sudo systemctl start eodi-trafico.service         # lanzar una ahora (sigue con la cola)
sudo systemctl stop eodi-trafico.timer            # parar el procesado
sudo -u eodi sh -c 'cd /home/eodi/droneobservatory && EODI_TRAFICO_DATOS=/home/eodi/datos/trafico .venv/bin/python -m recogida.trafico resumen'
```

Un día suelto (por ejemplo, para repetirlo tras un cambio de regla, borrando antes su carpeta):

```
sudo -u eodi sh -c 'cd /home/eodi/droneobservatory && EODI_TRAFICO_DATOS=/home/eodi/datos/trafico .venv/bin/python -m recogida.trafico dia 2025-09-22'
```

## Secretos en local

En `%USERPROFILE%\.eodi\`, fuera de cualquier repositorio:

| Fichero | Qué es |
| --- | --- |
| `hcloud_token.txt` | Token de la API de Hetzner Cloud del proyecto EODI |
| `servidor_ssh`, `servidor_ssh.pub` | Par de claves SSH del operador, solo para este servidor |
| `servidor_known_hosts` | Clave de host del servidor, anotada en la primera conexión |
| `clave_age.txt` | Identidad age de la base |
| `extractor.env` | Variables del extractor (`EODI_EXTRACTOR_*`) |
| `firms_map_key.txt` | Clave de la API de NASA FIRMS (32 caracteres); `reconstruir.sh` la añade como `EODI_FIRMS_MAP_KEY` al `extractor.env` del servidor. También es el secreto `EODI_FIRMS_MAP_KEY` del repositorio, para la recogida de emergencia |
| `cloudflare_token.txt` | Token de la API de Cloudflare (R2 y DNS de las teselas) |
| `r2_estado.env` | Credenciales S3 de R2 para subir `estado.json` (`R2_ID`, `R2_SECRETO`, `R2_CUENTA`), derivadas del token por `reconstruir.sh` si no existen |

## Reconstruir desde cero

Hace falta `hcloud`, `gh` con sesión de la cuenta QuantuSync, `ssh` y los ficheros
`hcloud_token.txt`, `clave_age.txt` y `extractor.env` de la tabla anterior. En Windows,
desde Git Bash y en la raíz del clon:

```
bash servidor/reconstruir.sh
```

El script:

1. crea, si no existen, el par de claves SSH local, la clave en Hetzner, el cortafuegos y
   el servidor;
2. copia `servidor/` al servidor y ejecuta `endurecer.sh` y `instalar.sh` (que deja también
   la unidad y el temporizador del procesado de adsb.lol y sus carpetas de datos);
3. copia la clave age y las variables del extractor, con la clave de FIRMS;
4. sustituye en GitHub las claves de despliegue «servidor eodi-recogida» de los dos
   repositorios por las del servidor;
5. activa los temporizadores de la recogida horaria, de la exportación semanal, de las
   fuentes oficiales de detalle y del procesado de adsb.lol.

Puede repetirse sobre un servidor que ya existe: deja igual lo que ya está y vuelve a
aplicar la configuración. Para empezar de verdad desde cero se borra antes el servidor:

```
export HCLOUD_TOKEN="$(tr -d '\r\n' < ~/.eodi/hcloud_token.txt)"
hcloud server delete eodi-recogida
bash servidor/reconstruir.sh
```

Nada de lo que hay en el servidor es irrecuperable: la base vive en la rama `estado` y la
caché de páginas (`data/cache/`) se vuelve a llenar sola.

## Estado del sistema para la web

Al salir, con el código que sea, [`servidor/recogida.sh`](../servidor/recogida.sh) compone
`estado.json` ([`recogida/estado.py`](../recogida/estado.py)) y lo sube al bucket R2
`eodi-teselas`, que se sirve en <https://tiles.droneobservatory.eu/estado.json>. No hay
commit en git, así que la web no se reconstruye cada hora.

El fichero lleva la hora de inicio y de fin de la recogida, su resultado (`correcta`,
`con_avisos` o `fallida`), la hora de la última correcta, la de la siguiente prevista
(minuto 17) y, por cada fuente (`fuerza_aerea_ua`, `mindef_ru`, `gdelt`, `oficiales`,
`extractor`, `firms`, las de detalle: `airprox`, `parlamentos`, `investigaciones`,
`estadisticas_oficiales` y `paginas_js`, las de la capa de guerra con lugar: `ova_ua`,
`estado_mayor_ua`, `gobernadores_ru` y `rosaviatsia`, y las medidas: `trafico_aereo` y
`condiciones`), su estado (`leida`, `con_aviso` o `no_leida`) y la hora de su último dato; en
`firms`, la de la última descarga correcta; en las de detalle, la de su última lectura
correcta; en las de la capa de guerra, la de la última lectura correcta de alguno de sus
canales (leída si se leyeron todos; con aviso si alguno no); en `trafico_aereo`, la hora en
que terminó de procesarse el último día del archivo de adsb.lol (con aviso si pasan más de 48
horas sin procesar ninguno); en `condiciones`, la de la última petición correcta a Open-Meteo
o al IEM.
Lleva también `ultima_exportacion`: la hora en que terminó la última exportación semanal
correcta (o null si no consta ninguna), del registro que deja la exportación.
No lleva ningún contenido. La recogida deja el estado de cada fuente en un fichero
temporal (`recogida.horaria --estado`). El último estado publicado se guarda en
`/home/eodi/.eodi/estado.json`, de donde sale la hora de la última recogida correcta.

- **Subida**: `curl --aws-sigv4` contra el punto S3 de R2, con `Cache-Control: public,
  max-age=60` (la web lo pide cada 5 minutos). El CORS es el del bucket, el mismo que para
  las teselas. Las credenciales llegan a curl por su entrada, no por la línea de órdenes.
- **Si falla** (sin credenciales, sin red, R2 caído), la recogida no cambia de resultado:
  queda un aviso en el diario («aviso: no se pudo subir estado.json al bucket»).
- **Credenciales**: `/home/eodi/.eodi/r2.env`, con permisos 600. El token de Cloudflare no
  puede crear otros tokens (la API responde 9109) y las credenciales temporales de R2
  caducan, así que se derivan del propio token: identificador del token como clave de
  acceso y SHA-256 del token como secreto. Tienen los permisos de R2 del token, que son de
  toda la cuenta, no solo de este bucket. Para limitarlas al bucket hay que crear en el
  panel de Cloudflare un token de R2 con escritura solo en `eodi-teselas`, guardarlo en
  `r2_estado.env` con el mismo formato y volver a ejecutar `reconstruir.sh`.

## Órdenes útiles

Entrar en el servidor (la IP la da `hcloud server ip eodi-recogida`):

```
ssh -i ~/.eodi/servidor_ssh -o UserKnownHostsFile=~/.eodi/servidor_known_hosts operador@<IP>
```

Y dentro:

```
systemctl list-timers eodi-recogida.timer     # cuándo fue la última y cuándo es la siguiente
journalctl -u eodi-recogida.service -n 80     # registro de las últimas recogidas
systemctl status eodi-recogida.service        # resultado de la última
sudo systemctl start eodi-recogida.service    # lanzar una ahora
sudo systemctl stop eodi-recogida.timer       # parar la recogida horaria
sudo systemctl start eodi-recogida.timer      # reanudarla
```

## NASA FIRMS

Clave: `EODI_FIRMS_MAP_KEY` en `/home/eodi/.eodi/extractor.env`. Para cambiarla, se cambia
`%USERPROFILE%\.eodi\firms_map_key.txt` y se vuelve a ejecutar `reconstruir.sh` (o se
edita esa línea en el servidor como `eodi`); el secreto del repositorio, con
`gh secret set EODI_FIRMS_MAP_KEY < firms_map_key.txt`. Lo que quedan de transacciones (sin
mostrar la clave):

```
sudo -u eodi sh -c 'k=$(sed -n "s/^EODI_FIRMS_MAP_KEY=//p" /home/eodi/.eodi/extractor.env); curl -s "https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY=$k"'
```

**Histórico.** Desde octubre de 2022, con los productos SP (procesado estándar: Suomi NPP,
NOAA-20 y MODIS hasta unos meses atrás) y NRT donde SP no llega (NOAA-21 y los últimos
meses). Lo lanza [`servidor/firms_historico.sh`](../servidor/firms_historico.sh), en segundo
plano y por tandas con el cerrojo de la recogida: cada tanda termina en el minuto 12 de la
hora y no empieza otra hasta que la recogida horaria ha terminado, así que nunca se solapan.
Es reanudable (lo descargado no se vuelve a pedir) y respeta el límite de 5000 transacciones
cada 10 minutos (una llamada cada 2 s y espera si el contador pasa de 4000).

```
sudo systemd-run --unit=eodi-firms-historico --uid=eodi --gid=eodi \
  /usr/bin/env bash /home/eodi/droneobservatory/servidor/firms_historico.sh
journalctl -u eodi-firms-historico -n 40          # cómo va
sudo -u eodi sh -c 'cd /home/eodi/droneobservatory && EODI_FIRMS_DATOS=/home/eodi/datos/firms .venv/bin/python -m recogida.firms resumen'
```

Si se corta (reinicio, seis fallos seguidos), se vuelve a lanzar igual y sigue donde lo dejó.

## Fuentes oficiales de detalle

UK Airprox Board, respuestas de gobiernos en el Bundestag, la Tweede Kamer y el Parlamento
británico, informes de organismos de investigación, comunicados de la policía danesa,
sentencias, estadísticas oficiales y las tres listas de noticias oficiales que se cargan con
JavaScript ([`recogida/detalle.py`](../recogida/detalle.py), tabla de fuentes en
[`configuracion/fuentes_detalle.json`](../configuracion/fuentes_detalle.json), informe en
[`docs/informe_fuentes_detalle.md`](informe_fuentes_detalle.md)). Se leen en dos tiempos:

1. **Recogida**: `eodi-detalle.timer` lanza `eodi-detalle.service` cada 3 horas en el minuto 52
   (02:52, 05:52…, UTC), como `eodi`, con un tope de 120 minutos y prioridad baja (`Nice=15`).
   La unidad ejecuta [`servidor/detalle.sh`](../servidor/detalle.sh), que toma su propio
   cerrojo (`detalle.lock`: no espera a la recogida horaria ni la hace esperar), reinstala
   Playwright y Chromium solo si cambia `requirements-navegador.txt`, y ejecuta
   `python -m recogida.detalle recoger` con el código del clon tal como lo dejó la última
   recogida. Descarga lo nuevo de cada fuente y lo deja en `datos/detalle/`; no toca la base.
   Una fuente que falla queda en `datos/detalle/control.json` con su error y no para las
   demás.
2. **Incorporación**: la recogida horaria, con su cerrojo de siempre, guarda en la base lo
   que dejó la recogida (encuentros, documentos, estadísticas y resultados de lotes),
   extrae los documentos de los últimos 30 días con lo que deje del límite diario el
   extractor de noticias y cruza todo con los incidentes. Un fallo aquí deja aviso en sus
   fuentes de `estado.json` (`airprox`, `parlamentos`, `investigaciones`,
   `estadisticas_oficiales`, `paginas_js`, con su última lectura correcta) y no cambia el
   resultado de la recogida.

En `/home/eodi/datos/detalle/`, con permisos 700 y propiedad de `eodi`: `airprox/` (Excel
histórico, catálogos y texto de los informes de la UKAB, comprimido, y los encuentros
leídos), `documentos/` (por fuente, cada documento con sus pasajes sobre drones, nunca el
texto entero), `estadisticas/` (tablas leídas por código), `paginas_js/` (la última lista
renderizada de cada fuente con JavaScript, con su tiempo y su memoria), `lotes/` (resultados
del histórico) y `control.json`.

**Navegador sin interfaz.** `instalar.sh` instala Playwright en el entorno del observatorio,
las bibliotecas del sistema que pide Chromium (como root; si su herramienta no reconoce esta
Ubuntu, la lista de paquetes a mano) y Chromium en la caché de `eodi`. Solo lo usa la
recogida de detalle, nunca la horaria.

Lanzarla a mano y ver cómo va, como `operador`:

```
sudo systemctl start eodi-detalle.service
journalctl -u eodi-detalle.service -n 60
systemctl show eodi-detalle.service -p MemoryPeak -p CPUUsageNSec
sudo -u eodi cat /home/eodi/datos/detalle/control.json
```

**Histórico, una sola vez.** Recoge todo lo que cada fuente permite y envía al extractor, como
un lote, los documentos de antes de los últimos 30 días, con su presupuesto propio (3
dólares, modo de gasto «detalle», aparte del límite diario). Espera al lote y deja los
resultados en `datos/detalle/lotes/`; la recogida horaria siguiente los incorpora y anota su
gasto. Si no caben todos en una tanda (se recorta por el peor caso), se vuelve a lanzar
después de esa incorporación.

```
sudo systemd-run --unit=eodi-detalle-historico --uid=eodi --gid=eodi \
  /usr/bin/env bash /home/eodi/droneobservatory/servidor/detalle_historico.sh
journalctl -u eodi-detalle-historico -n 40
```

## Canales de la capa de guerra con lugar

Los canales oficiales de Telegram que dan los lugares concretos alcanzados por los ataques
con drones (administraciones militares regionales de Ucrania, Estado Mayor ucraniano,
gobernadores y gobiernos regionales rusos) y las restricciones de aeropuertos de Rosaviatsia
([`recogida/canales_guerra.py`](../recogida/canales_guerra.py), canales y prueba de que son
oficiales en [`configuracion/canales_guerra.json`](../configuracion/canales_guerra.json),
informe en [`docs/informe_capa_guerra.md`](informe_capa_guerra.md)). En dos tiempos:

1. **Lectura**: `eodi-guerra.timer` lanza `eodi-guerra.service` en el minuto 50 de cada hora.
   La unidad ejecuta [`servidor/guerra.sh`](../servidor/guerra.sh), que toma su propio cerrojo
   (`guerra.lock`), lee lo nuevo de cada canal por su vista pública web, con la identificación
   del observatorio y una petición cada 3 segundos, tras comprobar que sigue siendo el oficial
   (título, insignia, enlaces de su descripción y la web de la institución), y con el tiempo
   que queda sigue el histórico desde el 1 de enero de 2025 donde lo dejó. Guarda en
   `datos/guerra/canales/<canal>/<AAAA-MM>.jsonl` solo las publicaciones que hablan de drones
   (o de aeropuertos, en Rosaviatsia) y en `datos/guerra/control.json` el resultado de cada
   canal. No toca la base. Un canal que falla no para a los demás.
2. **Incorporación**: la recogida horaria (`recogida/guerra.py`) lee esos ficheros, convierte
   los mensajes en impactos con localidad o instalación (`proceso/mensajes_guerra.py`,
   nomenclátor en `configuracion/nomenclator_guerra.json.gz`), los enlaza con el ataque de la
   noche y les da su credibilidad. Lo que el código no resuelve lo lee el extractor con su
   límite diario propio de 0,20 dólares (modo «guerra»). Un fallo aquí no cambia el resultado
   de la recogida. El nomenclátor ocupa unos 500 MB mientras se usa y se libera al terminar.

Órdenes, como `operador`:

```
sudo systemctl start eodi-guerra.service          # una lectura ahora
journalctl -u eodi-guerra.service -n 60
sudo -u eodi sh -c 'cd /home/eodi/droneobservatory && .venv/bin/python -m recogida.canales_guerra resumen'
```

**Reprocesar todo** (tras cambiar el analizador, el nomenclátor o las palabras corrientes, o al
terminar el histórico) y, con `lote`, mandar al extractor por lotes los mensajes que el código
no resuelve (presupuesto único de 5 dólares, modo «guerra_historico», primero los objetivos de
combustible, energía e industria). [`servidor/guerra_reproceso.sh`](../servidor/guerra_reproceso.sh)
toma el cerrojo de la recogida, descarga la base de la rama `estado` y la vuelve a subir; la
recogida siguiente publica el resultado:

```
sudo systemd-run --unit=eodi-guerra-reproceso --uid=eodi --gid=eodi \
  /usr/bin/env bash /home/eodi/droneobservatory/servidor/guerra_reproceso.sh lote
journalctl -u eodi-guerra-reproceso -n 60
```

## Revisión de todo lo publicado

Cuando cambian las reglas con que se construyen los incidentes, lo ya publicado se revisa
en el servidor con [`servidor/revision.sh`](../servidor/revision.sh), como `eodi` y desde
la rama que trae las reglas:

```
sudo -u eodi bash /home/eodi/droneobservatory/servidor/revision.sh <rama> /home/eodi/revision.liberar
```

Toma el mismo cerrojo que la recogida horaria (espera a que termine la que esté en marcha),
deja un clon aparte en `/home/eodi/revision` con la rama y con los ficheros publicados de
`main`, y ejecuta `python -m recogida.revision`: muestra de coste, lote del extractor
dentro de su propio límite de gasto (5 dólares), reconstrucción de todos los incidentes,
fusiones y episodios, publicación en el clon aparte y subida de la base. El informe queda
en `/home/eodi/revision-informe.json`. Con un fichero de aviso, retiene el cerrojo hasta
que ese fichero existe (como mucho tres horas): se crea con `touch` cuando la rama ya está
fusionada, y así la recogida horaria no vuelve a publicar con el código anterior mientras
tanto.

## Emergencia: recogida desde GitHub

El workflow `recogida` sigue en el repositorio, solo con lanzamiento a mano, y conserva sus
secretos. Si el servidor no está disponible:

```
gh workflow run recogida.yml --ref main
```

Si el servidor sigue encendido, antes hay que parar su temporizador: dos recogidas a la
vez se pisarían la rama `estado`.

## Cómo se ve si la recogida se para

El workflow `vigia-recogida` se lanza cada hora en el minuto 41 y lee
<https://tiles.droneobservatory.eu/estado.json> ([`recogida/salud.py`](../recogida/salud.py)).
Si la última recogida correcta tiene más de 2 horas, o si el fichero no responde en tres
intentos separados un minuto, abre una incidencia en este repositorio («La recogida horaria
no actualiza la base»), una sola mientras dure el problema, y la cierra cuando la recogida
vuelve a terminar bien. Una recogida fallida o con avisos no abre nada mientras haya una
correcta reciente. Tiene permiso para leer el código y para las incidencias, nada más.

Antes miraba la fecha del último commit de la rama `estado` del repositorio de datos, que
no avanza cuando una recogida no cambia la base, y a las dos horas habría dado un aviso
falso. Con eso se retiró la clave de despliegue de solo lectura de ese repositorio que
usaba («droneobservatory: salud (solo lectura)», secreto `EODI_DATOS_CLAVE_LECTURA`).

GitHub lanza las ejecuciones programadas con retraso y a veces se salta alguna: el aviso
puede llegar tarde.
Además, desactiva las programaciones de un repositorio público sin actividad durante 60
días; la recogida publica en `main` casi cada hora, así que no debería pasar.

El trabajo `salud-recogida` del workflow de tests hace la misma comprobación en cada push o
pull request y la deja en su resumen, sin hacer fallar los tests.

## Fuentes que no se leen desde el servidor

- **Ministerio de Defensa de Finlandia** (`mod_fi`, `defmin.fi/ajankohtaista`). Retirada
  de `configuracion/fuentes_oficiales.json` el 30 de septiembre de 2026. Al servidor, que
  tiene una dirección de centro de datos, le responde 403 con una página de comprobación
  anti-robots, con la identificación del observatorio y con la de un navegador, y también a
  `robots.txt`; desde una conexión doméstica responde 200. Leerla exigiría saltarse esa
  comprobación, y el observatorio lee las fuentes con su identificación y respetando lo que
  piden. Sigue en `fuentes_oficiales_candidatas.json` por si el ministerio publica un canal
  RSS o deja de vetar esas direcciones. Las confirmaciones oficiales de Finlandia quedan en
  las declaraciones que cita la prensa.
