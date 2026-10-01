# Tráfico aéreo medido, respuesta militar, interferencia GNSS y meteorología

Fecha: 1 de octubre de 2026. Rama `trafico-aereo`, PR #33.

Cada incidente europeo de la base lleva ahora lo que dicen los datos físicos: el tráfico aéreo
real del archivo de adsb.lol alrededor de su hora (cierre medido del aeropuerto, aeronaves en
espera, aproximaciones frustradas, desvíos), las aeronaves militares que emitían cerca, la
interferencia GNSS de su zona y las condiciones meteorológicas y astronómicas de su lugar y su
hora. Todo con origen «medido» y método «regla», con la versión de la regla. Es la base física
del futuro motor de deducción. En la web solo sale el cierre medido; el resto es interno, para
AEGIS.

## 1. El archivo de adsb.lol, comprobado con ficheros reales

- **Repositorios y publicaciones.** Uno por año: `adsblol/globe_history_2024`, `_2025` y `_2026`
  (licencia ODbL 1.0 en GitHub). Cada día tiene varias publicaciones:
  `v2025.09.22-planes-readsb-prod-0`, `...-staging-0` y, en algunos días de mayo y junio de 2025,
  `...-prod-0tmp`, más `...-mlatonly-0` (solo MLAT, no se usa). Los últimos días de diciembre
  están también en el repositorio del año siguiente. Contadas el 1 de octubre de 2026 con la API
  de GitHub: 946 publicaciones en 2025 y 837 en 2026.
- **Ficheros.** Un tar partido en trozos de 2 GB (`.tar.aa`, `.tar.ab`) o entero (`.tar`) en los
  días pequeños. Dentro: `README.txt`, las licencias (ODbL y CC0 de los receptores), `acas/`,
  `heatmap/` (49 ficheros de repetición, unos 900 MB que se saltan) y `traces/xx/trace_full_<icao>.json`,
  una traza por aeronave y día en JSON comprimido con gzip (67 615 trazas el 22 de septiembre de
  2025, 13 525 de ellas en Europa).
- **Traza.** Cabecera con `icao`, `r` (matrícula), `t` (tipo OACI), `dbFlags` (bits: 1 militar,
  2 interesante, 4 PIA, 8 LADD), `desc`, `ownOp`, `year`, `version` de readsb y `timestamp`
  (inicio del día). `trace` es una lista de puntos de 14 campos: segundos desde `timestamp`,
  latitud, longitud, altitud barométrica en pies (o `"ground"`, o null), velocidad sobre el suelo,
  rumbo, marcas (1 posición antigua, 2 inicio de tramo, 4 velocidad vertical geométrica, 8
  altitud geométrica), velocidad vertical, datos de la aeronave (null salvo cuando cambian), fuente
  de la posición (`adsb_icao`, `mlat`, `tisb_icao`...), altitud geométrica, velocidad vertical
  geométrica, velocidad indicada y alabeo. Los datos de la aeronave llevan `nic`, `rc`, `nac_p`,
  `nac_v`, `sil`, `sil_type`, `version` (DO-260), `flight` (indicativo), `category`, `squawk`,
  `nic_baro`, `gva`, `sda`... En una muestra de 3000 trazas, el 25 % de los puntos los traen; hay
  puntos repetidos con el mismo instante, uno con esos datos. NIC, NACp, versión e indicativo se
  arrastran de su último valor.
- **Tamaño.** De 0,24 a 4,28 GB por día (mediana 3,30 GB) en prod-0 desde diciembre de 2024. Se
  descarga a unos 50 MB/s desde el servidor: el día entero en poco más de un minuto.
- **Hora de publicación.** prod-0 sale entre las 03:01 y las 03:26 UTC del día siguiente (la
  mediana, 3 h 26 min después de medianoche); nueve de cada diez días antes de las 00:40 del
  día siguiente a ese; el más tardío, el 18 de diciembre de 2025, 26 días después.
- **Días que faltan.** Sin ninguna publicación: el 6 de mayo de 2026. Sin prod-0 pero con
  prod-0tmp: del 28 de mayo al 10 de junio de 2025. Incompletos (mucho más pequeños): el 5 de
  mayo de 2026 (0,24 GB), el 11 de junio de 2025 (0,73 GB) y el 7 de mayo de 2026 (1,08 GB); su
  cobertura sale insuficiente por sí sola. El código usa prod-0, prod-0tmp donde no hay prod-0 y
  staging-0 si es más de un 10 % mayor (adsb.lol pide usar la que no sea mucho menor); un día sin
  publicar se vuelve a mirar cada hora y, tres días después, se da por perdido.
- **Licencia.** ODbL 1.0 (© adsb.lol contributors); los receptores ceden sus datos con CC0. La API
  en tiempo real anuncia que pedirá una clave (sin fecha); no se usa.

## 2. Qué se publica y con qué licencia

- En `incidentes.geojson` e `incidentes_sin_ubicacion.json`, solo el bloque `trafico_aereo` de
  los incidentes con un cierre medido válido (resultado `cierre_medido` y cobertura alta o media):
  aeropuerto, inicio y fin, duración, vuelos desviados, vuelos en espera, si difiere de lo
  declarado y los enlaces a las publicaciones de adsb.lol usadas. Además, la fuente «Tráfico aéreo
  medido (adsb.lol)» y sus afirmaciones públicas (cierre, minutos, desviados) aparecen en «qué dice
  cada fuente» junto a las de la prensa.
- Ese bloque es una base de datos derivada del archivo de adsb.lol: se ofrece con ODbL 1.0
  (`LICENSE-DATOS`), atribuyendo «© adsb.lol contributors» en la web. El resto de los datos sigue
  con CC BY 4.0.
- Open-Meteo (CC BY 4.0, «Weather data by Open-Meteo.com»), METAR del IEM (dominio público),
  OurAirports (dominio público), la referencia de EUROCONTROL (uso no comercial con mención, sin
  modificarla: no se publica ninguna cifra suya) y la biblioteca traffic (MIT) figuran en los
  créditos de la web. Detalle en `docs/licencias_terceros.md`.
- No se publica: las trazas, las anomalías candidatas, la respuesta militar, la interferencia
  GNSS, la cobertura, las condiciones meteorológicas ni las interrupciones que no casan con un
  incidente.

## 3. Procesado en el servidor

`servidor/trafico.sh`, lanzado por `eodi-trafico.timer` en el minuto 40 de cada hora como `eodi`
(`Nice=15`, `IOSchedulingClass=idle`), con su propio cerrojo (`trafico.lock`): nunca toma el de
la recogida horaria, que sigue a su hora mientras el procesado trabaja. Cada ejecución procesa
días de la cola hasta 50 minutos. Por día, en una sola pasada y en flujo (`recogida/adsb.py`,
`recogida/trafico.py`):

1. Localiza la publicación (peticiones HEAD a GitHub, sin la API) y lee los trozos seguidos.
2. Descarta las trazas que no tocan la zona de cálculo (25° O–45° E, 34°–72° N: Europa,
   Turquía, Ucrania, Moldavia y Chipre) y recorta las demás con 5° de margen.
3. Movimientos en los 926 aeropuertos de `configuracion/aeropuertos_trafico.json` (los grandes y
   medianos de OurAirports de Europa, Turquía y Chipre con código OACI, sin Rusia ni Bielorrusia;
   516 con tráfico regular; los de Ucrania aunque no tengan vuelos): aterrizajes, despegues,
   frustradas, desvíos y esperas (`proceso/vuelos.py`, apartado 5).
4. Aeronaves por celda H3 y hora con la posición degradada (`proceso/gnss.py`).
5. Aeronaves militares, con su traza cada 30 s.
6. Trazas filtradas: los puntos en tierra o por debajo de 10 000 pies a 40 km o menos de un
   aeropuerto con tráfico regular o de un incidente, o a 60 km de un incidente que no es
   aeropuerto, cada 20 s, codificadas por diferencias (`trazas.txt.gz`; se leen con
   `recogida.trafico.leer_trazas`).
7. METAR del día de los 926 aeropuertos (IEM, en tandas de 60, una petición cada 2 s; 736
   estaciones con METAR el 22 de septiembre de 2025).
8. `resumen.json` al final, que marca el día como hecho.

La recogida horaria, que ya tiene la base abierta con su cerrojo, lee esos ficheros y escribe en
la base los resultados agregados (`recogida/mediciones.py`, `proceso/mediciones.py`). Escribir es
cosa de segundos: el procesado pesado no retiene nunca el cerrojo principal. Lo comprueban
`tests/test_trafico_servidor.py` (en Linux: el procesado corre con el cerrojo de la recogida
ocupado y lo deja libre mientras trabaja) y la CI.

**Consumo medido** (22 de septiembre de 2025, un núcleo, CX23 con 2 vCPU y 4 GB):

| | |
| --- | --- |
| Duración por día | 590 s (632 s con dos días a la vez) |
| CPU por día | 545–555 s |
| Memoria máxima | 265–272 MB |
| Descarga por día | 3,46 GB en flujo, nada en disco |
| Disco por día | unos 16 MB (trazas 14,3 MB, militares 1,3 MB, movimientos 0,6 MB, GNSS 0,4 MB, METAR 0,4 MB) |

Un día tarda unos 10 minutos de un núcleo, frente al tope de 6 horas: **no hizo falta subir de
máquina**. La recogida horaria (5–7 minutos de un núcleo por hora) tiene el otro núcleo y va
siempre por delante por prioridad. Disco: 2,3 GB usados y 34 GB libres antes de empezar.

## 4. Base de datos y esquema 1.5.0

(Ver la descripción de cada campo en `esquema/1.5.0/comun.schema.json`.)

- `trafico_aereo` (tabla con historial, una fila por incidente): `cierre` (resultado
  `cierre_medido`, `sin_interrupcion`, `cobertura_insuficiente`, `sin_linea_base`, `sin_datos` o
  `no_aplicable`, con horas, duración, desvíos, esperas, frustradas, llegadas y salidas perdidas,
  línea base, cobertura, motivos meteorológicos, lo declarado y las diferencias),
  `respuesta_militar` y `interferencia_gnss`, con la ventana, las publicaciones de adsb.lol usadas,
  `origen` medido, `metodo` regla, `regla` (nombre y versión) y una huella de lo que se usó: si no
  cambia, no se vuelve a evaluar.
- `condiciones` (tabla con historial): por incidente, el lugar (punto, o el aeropuerto si no
  tiene) con meteorología, METAR y sol y luna; por ataque RU→UA, las zonas de lanzamiento y de
  impacto con su viento.
- `anomalias_trafico` (tabla con historial): cada interrupción de un aeropuerto con su estado
  (`casada` con un incidente, `meteorologia` o `candidata`). Interna.
- `cobertura_trafico` y `gnss_diaria`: una fila por aeropuerto y día o por celda y día, solo
  inserción (una regla nueva es otra fila). En `gnss_diaria` solo entran las celdas con el mínimo
  de aeronaves del día y al menos una degradada además de la que se resta; un día sin ninguna deja
  una fila de control. La serie completa por celda y hora queda en el servidor.
- Fuente nueva por medición: «Tráfico aéreo medido (adsb.lol)», fiabilidad B, credibilidad 2 con
  cobertura alta y 3 con media (con cobertura insuficiente no hay fuente ni afirmaciones), con tres
  afirmaciones (`cierre`, `cierre_minutos`, `vuelos_desviados`) de origen medido y método regla,
  que se guardan junto a las de la prensa: si difieren, quedan las dos y `diferencias` lo dice.
  Las condiciones, como fuente «Condiciones medidas (Open-Meteo, METAR del IEM)», interna.
- `estado.json`: fuentes `trafico_aereo` (hora del último día procesado; con aviso si pasan más de
  48 horas sin ninguno) y `condiciones` (última petición correcta). Un fallo de cualquiera de las
  dos no cambia el resultado de la recogida horaria.
- Exportación semanal para AEGIS: lleva los bloques completos (también lo interno), su procedencia
  (medido, regla) y las afirmaciones medidas como vigentes.

## 5. Reglas y umbrales

### 5.1 Movimientos de cada aeronave (`proceso/vuelos.py`)

Una traza se parte en tramos: marca de tramo nuevo de readsb, hueco de más de 30 minutos, hueco
de más de 10 minutos con el avión por debajo de 5000 pies a ambos lados (una escala sin cobertura
en tierra) o más de 10 minutos parado en tierra. Altitud sobre el aeropuerto más cercano a 15 km
o menos, para los puntos por debajo de 8000 pies.

| Movimiento | Regla |
| --- | --- |
| Aterrizaje | El tramo acaba junto al aeropuerto por debajo de 2500 pies sobre él, tras estar más alto o más lejos, y baja a 1500 pies o menos (o toca tierra). Hora: primer punto en tierra o último en el aire |
| Despegue | El tramo empieza junto al aeropuerto en tierra o a 1500 pies o menos y sube por encima de 2500. Hora: último punto en tierra o primero en el aire |
| Sin cobertura a baja altura | Si no se cumple lo anterior: el tramo acaba a 30 km o menos de un aeropuerto con tráfico regular, por debajo de 6000 pies sobre él, acercándose 3 km o más y bajando 1000 pies o más en sus últimos 5 minutos (aterrizaje), o empieza así alejándose y subiendo (despegue). Hora estimada con la distancia y la velocidad, como mucho 15 minutos |
| Aproximación frustrada | Tras haber estado por encima de 3000 pies sobre el aeropuerto, baja a 1000 pies o menos a 8 km o menos de un umbral, alineada con su pista (25°), a más de 80 nudos y sin tocar tierra, y vuelve a subir por encima de 2000 pies en 10 minutos o menos sin alejarse más de 25 km ni huecos de más de 2 minutos (el criterio de traffic: dos intentos alineados con la pista con una subida entre ellos) |
| Espera | El detector de traffic sin cambios: ventanas de 6 minutos cada 2, al menos 5 minutos de datos, 30 muestras del cambio de rumbo acumulado y su red (pesos en `configuracion/espera_traffic.json`). Se evalúa solo donde el giro acumulado llega a 180° (la red da menos de 0,01 por debajo). Se asigna al aeropuerto de llegada si está a 120 km o menos; si no, al aeropuerto regular más cercano en ese radio |
| Desvío | El tramo acaba en B, pero antes hizo una espera asignada a otro aeropuerto A (a 50 km o más de B), o bajaba hacia A (a 40 km o menos y por debajo de 8000 pies sobre él, con el rumbo a 20° o menos de A y a más de 45° del de B, acercándose y bajando de un minuto al siguiente) y luego se alejó 20 km de su punto más cercano a A |

Solo cuentan los aviones de transporte y de negocios (categoría de emisor A2 a A6; ni ligeros, ni
helicópteros, ni militares): los que vuelan en IFR y cuenta la referencia de EUROCONTROL.

Comprobado con trazas reales del 22 de septiembre de 2025 (`tests/test_trafico.py`): NOZ948
aterriza en Kastrup a las 17:03 y sale como NOZ949 a las 17:50 sin puntos en tierra; SAS652 hace
una frustrada en Kastrup a las 18:28 (empezaba el cierre) y aterriza en Malmö a las 18:52; RYR1EE
espera dos veces sobre Øresund (18:39–18:48 y 18:49–19:14) y aterriza en Billund a las 19:48
(desvío); una salida de Oslo vista por primera vez a 2100 pies sobre la pista y una llegada a
Atenas perdida a 5000 pies cuentan con su hora estimada.

Ajustes hechos con los datos reales del primer día procesado (22 de septiembre de 2025, toda
Europa):

- Con la primera versión salían 10 828 frustradas y 521 desvíos en un día. Casi todas las
  frustradas eran escalas sin cobertura en tierra (el avión baja, desaparece 40 minutos y vuelve
  a subir) y subidas iniciales de despegues; con el corte por escala, la exigencia de haber estado
  arriba antes y la continuidad, quedaron 347 (el 1,4 % de los aterrizajes), y los desvíos, 277. La
  línea base resta lo que sale un día normal.
- Los desvíos por geometría no ven a los aviones que se desviaron sin bajar cerca del aeropuerto
  (en Copenhague, casi todos fueron a Malmö tras esperar sobre Øresund). Por eso el recuento de
  desvíos de una interrupción suma los aviones que aterrizan en otro aeropuerto con un indicativo
  que las semanas anteriores aterrizaba en este a esa hora (5.2).
- Con la primera versión, Oslo salía con 277 llegadas y 1 salida, Atenas con 407 salidas y ninguna
  llegada y Palma sin nada: en esos aeropuertos los receptores de adsb.lol no ven los aviones por
  debajo de unos miles de pies, o solo en un sentido. Con la regla «sin cobertura a baja altura»,
  Oslo pasa a 337 llegadas y 312 salidas (cobertura 0,91), Atenas a 101 llegadas y 435 salidas
  (0,60) y Palma a 76 movimientos (0,09: sigue insuficiente, como debe). En Kastrup, con buena
  cobertura, no cambia nada (2 salidas más).

### 5.2 Cobertura, línea base e interrupciones (`proceso/trafico.py`)

| | |
| --- | --- |
| Cobertura | Aterrizajes y despegues IFR vistos / vuelos IFR de EUROCONTROL ese día (si aún no está publicado, la mediana del mismo día de la semana de sus cuatro últimas semanas; si el aeropuerto no está en EUROCONTROL, la mediana propia de la línea base). Alta desde 0,80, media desde 0,50; con la mediana propia, media como mucho (mediana de 20 movimientos o más y el día a 0,75 de ella). Con cobertura insuficiente no se interpreta ningún hueco |
| Línea base | Mediana por franja de 15 minutos del mismo día de la semana de las cuatro semanas anteriores; al menos dos de esos días procesados y con cobertura |
| Franja baja | Base de 2 movimientos o más y se ve el 30 % o menos |
| Interrupción | Franjas bajas seguidas (con una intermedia a la mitad de su base como mucho) cuya base suma 6 movimientos o más y se ve el 30 % o menos |
| Inicio y fin | El mayor hueco sin movimientos alrededor del tramo, si cubre la mitad del tramo o más (último movimiento antes, primero después); si no, los bordes de las franjas |
| Desvíos | Desvíos de trayectoria hacia el aeropuerto más aterrizajes en otro aeropuerto de indicativos que aterrizaron en este, a esa hora con dos horas de margen, en al menos dos de las cuatro semanas anteriores; desde 30 minutos antes del inicio hasta 15 después del fin |
| Esperas | Esperas asignadas al aeropuerto o de esos indicativos, desde 30 minutos antes del inicio hasta el fin |
| Exclusión meteorológica | Algún METAR del aeropuerto de una hora antes del inicio al fin con niebla, visibilidad menor de 550 m, techo por debajo de 200 pies, tormenta, granizo, nieve o engelamiento, viento medio de 35 nudos o rachas de 45, o pista contaminada |
| Cierre de un incidente | Interrupción del aeropuerto del incidente que se solapa con él con una hora de margen, en su ventana (dos horas antes y cuatro después, o el día UTC si solo se sabe el día); si hay varias, la de más movimientos perdidos |
| Diferencia con lo declarado | Duración: fuera del rango declarado en más de 15 minutos y más de un 25 %. Desvíos: fuera en más de 2 vuelos y más de un 30 %. Cierre declarado «no» con cierre medido |
| Anomalía candidata | Interrupción de un aeropuerto regular con cobertura que no casa con ningún incidente (de su aeropuerto o a 25 km o menos) ni la explica el tiempo |

### 5.3 Respuesta militar

Aeronaves con la marca militar de adsb.lol o con un tipo solo militar (cazas, aviones radar,
cisternas, patrulla marítima, drones, helicópteros de combate, transportes militares) a 150 km o
menos del incidente desde dos horas antes de su inicio hasta dos horas después de su fin: tipos,
clases, número, primera aparición y distancia mínima. La ausencia no demuestra nada
(`ausencia_no_concluyente`).

### 5.4 Interferencia GNSS

Una aeronave tiene la posición degradada en una celda H3 de resolución 4 (la de gpsjam.org) y una
hora si alguna de sus posiciones ADS-B allí (versión 1 o posterior, en el aire) trae NIC menor que 7
o NACp menor que 8 (los mínimos de ADS-B Out de la FAA, 14 CFR 91.227; el umbral NIC < 7 de Liu, Lo
y Walter, ION ITM 2022). Proporción = (degradadas − 1) / aeronaves, como gpsjam.org; mínimo de 5
aeronaves por celda y hora y 20 por celda y día. Niveles: por debajo del 2 % sin interferencia, del
2 al 10 % media, más del 10 % alta. En el incidente, su celda y las seis vecinas durante el
incidente. Ni gpsjam.org ni Flightradar24 publican su umbral por aeronave (el primero dice que usa
NACp, el segundo NIC, sin cifra), así que el nuestro es el de la norma.

## 6. Meteorología, METAR, sol y luna

- **Open-Meteo**, Historical Forecast API, modelo por defecto: superficie (temperatura, humedad,
  precipitación, nubosidad, viento y rachas a 10 m, viento a 100 m) y niveles de presión de 1000,
  925, 850 y 700 hPa (viento y temperatura). Comprobado el 1 de octubre de 2026: la Historical
  Weather API (ERA5) no da niveles de presión; la Historical Forecast sí, completos el 10 de
  octubre y el 30 de noviembre de 2022, el 1 de junio de 2023 y el 2 de enero de 2025 en Kursk, y
  en los incidentes probados de 2025 y 2026: cubre todo el periodo de los incidentes (desde septiembre
  de 2024) y de la capa de guerra (desde octubre de 2022). Lo que llegue vacío se guarda vacío.
- **Límites**: 600 llamadas por minuto, 5000 por hora y 10 000 por día; una petición de más de 10
  variables cuenta como varias. Cada ejecución horaria pide como mucho 300 unidades (las 21
  variables de un incidente son 2,1; el viento de 10 variables de un punto de la capa de guerra,
  1). Caché en el servidor por punto y día.
- **METAR**: los del día procesado (todas las estaciones) o, si no, los de la estación pedidos al
  IEM. Estación: el aeropuerto del incidente o el más cercano a 50 km o menos. Con hora: el METAR a
  una hora o menos; con solo el día, el de peor visibilidad.
- **Sol y luna**: elevación del sol (NOAA), luz (día por encima de −0,833°, crepúsculo hasta −12°,
  noche), altura y fracción iluminada de la luna (Meeus). Con solo el día: horas de luz y fracción
  iluminada a mediodía.
- **Capa de guerra**: viento a 10 y 100 m y en 925, 850 y 700 hPa en las zonas de lanzamiento que
  nombra el parte (19 aeródromos y polígonos con sus raíces en ucraniano en
  `configuracion/lugares_meteo_ucrania.json`; un nombre de región o de mar no tiene punto), a la
  hora de inicio del periodo, y en las capitales de las regiones del ataque, a la mitad del periodo.
- Prueba con los servicios reales sobre la base del 1 de octubre (sin subir nada): con un cupo de
  12 unidades se evaluaron los 7 incidentes más recientes (dos sin lugar, que lo declaran), con
  METAR de Lublin y de Chisinau y los niveles de presión completos.


## 7. Validación con casos reales

47 días procesados en el servidor para validar: los 11 días de los casos (22–26/09, 2–4/10,
4–5/11 y 22/11/2025) y su línea base de cuatro semanas, con dos procesos en paralelo y prioridad
baja mientras la recogida horaria seguía a su hora. Horas oficiales o mejor documentadas
(policía, gestores de navegación y aeropuertos, o Reuters, AP, AFP, TV2, NRK y NL Times
citándolos), en UTC. «Medido» es lo que sale de la regla final.

| Caso | Oficial (UTC) | Medido | Esperas, desvíos y frustradas | Cobertura | Resultado |
| --- | --- | --- | --- | --- | --- |
| Copenhague, 22/09 (EODI-2025-00154) | 18:26–22:20; unos 50 desviados (Flightradar24 vía Reuters; el aeropuerto dijo 31) | **18:26–22:38**, 252 min; 136 de 138 movimientos esperados perdidos | 13 en espera, **48 desviados**, 1 frustrada (SAS652, 18:28) | alta (0,98) | **Acierto.** Inicio exacto; el fin medido es el primer aterrizaje, 18 min tras la reapertura oficial. La base decía 35 desviados: la diferencia queda marcada |
| Oslo, 22–23/09 (EODI-2025-00042) | ~22:00–01:00/01:30 (medianoche a 03:00–03:30 local); llegadas desviadas, aviones en espera | — | **9 desviados** en la ventana | alta (0,91) | **No medible, declarado** (`sin_trafico_esperado`): de madrugada Gardermoen casi no tiene vuelos (2,5 movimientos esperados en la hora del incidente). Los 9 desviados casan con los «12 vuelos afectados» de la prensa |
| Aalborg, 24/09 (EODI-2025-00228) | 19:44–23:00; 3 desviados | — | 1 en espera, **2 desviados** | media (0,90) | **No medible** (`sin_trafico_esperado`): 3 movimientos esperados en toda la noche. Desvíos casi iguales a los declarados |
| Aalborg, 25–26/09 (segundo cierre) | 21:40–22:35; 2 desviados | — | — | media | **Sin incidente en la base** para esa noche; tampoco habría tráfico que medir |
| Billund, 25/09 (EODI-2025-00291) | 02:21–03:21 | — | 1 desviado | media (1,03) | **No medible** (`sin_trafico_esperado`): 1 movimiento esperado a esa hora |
| Múnich, 2/10 (EODI-2025-00277, solo el día) | 20:18 (pistas cerradas 20:35) hasta la madrugada; 15 desviados, 17 cancelados | **21:15–21:45**, 30 min (antes, 20:30–20:57 sin llegar a significativa) | 6 en espera, **12 desviados** | alta (0,97) | **Acierto parcial.** El cierre empezó al final de la última oleada de la tarde y siguió en el toque de queda nocturno (de 22:00 a 04:00 UTC no hay vuelos): solo se ven los últimos movimientos perdidos. Los desviados medidos (12) se acercan a los oficiales (15) |
| Múnich, 3/10 | ~19:30 restricción y parada hasta las 05:00; 23 desviados | **19:30–21:45**, 135 min, 97 de 97 movimientos perdidos | 6 en espera, **31 desviados** | alta (0,95) | **Acierto en la hora de inicio** (exacta). No hay incidente de Múnich del 3/10 en la base: queda como anomalía candidata, sin causa |
| Bruselas, 4/11 (EODI-2025-00072, solo el día) | ~19:00–20:30 y 21:00–22:15 (skeyes); 24 desviados (aeropuerto) | **18:45–22:00** (195 min, por franjas), 78 de 85 movimientos perdidos; después, 22:28–00:26 (118 min) | 8 en espera, **17 desviados**, 1 frustrada en el primero; 5 desviados en el segundo | alta (0,88) | **Acierto.** Inicio 15 min antes de la hora redonda de la prensa y fin 15 min antes de la reapertura oficial; la media hora de reapertura entre los dos cierres no llega a verse (casi no hubo movimientos), así que los dos cierres salen como un solo hueco. El incidente toma ese hueco; el de después queda en `anomalias_trafico`. 22 desviados en total frente a 24. Con la línea base sin alinear a la hora local (el 4/11 ya es horario de invierno y dos de las cuatro semanas de base no) salían dos huecos de 89 y 95 min |
| Lieja, 4/11 | ~19:00/19:30–20:00/20:30 y desde ~21:00; reapertura final sin verificar | **19:09–00:45** sin tráfico | 8 en espera, **11 desviados** (DHL a Maastricht y Colonia) | alta (0,87) | **Acierto, sin incidente en la base**: no hay incidente de Lieja del 4/11 (está dentro del de Bruselas), así que queda como anomalía candidata. Lieja es un aeropuerto de carga con poco tráfico de tarde: el hueco medido cubre las dos interrupciones y la noche |
| Eindhoven, 22/11 (EODI-2025-00051, solo el día) | 18:00–21:30/22:00; 6 desviados | ninguna interrupción | — | media (0,90, mediana propia) | **Fallo explicado**: por la tarde Eindhoven tiene muy pocos vuelos por franja (menos de 2 de base en cada una), así que no hay tramo bajo que detectar; con solo el día no se pueden calcular los indicios de la hora del incidente |
| Vilna, 25/09 (EODI-2025-00060) | 15:57–16:11 (14 min) | — | — | alta | **No medible**: 4 movimientos esperados en 14 minutos, por debajo del mínimo de 6 de una interrupción |
| Copenhague, 24/09 (EODI-2025-00172, solo el día) | sin cierre conocido | ninguna interrupción significativa | — | alta | **Acierto** (con la primera regla casaba un bajón de 15 minutos a las 04:15) |

Resumen: de los ocho cierres oficiales con tráfico que interrumpir (Copenhague, Múnich ×2,
Bruselas ×2, Lieja, Eindhoven y Oslo; Aalborg y Billund caen de noche), la regla mide bien el
inicio en seis (Copenhague, Múnich 3/10, los dos de Bruselas como un solo hueco, Lieja y, tarde,
Múnich 2/10) y falla en
Eindhoven por falta de tráfico por franja y en Oslo por la hora. Las horas medidas quedan a 0–20
minutos de las oficiales; el fin medido es el primer movimiento tras la reapertura, así que
tiende a salir algo más tarde. Los desvíos medidos se quedan algo por debajo de los oficiales
(48/50, 12/15, 31/23, 22/24): un vuelo desviado que no llega a bajar cerca ni tiene un
indicativo habitual no se cuenta. En ningún caso la meteorología explicaba el hueco. La respuesta
militar no se puede validar con fuentes abiertas: en Copenhague solo se vieron dos A400M alemanes
de paso a más de 130 km; en Bruselas, 88 aeronaves militares en 150 km a lo largo del día (E-3,
F-16, KC-135, RC-135, un MQ-9...), lo normal en Bélgica. La interferencia GNSS fue nula o baja en
todos los aeropuertos de los casos.

**Ajustes hechos con estos casos** (no con suposiciones):

- Un avión que aterrizó a las 19:25 en mitad del cierre de Copenhague partía el hueco en dos: se
  admiten movimientos sueltos dentro (el 3 % de los esperados), recortando los pegados a los
  bordes.
- Las ventanas que pasan de medianoche (Copenhague, Aalborg, Oslo) dejaban el incidente sin
  línea base: la línea base se calcula franja a franja con las semanas disponibles y la cola del
  histórico añade el día siguiente y su línea base; la ventana se recorta a los días procesados y
  con cobertura.
- Aalborg y Billund, que no están en EUROCONTROL, se quedaban sin línea base por una cadena de
  coberturas: un día de su línea base vale si tiene 20 movimientos o más.
- Con solo el día, un bajón de 15 minutos a las 04:15 casaba con el incidente de Copenhague del
  24/09: con solo el día, solo casa una interrupción significativa.
- De madrugada no se distingue un cierre: resultado `sin_trafico_esperado` (antes
  `sin_interrupcion`, que era engañoso) y, como indicios internos, las esperas y desvíos de la
  ventana (Oslo, 9 desviados).
- Múnich el 3/10 perdió 97 de 97 movimientos con algún movimiento suelto y salía como «menor»: es
  significativa también la interrupción en que se pierde el 80 % o más.
- Ámsterdam, Gatwick y Copenhague salían interrumpidos entre las 04:30 y las 05:45 UTC los días
  tras el cambio de hora del 26/10: la línea base compara ahora la misma hora local.
- Una traza dañada del 15/10/2025 tumbaba el día, y su prod-0 se corta siempre en el mismo byte
  (el tar quedaba leído a medias sin error): una traza ilegible se salta y se cuenta, una
  descarga que no llega entera nunca se da por buena (se reanuda si la conexión se corta) y, si
  una publicación no se lee entera, se usa la otra (aquí, staging-0).

## 8. Cobertura de adsb.lol por aeropuerto

En los 47 días con resumen de la validación, 337 aeropuertos con referencia de EUROCONTROL:
131 con cobertura alta (mediana del índice ≥ 0,80), 62 media y 144 insuficiente. La mitad de los
aeropuertos de EUROCONTROL tienen índice ≥ 0,77; los grandes de Europa occidental y central,
0,94–0,99.

Los 30 de más tráfico (movimientos IFR diarios de EUROCONTROL, mediana; índice mediano y mínimo):

| Aeropuerto | Ref. | Índice | Mín. | | Aeropuerto | Ref. | Índice | Mín. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LTFM Estambul | 1584 | 0,44 | 0,21 | | LSZH Zúrich | 794 | 0,94 | 0,89 |
| EHAM Ámsterdam | 1434 | 0,97 | 0,94 | | EIDW Dublín | 784 | 0,98 | 0,93 |
| EDDF Fráncfort | 1388 | 0,94 | 0,93 | | LTFJ Sabiha Gökçen | 782 | 0,03 | 0,00 |
| LFPG París CDG | 1382 | 0,94 | 0,92 | | LOWW Viena | 780 | 0,95 | 0,90 |
| EGLL Heathrow | 1348 | 0,99 | 0,96 | | ENGM Oslo | 725 | 0,84 | 0,75 |
| LEMD Madrid | 1218 | 0,96 | 0,85 | | LIMC Malpensa | 682 | 0,95 | 0,92 |
| LEBL Barcelona | 1066 | 0,97 | 0,94 | | LPPT Lisboa | 666 | 0,96 | 0,91 |
| EDDM Múnich | 1030 | 0,96 | 0,94 | | LFPO Orly | 654 | 0,97 | 0,95 |
| LIRF Roma | 951 | 0,96 | 0,95 | | ESSA Estocolmo | 649 | 0,94 | 0,89 |
| LTAI Antalya | 946 | 0,94 | 0,00 | | EGCC Mánchester | 629 | 0,98 | 0,94 |
| LEPA Palma | 908 | 0,48 | 0,05 | | EPWA Varsovia | 611 | 0,97 | 0,93 |
| LGAV Atenas | 902 | 0,60 | 0,54 | | EBBR Bruselas | 607 | 0,97 | 0,88 |
| EGKK Gatwick | 810 | 0,97 | 0,95 | | EGSS Stansted | 606 | 0,97 | 0,93 |
| EKCH Copenhague | 796 | 0,97 | 0,93 | | EDDB Berlín | 588 | 0,94 | 0,89 |
| | | | | | LEMG Málaga | 566 | 0,95 | 0,91 |

Turquía (Estambul, Sabiha Gökçen; Antalya con días sin datos), Palma (sin receptores en la isla
que vean los aviones bajos) y Atenas tienen poca cobertura: allí un hueco solo se interpreta los
días con cobertura suficiente.

Aeropuertos de incidentes (46 días; índice mediano y días por nivel):

| Cobertura | Aeropuertos |
| --- | --- |
| Alta casi siempre | EBBR 0,97, EBCI 0,94, EBLG 0,94, EDDB, EDDF, EDDK, EDDL, EDDM, EDDP, EDDV 0,93, EFHK, EGLL, EGPH, EGLC, EHAM, EIDW, EINN, EKCH 0,97, ELLX, ENGM 0,85, EVRA 0,89, LBSF, LCLK, LCPH, LFBO, LKPR, LROP |
| Alta o media | BIKF 0,80, EDDC 0,80, EDDE 0,74, EDDW 0,77, EGHI 0,85, ENBR 0,81, EPLB 0,75, EPRZ 0,82, EYVI 0,72, LEAL, LEIB 0,75, LEZL 0,75, ENZV 0,65 (media) |
| Media con la mediana propia (sin EUROCONTROL) | EKYT 1,02, EKBI 0,98, EHEH 0,95, EDJA, EDLV, EDSB (días de media e insuficiente) |
| Insuficiente | LEPA (a medias), LIMZ, EYPA, ESNN, EGSH, LXGB (Gibraltar, 10 movimientos al día), y sin ningún movimiento visto: EKKA (Karup), ENAT, ENBN, ENDU, ENSH (norte de Noruega), LBWN (Varna), LRIA (Iasi), LUKK (Chisinau) y las bases militares EGUL, EHGR, EHVK, EGNR |

## 9. Resultados en la base y anomalías

Con los 47 días de la validación, de los 68 incidentes evaluables:

| Resultado del cierre | Incidentes |
| --- | --- |
| `cierre_medido` | 4: Copenhague 22/09, Bruselas 4/11, Múnich 2/10 y Vilna 11/09 (17:48–19:10, 82 min, 3 en espera) |
| `sin_interrupcion` | 15 |
| `sin_trafico_esperado` | 11 (de madrugada o cierres de menos de media hora en aeropuertos medianos) |
| `sin_linea_base` | 3 (días al borde del lote) |
| `cobertura_insuficiente` | 2 (Karup y Gibraltar) |
| `no_aplicable` | 33 (no son en un aeropuerto con tráfico regular) |

Respuesta militar vista en 44 de los 49 con lugar (5 sin ninguna; 19 sin lugar). Interferencia
GNSS: sin interferencia en 33, media en 7, alta en 2 (Vilna y una zona de Polonia), cobertura
insuficiente en 7.

Interrupciones de todos los aeropuertos con cobertura en esos 47 días (`anomalias_trafico`,
interna): 1343, de las que 1084 son menores (por debajo de significativa: menos de 30 minutos,
menos de 8 movimientos perdidos o un hueco que no llega al 80 % de lo esperado), 46 las explica
el METAR (tormenta, niebla, techo o visibilidad), 13 casan con un incidente de la base y 200
quedan como candidatas. Entre las candidatas están Múnich 3/10 y Lieja 4/11, que son cierres
reales sin incidente en la base, pero también huecos de media hora en aeropuertos medianos
(Ibiza, Menorca, Larnaca, Antalya) que no tienen por qué ser drones: una candidata es un
hueco sin explicar, no un incidente, y por eso no se publica. Con la línea base sin alinear a
la hora local eran 462: 401 en las cuatro semanas tras el cambio de hora del 26 de octubre,
frente a 137 ahora.

Las cifras del histórico entero (522 días) las da la base cuando termine (apartado 10).
