# Servidor de recogida

La recogida de cada hora la lanza un servidor propio en Hetzner Cloud, no GitHub Actions.
Todo lo que hay en él sale de los scripts de [`servidor/`](../servidor), que no llevan
ningún secreto: con ellos y con los secretos que se guardan en local se reconstruye desde
cero con una sola orden.

## Qué hay en el servidor

| | |
| --- | --- |
| Servidor | `eodi-recogida`, tipo CX33 (4 núcleos compartidos, 8 GB de memoria, 80 GB de disco), Núremberg (`nbg1`), Ubuntu 26.04 LTS, IPv4 2.28.197.102 |
| Cortafuegos de Hetzner | `eodi-recogida`: solo entra SSH (TCP 22); lo demás, cerrado |
| Usuario `eodi` | Ejecuta el observatorio. Sin privilegios, sin contraseña y sin entrada por SSH |
| Usuario `operador` | Administra: entra por SSH con clave y usa `sudo` |
| SSH | Solo con clave, sin contraseña y sin root |
| Además | fail2ban, actualizaciones de seguridad automáticas con reinicio a las 04:45 si hace falta, zona horaria UTC, hora sincronizada, diario de systemd con tope de tamaño y de antigüedad |
| needrestart | No reinicia las unidades `eodi-*` tras una actualización (`/etc/needrestart/conf.d/50-eodi.conf`): son trabajos con temporizador y reiniciarlos corta su trabajo |

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
  - `exportacion.json`: la última exportación semanal correcta (versión, hora y huella);
  - `deduccion.json`: la última ejecución correcta del motor de deducción;
  - `directo.json`: el último ciclo correcto de la detección en directo y su fuente;
  - `almacen.env`: las credenciales S3 del almacén público (`ALMACEN_ID` y
    `ALMACEN_SECRETO`), para subir `estado.json`;
  - `estado.json`: el último estado publicado.
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
- `datos/busqueda/`, con permisos 700 y propiedad de `eodi`: la búsqueda dirigida de noticias
  (apartado «Búsqueda dirigida de noticias»): `anomalias.json` (lo que falta buscar, lo
  escribe la recogida horaria), `dias/<AAAA-MM-DD>.jsonl.gz` (todos los titulares con dron de
  ese día leídos de GDELT, para no volver a bajarlos) y `hallados/<anomalía>.json`.
- `datos/deduccion/`, con permisos 700 y propiedad de `eodi`: lo que calcula el motor de
  deducción (apartado «Motor de deducción»): `resultados.jsonl.gz`, `control.json`,
  `validacion.json`, `horizontes.json` y las teselas de Copernicus DEM GLO-90 (`dem/`). Todo
  se puede volver a calcular.
- `datos/catalogo/`, con permisos 700 y propiedad de `eodi`: lo que encuentra el barrido del
  catálogo vivo (apartado «Catálogo vivo»): `novedades.jsonl`, `catalogo_vivo.json`,
  `historial.jsonl`, `tacticas.json`, `apariciones.json`, `control.json` y `gasto.json`.
- `datos/satelite/`, `datos/luces/` y `datos/focos_vivo/`, con permisos 700 y propiedad de
  `eodi`: lo que guardan las tres piezas de la guerra por satélite (apartado «Guerra por
  satélite»). Todo se puede volver a calcular.
- `datos/reintentos/`, propiedad de `eodi`: un fichero por sitio con los reintentos del día
  (apartado «Reintentos por fuente»).
- `datos/directo/`, con permisos 700 y propiedad de `eodi`: el estado de la detección en directo
  de cierres y lo publicado del mapa de interferencia GPS (apartado «Detección en directo de
  cierres»).

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

**Puesta en marcha.** En servicio desde el 1 de octubre de 2026, con los 47 días de la
validación ya procesados. El histórico (522 días) avanza unos 4 días y medio por hora y termina
hacia el 6 de octubre; mientras tanto, cada recogida horaria evalúa primero los incidentes y con
lo que quede de su tope sigue con las interrupciones de todos los aeropuertos, que se ponen al
día cuando el histórico acaba.

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

## Búsqueda dirigida de noticias

Informe: [`informe_calidad_datos_3.md`](informe_calidad_datos_3.md). Cuando el tráfico aéreo
mide en un aeropuerto con cobertura alta una interrupción que no casa con ningún incidente ni
explica el tiempo (anomalía candidata), se buscan en los GKG de GDELT de ese día y del
siguiente las noticias que nombran el aeropuerto o su ciudad, en cualquiera de sus nombres,
junto a una palabra de dron ([`recogida/busqueda_dirigida.py`](../recogida/busqueda_dirigida.py)).
En dos tiempos:

1. **Lectura**: `eodi-busqueda.timer` lanza `eodi-busqueda.service` en el minuto 2 de cada
   hora, como `eodi`, con prioridad baja (`Nice=15`, E/S en reposo) y su propio cerrojo
   (`busqueda.lock`). La unidad ejecuta [`servidor/busqueda.sh`](../servidor/busqueda.sh), que
   lee `datos/busqueda/anomalias.json` y descarga los GKG de los días que faltan, hasta 40
   minutos por ejecución (un día son 192 ficheros: de 2 a 5 minutos). No toca la base ni el
   clon.
2. **Incorporación**: la recogida horaria guarda lo hallado como artículos del aeropuerto por
   el flujo normal (deduplicado, candidato), anota cada anomalía como buscada (cursor
   `busqueda_dirigida`) y deja al día `anomalias.json`. Sus candidatos van los primeros en la
   cola del extractor horario (recogida/extractor.prioritarios), dentro del límite diario. Un
   fallo aquí queda en el diario («búsqueda dirigida no incorporada») y no cambia el resultado
   de la recogida.

Órdenes, como `operador`:

```
sudo systemctl start eodi-busqueda.service       # una lectura ahora
journalctl -u eodi-busqueda.service -n 40
sudo -u eodi ls /home/eodi/datos/busqueda/hallados | wc -l
```

## Revisión de la calidad de los datos (una vez)

[`servidor/calidad.sh`](../servidor/calidad.sh) aplica a lo ya recogido las reglas de la tercera
revisión ([`recogida/calidad.py`](../recogida/calidad.py)): separa los candidatos que juntan dos
sucesos del mismo sitio, sitúa los artículos que ahora nombran una instalación reconocible,
incorpora lo hallado por la búsqueda dirigida, extrae en un lote lo pendiente (modo de gasto
«calidad», 2 dólares en total) y rehace incidentes, fusiones y episodios. Toma el cerrojo de la
recogida, trabaja en un clon aparte (`/home/eodi/calidad`) con la rama `main` y sube la base;
la recogida siguiente publica y repite los cruces que dependen de la fecha (FIRMS, tráfico
aéreo, condiciones). Si el lote se queda a medias, se relanza con `--lote <id>`; si quedan peticiones fuera del
límite por el peor caso, se vuelve a lanzar y sigue con ellas.

Ejecutada el 2 de octubre de 2026, tras el barrido inicial de la búsqueda dirigida (216
anomalías, 57 días de GKG en 3 h 44 min): tres tandas, 0,692 USD; de 383 a 466 incidentes
publicados ([`informe_calidad_datos_3.md`](informe_calidad_datos_3.md)). Usa unos 2,2 GB al
cifrar y subir la base: con el histórico de tráfico y la búsqueda dirigida en marcha una pasada
murió por falta de memoria (antes de subir nada); se repite con `eodi-busqueda` parado
(`sudo systemctl stop eodi-busqueda.timer eodi-busqueda.service`, y `start` del temporizador al
terminar).

```
sudo systemd-run --unit=eodi-calidad --uid=eodi --gid=eodi \
  /usr/bin/env bash /home/eodi/droneobservatory/servidor/calidad.sh
journalctl -u eodi-calidad -n 60
sudo -u eodi cat /home/eodi/calidad-informe.json | head
```

## Motor de deducción

Informe: [`informe_deduccion.md`](informe_deduccion.md). Para cada incidente europeo, cada
impacto con lugar de la capa de guerra (sin los partes diarios ni los FPV de la línea del
frente) y cada ataque, qué clases de dron son compatibles, cuáles quedan descartadas y por
qué, con reglas físicas sobre el catálogo de prestaciones (`configuracion/catalogo_drones.json`).
En dos tiempos:

1. **Cálculo.** `eodi-deduccion.timer` lanza `eodi-deduccion.service` en el minuto 5 de cada
   hora (`Nice=15`, E/S en reposo, tope de 50 minutos). La unidad ejecuta
   [`servidor/deduccion.sh`](../servidor/deduccion.sh), que toma su propio cerrojo
   (`deduccion.lock`; si el cálculo anterior sigue, este no se lanza) y ejecuta
   `python -m recogida.deduccion calcular` con el código del clon tal como lo dejó la última
   recogida. Descarga la base de la rama `estado` solo para leerla (no toma el cerrojo de la
   recogida horaria: un clon es atómico, como mucho lee la versión anterior), recalcula solo
   lo que ha cambiado (cada caso lleva la huella de sus datos y de la versión del motor, de
   cada regla, del catálogo y de las zonas: al subir una versión se recalcula todo) y deja
   los resultados en `datos/deduccion/`. La validación pide a Open-Meteo, con la caché común
   y un tope de 100 llamadas por ejecución, el tiempo de los casos que no están en la base. El
   horizonte de radar descarga de AWS las teselas de Copernicus DEM que necesita (como mucho
   150 nuevas por ejecución). Si termina bien, deja la hora en `/home/eodi/.eodi/deduccion.json`.
2. **Incorporación.** La recogida horaria, con su cerrojo, guarda en la tabla `deducciones` lo
   que ha cambiado, en segundos, y el resumen de la validación en el cursor `deduccion`. Un
   fallo ahí queda en el diario y no cambia el resultado de la recogida.

`estado.json` lleva `ultima_deduccion` (la última ejecución correcta, del registro), que la
web acepta sin mostrarla. Un fallo del motor no rompe la recogida horaria: la base sigue con
lo último que se incorporó.

Órdenes, como `operador`:

```
systemctl list-timers eodi-deduccion.timer
journalctl -u eodi-deduccion.service -n 40          # recuentos, duración, teselas, validación
sudo systemctl start eodi-deduccion.service         # un cálculo ahora (incremental)
sudo systemd-run --unit=eodi-deduccion-todo --uid=eodi --gid=eodi \
  /usr/bin/env bash /home/eodi/droneobservatory/servidor/deduccion.sh --todo
sudo -u eodi cat /home/eodi/datos/deduccion/control.json
```

El motor 1.1.0 toma de cada incidente la hora y la duración de mejor origen con las mismas
reglas que la exportación (`exportacion/mejor_origen.py`: un cierre medido, un registro oficial,
la hora que escribe una autoridad o la única interrupción medida antes de una fecha de
publicación), pide a Open-Meteo el viento de esa hora si las condiciones guardadas son de otra
hora o solo del día (tope de 400 llamadas por ejecución, con la caché común) y, en los cruces a
países de la OTAN con solo el día, el viento de cada hora del día local para la deriva. Usa
además las frases de las fuentes (testigos, pilotos, autoridades) para la regla de la
descripción y para el país desde el que una autoridad dice que entró el dron, y deja en cada
incidente la dirección de entrada (`direccion_entrada`: declarada o deducida de la zona de
despegue y el viento). Usa el catálogo con lo que ha admitido el barrido del catálogo vivo.

## Catálogo vivo

Barrido periódico del catálogo de prestaciones ([`recogida/catalogo_vivo.py`](../recogida/catalogo_vivo.py),
lógica sin red en [`proceso/catalogo_vivo.py`](../proceso/catalogo_vivo.py), fuentes y ritmo en
[`configuracion/barrido_catalogo.json`](../configuracion/barrido_catalogo.json), informe en
[`informe_catalogo_vivo.md`](informe_catalogo_vivo.md)). En dos tiempos:

1. **Barrido.** `eodi-catalogo.timer` lanza `eodi-catalogo.service` una vez al día a las 05:23
   UTC (`Nice=15`, E/S en reposo, tope de 60 minutos). La unidad ejecuta
   [`servidor/catalogo.sh`](../servidor/catalogo.sh), que toma su propio cerrojo
   (`catalogo.lock`) y ejecuta `python -m recogida.catalogo_vivo barrer`: descarga la base de la
   rama `estado` solo para leerla (los datos propios) y lee War&Sanctions y los datos propios cada
   día y el resto de fuentes (fabricantes, listas de marcado de clase, autoridades, centros de
   análisis y prensa técnica) una vez a la semana, con la identificación del observatorio, el
   robots.txt de cada sitio, una petición cada 5 s por sitio, la espera creciente del
   descargador y el tope diario de reintentos por sitio. Lo estructurado (fichas de
   War&Sanctions, tablas de especificaciones, listas de marcado de clase) lo lee el código; el
   extractor solo lee las frases que nombran un modelo con una cifra que el código no resuelve,
   con salida por esquema y cada cifra validada por código (la frase en el texto, el número en
   la frase). Presupuesto del extractor: 0,10 dólares al día y 3 dólares una vez para la primera
   pasada, en su propio registro (`gasto.json`). Deja todo en `datos/catalogo/`.
2. **Incorporación.** La recogida horaria guarda en la tabla `catalogo_vivo` de la base (con
   historial) el catálogo vivo, las novedades, las tácticas y las apariciones, en segundos. El
   motor de deducción y la exportación semanal usan el catálogo de la configuración con lo
   admitido (versión `1.1.0+vivo.N`). Nada de esto se publica en la web.

Regla de entrada: lo que viene de un fabricante, de inteligencia, de una lista oficial, de una
autoridad o de un centro de análisis entra directo; lo que viene solo de prensa queda como
candidato hasta que lo diga una segunda fuente de otro sitio. Un dato nuevo se añade a los que ya
hay (la envolvente de una clase solo se ensancha) y cada versión queda en `historial.jsonl`.

Órdenes, como `operador`:

```
systemctl list-timers eodi-catalogo.timer
journalctl -u eodi-catalogo.service -n 40          # hallazgos, novedades, versión y gasto
sudo systemctl start eodi-catalogo.service         # un barrido ahora (solo lo que toca hoy)
sudo systemd-run --unit=eodi-catalogo-primera --uid=eodi --gid=eodi \
  /usr/bin/env bash /home/eodi/droneobservatory/servidor/catalogo.sh --primera
sudo -u eodi sh -c 'cd /home/eodi/droneobservatory && EODI_CATALOGO_DATOS=/home/eodi/datos/catalogo .venv/bin/python -m recogida.catalogo_vivo resumen'
```

## Barrido dirigido de España, puertos y presas (una vez)

[`recogida/barrido_dirigido.py`](../recogida/barrido_dirigido.py): las noticias de GDELT desde el
1 de enero de 2025 con una palabra de dron (también en catalán, gallego y euskera) que nombran
una instalación de España o un puerto o una presa de Europa del nomenclátor. Primero la lectura
de los días que faltan, sin la base y con prioridad baja (comparte la caché de días de la
búsqueda dirigida); después, con el cerrojo de la recogida, la búsqueda, la incorporación como
artículos y candidatos, el lote del extractor (modo «dirigida», 3 dólares una vez) y la
reconstrucción de los incidentes. El informe queda en `/home/eodi/dirigido-informe.json`.

```
sudo systemd-run --unit=eodi-dirigido-lectura --uid=eodi --gid=eodi -p Nice=19 \
  -p IOSchedulingClass=idle -p MemoryMax=900M \
  --setenv=EODI_BUSQUEDA_DATOS=/home/eodi/datos/busqueda \
  --working-directory=/home/eodi/droneobservatory \
  /home/eodi/droneobservatory/.venv/bin/python -m recogida.barrido_dirigido leer --hilos 2
sudo systemd-run --unit=eodi-dirigido --uid=eodi --gid=eodi \
  /usr/bin/env bash /home/eodi/droneobservatory/servidor/dirigido.sh
journalctl -u eodi-dirigido -n 60
```

Si el lote se queda a medias, se relanza con `--lote <id>`.

## Criterio de presencia del dron, titulares y noches de cierre (una vez)

[`recogida/criterio_presencia.py`](../recogida/criterio_presencia.py) lo aplica la propia recogida
horaria, antes del extractor, una vez por versión (cursor `criterio_presencia` de la base): separa
los candidatos que juntaron el cierre de una noche y la repetición de la siguiente (la repetición se
mide desde el inicio del suceso), rehace todos los incidentes con el criterio de presencia y los
titulares coherentes, funde hasta que no queda nada que fundir (dos cierres de noches distintas nunca
se funden) y deja el motivo de cada cambio en el historial. No lanza ningún trabajo aparte. Los
candidatos separados (las dos partes) van delante en el extractor (recogida/extractor.prioritarios),
hasta 10 por hora. El resumen queda en el cursor:

```
sudo -u eodi sh -c 'cd /home/eodi/droneobservatory && journalctl -u eodi-recogida -n 400 | grep "criterio de presencia"'
```

## Detección en directo de cierres

Informe: [`informe_europa_directo.md`](informe_europa_directo.md). Cada minuto, las posiciones en
tiempo real de los aeropuertos vigilados (los de cobertura alta del archivo de adsb.lol, unos
noventa), sus aterrizajes y despegues frente a la línea base del mismo día de la semana y la
misma hora local, y los avisos de cierre ([`recogida/directo.py`](../recogida/directo.py),
reglas en [`proceso/directo.py`](../proceso/directo.py)).

- **Unidad.** `eodi-directo.service`, siempre en marcha (`Restart=always`, a los 30 s), como
  `eodi`, con `Nice=5` y un tope de 1,5 GB de memoria. Ejecuta
  [`servidor/directo.sh`](../servidor/directo.sh), que toma su propio cerrojo
  (`directo.lock`): nunca toma el de la recogida horaria ni la hace esperar, y no toca la base
  ni el clon. Usa el código del clon tal como lo deja la recogida horaria: cuando ve un commit
  nuevo, guarda sus trazas y sale, y systemd la vuelve a lanzar con el código nuevo.
- **Fuente.** adsb.lol (`/v2/point`, sin clave), en círculos de 200 millas que cubren todos los
  aeropuertos vigilados, una petición cada 1,5 s como mucho y con compresión. Respaldo
  automático: adsb.fi (mismo formato), si en un ciclo falla la mitad de los círculos; tras tres
  ciclos así sigue con el respaldo y prueba la principal cada 10 minutos. Los reintentos esperan
  2 y 4 s y cuentan en el tope diario por sitio de `datos/reintentos/`.
- **Datos** en `datos/directo/`, con permisos 700 y propiedad de `eodi`: `estado.json` (avisos,
  señales y fuente en uso), `avisos.json` (los avisos, para la búsqueda dirigida y la recogida
  horaria), `avisos_historial.jsonl` (cada aviso al abrirse y al reanudarse),
  `confirmaciones.json` (lo escribe la recogida horaria), `vivos.pickle` (las trazas de las tres
  últimas horas, guardadas cada 10 minutos y al parar: al volver a arrancar en menos de 15
  minutos sigue con ellas) y `gnss.json` (los días publicados del mapa de interferencia GPS).
  El registro para `estado.json` (último ciclo correcto y fuente) es
  `/home/eodi/.eodi/directo.json`.
- **Publica** en el almacén público, en cada ciclo, `directo.json` (`Cache-Control: public,
  max-age=30`), y al aparecer cada día nuevo del archivo, el mapa de interferencia GPS de ese
  día y de su mes y el índice (`gnss/`, con compresión gzip), unos pocos días por ciclo hasta
  tener todo el histórico.
- **Un aviso nuevo** lanza la búsqueda dirigida de noticias de ese aeropuerto
  (`python -m recogida.busqueda_dirigida directo`, con el cerrojo de la búsqueda) y la repite
  cada media hora mientras sigue abierto; la recogida horaria incorpora lo hallado y, cuando un
  incidente de la base recoge el cierre, lo deja en `confirmaciones.json`.
- **Vigilancia.** `estado.json` lleva `directo` (en marcha, con respaldo o parada, y el último
  ciclo correcto), y el workflow `vigia-recogida` abre la incidencia «La detección en directo no
  se actualiza» si `directo.json` lleva más de media hora sin publicarse.

Órdenes, como `operador`:

```
systemctl status eodi-directo.service
journalctl -u eodi-directo.service -n 40            # un ciclo por minuto: peticiones, señales, avisos
sudo systemctl restart eodi-directo.service         # relanzar (sigue con las trazas guardadas)
sudo -u eodi cat /home/eodi/datos/directo/estado.json | head -40
sudo -u eodi tail -n 5 /home/eodi/datos/directo/avisos_historial.jsonl
```

**Reproducir días pasados** con las trazas guardadas del archivo (para ajustar umbrales; no toca
nada del servicio):

```
sudo systemd-run --unit=eodi-directo-reproduccion --uid=eodi --gid=eodi --nice=10 \
  --working-directory=/home/eodi/droneobservatory /home/eodi/droneobservatory/.venv/bin/python \
  -m recogida.directo_reproduccion 2025-09-22 --datos /home/eodi/datos/trafico \
  --salida /home/eodi/datos/directo/reproduccion.jsonl
```

## Guerra por satélite

Informe: [`informe_guerra_satelite.md`](informe_guerra_satelite.md). Tres servicios, cada uno con
su propio temporizador, su propio cerrojo (en `/home/eodi/.eodi/`), prioridad baja de CPU y de
disco (`Nice=15`, E/S en reposo) y un tope de memoria de 1 GB (`MemoryMax`): si una pieza lo
pasara, systemd la para a ella sola. Ninguno toma el cerrojo de la recogida horaria, toca el clon
ni arranca entre los minutos 15 y 40, los de la recogida; la luz nocturna y las imágenes, además, no
empiezan si el cerrojo de la recogida está ocupado.

| Unidad | Cuándo | Qué hace | Datos |
| --- | --- | --- | --- |
| `eodi-satelite` ([`satelite.sh`](../servidor/satelite.sh), [`recogida/satelite.py`](../recogida/satelite.py)) | 06:43 y 18:43 UTC, tope de 30 minutos | Lee los objetivos que deja cada hora la recogida horaria (`datos/satelite/objetivos.json`: los impactos públicos con foco térmico detectado o en una instalación; así no carga la base) y, para cada impacto con foco térmico detectado o en una instalación, busca en el catálogo STAC de Earth Search la última imagen de Sentinel-2 sin nubes sobre el recorte antes del ataque y la primera después; lee solo la ventana del recorte de cada banda y sube las imágenes y el índice `satelite/parejas.json` al almacén público | `datos/satelite/objetivos.json`, `control.json` (lo buscado) y una copia del índice |
| `eodi-luces` ([`luces.sh`](../servidor/luces.sh), [`recogida/luces.py`](../recogida/luces.py)) | Minuto 41 de cada hora; no empieza una noche nueva pasados 29 minutos | Mide el brillo de cada ciudad en los gránulos de VIIRS de NOAA-20 de las noches que hacen falta (las de los ataques contra la energía y su referencia, las de la validación y la última) y evalúa cada ataque (también los apagones documentados de la validación, con el ataque en curso ese día); la recogida horaria guarda el resultado en la base (tabla `luces_nocturnas`). Con todas las noches medidas, las ciudades con alumbrado reducido de forma permanente, que sube al almacén público (`luces/alumbrado.json`, caché de una hora) | `datos/luces/`: `noches/`, `anillos/` (huellas de los gránulos), `nubes/` (Open-Meteo por ciudad y mes), `resultados.json`, `alumbrado.json`, `validacion.json`, `control.json` |
| `eodi-focos-vivo` ([`focos_vivo.sh`](../servidor/focos_vivo.sh), [`recogida/focos_vivo.py`](../recogida/focos_vivo.py)) | Minuto 42 de cada hora | Con los CSV de FIRMS que descarga la recogida, los focos de las últimas 24 horas sobre Ucrania y la Rusia europea con los filtros del cruce; sube `focos/ultimas24h.json` (caché de 5 minutos) al almacén público | `datos/focos_vivo/` (resumen diario de emplazamientos del año y la última copia) |

Las imágenes, los focos y las ciudades con alumbrado reducido suben al almacén con las
credenciales de `almacen.env`. La última
ejecución correcta de cada pieza queda en `satelite.json`, `luces.json` y `focos_vivo.json` de
`/home/eodi/.eodi/`.

Órdenes, como `operador`:

```
systemctl list-timers eodi-satelite.timer eodi-luces.timer eodi-focos-vivo.timer
journalctl -u eodi-luces.service -n 20             # noches medidas, pendientes y validación
sudo systemctl start eodi-focos-vivo.service       # un fichero de focos ahora
sudo -u eodi cat /home/eodi/datos/luces/control.json
sudo -u eodi cat /home/eodi/datos/luces/validacion.json | head -c 2000
```

Un histórico se completa solo: cada ejecución de `eodi-luces` sigue con las noches pendientes de
la más reciente a la más antigua, y `eodi-satelite` vuelve a mirar cada pareja a medias en las
escenas nuevas. Para adelantarlo, se lanza la unidad a mano o, con más tiempo, con
`systemd-run`:

```
sudo systemd-run --unit=eodi-luces-historico --uid=eodi --gid=eodi -p MemoryMax=1G \
  -p Nice=15 -p IOSchedulingClass=idle /usr/bin/env bash /home/eodi/droneobservatory/servidor/luces.sh
sudo systemd-run --unit=eodi-satelite-historico --uid=eodi --gid=eodi -p MemoryMax=1G \
  -p Nice=15 -p IOSchedulingClass=idle /usr/bin/env bash /home/eodi/droneobservatory/servidor/satelite.sh
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
| `almacen.env` | Credenciales S3 del almacén público de Hetzner (`ALMACEN_ID=…` y `ALMACEN_SECRETO=…`, una por línea); las llevan al servidor `reconstruir.sh` y `preparar_almacen.sh` |
| `cloudflare_token.txt` | Token de la API de Cloudflare. Ya no se usa: el DNS está en Hetzner desde el 3 de octubre de 2026. Se borra al cerrar la cuenta de Cloudflare |
| `r2_estado.env` | Credenciales S3 del bucket R2 anterior (`eodi-teselas`); ya no responden (401). En el servidor se borraron |

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
   fuentes oficiales de detalle, del lector de canales de la capa de guerra, del procesado de
   adsb.lol, de la búsqueda dirigida de noticias, del motor de deducción y del barrido del
   catálogo vivo, de las tres piezas de la guerra por satélite (imágenes, luz nocturna y focos en
   vivo) y el servicio de detección en directo de cierres.

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
`estado.json` ([`recogida/estado.py`](../recogida/estado.py)) y lo sube al almacén público
(apartado siguiente), que lo sirve en
<https://droneobservatory-almacen.nbg1.your-objectstorage.com/estado.json>. No hay commit en
git, así que la web no se reconstruye cada hora.

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
correcta (o null si no consta ninguna), del registro que deja la exportación, y
`ultima_deduccion`: la de la última ejecución correcta del motor de deducción, y `directo`: el
estado de la detección en directo (`en_marcha`, `con_respaldo` o `parado`, este si no ha
tenido un ciclo correcto en 10 minutos) con su último ciclo correcto.
No lleva ningún contenido. La recogida deja el estado de cada fuente en un fichero
temporal (`recogida.horaria --estado`). El último estado publicado se guarda en
`/home/eodi/.eodi/estado.json`, de donde sale la hora de la última recogida correcta.

- **Subida**: [`recogida/almacen_publico.py`](../recogida/almacen_publico.py) firma la
  petición S3 (Signature Version 4, sin dependencias) con `Cache-Control: public,
  max-age=60` (la web lo pide cada 5 minutos). Tres intentos con 2 y 4 s de espera entre
  ellos y 60 s como mucho en total; un 400, 401, 403 o 404 no se repite. Las credenciales
  van en el entorno del proceso, no en la línea de órdenes.
- **Si falla** (sin credenciales, sin red, almacén caído), la recogida no cambia de
  resultado y publica igual la base y los ficheros de la web: queda un aviso en el diario
  («aviso: no se pudo subir estado.json al almacén»). La web, mientras tanto, mide la
  antigüedad desde el último cambio de los datos.
- **Credenciales**: `/home/eodi/.eodi/almacen.env`, con permisos 600.

## Almacén público

Teselas del mapa de fondo y `estado.json`, en Hetzner Object Storage (compatible con S3),
en Núremberg, la misma ubicación que el servidor. Sustituye al bucket R2 `eodi-teselas`
de Cloudflare desde el 2 de octubre de 2026 (informe en
[`informe_migracion_almacen.md`](informe_migracion_almacen.md)).

| | |
| --- | --- |
| Configuración | [`configuracion/almacen_publico.json`](../configuracion/almacen_publico.json): ubicación, punto S3, bucket, dirección pública, objetos, huella de las teselas y CORS. Ningún programa lleva la dirección escrita |
| Bucket | `droneobservatory-almacen`, `nbg1`, lectura pública (política del bucket: solo `s3:GetObject`) |
| Dirección pública | <https://droneobservatory-almacen.nbg1.your-objectstorage.com> |
| Objetos | `europa-z14.pmtiles` (24 570 229 564 bytes, SHA-256 `393c9a0d…11c98`, `Cache-Control: public, max-age=3600`) y `estado.json` |
| CORS | `https://droneobservatory.eu` y `https://www.droneobservatory.eu`; GET y HEAD; cabecera `Range`; expone `ETag`, `Content-Range`, `Content-Length` y `Accept-Ranges` |
| Quién lo lee | La web (teselas y estado), los workflows `vigia-recogida` y `tests` (estado) |
| Quién escribe | La recogida horaria (`estado.json`) y `preparar_almacen.sh` (bucket y teselas) |

**Preparación**, con una orden desde Git Bash en la raíz del clon (repetible):

```
bash servidor/preparar_almacen.sh
```

Lleva las credenciales al servidor, crea el bucket con su política y su CORS, copia las
teselas (si ya están con la misma huella no las vuelve a subir), publica el último
`estado.json` y comprueba por la dirección pública el tamaño, la respuesta 206 a una
petición Range y el CORS de cada origen. Las teselas salen de la copia verificada
`C:\dev\eodi-teselas-copia\europa-z14.pmtiles` (desde este equipo, unos 10 minutos a
40 MB/s); la vía desde R2 ya no responde (401 desde el 3 de octubre de 2026). Preparado el
3 de octubre de 2026 a las 02:27 UTC.

**Credenciales.** La API de Hetzner Cloud no gestiona Object Storage (ni buckets ni
credenciales): las credenciales S3 se generan en la consola, en el proyecto EODI →
*Security* → *S3 credentials* → *Generate credentials*. El secreto solo se muestra una vez;
se guarda en `%USERPROFILE%\.eodi\almacen.env` como `ALMACEN_ID=<Access key>` y
`ALMACEN_SECRETO=<Secret key>`. Valen para todos los buckets del proyecto.

**Coste.** Tarifa de Hetzner (la de su página de Object Storage, consultada el 3 de octubre
de 2026; la API de precios de Hetzner Cloud no incluye Object Storage): precio base de
**6,49 € al mes sin IVA**, cobrado por horas mientras haya al menos un bucket y con ese
máximo al mes, con 1 TB de almacenamiento y 1 TB de tráfico de salida incluidos. Por encima
de la cuota, 6,26 € por TB y mes de almacenamiento y 1 € por TB de salida. La entrada, el
tráfico interno de eu-central (el servidor está en `nbg1`) y las llamadas a la API no se
cobran. La cuenta factura con un 21 % de IVA: **7,85 € al mes con IVA**.

Con lo que hay (24,57 GB de teselas más 2 kB de estado, el 2,5 % del almacenamiento incluido)
el coste es el precio base mientras la salida no pase de 1 TB al mes (unas 200 000 visitas
con unos 5 MB de teselas cada una); cada TB de salida más, 1 € sin IVA. La factura real se ve
en la consola de Hetzner, en *Billing*, a final de mes.

**Cambiar las teselas**: se sube el fichero nuevo con otro nombre, se cambian
`objetos.teselas` y `huellas_sha256` en la configuración, se despliega la web y después se
borra el objeto anterior.

## Dónde está cada cosa

Desde el 3 de octubre de 2026 la infraestructura está en tres sitios y ninguno es Cloudflare:

| Qué | Dónde |
| --- | --- |
| Servidor de recogida | Hetzner Cloud, proyecto EODI: `eodi-recogida`, CX33, `nbg1` |
| Almacén público (teselas y `estado.json`) | Hetzner Object Storage, bucket `droneobservatory-almacen`, `nbg1` (apartado «Almacén público») |
| DNS de `droneobservatory.eu` | Hetzner DNS, zona en el proyecto EODI (apartado «DNS») |
| Web | Vercel, proyecto `droneobservatory` |
| Código y datos | GitHub: `QuantuSync/droneobservatory` (público) y `QuantuSync/droneobservatory-datos` (privado) |
| Dominio | Registrado en Arsys, que también da el correo del dominio |

## DNS

El DNS autoritativo de `droneobservatory.eu` es Hetzner DNS desde el 3 de octubre de 2026
(informe en [`informe_migracion_almacen.md`](informe_migracion_almacen.md)). La zona se
gestiona con la API de Hetzner Cloud y el mismo token del proyecto (`hcloud_token.txt`):
`hcloud zone …`. La API antigua de DNS de Hetzner (`dns.hetzner.com`) cerró en mayo de 2026.

| | |
| --- | --- |
| Servidores de nombres | `hydrogen.ns.hetzner.com` (213.133.100.98), `oxygen.ns.hetzner.com` (88.198.229.192), `helium.ns.hetzner.de` (193.47.99.5) |
| Registros | [`configuracion/dns_droneobservatory.eu.zone`](../configuracion/dns_droneobservatory.eu.zone): web en Vercel (ápex A y `www` CNAME), CAA y correo de Arsys (MX, SPF, `autodiscover`, `autoconfig`, `webmail`) |
| TTL | 3600 s (1 hora) |
| DNSSEC | No. El registro .eu no tiene registro DS del dominio |
| Protección | La zona no se puede borrar sin quitar antes la protección |
| Registrador | Arsys: allí se cambian los servidores de nombres |

Órdenes:

```
export HCLOUD_TOKEN="$(tr -d '\r\n' < ~/.eodi/hcloud_token.txt)"
hcloud zone describe droneobservatory.eu          # servidores asignados y delegación
hcloud zone rrset list droneobservatory.eu        # registros
hcloud zone export-zonefile droneobservatory.eu   # la zona en formato BIND
```

Un cambio de registros se hace en el fichero de la zona y se aplica con
`hcloud zone import-zonefile droneobservatory.eu --zonefile configuracion/dns_droneobservatory.eu.zone`,
que sustituye todos los registros por los del fichero. Avisa `@: missing (@, NS)` porque el
fichero no lleva NS ni SOA: los pone Hetzner y los conserva. Si se borrara la zona, se
recrea con la orden de la cabecera del fichero.

Vercel no pide ningún TXT de verificación: el dominio está verificado y los certificados
(Let's Encrypt) se renuevan por el reto HTTP, sin tocar el DNS. Si Vercel cambiara los
valores que recomienda, los da su API:
`GET https://api.vercel.com/v6/domains/droneobservatory.eu/config`.

## Coste mensual en Hetzner

Precios de la API de precios de Hetzner Cloud y de la página de Object Storage, consultados
el 3 de octubre de 2026, sin IVA; la cuenta factura con un 21 % de IVA.

| Qué | Sin IVA | Con IVA |
| --- | --- | --- |
| Servidor CX33 (`nbg1`), con 20 TB de tráfico incluidos | 8,49 € | 10,27 € |
| Dirección IPv4 principal | 0,50 € | 0,61 € |
| Object Storage (precio base: 1 TB de almacenamiento y 1 TB de salida) | 6,49 € | 7,85 € |
| DNS | sin coste | sin coste |
| **Total** | **15,48 €** | **18,73 €** |

Sin copias de seguridad ni instantáneas de pago. Hasta el 3 de octubre de 2026 el servidor
era un CX23 (2 núcleos, 4 GB, 5,49 € sin IVA): una pasada de revisión murió por falta de
memoria el 2 de octubre y la recogida horaria sola llega a 3 GB de pico. El cambio a CX33
se hizo el 3 de octubre a las 07:40 UTC con el servidor apagado: misma IP, mismos datos.
Las horarias de las 08:17, 09:17, 10:17 y 11:17 terminaron bien, con picos de 2,9 a 3,1 GB
de los 7,7 GB disponibles; tardaron de 14,7 a 16,6 minutos (unos 12 antes del cambio),
con lo que publican hacia el minuto 33: sigue dentro de la ventana de los minutos 12 a 40.
Al cambiar de tipo Hetzner amplió también el disco a 80 GB, que no se puede reducir: para
volver a un CX23 hay que recrear el servidor con `reconstruir.sh` (con `SERVIDOR_TIPO="cx23"`
en `configuracion.sh`) y copiar antes `/home/eodi/datos`.

## Reintentos por fuente

Dentro de una ejecución, el descargador común
([`recogida/descarga.py`](../recogida/descarga.py)) espera el doble en cada reintento (5,
10, 20 y 40 s) y no reintenta 403 ni 404. Entre ejecuciones
([`recogida/reintentos.py`](../recogida/reintentos.py)):

- **Tope diario por sitio**: 40 reintentos al día entre todas las unidades, anotados en
  `/home/eodi/datos/reintentos/<sitio>.json` (variable `EODI_REINTENTOS_DATOS`, en
  `configuracion.sh`). Pasado el tope, ese día cada petición a ese sitio se hace una vez.
- **Espera creciente tras fallos seguidos** en la comprobación de la web oficial de cada
  canal de la capa de guerra: 1, 2, 4, 8 y 16 horas y después una vez al día; un rechazo
  (401, 403, 451 o una página de bloqueo), un día entero. Antes se repetía en cada lectura
  horaria y otra vez en el histórico.
- **Reanudaciones del archivo de adsb.lol** con 2, 4, 8, 16 y 32 s de espera.

Las cifras medidas antes del cambio están en
[`informe_migracion_almacen.md`](informe_migracion_almacen.md).

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
3. **Lote del histórico**: cuando el histórico de todos los canales está completo y la
   recogida ha procesado todo lo leído, la recogida horaria envía una sola vez al extractor,
   por lotes, los mensajes antiguos que el código no resuelve (presupuesto único de 5
   dólares, modo «guerra_historico», primero los objetivos de combustible, energía e
   industria) y deja la marca `guerra:lote_historico` en la base. No espera: cada recogida
   pregunta si el lote terminó y la primera que lo ve terminado lo incorpora y anota en la
   marca impactos, fallos y gasto. Nunca se retiene el cerrojo esperando al servicio.

Órdenes, como `operador`:

```
sudo systemctl start eodi-guerra.service          # una lectura ahora
journalctl -u eodi-guerra.service -n 60
sudo -u eodi sh -c 'cd /home/eodi/droneobservatory && .venv/bin/python -m recogida.canales_guerra resumen'
```

**Corrección de lo guardado.** Una vez por versión (cursor `guerra:correccion`), la recogida
horaria vuelve a leer con las reglas de ahora el mensaje de cada fuente de los impactos vigentes
(`recogida/guerra.corregir`): quita las fuentes que no describen un ataque con dron sobre un lugar
(homenajes, obituarios, memoria), retira con su motivo los impactos que se quedan sin fuentes y
rehace sus víctimas ([`informe_errores_datos.md`](informe_errores_datos.md)). Tarda unos 30
segundos y no lanza ningún trabajo aparte.

**Histórico y relectura en la recogida horaria.** Cada hora, después de lo nuevo, la recogida
lee con lo que quede de su tope (como mucho 150 s) las publicaciones guardadas que aún no tienen
registro (el histórico que el lector añade hacia atrás) y las leídas con otra versión del
analizador o del nomenclátor: un cambio de reglas llega solo a todo lo guardado en unas horas
([`informe_errores_datos.md`](informe_errores_datos.md), bloque 2). El reproceso de abajo solo
hace falta para tenerlo todo en una pasada.

**Reprocesar todo** (tras cambiar el analizador, el nomenclátor o las palabras corrientes) y,
con `lote`, enviar ya el lote del histórico sin esperar a que el histórico termine (solo lo
envía si no se envió antes; lo incorpora la recogida horaria).
[`servidor/guerra_reproceso.sh`](../servidor/guerra_reproceso.sh) toma el cerrojo de la
recogida, descarga la base de la rama `estado` y la vuelve a subir; la recogida siguiente
publica el resultado:

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
`estado.json` en el almacén público ([`recogida/salud.py`](../recogida/salud.py), que toma
la dirección de `configuracion/almacen_publico.json`).
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
