# Europa en directo: cierres de aeropuerto, interferencia GPS, presión por país y panel

Fecha: 3 de octubre de 2026. Rama `europa-directo`, PR #63.

Cuatro piezas públicas nuevas en droneobservatory.eu:

1. **Detección en directo de cierres de aeropuerto**: un servicio propio en el servidor lee las
   posiciones en tiempo real, reconstruye las llegadas y salidas de los aeropuertos europeos de
   cobertura alta, las compara con su línea base y publica los avisos en `directo.json`.
2. **Mapa diario de interferencia GPS**: las celdas H3 con la proporción de aeronaves con la
   posición degradada, por día y por mes, ligadas a la línea de tiempo.
3. **Mapa de presión por país**: los países por número de incidentes del periodo elegido, con la
   tendencia frente al periodo anterior de igual duración.
4. **Panel «Europa ahora»**: las cifras del momento, cada una con un enlace al sitio del mapa que
   la explica.

## 1. Fuente en tiempo real

Comprobado desde el servidor el 3 de octubre de 2026:

| Servicio | Acceso | Condiciones | Tope medido o publicado | Uso aquí |
| --- | --- | --- | --- | --- |
| adsb.lol, `/v2/point/<lat>/<lon>/<radio>` | Sin clave | ODbL 1.0 (© adsb.lol contributors), uso libre; anuncia que pedirá clave a los que no aporten receptor, sin fecha | «Dinámico según la carga»: medido, responde 429 hacia la décima petición seguida a 3 s; a 5 s, algún 429 suelto según la hora | **Principal** |
| adsb.fi, `/api/v3/lat/<lat>/lon/<lon>/dist/<radio>` | Sin clave | Uso no comercial, citando adsb.fi con enlace a su web | 1 petición por segundo | **Respaldo automático** |
| airplanes.live | Pide escribir antes con la descripción del proyecto (403 sin ello) | — | — | No |
| OpenSky Network, `/api/states/all` | Anónimo con 400 créditos al día (una caja grande cuesta 4) | Uso no comercial y de investigación | Una consulta de Europa cada 15 minutos | No: no llega al ritmo necesario |

**Por qué adsb.lol.** Es la misma red de receptores que el archivo diario con que se calculan las
líneas base y la cobertura de cada aeropuerto: lo que se ve en directo y lo que se esperaba se
miden con los mismos ojos. Sus datos son abiertos (ODbL) y el formato es el de readsb, igual
que adsb.fi, así que el respaldo usa el mismo lector. Un círculo de 250 millas náuticas (el
máximo) devuelve de 300 a 1000 aeronaves; los 86 aeropuertos vigilados caben en 16 círculos.

**Ritmo.** Un ciclo dura 80 s: las 16 peticiones salen repartidas en sus primeros 75 s (5 s entre
una y otra como mínimo, 12 por minuto), con compresión gzip (unos 900 kB por ciclo). Un 429 o un
fallo se repiten con 2 y 4 s de espera y respetan Retry-After; los reintentos cuentan en el tope
diario por sitio que ya existía (`datos/reintentos/`). Los círculos que la principal no da en un
ciclo se piden al respaldo en ese mismo ciclo; si falla la mitad o más, todo el ciclo va al
respaldo, y tras tres ciclos así el servicio sigue con él y prueba la principal cada 10
minutos.

## 2. Cómo se detecta un cierre

Código: [`proceso/directo.py`](../proceso/directo.py) (reglas), [`recogida/directo.py`](../recogida/directo.py)
(servicio), [`recogida/directo_reproduccion.py`](../recogida/directo_reproduccion.py) (reproducción
de días pasados).

- **Aeropuertos vigilados.** Los de cobertura alta del archivo de adsb.lol los cuatro días de su
  línea base y con 40 movimientos IFR al día o más: 86 el 3 de octubre de 2026 (de 88 a 100 los
  días reproducidos). Se recalculan cada día.
- **Posiciones guardadas.** De cada aeronave, las de las tres últimas horas en tierra o por
  debajo de 10 000 pies a 40 km o menos de un aeropuerto con tráfico regular: lo mismo que las
  trazas filtradas del archivo. Con ellas se reconstruyen aterrizajes y despegues con las reglas
  del archivo (`proceso/vuelos.py`). Un movimiento se da por asentado cuando la aeronave deja de
  verse o su traza sigue dos minutos más, y nunca antes de 4 minutos.
- **Línea base.** Por franja de 15 minutos, la mediana del mismo día de la semana de las cuatro
  semanas anteriores a la misma hora local (la de `proceso/trafico.py`), repartida dentro de cada
  franja.
- **Señal.** Se prueba como comienzo del hueco cada uno de los últimos movimientos vistos; hay
  señal si desde ese comienzo faltan al menos 12 movimientos esperados, se ha visto como mucho
  el 10 % de ellos, lo que falta ha crecido al menos 0,5 movimientos por minuto de hueco y ninguna
  aeronave está despegando o aterrizando en ese momento (en tierra a más de 40 nudos, o por
  debajo de 1500 pies a 8 km o menos). Lo esperado se multiplica por la proporción vista de lo
  esperado en las tres horas anteriores (entre 0,6 y 1,2; por debajo de 0,6 no hay señal).
- **Mal tiempo.** Si un METAR del aeropuerto desde una hora antes del comienzo del episodio
  explica el hueco (los motivos de `proceso/metar.py`: niebla, visibilidad, techo, tormenta,
  granizo, nieve o engelamiento, viento, pista contaminada), no hay aviso. Los METAR del momento
  se piden al IEM solo para un aeropuerto con señal.
- **Hueco de la fuente.** Un aeropuerto sin datos de ninguna fuente durante más de 5 minutos
  (o desde que arranca el servicio sin trazas guardadas) no puede abrir un aviso en las tres
  horas siguientes. Si más de una cuarta parte de los aeropuertos da señal a la vez, es la
  fuente y no los aeropuertos: no se abre ninguno.

### Estados de un aviso

| Estado | Cuándo |
| --- | --- |
| `posible_cierre` | Hay señal y el tiempo no la explica |
| `cierre_confirmado` | Un incidente de la base en ese aeropuerto recoge el cierre en su ventana (de tres horas antes del comienzo a doce después de la detección); `oficial` si alguna de sus fuentes es oficial (fiabilidad A). Lo comprueba la recogida horaria, que tiene la base abierta (`recogida/directo_horaria.py`) |
| `operacion_reanudada` | Vuelven al menos 2 movimientos y en la última media hora se ve la mitad o más de lo esperado. La hora de reanudación es la del primero |

Cada aviso guarda su hora de detección, el comienzo estimado (el último movimiento antes del
hueco), la evidencia (esperados y vistos, llegadas y salidas perdidas, aeronaves en espera y
vuelos desviados, con las reglas de `proceso/trafico.py`: indicativos que aterrizan
habitualmente allí a esa hora y acaban en otro aeropuerto) y, cuando llega la confirmación, la
hora de la primera noticia y la ventaja de la detección en minutos. Un aviso reanudado se publica
12 horas; uno abierto se cierra a las 24.

**Flujo de un aviso.** Al abrirse, el servicio lanza la búsqueda dirigida de noticias de ese
aeropuerto (`python -m recogida.busqueda_dirigida directo`), que lee las franjas de GDELT ya
publicadas desde una hora antes del comienzo hasta 36 horas después, y la repite cada media hora
mientras el aviso sigue abierto. La recogida horaria incorpora lo hallado como artículos del
aeropuerto (deduplicado, candidato, extractor con prioridad) y, cuando el incidente entra en la
base, confirma el aviso. El cierre medido del incidente llega con el archivo diario de adsb.lol,
con origen «medido», como hasta ahora.

## 3. Umbrales y reproducción de días reales

Los umbrales salen de reproducir días reales con las trazas guardadas del archivo diario
(`recogida/directo_reproduccion.py`): las posiciones de cada día se reparten en consultas de 80 s
(la última posición de cada aeronave en cada ciclo, como la daría la consulta en tiempo real),
se pasan por el detector ciclo a ciclo con las líneas base del archivo y los METAR guardados, y
se anotan los avisos y, con umbrales holgados, todos los episodios de señal, para probar otros
umbrales sin repetir la reproducción. Cada día cuesta unos 7 minutos de un núcleo.

Se reprodujeron 12 días con cierre conocido y 40 días sin él (del 16/09/2025 al 01/10/2026,
con su línea base de cuatro semanas en el archivo), cuatro veces: las tres primeras sirvieron
para ajustar (sección 3.2) y la última da las cifras con los umbrales finales. Las horas son UTC;
el retraso se cuenta desde la hora oficial o, si no la hay, desde el comienzo medido en el
archivo.

### 3.1 Resultados con los umbrales finales

**Cierres conocidos**

| Cierre | Comienzo | Detectado | Retraso | Reanudado | Evidencia |
| --- | --- | --- | --- | --- | --- |
| Copenhague, 22/09/2025 | 18:26 (oficial) | 18:52 | **26 min** | 22:38 | 129 movimientos esperados, 1 visto; 13 en espera, 48 desviados |
| Múnich, 03/10/2025 | ~19:30 (oficial) | 20:05 | **35 min** | 03:43 del 04/10 (fin del toque de queda) | 89 esperados, 0 vistos; 6 en espera, 34 desviados |
| Bruselas, 04/11/2025 | 18:45 (medido; ~19:00 oficial) | 19:09 | **24 min** (9 desde la hora oficial) | 22:06 | 98 esperados, 8 vistos; 8 en espera, 18 desviados |
| Múnich, 30/05/2026 | 06:56 (medido) | 07:25 | **29 min** | 08:11 | 71 esperados, 0 vistos; 12 en espera, 23 desviados |
| Múnich, 06/09/2026 | 14:25 (medido) | 14:46 | **21 min** | 14:47 | 25 esperados, 2 vistos |
| Múnich, 02/10/2025 | 20:18 (oficial) | — | — | — | El cierre empezó al final de la última oleada de la tarde y siguió con el toque de queda nocturno: el archivo solo mide 30 minutos con unos pocos movimientos perdidos |
| Múnich, 04/10/2025 | 03:51 (medido) | — | — | — | Al amanecer: lo que falta crece menos de 0,5 movimientos por minuto |
| Colonia/Bonn, 05/11/2025 | 04:51 (medido) | — | — | — | Igual, de madrugada |
| Helsinki, 14/05/2026 | 22:52 (medido) | — | — | — | De noche, con poco tráfico esperado |
| Ibiza, 16/06/2026 | 11:17 (medido) | — | — | — | Unos 20 movimientos por hora: lo que falta crece despacio |
| Berlín, 23/09/2026 | 18:14 (medido) | — | — | — | Un movimiento a las 18:56, en mitad del cierre de 53 minutos, cumple la condición de reanudación antes de los 4 minutos de persistencia |
| Lieja, 04/11/2025 y Chisináu, 08/09/2026 | — | — | — | — | Fuera de los vigilados: Lieja tiene poco tráfico de pasajeros y Chisináu, cobertura insuficiente |

Retraso de los cinco detectados: de 21 a 35 minutos (mediana, 26). La ventaja frente a la
primera noticia se mide en cada aviso real cuando la recogida horaria lo confirma (campo
`ventaja_min` de `directo.json`).

**Días sin cierre conocido (40)**: 37 sin ningún aviso. Los avisos de los otros, y los de los
días de cierre que no corresponden al cierre conocido:

| Día | Aeropuerto | Hueco | Qué hay en el archivo diario |
| --- | --- | --- | --- |
| 04/11/2025 | Múnich | 18:50–19:30 (detectado 19:25) | Ningún aterrizaje ni despegue en 40 minutos, con 30 aeronaves a menos de 40 km y 25 bajas a menos de 20 km: un parón real, la misma tarde de los cierres de Bruselas y Lieja, sin incidente en la base |
| 02/06/2026 | Bruselas | 12:14–19:01 (detectado 12:49) | Ningún movimiento de 12:04 a 19:00 con tráfico alrededor: un parón real de siete horas, sin incidente en la base |
| 08/10/2025 | Antalya | desde 09:05 (detectado 09:30) | El archivo también se queda sin movimientos y sin aeronaves cerca (de 24 por media hora a 1): los receptores de la zona dejaron de verla. **Aviso falso** |

Los dos parones reales son lo que la detección busca: aeropuertos parados sin noticia en la base.
Con el servicio en marcha habrían lanzado la búsqueda dirigida de noticias. El aviso de Antalya
es el único falso en 40 días normales; su arreglo está en los pendientes.

### 3.2 Cómo se llegó a los umbrales

- **Primera versión** (8 movimientos esperados, sin ritmo, con 5 minutos de persistencia):
  detectaba Copenhague a los 22 minutos, pero daba avisos en huecos cortos de Stansted, Otopeni
  y Fráncfort que se reanudaban antes de la detección. La causa: movimientos ya hechos pero aún
  sin asentar. Se añadió la actividad en curso (aeronaves rodando deprisa o por debajo de 1500
  pies junto a la pista, y movimientos reconstruidos aún sin asentar).
- **Ciclo real.** adsb.lol respondía 429 con 26 círculos cada minuto; con círculos de 250 millas
  (16) y 5 s entre peticiones, el ciclo pasó a 80 s, y la reproducción se repitió con ese ciclo.
- **Ritmo.** Los episodios de señal de 26 días mostraron que en los cierres reales lo que falta
  crece deprisa (Copenhague: 14 esperados a los 24 minutos; Múnich 03/10: 16 a los 23; Bruselas:
  14 a los 21), y en los avisos falsos despacio (Oporto, Bilbao, Riga, Bristol, Heathrow al
  empezar la noche: de 0,15 a 0,4 por minuto). Con 0,5 por minuto como mínimo y 12 esperados
  desaparecían todos los falsos salvo los huecos que también tiene el archivo.
- **Cobertura.** Se vigila un aeropuerto solo con cobertura alta en todos los días completos de
  su línea base (sin días a medias del archivo, como el 07/05/2026 o el 09/08/2026, que dejaban
  algún día sin ningún aeropuerto vigilado).
- **Fallos del archivo y de la fuente.** El 09/08/2026 el archivo de adsb.lol no tiene datos de
  toda Europa de 12:12 a 18:03, y la reproducción abría 19 avisos a la vez. Ahora, si entre todos
  los vigilados se ve en los últimos 10 minutos menos de la mitad de lo esperado, no se abre
  ninguno; y el hueco tiene que seguir abierto (en el último cuarto de hora, como mucho un
  movimiento o el 10 % de lo esperado), para que no salte al volver los datos.
- **Persistencia de 4 minutos.** Quitó el aviso de Roma del 23/08/2026 (un movimiento asentado
  tarde) y el de Stansted del 18/09/2025, a cambio de unos 4 minutos más de retraso.
- **Mal tiempo.** Un día real de Copenhague con una tormenta añadida en el METAR de las 18:20 no
  da aviso (test); el METAR se mira desde el comienzo del primer hueco del episodio, para que no
  vuelva el aviso al moverse el comienzo con un movimiento suelto.

### 3.3 Tests sin red

`tests/test_directo.py` (36 tests): días reales recortados del archivo (`tests/fixtures/directo/`:
cierre de Copenhague, Copenhague un día normal, el mismo día con tormenta en el METAR, Palma con
cobertura baja), la señal y los estados de un aviso con movimientos sintéticos, la confirmación,
la caducidad, la evidencia de esperas y desvíos, el respaldo de fuente (ciclo entero y círculo a
círculo), el tope de reintentos, los huecos de la fuente, la salvaguarda global, los días
incompletos, los círculos, los ficheros públicos y su lista cerrada, la búsqueda dirigida de un
aviso, `estado.json` y la vigilancia.

## 4. Mapa diario de interferencia GPS

La interferencia GNSS por celdas ya se calculaba en el procesado diario del archivo
(`proceso/gnss.py`): por celda H3 de resolución 4 (la de gpsjam.org) y día, las aeronaves
distintas y las que tuvieron alguna posición ADS-B con NIC menor que 7 o NACp menor que 8.
Ahora se publica ([`recogida/gnss_publico.py`](../recogida/gnss_publico.py)):

- `gnss/dia/AAAA-MM-DD.json` y `gnss/mes/AAAA-MM.json` en el almacén público, con compresión
  gzip, y `gnss/indice.json` con los días y meses publicados. Por celda: índice H3, aeronaves,
  degradadas, proporción ((degradadas − 1) / aeronaves, como gpsjam.org), nivel (`sin` por debajo
  del 2 %, `media` del 2 al 10 %, `alta` por encima) y contorno (seis vértices, para que la web
  la dibuje sin calcular H3). Solo las celdas con 20 aeronaves o más en el día. En un mes,
  aeronaves y degradadas son la suma de sus días.
- Resumen del día: celdas por nivel, la proporción de toda Europa y el nivel del día, el de la
  celda del percentil 90 (el que alcanza una de cada diez celdas). Un día típico
  tiene unas 4500 celdas, de ellas unas 600 con interferencia media y entre 280 y 390 altas; la
  proporción de Europa está entre el 1,7 y el 2,1 % (22/09/2025, 30/09 y 02/10/2026).
- Lista cerrada de campos en `exportacion/campos.CAMPOS_PUBLICOS_GNSS`, comprobada antes de cada
  subida y con su test.
- Lo publica el servicio en directo en cada ciclo, dos días como mucho (los nuevos primero,
  después el histórico).

En la web, capa «GPS» ligada a la línea de tiempo: hasta 7 días se suman los ficheros diarios del
periodo, con más se usan los mensuales; relleno en grises por proporción y el nivel alto con el
color de estado; leyenda; al pulsar una celda, la proporción de aeronaves afectadas, el número
de aeronaves y de degradadas y el periodo.

## 5. Mapa de presión por país

Calculado en la web con los incidentes ya publicados y los filtros activos: los países de
`paises.geojson` en cinco escalones de gris según sus incidentes del periodo elegido, con la
tendencia frente al periodo anterior de igual duración (sube, baja o estable, con la diferencia;
estable si la diferencia es 0, o si es 1 y no pasa del 10 % de lo anterior). Al pulsar un país,
sus cifras por tipo y por estado y la lista de sus incidentes con enlace a cada ficha.

## 6. Panel «Europa ahora»

Franja bajo los filtros en escritorio y dentro de la cabecera en el teléfono (botones de 44 px
con desplazamiento lateral, sin tapar la hoja inferior). Cifras: cierres en curso (avisos
posibles y confirmados de `directo.json`), incidentes de los últimos 7 días, drones lanzados la
última noche (el ataque más reciente de la capa de guerra), focos térmicos confirmados en 7
días e interferencia GPS del día (nivel del último día publicado y celdas altas). Cada cifra
lleva al sitio del mapa: el aviso más grave, el filtro de 7 días, la capa de Ucrania con esa
noche, el periodo de 7 días y la capa GPS con el último día. Una cifra sin su fichero sale como
«—».

## 7. Textos de la web

Revisada toda la web en español e inglés (metodología, fichas, leyendas, ayuda, créditos): los
párrafos del satélite, del tráfico aéreo y de la capa de guerra añadidos en trabajos anteriores
se reescriben como descripción de lo que es cada dato y cómo se obtiene, y la antigua sección
sobre la cobertura de la prensa pasa a la descripción de la presión por país. Las
atribuciones obligatorias siguen (adsb.lol ODbL, adsb.fi, Open-Meteo, NASA FIRMS, UKAB,
OpenStreetMap, Protomaps, Natural Earth y las demás) y se añade la del tráfico en tiempo real. En
créditos solo quedan los proveedores en uso. La metodología explica las tres piezas nuevas con
sus umbrales.

## 7 bis. Colores de los estados y pulso de las marcas

En toda la web (mapa, grupos, filtros, contadores de la cabecera, ficha, línea de tiempo,
leyendas, ayuda y metodología, ES y EN):

| Estado | Color | Contraste con el fondo y los paneles |
| --- | --- | --- |
| Notificado | naranja `#ff9a2e` | 8:1 o más |
| Confirmado | rojo `#f53a50` | 4,56:1 o más |
| Atribuido | el mismo rojo, con una bandera roja pequeña fuera de la forma del símbolo; en la ficha, «Confirmado · atribuido a …, según …» | 4,56:1 o más |
| Desmentido | gris `#93a0b4`, contorno discontinuo | — |

Entre el naranja y el rojo hay una razón de luminancia de 1,77:1 con visión normal, 1,62 con
deuteranopía, 2,15 con protanopía y 1,66 con tritanopía (simulación de Machado, 2009); lo
comprueba `web/tests/colores.test.tsx`. Un grupo es rojo si contiene algún confirmado o
atribuido y naranja si todos son notificados. Los avisos en directo usan la misma escala
(naranja posible, rojo confirmado, gris reanudado) con su propia marca de aeropuerto y sin
pulso. El verde queda solo para los indicadores de funcionamiento de la barra de estado.

**Atribuido** se dibuja como una bandera roja con su mástil, sin forma debajo: icono de 28 px
con el pie del mástil en el punto del incidente y, en el teléfono, la marca más cercana en 44 px
como objetivo del dedo; los grupos y los episodios unidos por línea lo tratan como al resto.

**Pulso.** Solo laten los incidentes nuevos desde la última visita (los que cuenta el aviso de
novedades) y los grupos que contienen alguno; se apagan con «Verlas», «Descartar» o al abrir el
incidente; en la primera visita no late nada; con movimiento reducido, un anillo fijo. El pulso
solo cambia la opacidad de un anillo: la marca no cambia de tamaño ni de sitio.

**Capa de guerra** (la lleva otra sesión): las regiones de Ucrania, la línea de lanzamientos de
la línea de tiempo y la cifra de drones de la noche usan un rojo coral (`#f25c4f`, ahora en el
token `PALETA.guerra`) muy cercano al rojo nuevo de los confirmados (1,15:1 de luminancia, 11° de
tono): esa sesión debería moverlo a otro tono o a grises. Los impactos y sus grupos no laten,
así que el pulso no le afecta. El cambio de nombre del token toca `src/mapa/estilo.ts`,
`src/componentes/LineaTiempo.tsx` y `src/App.tsx`, que también edita esa sesión.

## 7 ter. La pantalla es el mapa

Sobre el mapa solo hay botones pequeños; lo demás se abre al pedirlo:

- **Sin barra de tiempo inferior.** El periodo se elige en los filtros: últimas 24 horas, 7 días,
  30 días, último año, todo (por defecto, como al abrir la web hasta ahora) o entre dos fechas. Con
  un periodo distinto, el botón de filtros lo lleva escrito («Filtros · Últimos 7 días ×»; la
  equis vuelve a todo). El mapa, la lista, las cifras y todas las capas siguen el periodo; los
  enlaces `?ultimos=` y `?desde=…&hasta=…` lo abren, y un enlace a una ficha la abre aunque quede
  fuera del periodo.
- **«Europa ahora»** es un botón con desplegable (hoja inferior en el teléfono), cerrado al
  entrar; lleva un número si hay cierres en curso y un punto si hay novedades desde la última
  visita. Se cierra con el botón, la equis, Escape, pulsando fuera o, en el teléfono, arrastrando
  la hoja hacia abajo; pulsar una entrada lleva a su sitio y lo cierra.
- **Además se pliega:** la barra de filtros pasa a un botón con desplegable, el botón «Periodo»
  de la cabecera del teléfono desaparece, y las leyendas solo salen con su capa activa y se
  pliegan. Los botones sobre el mapa llevan el fondo de los paneles.

Comprobado en producción el 3 de octubre de 2026 con `web/data/comprobar-pantalla.mjs` (escritorio
y 390×844): 72 comprobaciones bien y 0 mal. Al entrar, el mapa llega hasta el borde inferior, sin
ningún panel ni desplegable abierto. Las cifras de cada periodo coinciden con la lista: todo 507,
24 horas 10, 7 días 33, 30 días 92, último año 379 y noviembre de 2025 61. Los enlaces con periodo
y la ficha más antigua (`EODI-2024-00001`, también con `?ultimos=24h`) abren lo que deben. Con
`web/data/capturar-estados.mjs` se comprobaron tres atribuidos en el mapa y en su ficha con el
historial de estados (EODI-2026-00015, EODI-2026-00074 y EODI-2026-00283), la leyenda, y que
laten 4 o 5 novedades con una visita anterior y ninguna en la primera visita.

## 7 quater. Todos los incidentes como círculo

Desde el PR #78 el marcador de un incidente suelto solo indica su estado: círculo naranja relleno
(notificado), círculo rojo relleno (confirmado), círculo gris de borde discontinuo (desmentido) y
la bandera roja (atribuido). El tipo se lee como texto en la ficha, la lista y los filtros, y la
leyenda tiene cuatro entradas. «Europa ahora» lleva todas sus cifras en una columna fija; la del
GPS es el número de zonas con interferencia alta del día («384 zonas con interferencia GPS hoy»
el 2 de octubre de 2026), el mismo que da la leyenda de la capa. Paneles, hojas y desplegables
son opacos. Los avisos en directo tienen su propia etiqueta con el código OACI, por encima del
punto del aeropuerto, y el número de los grupos va por encima de todo. Comprobado en producción
con `web/data/comprobar-circulos.mjs` (escritorio y 390×844): 49 comprobaciones bien y 0 mal;
capturas `europa-*-entrada.png` y `europa-*-ahora.png`.

## 8. Servidor y vigilancia

- Unidad `eodi-directo.service`, siempre en marcha (`Restart=always`), con su propio cerrojo,
  `Nice=5` y un tope de 1,5 GB. Guarda sus trazas cada 10 minutos y al parar; al volver a
  arrancar en menos de 15 minutos sigue con ellas. Cuando la recogida horaria pone código nuevo en
  el clon, guarda sus trazas y sale, y systemd la vuelve a lanzar con ese código.
- `estado.json` lleva `directo` (en marcha, con respaldo o parada, y el último ciclo correcto) y
  la web lo enseña en la barra de estado. El workflow `vigia-recogida` abre la incidencia «La
  detección en directo no se actualiza» si `directo.json` lleva más de media hora sin publicarse
  y la cierra cuando vuelve.
- Detalle de órdenes en [`servidor.md`](servidor.md), «Detección en directo de cierres».

### Consumo

| | |
| --- | --- |
| Servicio en directo (medido una hora en el servidor, sin publicar) | ~300 MB de memoria; unos 10 s de CPU cada media hora; 16 a 19 peticiones por ciclo, de ellas 1 a 3 al respaldo; ~900 kB comprimidos por ciclo (unos 0,9 GB al día de descarga); unas 6000 posiciones por ciclo |
| Mapa de interferencia GPS | Unas 4500 celdas por día; cada fichero diario o mensual, comprimido, unos cientos de kB; dos días por ciclo hasta tener el histórico |
| `directo.json` | Unos kB, una subida por ciclo (las peticiones al almacén no se cobran) |
| Reproducción de un día | Unos 5 minutos de un núcleo y 0,9 GB como máximo leyendo las trazas en flujo |

La reproducción se lanza como un solo trabajo con `MemoryMax=1G`, `nice` 19 y E/S en reposo, y
se pausa entre los minutos 15 y 40 y mientras la recogida horaria está en marcha
(`recogida/directo_reproduccion.esperar_turno`). Las primeras reproducciones de este trabajo
corrieron tres a la vez con 2,5 GB cada una y coincidieron con las recogidas de las 09:17 y las
11:17 del 3 de octubre, que el sistema cortó por falta de memoria.

## 9. Capturas de producción

Tomadas en droneobservatory.eu el 3 de octubre de 2026 hacia las 15:58 UTC, con el servicio en
directo recién instalado (0 cierres en curso a esa hora) y el histórico del mapa GPS
publicándose:

| Captura | Qué se ve |
| --- | --- |
| [`europa-escritorio-panel.png`](capturas/europa-escritorio-panel.png) | Franja «Europa ahora» bajo los filtros, con las cinco cifras |
| [`europa-escritorio-directo.png`](capturas/europa-escritorio-directo.png) | Panel en directo, sin cierres en curso |
| [`europa-escritorio-gps.png`](capturas/europa-escritorio-gps.png) | Capa de interferencia GPS del último día, con su leyenda: el rojo del Báltico, Kaliningrado, el mar Negro y el este de Turquía |
| [`europa-escritorio-presion.png`](capturas/europa-escritorio-presion.png) | Capa de presión por país |
| [`europa-390x844-panel.png`](capturas/europa-390x844-panel.png), [`europa-390x844-gps.png`](capturas/europa-390x844-gps.png) | Versión reducida de la franja en la cabecera del teléfono, y la capa GPS |
| [`estados-escritorio.png`](capturas/estados-escritorio.png), [`estados-390x844.png`](capturas/estados-390x844.png) | Notificados en naranja, confirmados en rojo y atribuidos como bandera roja (Moldavia y Rumanía) |
| `atribuido-{1,2,3}-mapa-*.png`, `atribuido-{1,2,3}-ficha-*.png`, `leyenda-*.png` | Tres atribuidos como bandera sin forma en el mapa y en su ficha con el historial de estados, y la leyenda, en escritorio y 390×844 |
| [`novedades-escritorio.png`](capturas/novedades-escritorio.png), [`novedades-390x844.png`](capturas/novedades-390x844.png) | Con una visita anterior de hace tres días: laten las 4 marcas con novedades |
| [`sin-novedades-escritorio.png`](capturas/sin-novedades-escritorio.png), [`sin-novedades-390x844.png`](capturas/sin-novedades-390x844.png) | Primera visita: no late nada |

En las capturas, la cifra GPS del panel aún sale con el nivel calculado como media de Europa
(«sin interferencia» con 384 celdas altas); desde este cierre es el del percentil 90.

## 10. Pendientes

| Pendiente | Arreglo |
| --- | --- |
| Un aviso falso en 40 días normales: Antalya, 08/10/2025, cuando los receptores dejaron de ver la zona | Vigilar solo aeropuertos con cobertura alta también en los 28 días procesados anteriores (Antalya tiene días con índice 0); se calcula una vez al día con las coberturas que ya guarda la base |
| Cierres de madrugada, de noche y en aeropuertos de unos 20 movimientos por hora (Múnich 04/10, Colonia/Bonn, Helsinki, Ibiza) no se detectan | Segunda vía de señal con lo que se ve en directo: dos o más aeronaves en espera cerca del aeropuerto o vuelos habituales desviados, con lo que falta por debajo del ritmo mínimo |
| Berlín, 23/09/2026: un movimiento suelto en mitad del cierre corta la señal | Admitir dentro del hueco abierto los movimientos sueltos que ya admite el archivo (el 3 % de lo esperado) |
| La ventaja frente a la primera noticia aún no tiene casos reales | Se rellena sola en `directo.json` cuando la recogida horaria confirma el primer aviso |
| El coral de la capa de guerra está muy cerca del rojo de los confirmados | Moverlo en la sesión de la capa de guerra (sección 7 bis) |
