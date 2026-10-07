# Tipo de dron y rutas de los drones sobre Ucrania

European Observatory of Drone Incidents, 7 de octubre de 2026. Las horas son UTC. Fase 1 (tipo de
dron): PR #144, fusionado el 6 de octubre (`05a81bb`). Fase 2 (rutas y recorridos): PR #145,
fusionado el 7 de octubre (`5df612a`). Este informe va en su propio PR.

**En resumen.**

- Cada incidente de Europa tiene ahora una fila **«Tipo de dron»**. Hay tres casos: **lo dice la
  autoridad** (6 incidentes), **lo deduce el observatorio** con una probabilidad por clase y sus
  razones (69), o **no se muestra nada** (363) porque no hay datos suficientes.
- Las deducciones solo se publican para las dos clases que pasan la comprobación con casos de
  respuesta conocida: **dron de ataque de largo alcance de hélice** y **señuelo de largo
  alcance**. Las demás clases no se publican todavía.
- En «Filtros» hay un grupo nuevo, **«Tipo de dron»**, que filtra por lo identificado y por lo
  deducido por separado.
- Sobre Ucrania hay una subcapa nueva, **«Rutas»**, apagada al empezar: franjas violetas finas con
  su anchura de incertidumbre. Hoy se publican **2 noches** (4–5 y 5–6 de octubre), las dos con
  pistas de NEPTUN y su enlace.
- La reconstrucción de rutas con los mensajes de seguimiento de la Fuerza Aérea de Ucrania **no
  pasa** la comprobación contra NEPTUN y la línea recta, así que no se publica ninguna noche
  reconstruida con ellos. La comprobación se repite cada hora y publicaría sola si pasara.
- Cuatro incidentes de frontera tienen un **recorrido según la autoridad**: los lugares que nombra
  una declaración oficial, en orden, dibujados como franja al abrir la ficha.

## Qué ve el usuario

**En la ficha del incidente** hay una fila «Tipo de dron», debajo de «Drones»:

- *Lo dice la autoridad*: la clase («Señuelo de largo alcance», por ejemplo), la cita literal y su
  fuente. Si la autoridad nombra el modelo, se muestra tal cual lo dice ella.
- *Deducido*: «Dron de ataque de largo alcance de hélice · 5 de cada 10 (49 %)», «Señuelo de
  largo alcance · 4 de cada 10 (42 %)», «Otras clases: 9 %», con la frase «Deducido por el
  observatorio a partir de lo publicado; ninguna autoridad ha dicho qué dron era» y, plegado,
  «Por qué»: el punto de partida (cuántos casos conocidos de esa zona) y cada razón física que
  movió la probabilidad (distancia a Ucrania, Rusia o Bielorrusia frente al alcance de cada
  clase, velocidad, altura, duración, viento). Nunca se escribe un modelo concreto en lo
  deducido: siempre «compatible con» una clase.
- *Sin base*: la fila no aparece.

**En «Filtros»** un grupo «Tipo de dron» con las clases que tienen algún incidente, separando
«según la autoridad» y «deducido». Va en la dirección de la página (`?dron=`), como los demás.

**En la capa de Ucrania**, una subcapa más, **«Rutas»**, junto a «Corredores», apagada al
empezar. En el teléfono las subcapas pasan a una rejilla de tres para que quepan sin bajar al
mapa. Al encenderla:

- Franjas violetas finas, con relleno muy suave, por debajo de los marcadores del periodo. Con
  periodos largos se dibujan solo las noches con más drones (diez como máximo) y la leyenda lo
  dice: «Rutas de las 10 noches con más drones, de N del periodo».
- La leyenda, plegable, dice cuántas noches, que son franjas con su anchura de incertidumbre y no
  líneas exactas, y enlaza a NEPTUN.
- Al tocar una franja se abre su ficha: noche, grupo, tipo, tramo con sus horas, precisión
  («franja de 70 km de radio»), fuente con enlace a NEPTUN y los incidentes y el ataque de esa
  noche. Cerrarla no mueve el mapa.
- En **«Noche a noche»** se ven las rutas de la noche que se está mostrando, si las tiene.

**En la ficha de un incidente con recorrido**, una fila «Recorrido según la autoridad»
(«Biliaivka → Tudora»), con la cita, y en el mapa la franja que une cada dos lugares. Se quita al
cerrar la ficha.

**Páginas de texto** (las que se leen sin código): la página de cada incidente lleva la fila del
tipo de dron y la de recorrido; la página de Ucrania lleva un apartado de rutas; la metodología
tiene dos apartados nuevos, «Tipo de dron» y «Rutas».

**Exportación semanal**: formato 1.6.0. Cada incidente lleva `tipo_dron` y `recorrido`, y cada
valor tiene su regla de procedencia (autoridad, cita oficial o deducido por el observatorio, con
la versión del método). Lleva también las noches de ruta publicadas y las cifras por grupo.

## Cómo se obtiene y se comprueba cada cosa

### Tipo de dron que dice la autoridad

Se buscan en las fuentes de cada incidente los nombres de familias de drones (Shahed, Geran,
Gerbera, Orlan, Lancet, DJI, etc.) y se pasan a una de ocho clases. Cuenta solo lo que viene de una
fuente oficial o de una cita literal de la autoridad, y solo si no expresa duda («posiblemente»,
«similar a»). Se guarda la frase literal y su fuente; la cita se muestra solo si la fuente es
pública.

### Rasgos con cita

Un extractor en varios idiomas saca de los textos los rasgos que sirven para descartar clases:
velocidad, altura, duración, tamaño, número de aparatos, si venía del mar. Cada rasgo guarda su
cita y su fuente. Se probó con los textos de la base y se corrigieron falsos positivos (nombres
propios como Kleine-Brogel, «grande» referido a un aeropuerto, duraciones de un cierre tomadas
por la del vuelo, «enjambre» de policías).

### Tipo de dron deducido

Para cada incidente se parte de la frecuencia de cada clase en los casos conocidos de su zona
(frontera con la guerra o interior), quitando siempre el propio caso. Luego se aplican
restricciones físicas fijadas de antemano con su fuente en `configuracion/tipo_dron.json`:

- distancia a Ucrania, Rusia o Bielorrusia y a la costa frente al alcance de cada clase;
- viento y tiempo de esa hora y lugar, de la misma fuente meteorológica que ya usa el
  observatorio;
- duración y altura frente a la autonomía y el techo de cada clase;
- velocidad: por debajo de 230 km/h, hélice; por encima de 300 km/h, reacción.

**Comprobación.** 69 casos en los que una autoridad identificó el dron: 6 de la base, 23 del
conjunto de validación y 40 de los informes británicos de cuasi colisiones (de estos, solo los de
2017 en adelante cuentan para «ala fija», porque antes esa categoría era la que se ponía por
defecto). 31 tienen datos suficientes para deducir algo. Cada caso se calcula sin usarse a sí
mismo.

| | Método | Siempre la clase más frecuente | La más frecuente de su zona |
|---|---|---|---|
| Acierta la primera | 61 % (19 de 31) | 23 % (7 de 31) | 61 % (19 de 31) |
| Está entre las dos primeras | 94 % | 61 % | 94 % |
| Puntuación logarítmica por caso | −1,01 | −2,30 | −1,51 |

La puntuación logarítmica mide cuánta probabilidad se dio a lo que pasó: el método la mejora en
1,28 por caso frente a la referencia simple, y en 0,87 en el peor 10 % de 1.000 remuestreos. Frente
a la frecuencia por zona acierta igual en la primera clase, pero reparte mejor la probabilidad
(−1,01 frente a −1,51).

**Qué clases se publican.** Una clase se publica si tiene al menos 5 casos conocidos propios, mejora
la puntuación frente a la referencia y su probabilidad está bien calibrada (error de 0,1 como
máximo, medido por zona):

| Clase | Casos | Mejora | Error de calibración | Se publica |
|---|---|---|---|---|
| Ataque de largo alcance de hélice | 12 | 0,98 | 0,006 | sí |
| Señuelo de largo alcance | 10 | 0,89 | 0,004 | sí |
| Comercial pequeño | 4 | 0,49 | 0,037 | no (faltan casos) |
| Ala fija militar | 1 | — | — | no |
| Reacción | 1 | — | — | no |
| Multirrotor grande, FPV, ala fija pequeña | 0 | — | — | no |

El señuelo nunca sale primero en la frontera (el ataque de hélice lleva siempre algo más), pero su
probabilidad está bien calibrada: por eso se publica como probabilidad, junto a la otra, y no
como respuesta única. Un incidente muestra deducción solo si la presencia del dron está
confirmada, no está desmentido y su clase más probable es una de las publicadas; se enseñan las
clases publicadas con un 10 % o más y el resto va junto en «Otras clases».

### Rutas sobre Ucrania

**Fuentes.** Solo tres: el archivo de NEPTUN (estimaciones a partir de informes, no un radar), los
mensajes de seguimiento de la Fuerza Aérea de Ucrania (los del archivo en directo y unos 33.000
históricos, que se movieron al archivo del servidor sin volver a descargarlos) y las
declaraciones oficiales de Rumanía, Moldavia y Polonia para los recorridos.

**Conversión.** Cada mensaje se pasa a estructura (zona, rumbo, destino, tipo, número) noche a
noche, por trozos y con tope de memoria. Una noche va de las 12:00 de su día a las 12:00 del
siguiente. Resultado: **1.420 noches con mensajes, 37.152 mensajes de seguimiento** y 51.380
avisos de otro tipo; **1.354 pistas de NEPTUN**.

**Cuándo termina un ataque.** Una noche se da por terminada cuando ha pasado su ventana y además
dos horas desde su último mensaje. Nunca se publica una ruta de una noche en curso; hay una
prueba que lo comprueba.

**Franjas.** Cada tramo es una franja con su radio de incertidumbre (la precisión de la zona del
mensaje o la que da NEPTUN para su pista). Los grupos no se identifican por el texto: un tramo une
dos avisos compatibles en tiempo, rumbo y velocidad (250 km/h como máximo; 450 km/h los de
reacción; ventana de 3 horas), con divisiones y uniones marcadas. Cada tramo guarda los mensajes
de los que sale.

**Comprobación de la reconstrucción.** En las noches con NEPTUN se mide la distancia mediana de
cada posición de NEPTUN a la franja reconstruida activa a esa hora, y se compara con la línea
recta entre la zona de lanzamiento y los impactos de esa noche. Para publicar, la reconstrucción
tiene que ser al menos un 20 % mejor, mejor en cada noche y en 2 noches como mínimo.

- Primer intento: pasaba (33 km frente a 78 km), pero solo porque los avisos de región entera
  daban franjas de cientos de kilómetros que lo cubrían todo. En el mapa era una mancha violeta.
- Segundo intento, sin zonas de más de 90 km de precisión: **121,8 km frente a 77,3 km de la
  recta**, sobre 3.949 posiciones de NEPTUN en 2 noches. No pasa. Por la regla del encargo, se publican solo las noches con NEPTUN.

**Enlaces.** Cada noche se une a su ataque (los partes diarios), a los corredores y a los
incidentes de Europa que caen a 50 km de una franja más su radio. En las dos noches publicadas no
hay incidente europeo dentro de las franjas.

### Recorrido de las incursiones

Cuando una declaración oficial de Rumanía, Moldavia o Polonia nombra los lugares por los que pasó
el dron («desde la dirección de Biliaivka, Ucrania, hacia Tudora»), se sitúan con el nomenclátor y
GeoNames (a 80 km como mucho del incidente) y se dibujan en orden como franja. Hoy tienen recorrido
**EODI-2025-00306, EODI-2025-00328, EODI-2026-00193 y EODI-2026-00325**.

### Velocidad entre avistamientos

Cuando dos avistamientos de un mismo episodio dan una velocidad, se usa como restricción del tipo:
solo decide «reacción» si la velocidad mínima posible pasa de 300 km/h. Con los datos actuales
**ningún episodio ni recorrido decide nada**: las velocidades que salen están dentro de lo que
pueden hacer varias clases.

## Cifras en producción

- Tipo de dron, sobre 438 incidentes: **6 según la autoridad** (3 señuelo, 3 ataque de largo
  alcance de hélice), **69 deducidos** (todos con las dos clases publicadas; en 68 sale primero el
  ataque de hélice, en 1 el señuelo) y **363 sin nada**.
- Rutas: **2 noches publicadas**, 4–5 de octubre (329 tramos, 182 grupos, ataque
  EODI-UA-2026-1030 con 205 drones lanzados) y 5–6 de octubre (407 tramos, 217 grupos, ataque
  EODI-UA-2026-1033 con 137), las dos de NEPTUN. La noche del 6 al 7 se publicará sola cuando termine.
  Ninguna noche reconstruida con la Fuerza Aérea.
- Recorridos: **4 incidentes**.

## Pruebas

- **Integración continua**: casos conocidos fijados en `tests/fixtures/tipo_dron/` y
  `tests/fixtures/rutas/`; la prueba falla si el método del tipo de dron deja de mejorar a su
  referencia o si la reconstrucción de rutas pasara a publicarse sin pasar su comprobación.
  Esquemas validados (datos 1.15.0, rutas 1.0.0, exportación 1.6.0). Una prueba impide publicar
  rutas de un ataque en curso.
- **Ensayos** de la recogida horaria y de la exportación semanal sobre una copia de la base real,
  con código 0, antes de cada fusión.
- **Navegador**: 34 pruebas contra producción en 360×800, 390×844, 412×915 y escritorio, todas
  bien: incidentes identificado, deducido y sin base; filtro por clase; «Rutas» con 7 días, 30 días
  y «Todo», sola y con corredores; ficha de una ruta con enlace a NEPTUN, cuyo cierre no mueve el
  mapa; «Noche a noche» con rutas; recorrido de EODI-2026-00193 dibujado y quitado; páginas de
  texto. Las capturas de producción están en la carpeta de capturas de este trabajo,
  `eodi-tr-cap/prod2` (fuera del repositorio): `tipo-identificado-*`, `tipo-deducido-*`,
  `tipo-sin-base-*`, `tipo-filtro-*`, `rutas-7d-*`, `rutas-30d-*`, `rutas-todo-*`,
  `rutas-corredores-*`, `rutas-ficha-*`, `rutas-noche-a-noche-*` y `recorrido-*`, cada una en los
  cuatro tamaños.
- **Primera carga**, en la misma máquina y con los mismos datos, antes de la fase 1 frente a
  ahora, mediana de 10 pasadas con la caché vacía: escritorio **1.485 → 1.518 ms**, móvil (CPU 4
  veces más lenta) **2.366 → 2.420 ms**. La diferencia es menor que lo que varía una pasada de otra
  (unos 400 ms). El HTML crece 5,9 KB y el código de la aplicación 30 KB. Los datos de rutas no se
  piden en la primera carga: solo al encender la subcapa.
- **Recogidas tras cada fusión**: tras la fase 1, las de 22:17 y 23:17 del 6 de octubre terminaron
  bien y publicaron. Tras la fase 2, las de 01:17 y 02:17 del 7 de octubre, también (picos de
  memoria de 4,7 y 4,6 GB, con caché incluida, por debajo del tope de 5 GB). El trabajo nuevo
  `eodi-rutas` (minuto 8, tope de 1 GB) terminó bien a las 01:08 y a las 02:08 (pico de 511 MB).

## En el servidor

- Unidad nueva `eodi-rutas` (minuto 8 de cada hora, prioridad baja, tope de memoria de 1 GB y de
  30 minutos), con su propio cerrojo; nunca toma el de la recogida.
- La recogida horaria deja a las rutas los ataques de cada noche (`datos/rutas/ataques.json`).
- El archivo histórico de la Fuerza Aérea (49 ficheros mensuales, 16 MB) está en el archivo del
  servidor y copiado al bucket privado. La importación se hizo una vez a mano con prioridad baja.
- `eodi-seguimiento` no se ha parado ni reiniciado.
- Los ficheros publicados van al almacén público: `rutas/indice.json` y una noche por fichero
  (`rutas/noches/AAAA-MM-DD.json`). Si una noche se retira, su fichero se borra del almacén.

## Pendiente, con su arreglo

1. **Clase «comercial pequeño»**: tiene 4 casos conocidos propios y hacen falta 5. Arreglo: sumar
   casos de incautaciones policiales con el modelo identificado (comunicados de policía y fiscalía)
   al conjunto de validación; la comprobación lo publica sola al pasar.
2. **Rutas reconstruidas con la Fuerza Aérea**: no pasan (121,8 km frente a 77,3 km). Arreglo: situar
   mejor los avisos de región entera usando el rumbo y el destino del mensaje siguiente, y esperar
   más noches con NEPTUN. La comprobación se repite cada hora.
3. **Velocidad entre avistamientos**: ningún caso decide nada todavía. Arreglo: ninguno de código;
   se aplica sola cuando un episodio tenga dos avistamientos con hora y lugar precisos.
4. **Lugares de recorrido sin situar** (Izmail, Cotlovina, Valea Perjei, Lesnaia): por eso hay solo
   4 recorridos. Arreglo: añadir esas formas al nomenclátor con su región.
5. **Día 5 de octubre en el informe de la captura del seguimiento**: el día está en el archivo pero
   no en su índice. Arreglo: regenerar el índice del informe de la captura.
