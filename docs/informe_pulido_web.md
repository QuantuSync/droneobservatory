# Pulido de la web: ocho arreglos vistos en el teléfono

Fecha: 4 de octubre de 2026. PR #87 (código y pruebas) y PR #88 (este informe y las capturas
de producción).

Los ocho defectos se vieron en un teléfono Android con Chrome. Cada arreglo se comprobó primero
en el teléfono (360 × 800, 390 × 844 y 412 × 915, con tacto) y después en escritorio
(1440 × 900), en local y en droneobservatory.eu. Las capturas de producción están en
`docs/capturas/pulido-*.png`: el punto 1 y el menú en los tres tamaños de teléfono, el resto en
390 × 844 y en escritorio.

Principio que se sigue en todos: la pantalla es el mapa; sobre él solo hay botones pequeños y
lo demás se abre cuando se pide. Colores de los estados sin cambios: notificado círculo naranja,
confirmado círculo rojo, atribuido bandera roja, desmentido círculo gris discontinuo; el verde,
solo para «datos al día».

## 1. El aviso de novedades se montaba con los botones

**Causa.** El aviso «N novedades desde tu última visita» iba en una capa colocada justo debajo
de la cabecera (`top-full`), y los botones «Filtros» y «Europa ahora» en otra colocada arriba
del mapa (`top-2`): las dos en el mismo sitio. En el teléfono el aviso, además, era un panel
ancho que partía la línea en tres. Las pruebas de la pantalla de entrada se hacían sin visita
anterior guardada, es decir, sin novedades, y el choque no salía.

**Cambio.** Sobre el mapa ya no hay aviso: el botón «Europa ahora» lleva el número de novedades
en una cifra blanca pequeña (junto a la naranja de los cierres en curso, si los hay), que es lo
que menos sitio ocupa. Dentro de «Europa ahora», la primera línea dice «N novedades desde tu
última visita» con «Verlas» y «Descartar». «Verlas» abre la primera y el recorrido («Novedad 1
de 98 · Anterior · Siguiente») va dentro de la ficha, no sobre el mapa. Lo que sí se sigue
mostrando sobre el mapa (la reproducción «Noche a noche» y los avisos de error) va en la misma
columna que los botones, debajo de ellos: por construcción no se pueden montar. Igual en
escritorio.

**Pruebas.** `e2e/pulido.spec.ts`, punto 1, en 360, 390, 412 px y escritorio, con novedades y
sin ellas: el centro y los extremos de cada botón son del propio botón (nada encima), ningún
aviso cae en la fila de los botones, ningún texto de los botones ni de la línea de novedades se
sale de su caja, «Verlas» abre la ficha con su recorrido. En Vitest
(`tests/diseno.test.tsx`): el número del botón, la línea dentro del panel, «Verlas» y
«Descartar».

## 2. El menú del teléfono

**Causa.** «Noche a noche» se pintaba dentro de «Capas» con un estilo propio (texto gris y más
pequeño, sin el blanco de los demás botones del menú), así que parecía desactivado; su bloque de
44 px bajo el selector de capas era el hueco grande que se veía antes de «Más». Las cinco capas
iban en una sola fila de 328 px útiles, y «Incidentes» tocaba el borde de su casilla.

**Cambio.** «Noche a noche» es una vista, no una capa: va en «Más», junto a «En directo», con
el mismo estilo, y al pulsarlo el menú se cierra para que se vea la reproducción. Las capas van
en una rejilla de tres columnas (dos filas: Incidentes, Ucrania, Densidad / Presión, GPS); con
la capa de Ucrania encendida, las de la guerra por satélite (PR #65) van en su propia rejilla
igual. Todas las secciones tienen el mismo espacio.

**Pruebas.** `e2e/pulido.spec.ts`, punto 2, en los tres teléfonos: las cinco capas, cada una
con al menos 6 px libres a cada lado del texto; «Noche a noche» en «Más» con la misma clase que
«En directo» y fuera de «Capas»; el espacio entre el último elemento de cada sección y su borde
es el mismo en todas.

## 3. «4 atribuidos» descuadrado

**Causa.** La bandera iba dentro del rótulo («🏴 atribuidos»), no junto al número: en la
rejilla del menú quedaba debajo del 4, en la línea del texto; en la cabecera de escritorio,
delante de la palabra.

**Cambio.** Las cuatro cifras tienen la misma estructura: el número (con la bandera a su lado,
en el caso de los atribuidos) y el rótulo, debajo en el menú y a la derecha en la cabecera.

**Pruebas.** `e2e/pulido.spec.ts`, punto 3, en los cuatro tamaños: en las cuatro cifras el
número va antes que el texto y la bandera queda dentro de la altura del número.

## 4. La bandera de «atribuido» tenía poca fuerza

**Causa.** Era un banderín triangular de 13 px de mástil con un borde oscuro del color del
fondo, más pequeño que algunos círculos; además, los atribuidos entraban en las agrupaciones del
mapa: en los zooms iniciales no se veía ninguna bandera, solo el anillo rojo del grupo, y el
número de los grupos se dibujaba por encima.

**Cambio.** Una sola forma de bandera para el mapa, la leyenda, las fichas, las cifras y el
pulso (`BANDERA` en `web/src/paleta.ts`): mástil de 28 px y paño de 20 × 13 px que ondea,
relleno en el rojo de «confirmado», con un contorno claro de 1,5 px que lo separa del fondo y de
los círculos vecinos. Un círculo de incidente suelto mide 13 px. Los atribuidos tienen su propia
fuente sin agrupar: cada uno con su bandera a cualquier zoom, por encima de círculos, grupos y
números. El pie del mástil sigue en el punto exacto (la capa ancla el icono por su esquina
inferior izquierda y lo desplaza hasta el pie). Con el dedo, el objetivo sigue siendo de 44 px
y se mide al centro de la bandera, no al pie. El pulso de los incidentes nuevos sigue la silueta
de la bandera, más ancho para que se vea sobre el contorno claro. Sin círculo debajo, detrás ni
alrededor; la marca del foco térmico, si lo hay, sigue a la izquierda del mástil. El incidente
abierto lleva la misma bandera con un contorno más ancho del color de selección. Los grupos
pasan a ser rojos solo por los confirmados que contienen, porque ya no contienen atribuidos.

**Pruebas.** Vitest (`tests/colores.test.tsx`): la forma (mástil vertical desde el pie, paño
dentro de la caja, más alta y más ancha que un círculo suelto), el contorno claro con contraste
mayor que 10 contra el fondo, el ancla y el desplazamiento que llevan el pie al punto, la fuente
sin agrupar, el orden de capas (encima de grupos, números e incidentes sueltos) y que en su
fuente no haya ningún círculo salvo la marca del foco. `tests/web.test.ts`: un atribuido en el
mismo punto que otro incidente va con su bandera y el otro queda solo. `tests/pulso.test.ts`:
el pulso de la bandera con la forma nueva. `e2e/pulido.spec.ts`, punto 4: EODI-2026-00015,
EODI-2026-00074 y EODI-2026-00283 en el mapa y en su ficha.

## 5. La leyenda de la presión no decía el periodo

**Causa.** El texto de la leyenda era fijo («Incidentes en el periodo»).

**Cambio.** La leyenda dice el periodo en palabras, en español e inglés: «Incidentes en los
últimos 30 días», «Incidentes del 1 al 30 de noviembre de 2025», «Incidentes del 28 de diciembre
de 2025 al 3 de enero de 2026», «Incidentes del 3 de octubre de 2026», «Incidentes desde el
primer dato». Al encender la presión con el periodo en «Todo» (sin periodo anterior con el que
comparar), el periodo pasa solo a «Últimos 30 días», que queda en la dirección y en el botón de
filtros como periodo activo. Con otro periodo elegido no se toca.

**Pruebas.** Vitest (`tests/periodo.test.tsx`): los textos de la leyenda en los dos idiomas, el
paso a 30 días con «Todo» y que con «Últimos 7 días» no cambia. `e2e/pulido.spec.ts`, punto 5,
en los cuatro tamaños.

## 6. Los círculos tapaban nombres de países

**Causa.** Los círculos de los grupos son una capa de tipo círculo, y MapLibre solo evita que
se pisen los símbolos (textos e iconos); los nombres de la base se colocaban sin tener en
cuenta los círculos, que se dibujaban encima y dejaban el texto partido asomando por los lados.

**Cambio.** Una capa de obstáculos invisibles, del tamaño exacto de cada círculo (grupos,
pilas e incidentes sueltos, y los grupos y puntos de la capa de guerra), que ocupa su sitio al
colocar los nombres: un nombre que chocaría con un marcador no se dibuja; o se ve entero o no se
ve. Las banderas y la etiqueta de un cierre en directo ocupan también su sitio. La etiqueta de un
cierre en directo pasa a ser lo último que se dibuja: ningún grupo vecino ni bandera la pisa.

**Pruebas.** Vitest: la etiqueta del cierre es la última capa y ocupa su sitio
(`tests/colores.test.tsx`). `e2e/pulido.spec.ts`, punto 6: capturas de los tres zooms iniciales
en los cuatro tamaños, revisadas una a una.

## 7. La fecha de «drones lanzados la última noche»

**Causa.** No había retraso: en la noche del día 3, el último parte publicado era el de la
noche del 2 al 3, publicado a las 06:01 UTC del día 3. La fecha que se escribía era la del
**inicio** del parte (las 15:00 UTC del día 2, las 18:00 en Kiev), y por eso se leía «02/10/2026».
Había además un fallo: la línea sumaba todos los partes que empezaban el mismo día, así que el
parte de día (de 06:30 a 18:00) y el de la noche siguiente se sumaban en uno (el 1 de octubre
habría salido 97 + 108 = 205 «la última noche»).

**Cambio.** El resumen de la capa de guerra lleva el último parte publicado (el que acaba más
tarde, contra Ucrania, con su cifra, sin los tramos que ya cuenta otro parte), con su inicio y su
fin. La línea dice su noche sin ambigüedad: «135 drones lanzados la última noche · noche del 3
al 4 de octubre» («night of 3 to 4 October»); si el último parte es de día, «drones lanzados en
el último parte de día · día 1 de octubre»; y si tiene más de 36 horas desde su fin, «drones
lanzados · último parte: noche del 2 al 3 de octubre». Pulsar la línea abre la capa de Ucrania
en el día en que empieza el parte, como antes.

**Pruebas.** Vitest: el último parte del resumen (sin sumar, sin el tramo incluido en otro, con
un parte de día posterior), los textos de noche, de noche que cambia de mes, de día y de parte
antiguo en los dos idiomas, y el paso a «último parte» al pasar las 36 horas
(`tests/datos.test.ts`, `tests/europa.test.tsx`). `e2e/pulido.spec.ts`, punto 7: la cifra y
la noche coinciden con `ucrania-resumen.json` publicado.

## 8. El filtro «Últimas 24 horas» salía vacío

**Causa.** La ya localizada: el periodo se contaba en días UTC enteros y «Últimas 24 horas» era
«el último día con datos». A primera hora del día quedaba vacío, y se quedaban fuera los
incidentes de la tarde anterior.

**Cambio.** «Últimas 24 horas» cuenta 24 horas hacia atrás desde el momento actual
(`ultimas24Horas` en `web/src/estado/filtros.ts`). Cada incidente lleva el instante de su
inicio cuando se conoce la hora (precisión de minuto o de hora): entra si empezó dentro de esas
24 horas. Si solo tiene día (o la fecha es aproximada, la de la noticia), entra si su día es hoy
o ayer. El mapa, la lista, las cifras, la capa de presión (que compara con las 24 horas
anteriores) y el destello de lo reciente usan la misma regla, y «En directo» enseña solo los
incidentes del periodo elegido, igual que el mapa. Los periodos de 7 y 30 días, el último año y
«Entre fechas» siguen contándose por días como antes, y los enlaces compartidos
(`?ultimos=24h`, `?ultimos=7d`, `?desde=…&hasta=…`) abren lo mismo.

**Pruebas.** `tests/periodo.test.tsx`, con la hora puesta a las 00:30, a las 06:45 y a las 23:30
UTC: qué entra (con hora hace 30 min, 23 h 59 min y 5 h; sin hora hoy y ayer; fecha aproximada
de ayer) y qué no (con hora hace 24 h y 1 min o tres días; sin hora anteayer); a las 00:30, la
tarde anterior entra. En la aplicación entera, a esas tres horas: el mapa, la cifra de
incidentes y «En directo» dan los mismos incidentes. Los periodos de días, «Entre fechas»,
«Todo» y los enlaces compartidos no cambian. La presión compara con las 24 horas anteriores.
`e2e/pulido.spec.ts`, punto 8: en producción, la cifra coincide con lo que da la regla sobre
`resumen.json` y «En directo» solo enseña incidentes del periodo.

## Otros cambios

- Textos de la ayuda y la metodología, en español e inglés: la bandera con su contorno y siempre
  encima, el número de novedades en el botón, «Últimas 24 horas» desde este momento y los nombres
  que ceden ante los círculos.
- Borrado lo que quedó sin uso: el aviso de novedades sobre el mapa, la suma de lanzamientos por
  noche, la bandera pequeña de la leyenda, el recuento de atribuidos de los grupos y los filtros
  de atribuidos de las capas de círculos, con sus pruebas.

## Comprobación

- Puerta local: lint, TypeScript estricto, `npm audit` sin avisos, Vitest (todas las pruebas
  en verde, junto con las del PR #65) y el build.
- Playwright (`e2e/pulido.spec.ts`): 28 pruebas (7 por tamaño en 360, 390, 412 y escritorio) en
  verde contra el servidor local y contra droneobservatory.eu tras el despliegue del 4 de
  octubre de 2026. En producción, con «Últimas 24 horas» a las 07:45 UTC: 10 incidentes (2 con
  punto en el mapa), y «En directo» solo con esos.
- Número de incidentes servidos: 513 antes y después de fusionar.
- Al fusionar #87, `main` recibió en el mismo minuto el informe del PR #84 y el commit único lo
  dejó fuera; se restauró enseguida, tal cual, con un commit propio (16a4223). Desde entonces el
  paso de comprobar la lista de ficheros se hace justo después del último fetch.

## Pendientes

- **Banderas casi en el mismo punto.** Dos atribuidos a pocos kilómetros (Chisináu) se dibujan
  una sobre otra al alejar. Arreglo: abrir en abanico las banderas a menos de 20 px entre sí,
  con una línea fina al punto real.
- **«Noche a noche» suma el parte de día con la noche siguiente.** La reproducción agrupa los
  partes por el día de inicio, como hacía la línea de «Europa ahora». Arreglo: agrupar por parte
  (con su inicio y su fin), igual que el último parte.
