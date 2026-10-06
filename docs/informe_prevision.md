# Previsión y tendencias, frontera o interior y arreglos del detector de cierres

European Observatory of Drone Incidents, 6 de octubre de 2026. Las horas son UTC. Fase 1 del
encargo de previsión y tendencias: PR #138 (fusionado a las 12:43, `d9b6041`) y este informe.

**En resumen.**

- La web dice ahora, sola y con números comprobados, qué está pasando más de lo normal y qué es
  probable que pase. Todo sale de un fichero nuevo, `publicacion/prevision.json`, que la recogida
  horaria calcula con lo recién publicado.
- Solo se publica lo que pasa una comprobación con el pasado: cada número se calcula con los datos
  anteriores a una fecha y se compara con lo que ocurrió después, avanzando en el tiempo, contra
  la frecuencia de siempre y contra «mañana igual que hoy». Pasan: el riesgo de esta noche en la
  frontera de **Rumanía** y **Moldavia**, las **rachas por país** y **la semana que viene** de
  Rumanía y Moldavia. No pasan y no se publican: el aviso de segunda noche, la frontera de Polonia,
  Lituania, Letonia y los demás países, y la semana del resto de países.
- Cada incidente guarda si es de **frontera** o de **interior** y por qué; el filtro «Dónde» lo
  usa y las cifras de la cabecera lo siguen.
- Arreglos: los confirmados incluyen a los atribuidos; los corredores con «Todo» se leen; la
  leyenda de Presión sin periodo lo dice; el detector de cierres del archivo diario baja las
  falsas alarmas de 1.633 a 141 en 342 días con los mismos cierres detectados salvo uno.

## Qué ve el usuario

Sobre el mapa, en escritorio, un botón pequeño más: **Previsión**, junto a «Filtros» y «Europa
ahora», que abre un desplegable. En el teléfono, **Previsión es una pestaña de «Europa ahora»**:
los tres botones caben en 360 px con el periodo «Todo», pero con un periodo elegido el botón de
filtros lo lleva escrito («Filtros · Últimos 7 días ✕») y el tercero bajaba a una segunda fila
sobre el mapa (captura `prevision-360-antes-de-integrar.png` en la carpeta de capturas de este
trabajo). En la hoja de «Europa ahora» hay dos pestañas, «Europa ahora» y «Previsión». Cerrar no
mueve el mapa (prueba de navegador en los cuatro tamaños).

De arriba abajo:

1. **Esta noche en la frontera.** Para Rumanía y Moldavia: «Rumanía: 4 de cada 10 noches como
   esta (40 %)», lo habitual del país («9 de cada 100 noches»), de qué depende hoy (drones lanzados
   contra Ucrania de media en las tres últimas noches y anoche, noches con salidas desde Crimea de
   las últimas 7, incidentes de frontera del país en 7 días; cada uno con «sube el riesgo», «lo
   baja» o «no lo cambia» frente a su valor habitual) y el historial de aciertos, con la tabla por
   tramos de probabilidad y las últimas noches.
2. **Aviso de segunda noche.** No ocupa sitio: hoy no pasa la comprobación (ver abajo).
3. **Rachas por país.** Los países por encima de lo normal, ordenados por cuántas veces lo normal:
   desde cuándo, cuántos incidentes frente a lo habitual y si crece, se mantiene o se apaga; debajo,
   los que han vuelto a lo normal en las últimas seis semanas. Tocar uno lleva el mapa al país con
   el país y el periodo de la racha en los filtros. El 6 de octubre: Moldavia desde el 17 de
   agosto (22 incidentes frente a 2,8 lo habitual) y Lituania desde el 7 de septiembre (7 frente a
   1,4, se apaga); han vuelto a lo normal Rumanía y Letonia.
4. **La semana que viene.** Rumanía y Moldavia con lo esperado y su margen («3,3 (entre 0 y 10, 8
   de cada 10 semanas)»), y el marcador de las semanas anteriores: previsto, margen, lo que hubo y
   si cayó dentro. Las semanas anteriores a hoy están **reconstruidas** (calculadas ahora solo con
   los datos de entonces) y marcadas con un asterisco; desde hoy se añaden las hechas en vivo.

Además:

- **Ficha de un país** (capa Presión): si el país tiene racha, la racha y una gráfica pequeña de
  incidentes por semana de las últimas 26 semanas con la banda gris de lo normal (del 10 al 90 %).
  Una sola serie, barras finas, texto equivalente para lectores de pantalla y un rótulo por barra.
- **Página de texto** `/prevision` y `/en/forecast`, en la navegación de todas las páginas de
  texto, en el sitemap y en llms.txt; se lee sin ejecutar código.
- **Metodología**: dos secciones nuevas, «Frontera o interior» y «Previsión y tendencias», en los
  dos idiomas (también en `/metodologia#prevision`).
- **Ficha de un incidente** y su página de texto: «Frontera o interior» con la regla que lo decide
  («a 150 km o menos de la frontera con Ucrania, Rusia o Bielorrusia, a 26 km…»).

## Cada número publicado

Datos: lo publicado el 6 de octubre de 2026 (429 incidentes no desmentidos, 1.076 noches con parte
de la Fuerza Aérea de Ucrania). La recogida de incidentes es sistemática desde enero de 2025, así
que el entrenamiento empieza el 1 de enero de 2025 y la comprobación el 1 de julio de 2025 (las
semanas, el 30 de junio). Ninguna comprobación usa un dato posterior a la noche o la semana que
prevé; hay una prueba que lo exige (`test_ninguna_comprobacion_usa_datos_futuros`).

**Criterio para publicar.** Mejora a las dos referencias (5 % de Brier en probabilidades; 0,02 en
el logaritmo de la probabilidad por semana en números) y la mejora sobre la frecuencia se sostiene
al remuestrear semanas con reemplazo (el percentil 10 de 1.000 remuestreos, con semilla fija, por
encima de cero). En la frontera, además, 20 noches con suceso como mínimo.

### Esta noche en la frontera

Suceso: el país tiene al menos un incidente de frontera esa noche. Método: regresión logística
con tres factores conocidos antes de la noche (drones lanzados de media en las tres últimas
noches, en logaritmo; noches de las últimas 7 con salidas desde Crimea; incidentes de frontera del
país en 7 días, hasta 3), reajustada el día 1 de cada mes con las noches que acabaron dos días
antes o más. Referencias: la frecuencia de siempre del país y «mañana igual que hoy» (la
frecuencia tras una noche con suceso o sin él).

| País | Noches comprobadas | Con dron | Área bajo la curva | Mejora sobre la frecuencia | Sobre «mañana igual que hoy» | Con dron entre el 25 % de más riesgo | ¿Se publica? |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Rumanía | 460 | 56 | 0,79 | 10,7 % | 7,3 % | 40 de 56 | Sí |
| Moldavia | 460 | 33 | 0,74 | 13,0 % | 12,9 % | 21 de 33 | Sí |
| Polonia | 460 | 6 | 0,18 | −0,3 % | 1,1 % | 0 | No |
| Lituania | 460 | 24 | 0,41 | −0,2 % | 2,2 % | 4 | No |
| Letonia | 460 | 7 | 0,64 | 0,0 % | 10,8 % | 4 | No |
| Estonia, Finlandia, Bulgaria | 460 | 2 a 3 | — | 0 % | — | — | No (pocos datos) |
| Hungría, Eslovaquia | 460 | 0 | — | — | — | — | No |

Tramos de Rumanía (lo que dijo y lo que pasó): por debajo del 5 %, 16 de 346 noches con dron; del 5
al 10 %, 18 de 39; del 10 al 20 %, 6 de 29; del 20 al 40 %, 13 de 43; por encima del 40 %, 3 de 3.
Moldavia: 14 de 376, 4 de 41, 6 de 25 y 9 de 18. La web enseña esta tabla tal cual.

Antes de la noche no hay más señal: con los factores del propio ataque de esa noche (tamaño y
salida desde Crimea, conocidos por la mañana) el área bajo la curva de Moldavia sube a 0,80, pero
ese número llega cuando el ataque ya ha pasado. El factor de anoche suelto se quitó: con la media
de tres noches la comprobación da lo mismo y el factor de anoche salía con el signo contrario,
confuso para el usuario.

### La semana que viene

Lo esperado: media con un peso que se reduce a la mitad cada cuatro semanas; margen del 10 al 90 %
de una binomial negativa con la dispersión del país. Referencias: la media de todas las semanas
anteriores del país y «la semana que viene igual que esta». Puntuación: logaritmo de la
probabilidad que dio cada método a lo que pasó (más es mejor), por semana.

| País | Incidentes | Semanas comprobadas | Mejora sobre la frecuencia | Sobre «igual que esta» | Semanas dentro del margen | ¿Se publica? |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Rumanía | 92 | 44 | 0,27 (un 31 % más de probabilidad al resultado) | 0,92 | 40 de 44 | Sí |
| Moldavia | 47 | 43 | 0,07 (un 8 % más) | 0,06 | 37 de 43 | Sí |
| Alemania | 50 | 52 | −0,03 | 0,16 | 51 de 52 | No |
| Bélgica | 24 | 47 | 0,00 | −0,02 | 45 de 47 | No |
| Dinamarca | 18 | 51 | 0,01 | −0,01 | 49 de 51 | No |
| Noruega | 27 | 52 | 0,01 | 0,01 | 49 de 52 | No |
| Lituania | 30 | 43 | −0,05 | 0,12 | 39 de 43 | No |
| Letonia, España, Reino Unido | 18 a 20 | 7 a 13 | negativa | — | — | No |

Separar frontera e interior no cambia la previsión semanal de un país: la media con pesos de la
suma es la suma de las medias, y la dispersión de cada parte se estima peor con menos datos.

### Rachas por país

Lo normal: media de las semanas del último año sin las cuatro últimas. Racha: las cuatro últimas
semanas suman más de lo que lo normal da 1 de cada 20 veces, con 3 incidentes como mínimo en 2 días
distintos o más; sin racha si el año normal tiene menos de 5 incidentes (con tan pocos no se sabe
qué es normal). Cuenta sucesos, no noticias: cada incidente una vez (los unidos ya no se publican),
en la fecha del suceso; la condición de dos días distintos evita que un mismo suceso contado varias
veces haga racha.

Comprobación: en las 55 semanas en que una serie estaba en racha desde julio de 2025, la semana
siguiente tuvo **90 incidentes donde lo normal daba 20,3**; la media móvil de la racha da al
resultado una probabilidad 1,8 veces mayor que lo normal (0,61 en logaritmo, percentil 10 del
remuestreo 0,32). Separando frontera e interior: 56 semanas, 91 frente a 18,9, mejora 0,59. Es casi
igual y algo peor, así que las rachas se calculan con todos los incidentes del país (`modo: todo`
en el fichero); la separación queda en el filtro y en la ficha.

### Probabilidades en lenguaje llano

«4 de cada 10 noches como esta (40 %)», con el número redondeado a la decena y el porcentaje
exacto. No se usan adjetivos.

## Lo que se probó y no se publica

| Qué | Resultado | Lo que haría falta para que sirva |
| --- | --- | --- |
| Aviso de segunda noche (tras una noche grande, otra grande) | 111 noches grandes desde 2024; la siguiente fue grande en 20 (18 %), frente al 13,7 % de siempre. La probabilidad comprobada hacia delante empeora la de siempre un 4,9 % de Brier | Definir «grande» por el tamaño absoluto y por la dirección (las oleadas grandes de 2025-2026 se agrupan por semanas, no noche a noche) y añadir el parte ruso de la misma noche; volver a comprobar cuando haya 200 noches grandes |
| Frontera de Polonia, Lituania, Letonia, Estonia, Finlandia, Bulgaria, Hungría, Eslovaquia | Ninguna mejora a la frecuencia de siempre (tabla de arriba); Polonia tiene 6 noches con dron y Lituania 24, casi todas de globos y drones desde Bielorrusia, que no dependen del ataque sobre Ucrania | Para Lituania y Letonia, un predictor propio (los ataques ucranianos contra el norte de Rusia, las alertas de Bielorrusia); para Polonia, esperar a tener 20 noches con dron |
| La semana que viene en los demás países | Ninguno mejora a las dos referencias | Más semanas con datos; los países de interior tienen semanas casi siempre a 0 o 1 |
| «Ataque en curso» como factor de la frontera | La captura del seguimiento en directo existe desde el 4 de octubre de 2026: dos días no se pueden comprobar | Con 6 meses de captura, añadir «drones en vuelo hacia Odesa a las 20:00 UTC» como factor y volver a comprobar |

## El punto de partida, comprobado de nuevo

| Afirmación del análisis previo | Con los datos del 6 de octubre de 2026 |
| --- | --- |
| Tras una oleada grande, otra grande la noche siguiente un 24 % de las veces | No se sostiene como previsión: con «grande» = 200 drones o más, 24,6 % frente al 19,9 % de siempre; con el percentil 90 de las 60 noches anteriores, 15,6 % frente al 12,7 %; y con 300 o más, 7,6 % frente al 10,4 %. Comprobada hacia delante, no mejora a la referencia (arriba) |
| Riesgo diario en Rumanía o Moldavia según el tamaño y la dirección del ataque, área bajo la curva 0,75 | Se sostiene: 0,79 en Rumanía y 0,74 en Moldavia antes de la noche (0,78 y 0,80 con el ataque de esa misma noche) |
| Los de interior vienen más en rachas (46,5 %) que los de frontera (20,8 %) | Con el criterio nuevo de frontera e interior, es al revés: tras un incidente, otro del mismo país en 7 días en el 58,7 % de los de frontera y el 36,0 % de los de interior, porque la frontera tiene más incidentes por semana. Las rachas se miden contra lo normal de cada país, no así |
| Los cierres de aeropuerto duran una mediana de 45 minutos | 40 minutos (42 incidentes con duración declarada). Es una descripción, no una previsión: no sale en «Previsión» |
| Ni la luna ni el día de la semana influyen | Se sostiene: 33 de 136 noches de frontera en Rumanía y Moldavia con luna llena (24 %, lo esperable); por día de la semana, de 14 a 27, sin diferencia (ji cuadrado 7,6 con 6 grados de libertad) |
| Los dos bandos atacan las mismas noches (correlación 0,33) | Correlación de 0,24 entre los drones lanzados por Rusia y los derribados según el parte ruso (0,45 en logaritmos), pero **0,01** quitando la tendencia de 30 días: los dos crecen a la vez, no atacan las mismas noches |

## Frontera o interior

Regla ([`proceso/zona.py`](../proceso/zona.py)), en orden, la primera que se cumple:

1. enlazado con el ataque ruso contra Ucrania de esa noche (`proceso/cruces.py`): frontera;
2. con punto: frontera si está a 150 km o menos de la frontera terrestre con Ucrania, Rusia
   (Kaliningrado incluido) o Bielorrusia, o a 50 km o menos de la costa del mar Negro; si no,
   interior;
3. sin punto: la misma distancia desde el lugar que nombran su localidad, su región o su titular
   (nomenclátor de localidades y lugares, con las formas de `nombres_equivalentes.json`); un titular
   en el mar Negro es frontera;
4. sin lugar: frontera si el dron entró desde fuera (incursión, entrada desde el exterior o dron
   de un Estado) en un país con frontera con Ucrania, Rusia o Bielorrusia o con costa en el mar
   Negro, o si todo el país está dentro de la banda (Moldavia); si no, interior.

Por qué 150 km y 50 km: de los 322 incidentes con punto, 97 están a menos de 50 km de esa frontera,
los demás de la banda llegan hasta 144 km (incursiones en Polonia, Rumanía y Lituania) y el
siguiente está a 191 km (aeropuerto de Bucarest, interior). El corte va en ese hueco. En el mar
Negro, el puerto de Constanza está en la costa y lo siguiente, el aeropuerto de Sofía, a más de 200
km del mar.

Resultado en producción tras la primera recogida con el código nuevo (13:17): de los 435
publicados, **205 de frontera y 230 de interior**. La recogida guarda el grupo en la base con todos
los datos del incidente (también si el dron entró desde fuera o es de un Estado, que no se
publican): por eso son 7 más de frontera que si se calcula solo con lo publicado (198), sobre todo
sobrevuelos de Polonia, Lituania y Letonia sin lugar que entraron desde fuera. Cada incidente guarda `zona` con
`grupo`, `motivo` y, si hay punto o lugar, `distancia_km` (esquema 1.14.0); el cambio queda en el
historial con su motivo. La recogida lo recalcula cada hora y solo guarda lo que cambia. En la
exportación semanal lleva origen «deducido», método «regla».

## Arreglos del mismo paquete

1. **Contadores.** Un atribuido es por fuerza un confirmado: los confirmados los incluyen. Con el
   filtro de atribuidos la cabecera dice «4 confirmados · 4 atribuidos». Las páginas de texto usan la
   misma cuenta y llms.txt dice «199 confirmados (4 de ellos atribuidos)». Prueba: los contadores
   cuadran con cualquier combinación de estado, zona y país (`web/tests/prevision.test.tsx`).
2. **Corredores con «Todo».** Con todo el periodo había 331 arcos de cada zona a cada región. Ahora
   se dibujan los 10 con más drones de cada sentido, con el grosor según los drones y el mismo
   violeta; una leyenda pequeña lo dice («Los 20 corredores con más drones, de 331») y deja ver todos.
3. **Leyenda de Presión.** Con «Todo» no hay periodo anterior con que comparar: la leyenda dice
   «Elige un periodo para ver la tendencia» («Choose a period to see the trend»), y la ficha del
   país lo mismo en lugar de «sin periodo anterior con datos».
4. **Detector de cierres por tráfico aéreo.** Ver el apartado siguiente.

## Detector de cierres

Hay dos detectores. El **del archivo diario** de adsb.lol marca cada hueco de tráfico de cada
aeropuerto («candidata» cuando no lo explica un incidente ni el tiempo) y alimenta la búsqueda
dirigida de noticias. El **en directo** no ha abierto ningún aviso desde que se puso en marcha
(`avisos_historial.jsonl` no existe en el servidor). Los falsos positivos de Antalya, Berlín y la
madrugada son del primero.

### Del archivo diario: antes y después

Comprobado contra los cierres confirmados de la base (incidentes con cierre declarado o
interrupción del aeropuerto, con su código OACI), en los 342 días procesados con cobertura alta o
media ese día: **47 cierres comprobables**. Detectado = una anomalía significativa del aeropuerto
que se solapa con el incidente (una hora de margen), sin el tiempo como explicación. Falsa alarma =
una anomalía marcada que no se solapa con ningún incidente de ese aeropuerto.

| | Detectados | Se le escapan | Falsas alarmas | Antalya | Berlín | De 22 a 03 UTC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Antes | 14 de 47 | 33 | 1.633 | 18 | 18 | 278 |
| Después | 13 de 47 | 34 | **141** | 0 | 2 | 17 |

Las causas, medidas en las 1.633 falsas alarmas, y lo que cambia
([`proceso/mediciones.revisar_candidatas`](../proceso/mediciones.py)): una candidata se revisa cada
hora y queda como

- `cobertura_baja` si la cobertura del día no llega a 0,7: los receptores dejaron huecos (Antalya y
  Berlín tenían días con cobertura «media» de 0,52 a 0,77 y huecos de 4 a 6 horas sin nada visto);
- `caida_de_la_fuente` si 10 aeropuertos o más tienen un hueco a la vez (el 9 de agosto de 2026 el
  archivo no tiene Europa de 12:12 a 18:03);
- `poco_trafico` si se esperaban menos de 6 movimientos por hora en el hueco: es la madrugada, y
  la línea base es la del mismo aeropuerto, el mismo día de la semana y la misma hora local;
- `sin_desvios` si hubo menos de 2 aeronaves en espera o desviadas: los aviones no fueron a otro
  sitio, son los receptores (todas las de Antalya; en los cierres detectados hubo de 3 a 61);
- `habitual` si ese aeropuerto tuvo un hueco así en el 15 % o más de sus 28 días anteriores con
  cobertura (Basilea-Mulhouse tenía 90 en 342 días).

El cierre que se pierde es el de Múnich del 4 de octubre de 2025 a las 03:51: al amanecer, sin
ninguna aeronave en espera ni desviada. Lo que sigue escapándose son sobre todo cierres declarados
de menos de 30 minutos o con menos de 8 movimientos perdidos (avistamientos que pararon la pista
unos minutos), que el archivo no distingue de un día normal.

### En directo

Cambios ([`proceso/directo.py`](../proceso/directo.py), regla `directo-1.1.0`):

- **Lieja, Chisináu y los demás aeropuertos con un cierre publicado** se vigilan con cobertura alta
  o media y 20 movimientos al día o más (`recogida.directo.aeropuertos_con_cierre`, que lee los
  incidentes publicados del clon). Hoy son 24 aeropuertos con cierre publicado fuera de los 62
  vigilados: EBCI, EDDE, EDDW, EDJA, EDSB, EGLL, EGPH, EHEH, EKBI, EKEB, EKKA, EKYT, ENBN, ENBR,
  ENDU, EPLB, LEAL, LEIB, LEMG, LEPA, LEZL, LRIA, LUKK y LXGB. La señal sigue exigiendo ver el 60 %
  de lo esperado en las tres horas previas, así que un aeropuerto con poca cobertura ese día no da
  avisos.
- **Receptores caídos** (Antalya): si en la última media hora se ven cerca del aeropuerto menos de
  la cuarta parte de las aeronaves que en cada media hora de las dos horas y media anteriores, no
  hay aviso.
- **Un despegue suelto** en mitad del cierre (Berlín, 23 de septiembre de 2026, a las 18:56) ya no
  reinicia la persistencia de la señal: ese ciclo no avisa, pero el siguiente sí si la señal sigue.

**Reproducción con las trazas del archivo** (`recogida/directo_reproduccion.py`, en el servidor,
como trabajo de sesión con 3 GB y prioridad baja; unos 14 minutos por día). Los cinco días clave,
con el código nuevo, frente a lo que daba el anterior según
[`informe_europa_directo.md`](informe_europa_directo.md):

| Día | Antes | Después |
| --- | --- | --- |
| Antalya, 08/10/2025 (los receptores dejan de ver la zona) | Aviso falso a las 09:30 | Sin aviso (Antalya vigilado) |
| Berlín, 23/09/2026 (cierre de 53 min con un despegue suelto) | No se detecta | **Detectado a las 18:49** (comienzo 18:15) |
| 04/11/2025: Bruselas, Lieja y Múnich | Bruselas 19:09, Múnich 19:25; Lieja no vigilado | Bruselas 19:09 y Múnich 19:25, igual; **Lieja vigilado**, su cierre no da señal: de noche, con poco tráfico de carga, lo que falta no llega a 0,5 movimientos por minuto |
| Chisináu, 08/09/2026 | No vigilado (cobertura insuficiente) | Sigue fuera: en el archivo de esos días la cobertura es insuficiente, también para la regla nueva |
| Copenhague, 22/09/2025 | Detectado a las 18:52 | Detectado a las 18:52, igual |

Los vigilados de esos días pasan de 86 a 90-109 (con los aeropuertos con cierre publicado). La
reproducción de los 16 días restantes de la lista (días de cierre no detectados y días normales) se
paró para dejar sitio al ensayo de la fusión (un trabajo de sesión a la vez); queda en los
pendientes.

## Registro en vivo y exportación

- Tabla `previsiones` de la base (`almacen/base.py`): una fila por previsión, con su hora, sin
  cambios ni borrados (disparadores). Entra la de la frontera de cada país en la primera recogida
  desde las 17:00 UTC (antes de que empiece la noche en Ucrania) y la de la semana el sábado. Se
  puntúa al publicar, sin tocarla: la de la noche a los 3 días, la de la semana una semana después de
  acabar.
- `prevision.json` lleva el registro entero con el resultado al lado; el marcador de la semana pone
  las previsiones en vivo ya puntuadas en lugar de las reconstruidas.
- Exportación semanal, formato 1.5.0: `previsiones.jsonl` con cada previsión registrada y su
  procedencia `{origen: "calculado", metodo: <versión>, fecha: <emitida>}`; esquema en
  `esquema/exportacion/1.5.0/prevision.schema.json`. Las rachas y las comprobaciones se recalculan
  con los incidentes de la propia exportación.
- Si el cálculo falla, la recogida publica todo lo demás, deja el aviso en el diario y no toca
  `prevision.json`, que la web enseña con su fecha de cálculo (prueba
  `test_un_fallo_deja_la_prevision_anterior`).

## Pruebas

- Python: `tests/test_prevision.py` (comprobación con el pasado sobre la copia fija
  `tests/fixtures/prevision/datos.json.gz`, que falla si un método publicado deja de mejorar a su
  referencia; esquema del fichero; registro inmutable; paso de la recogida), `tests/test_zona.py`,
  `tests/test_detector_cierres.py`. Toda la batería y la exportación de la base de prueba, en verde.
- Web: `web/tests/prevision.test.tsx` (fichero publicado contra su validador, panel, gráfica,
  contadores con cualquier filtro, filtro de zona, leyendas) y `web/e2e/prevision.spec.ts` (abrir y
  cerrar sin mover el mapa en 360, 390, 412 px y escritorio; tocar una racha; filtro; corredores;
  página de texto sin código), que corre también en la integración continua.

## Ensayo, fusión y producción

**Ensayo** (paso c2 de [`fusiones.md`](fusiones.md)) en el servidor, sobre una copia propia de la
base del disco y de las carpetas de datos, sin el cerrojo, con 3 GB y prioridad baja: recogida
completa y exportación semanal sin subir, **código 0** (19 min). Clasificó 436 incidentes
(205/231), calculó la previsión (frontera RO y MD, semana MD y RO, rachas MD y LT) y la exportación
1.5.0 validó. Se repitió tras sacar la revisión de candidatas del tope de tiempo del tráfico (en el
primer ensayo el histórico de anomalías se comía los 150 s y la revisión no llegaba a correr): de
nuevo código 0, con 1.550 interrupciones revisadas.

**Fusión**: PR #138, a las 12:43, por avance rápido con un solo commit con la dirección anónima, la
lista de ficheros comprobada (94, de `publicacion/` solo `prevision.json`, nuevo) y la CI en verde
sobre la rama rebasada (Python, web y las pruebas de navegador nuevas). Incidentes servidos antes y
después: 435.

**Recogidas siguientes**:

- 13:17: código 0, publicada en `main`; frontera o interior guardado en 436 incidentes, 1.527
  interrupciones revisadas, previsión calculada. Pico de 4 GB según systemd (con caché; tope 5 GB).
  `prevision.json` entra en la publicación desde la recogida siguiente: el script lee la lista de
  ficheros publicados antes de poner el código nuevo en el clon.
- 14:17: código 0, publicada en `main` a las 14:34, ya con `publicacion/prevision.json` (previsión
  del servidor: frontera RO y MD, semana MD y RO, rachas MD y LT); frontera o interior sin cambios
  (0 guardados). Pico de 3,7 GB.

**Producción** (droneobservatory.eu, después del despliegue con los datos de las 13:17): las 21
pruebas de `e2e/prevision.spec.ts` en verde en 360, 390, 412 px y escritorio (abrir y cerrar sin
mover el mapa, tocar una racha, filtro, corredores, página de texto sin código), y revisadas una a
una las capturas:

| Captura | Qué se ve |
| --- | --- |
| `prevision-360x800.png`, `prevision-390x844.png`, `prevision-412x915.png` | La pestaña «Previsión» dentro de «Europa ahora» en el teléfono |
| `prevision-escritorio.png` | El desplegable con Rumanía (4 de cada 10, 40 %) y Moldavia (4 de cada 10, 37 %) |
| `prevision-racha-*.png` | Tras tocar la racha de Moldavia: el país en el filtro, del 17/08 al 04/10, y el mapa sobre Moldavia |
| `frontera-filtro-*.png` | Filtro «Dónde» con «Frontera» |
| `corredores-todo-*.png` | Corredores con «Todo»: los 20 con más drones de 331 y «Ver los 331» |
| `prevision-contadores-atribuidos-escritorio.png`, `-390x844.png` | Con el filtro de atribuidos: 4 incidentes · 4 confirmados · 4 atribuidos |
| `prevision-presion-todo-escritorio.png`, `-390x844.png` | Presión con «Todo»: «Elige un periodo para ver la tendencia» |
| `prevision-ficha-moldavia-escritorio.png`, `-390x844.png` | Ficha de Moldavia con su racha y la gráfica semanal con la banda de lo normal |
| `prevision-360-antes-de-integrar.png` | Por qué «Previsión» va en una pestaña en el teléfono: con un periodo, el tercer botón bajaba a otra fila |

`/prevision` y `/en/forecast` se leen sin ejecutar código (prueba), con su enlace en el sitemap y en
llms.txt.

**Primera carga.** En producción, mediana de 7 pasadas (`web/scripts/medir-carga.ts`), antes y
después: escritorio FCP 300 → 252 ms y mapa listo 2.067 → 2.006 ms; móvil (CPU ×4) FCP 348 → 336 ms
y mapa listo 2.851 → 2.956 ms. Para separar el ruido de la red, medición intercalada en local con
las mismas teselas (3 rondas de 5 pasadas, versión anterior y nueva alternadas): móvil, mapa listo
2.026 → 2.002 ms; escritorio, 962 → 981 ms; FCP sin cambios. **No empeora.** La previsión no entra
en la primera carga (se pide al abrir «Previsión» o la ficha de un país). El HTML de la portada
crece 7 KB (unos 2 KB comprimido): las dos secciones nuevas de la metodología, que la portada ya
llevaba prerenderizada.

## Pendientes, con su arreglo

- **Factor «ataque en curso».** Arreglo: con 6 meses de captura del seguimiento en directo, añadir
  los drones en vuelo hacia el sur a las 20:00 UTC como factor y volver a comprobar.
- **Aviso de segunda noche.** Arreglo: el de la tabla de lo no publicado.
- **Frontera de Lituania y Letonia.** Arreglo: un predictor propio con los ataques ucranianos
  contra el norte de Rusia.
- **Reproducción de los 16 días restantes** (días de cierre no detectados y días normales) con el
  código nuevo y el anterior. Arreglo: lanzar en el servidor la misma lista (`/var/tmp/eodi-prev/
  reproducir.sh`, empezando por el sexto día) cuando no haya otro trabajo de la sesión; unas 4 horas.
- **Lieja de noche.** Arreglo: el pendiente ya anotado en `informe_europa_directo.md` (segunda vía
  de señal con aeronaves en espera y vuelos desviados cuando lo que falta crece despacio).
- **Chisináu sin cobertura.** Arreglo: un receptor de adsb.lol en Moldavia (lo aporta cualquiera
  con una antena) o el respaldo adsb.fi para ese círculo; hasta entonces no se puede vigilar.
- **Cierres declarados muy cortos que el archivo no ve.** Arreglo: casar también los huecos «menor»
  de 15 a 30 minutos cuando un incidente del aeropuerto los nombra, solo para medir su duración.
