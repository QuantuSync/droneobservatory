# Informe del rediseño de la web

Estado: rediseño y correcciones en producción en
[droneobservatory.eu](https://droneobservatory.eu) y
[droneobservatory.eu/en](https://droneobservatory.eu/en). Puerta local en verde (pytest,
ruff check, ruff format --check, mypy; en `web/`: npm audit, lint, TypeScript estricto,
Vitest y build) y Playwright en escritorio, en móvil y en seis tamaños de teléfono contra la
vista previa y contra producción. Lo que queda abierto está al final.

## Criterio

Mapa a pantalla completa y lo demás a su servicio, sin copiar otros productos. En escritorio,
una cabecera fina y una barra de filtros arriba, la ficha en un panel lateral y la línea de
tiempo abajo. En el teléfono, una versión propia: una barra compacta, un menú a pantalla
completa y una sola hoja inferior a la vez. La interfaz va en blancos y grises sobre un fondo
casi negro; los únicos colores son los de estado (verde, ámbar, rojo y gris discontinuo), los
de la capa de Ucrania y el logo. Onest para el texto y JetBrains Mono solo para cifras y
horas, nunca mezcladas en una misma frase ni en un mismo grupo de controles; las dos
autoalojadas.

## Pantalla en escritorio

- **Cabecera** de una sola línea: el logo simplificado y el nombre a la izquierda; en el
  centro las cifras en pequeño (incidentes, confirmados, atribuidos, países) y el estado
  («Actualizado hace 57 min» con su punto de color), que al pulsarlo abre el detalle (datos
  publicados, última recogida, resultado, siguiente recogida y el estado de cada fuente con
  su último dato); a la derecha las capas en un control de tres opciones, «Noche a noche»,
  «En directo», «Ayuda», «Metodología y datos abiertos» y ES · EN. Sin flechas ni adornos:
  cada control dice lo que hace. Cabe en una línea desde 1280 px; por debajo de 1536 px el
  nombre va en dos líneas cortas y por debajo de 1440 px el estado dice solo «hace 57 min» y
  los rótulos bajan a 11 px. Entre 768 y 1023 px la cabecera pasa a dos filas.
- **Filtros** en su barra, con fondo y borde discretos, agrupados con su rótulo: Estado
  (notificado, confirmado, atribuido, desmentido), Tipo (con su forma), Periodo (últimas 24
  horas, últimos 7 días) y País. Todos los controles miden lo mismo y «Quitar filtros»
  aparece en cuanto hay alguno puesto.
- **Ficha** en un panel lateral derecho de altura completa; el mapa vuela al incidente
  dejándolo a la vista a la izquierda del panel. Desaparecen la ficha flotante y su línea.
- **En directo** en un panel a la izquierda; al pulsar una entrada, el mapa vuela al
  incidente y abre su ficha.
- **Zoom y atribuciones** abajo a la derecha, en una sola línea («© OpenStreetMap ·
  Protomaps · Natural Earth», con enlaces); el detalle de fuentes y licencias, en la
  metodología, que lleva el logo completo en su cabecera.
- **Línea de tiempo** plegada con su histograma pequeño siempre a la vista y «Desplegar»; al
  pasar por encima o con la tecla T se despliega con reproducir, día/semana/mes y el periodo.

## Pantalla en el teléfono

Se aplica por debajo de 768 px de ancho y también con el teléfono en horizontal (poca altura
y pantalla táctil). Las dos disposiciones van en el HTML prerenderizado y el CSS muestra la
que toca antes de que llegue el script, así que no hay saltos al cargar; ya en el navegador
solo queda la que se usa.

- **Barra** compacta: logo, «EODI» (el nombre completo va para los lectores de pantalla),
  el punto de estado con «hace 26 min» y «Menú». Sin zoom: se amplía con los dedos.
- **Menú** a pantalla completa con las cifras, las capas y «Noche a noche», los filtros en su
  contenedor y agrupados, «En directo», «Ayuda», «Metodología y datos abiertos» y el idioma.
- **Hojas inferiores**, una sola a la vez (ficha, lista de un punto, línea de tiempo o
  directo): opacas, con un asa que se arrastra o se pulsa entre tres alturas (asomada, media y
  completa). Al abrir una se cierra la anterior. En horizontal se abren a pantalla completa.
- **Línea de tiempo plegada**: una fila fina con «Periodo», el histograma en miniatura y «Ver
  todo» si hay selección. Desplegada, en su hoja, con reproducir, día/semana/mes, «Ver todo»
  y el histograma. En horizontal «Periodo» sube a la barra de arriba y abajo queda un hilo
  con el histograma, para que el mapa siga ocupando la pantalla.
- Todo control mide al menos 44 × 44 px; los enlaces de las atribuciones se pueden tocar en
  44 px de alto sin que la línea crezca, y las asas del periodo tienen 44 px de agarre.
- Zonas seguras: `viewport-fit=cover` y márgenes con `env(safe-area-inset-*)` en la barra,
  el menú, las hojas y la barra de abajo.

Comprobado con Playwright a 360 × 800, 390 × 844 y 412 × 915, en vertical y en horizontal
(`e2e/telefono.spec.ts`): el mapa a la vista en al menos el 80 % de la pantalla en reposo,
ningún texto cortado con puntos suspensivos, todos los objetivos táctiles de 44 px, contraste
AA de todo el texto contra su fondo real, paneles opacos, una sola hoja a la vez y la lista de
un punto con varios incidentes con su primer elemento entero, a la vista y sin nada encima.
Chromium no simula la muesca: de las zonas seguras se comprueba que la página las declara.

## Marcas del mapa

Un solo sistema: un símbolo suelto es siempre un incidente (forma por tipo, color por estado)
y todo lo que junta varios es un círculo con su número, con el tamaño según la raíz de la
cuenta (de 11 a 26 px) y el anillo del color del estado más grave. Eso vale para los grupos de
la agrupación y para las pilas de un mismo punto exacto, que antes eran el símbolo con un
«×n»; al pulsar una pila se elige cuál abrir.

**Las estrellas de ocho puntas** que se veían en los extremos de las líneas de episodio no
eran parte de la codificación: en un mismo punto exacto coincidían un sobrevuelo (cuadrado) y
una incursión (rombo) del episodio EODI-EP-2026-0001, y el cuadrado y el rombo superpuestos
dibujaban una estrella. Ahora ese punto es un círculo con su número.

Confirmados y atribuidos laten (los atribuidos, más) y van por encima; los grupos que los
contienen también laten. Los notificados van más apagados y lo de las últimas 24 horas lleva
un halo. Los pulsos no los dibuja MapLibre: son elementos sobre el mapa que animan solo
escala y opacidad con CSS, algo que el navegador hace fuera del hilo principal; se recolocan
cuando el mapa se mueve, se paran con la pestaña en segundo plano y no se animan con
movimiento reducido.

## Línea de tiempo reversible

- «Ver todo» aparece en cuanto hay un periodo elegido o una reproducción en marcha, y vuelve
  al periodo completo y a la vista inicial del mapa.
- La reproducción se pausa, se reanuda y se detiene; al detenerla vuelve al periodo de antes.
- Escape y el doble clic en el histograma quitan la selección.
- El periodo va en la dirección (`?desde=…&hasta=…`, junto a los filtros) y el botón atrás
  deshace el último cambio: los pasos seguidos de un mismo gesto (un arrastre, las flechas)
  cuentan como uno solo en el historial.
- «Noche a noche» se pausa, se reanuda y se detiene, y «Ver todo» también la para.

Cubierto con tests de cada caso en Vitest y en Playwright.

## Datos

Tras los PR #20, #22, #23 y #24 de la recogida, la web publica 370 incidentes: 248 en el
mapa y 122 con ubicación imprecisa (`publicacion/incidentes_sin_ubicacion.json`), que salen en
el directo, la lista y los filtros como «ubicación imprecisa», con su país resaltado de forma
tenue y sin punto. El marcador cuenta los 370: 134 confirmados, 3 atribuidos y 28 países. Un
test de Playwright comprueba en cada ejecución que el marcador cuadra con los dos ficheros
publicados y que el mapa dibuja exactamente los incidentes con punto. La antigüedad se mide
desde la última recogida correcta de `estado.json` y su detalle lista cada fuente.

## Logo y marca

- Original en `web/marca/logo_eodi_original.png` (1,3 MB, circular, exterior ya
  transparente: no hizo falta recortarlo). No se sirve: un test comprueba que da 404.
- Versión simplificada en SVG (`web/public/marca/eodi-simplificado.svg` y `favicon.svg`):
  el círculo azul oscuro, los anillos claros y «EODI» en blanco más grande, sin mapa, puntos
  ni dron, con el texto en trazos (Montserrat ExtraBold, licencia SIL OFL, la más parecida a
  la del logo). Se usa en la cabecera y en los iconos pequeños.
- `favicon.ico` con 16, 32 y 48 px; `apple-touch-icon.png` de 180 px e iconos de 192 y 512 px
  del manifiesto con el logo completo sobre azul oscuro, y una variante adaptable con margen
  de seguridad; `theme-color` #021c3e, el azul del logo.
- Logo completo en WebP y PNG a 96, 192, 384 y 640 px.
- Imagen de vista previa al compartir rehecha por idioma (`compartir.png` y
  `compartir-en.png`): el logo completo, el nombre y el mapa.
- Todo lo genera `web/marca/generar_marca.py` (Pillow y fontTools) y
  `web/scripts/imagen-compartir.ts`; todo autoalojado y dentro de la política de contenido.

## Rendimiento

Criterio acordado: métricas reales medidas en navegador con Playwright y web-vitals, en
escritorio y en móvil emulado (con la CPU cuatro veces más lenta), con LCP por debajo de
2,5 s, CLS por debajo de 0,1 e INP por debajo de 200 ms; y la nota de Lighthouse móvil sin
caer más de 10 puntos respecto al diseño anterior.

Métricas reales (`e2e/rendimiento.spec.ts`, filtrar, cambiar de capa, abrir la línea de
tiempo y el directo, con un segundo entre acciones):

| Dónde | Escritorio LCP · CLS · INP | Móvil LCP · CLS · INP |
| --- | --- | --- |
| Local | 60–80 ms · 0,010 · 56 ms | 124 ms · 0 · 112–128 ms |
| Vista previa | 948 ms · 0,010 · 72 ms | 256 ms · 0,0003 · 112 ms |
| Producción | 996 ms · 0,010 · 56 ms | 360 ms · 0 · 128 ms |

Lighthouse, en las mismas condiciones para los dos diseños (vista previa del diseño anterior,
`main` en d54dc2e, y del nuevo, intercaladas): móvil 78 antes y 76,5 después (mediana de 6),
escritorio 99 y 99, accesibilidad 100 y 100. En el dominio de producción: móvil 75, escritorio
99, accesibilidad 100. La referencia del informe anterior era 74 en móvil y 97 en escritorio.

Lo que se cambió para llegar ahí:

- MapLibre se cargaba en el paquete inicial (1,2 MB) porque la aplicación importaba una
  constante del módulo del mapa; va aparte y una regla de lint lo impide en adelante.
- El pulso animaba capas del mapa, que obligaban a repintarlo entero en cada fotograma: en
  móvil un toque esperaba hasta 180 ms. Ahora es CSS fuera del hilo principal.
- El mapa cambia sus datos y sus capas justo después de pintar la respuesta al clic.
- Las dos fuentes de la primera pintura se piden desde la cabecera del HTML.
- Sin desenfoque detrás de los paneles: sobre el lienzo del mapa retrasaba la pintura.

Dos artefactos de medida en esta máquina, que no son de la web y se documentan en los
propios tests: Chrome sin interfaz en Windows marca a veces su ventana como tapada y pinta un
fotograma por segundo, lo que hundía la nota simulada de Lighthouse a 50–55 en la mitad de las
pasadas (a los dos diseños por igual); se mide con esa limitación desactivada. Y la primera
conexión de un navegador recién abierto tarda unos 3 s en recibir el primer byte (curl recibe
la página en 0,27 s); la medida abre antes un fichero pequeño del sitio.

## Seguridad y política de contenido

La política de contenido no cambia: `default-src 'self'`, scripts, estilos, imágenes, fuentes
y trabajadores solo del propio sitio, y conexiones además al subdominio de teselas; sin
`unsafe-inline`, sin `blob:` ni `data:`. El manifiesto y los iconos caen bajo
`default-src 'self'`. Playwright anota cualquier violación o error de consola en cada prueba:
ninguna en local, en la vista previa ni en producción. La barra de comentarios de Vercel se
desactivó en el proyecto porque su script violaba la política. Durante las pruebas se
añadieron a la regla CORS de las teselas los orígenes de la vista previa y de las dos
versiones medidas; al terminar se quitaron y la regla vuelve a admitir solo
`droneobservatory.eu` y `www.droneobservatory.eu`.

## Despliegues

- La comprobación de omitir el build (`web/scripts/omitir-build.ts`) construye siempre un
  despliegue de producción que no sale de `main`: probar una rama en el dominio real se hace
  con un despliegue a mano de su commit, y antes se cancelaba porque la vista previa de ese
  mismo commit ya estaba hecha.
- Commits de datos en `main`: los despliegues de producción de #20 (9c5d4f0), #22 (0a1c8ed) y
  #24 (d54dc2e), que cambian los datos publicados, terminaron en Ready; #23 (834a665), solo
  documentación, se omitió como corresponde. En la ventana vigilada (unas dos horas) el
  servidor no subió ningún commit «Actualiza los datos» a `main`: los datos llegaron por esos
  PR de la otra sesión.
- Mientras se probaba la rama en producción, el dominio sirvió durante unos minutos un build
  de la rama hecho antes de rebasar sobre `main`, con los datos anteriores (288 incidentes);
  se corrigió desplegando la rama ya rebasada.

## Pruebas

- Vitest: 255 tests (datos, filtros y periodo en la dirección, hojas inferiores, pulsos,
  marcas, cabecera, filtros agrupados, línea de tiempo reversible, noche a noche, teléfono,
  novedades, estado del sistema, efecto y fuentes).
- Playwright: 32 pruebas en verde contra la vista previa y contra producción (12 por cada
  uno de escritorio y móvil, las métricas reales en los dos y las 6 combinaciones de tamaño
  y orientación del teléfono).
- Python: 734 pruebas y 13 omitidas; ruff y mypy sin avisos.

## Capturas

En `data/capturas/` (fuera de git): `escritorio-*` y `movil-*` (inicio, cabecera a tamaño
real, estado, ficha, filtros, periodo, ver-todo, capas, guerra, feed, ataque, inglés, ayuda,
metodología, sin-acento), `telefono/<tamaño>-<orientación>-*` (inicio, menú, ficha, pila y
tiempo) y `favicon-tamanos.png` (el favicon a 16, 32 y 48 px, a tamaño real y ampliado).

## Arreglos tras probarlo en un móvil real

- **Etiqueta flotante.** En una pantalla táctil el navegador simula un paso del ratón al
  tocar, y la etiqueta de ayuda (tipo · estado · título) se quedaba fija encima del mapa,
  saliéndose por la derecha. Ahora solo aparece con ratón (`(hover: hover) and (pointer:
  fine)`); con el dedo, el toque abre la ficha directamente. En escritorio se recoloca para no
  salirse nunca de la pantalla, corta el texto largo en dos líneas y desaparece al abrir la
  ficha.
- **Hoja inferior.** Se arrastra desde el asa y desde la cabecera de la ficha siguiendo el
  dedo, y al soltar se ajusta a la altura más cercana (asomada, media o completa) proyectando
  la velocidad del gesto 250 ms. Un toque en el asa pasa a la siguiente altura (asomada →
  media → completa → media) y nunca la cierra; solo se cierra con la X o arrastrándola por
  debajo de la altura asomada. El contenido se desplaza con normalidad, y arrastrar hacia
  abajo solo mueve la hoja cuando el contenido está arriba del todo. Al abrir un incidente va
  a media altura con el título y la descripción enteros. Los gestos que empiezan en la hoja no
  llegan al mapa.
- **Por qué parpadeaba.** La hoja medía el alto disponible en un envoltorio sin altura y, al
  tocarla, se encogía a cero y volvía. Ahora lo mide en el bloque posicionado que la contiene,
  el mismo contra el que se calculan sus porcentajes. Además, el puntero se captura solo al
  empezar un arrastre, para que la X de la cabecera siga respondiendo a un clic.

Comprobado con gestos táctiles de verdad (eventos de toque de Chromium) en
`e2e/hoja.spec.ts`, a 360 × 800, 390 × 844 y 412 × 915 en vertical, y en `e2e/web.spec.ts` el
letrero de escritorio con el símbolo pegado al borde derecho. Capturas en
`data/capturas/hoja/` (la ficha de EODI-2025-00247 a sus tres alturas, sin ninguna etiqueta
encima) y `data/capturas/escritorio-letrero-borde.png`. Vitest 261 y Playwright 36 en verde
contra la vista previa y contra producción; métricas reales en producción: escritorio LCP
744 ms, CLS 0,010, INP 56 ms; móvil LCP 320 ms, CLS 0,0003, INP 112 ms. Lighthouse en
producción: móvil 78, escritorio 99, accesibilidad 100. El despliegue de producción del
primer commit de datos del servidor en `main` (5b8bfa3, «Actualiza los datos publicados»)
terminó en Ready.

## Abierto

- **Captura de la pestaña del navegador con el favicon**: no se hizo. Requiere capturar la
  pantalla del equipo, y el intento recogió la ventana del navegador personal en lugar de la
  de pruebas, así que se borró sin guardarla. Queda la imagen del favicon a sus tres tamaños y
  la comprobación de que se sirve y se enlaza; la captura de la pestaña conviene hacerla con
  alguien delante del equipo.
- Entre 768 y 1023 px de ancho (tabletas) la cabecera ocupa dos filas.
- La nota simulada de Lighthouse en móvil varía mucho entre pasadas en esta máquina; las
  cifras de arriba son medianas en condiciones iguales para los dos diseños.
- La muesca de los teléfonos no se puede simular en Chromium; las zonas seguras se declaran,
  pero no se han visto en un teléfono real.
