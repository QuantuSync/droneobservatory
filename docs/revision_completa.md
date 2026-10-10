# Revisión completa de la web como la usa una persona

10 de octubre de 2026. Tras los PR #195 a #203, en un Android real (Chrome) fallaban dos cosas
básicas: en Filtros el primer toque no seleccionaba y «Suscribirme» (Avisos) no hacía nada. Las
pruebas automáticas pasaban porque pulsaban los botones directamente, sin hacer lo que hace una
persona: abrir el panel, subirlo con el dedo, desplazar y entonces tocar.

Arreglo y pruebas en el PR #204 (fusionado a las 20:42 UTC, comprobado en producción).

## Cómo se ha probado

- **Android**: Chromium con el perfil de un Pixel 7 (412 × 915, táctil), con toques y arrastres
  de bajo nivel (`Input.dispatchTouchEvent` por CDP), nunca clics simulados.
- **iPhone**: WebKit con el perfil de un iPhone 14 (390 × 844, táctil). Nunca se había probado con
  WebKit. Playwright no tiene arrastres táctiles en WebKit: allí la hoja se arrastra con el puntero
  del motor y se toca con su pantalla táctil.
- **Escritorio**: Chromium y WebKit a 1366 × 768 y 1920 × 1080, con ratón y solo con teclado.
- **Tableta**: 768 × 1024 táctil (Chromium; es la disposición de escritorio).
- Contra la vista previa de la rama y contra producción, con los datos reales.

Primero, un recorrido exploratorio por configuración (ocho en total) que anota errores de consola,
excepciones, peticiones fallidas, desbordes, controles tapados o fuera de la pantalla, textos
cortados, dianas de menos de 44 px en táctil y todo lo que no responde al primer toque: cabecera,
filtros (opciones, periodo, país, «Aplicar», «Quitar filtros»), menú del móvil y sus capas, capa de
Ucrania («Con satélite», «Lista», elementos, cortinilla), mapa (tocar un incidente, ficha, tocar
fuera, pellizco), ficha (enlaces, copiar), Previsión, Avisos (buscar, canal, «Suscribirme»,
«Copiar», QR), páginas de texto (metodología, aviso legal, privacidad con «Borrar mi última
visita», independencia, accesibilidad, ayuda, /avisos, ficha en texto, versión inglesa), enlaces
del pie y descargas, atrás, recargar, dirección directa de un incidente y una 404. Cada hallazgo se
reprodujo después por separado antes de darlo por bueno o por ruido.

## Fallos encontrados

| # | Dónde | Dispositivo | Gravedad | Causa | Estado |
|---|---|---|---|---|---|
| 1 | Hoja inferior del móvil (Filtros, Avisos, Europa ahora, Ucrania, fichas): tras subir o bajar la hoja con el dedo, el primer toque se perdía | Android y iPhone | Grave | `HojaInferior` marcaba al soltar un arrastre el siguiente clic para descartarlo (con ratón un arrastre acaba en clic). Con el dedo ese clic no llega y el descarte se quedaba pendiente hasta comerse el siguiente toque legítimo | Arreglado, #204 |
| 2 | Avisos → «Suscribirme» no hacía nada | Android | Grave | La misma: el toque en «Suscribirme» era el primero tras subir la hoja y se anulaba (sin navegar). El enlace `ntfy://ntfy.droneobservatory.eu/<canal>?display=…` era correcto: es el del #199 y el formato de la documentación de ntfy | Arreglado, #204 |
| 3 | Hoja del móvil arrastrada con ratón o trackpad (ventana estrecha, iPad con trackpad): se cerraba sola | Chromium y WebKit con puntero de ratón | Medio | Si el primer movimiento ya salía del asa, el arrastre no se reconocía (solo se escuchaba sobre la hoja) y el clic final caía fuera, donde se cierra «al tocar fuera» | Arreglado, #204: el arrastre se sigue en toda la ventana y el cierre al tocar fuera ignora el clic de un arrastre |
| 4 | `e2e/web.spec.ts` no cargaba | Pruebas | Medio | Desde el #193, `urlDelAlmacen` lee `import.meta.env`, que no existe fuera de Vite (Playwright corre en Node) | Arreglado, #204 |
| 5 | `e2e/web.spec.ts`, cuatro pruebas desfasadas | Pruebas | Leve | Los confirmados del marcador incluyen ya los atribuidos; la ficha de región se llama «Región · capa de Ucrania: …»; hay dos botones «Járkov» desde la lista para el teclado (#197); `estado.json` se pedía sin la clave de la vista previa | Arreglado, #204 (25 de 25 en producción) |
| 6 | Al salir de la página del mapa a mitad de carga, WebKit da por fallidas las peticiones en curso («access control checks») y la del mapa de fondo prueba la reserva de Helsinki | WebKit (iPhone, Safari) | Leve | WebKit no marca como aborto las peticiones que corta la navegación; `FuenteAlmacen` lo toma por un fallo de la web. No se ve nada: la página ya se ha ido | Pendiente: solo ruido en la consola de WebKit, sin efecto para quien usa la web |
| 7 | Pruebas antiguas que fallaban en producción: pulso de las novedades (`europa.spec.ts`), «si no responde nunca» de la previsión (`prevision-reintentos.spec.ts`) y la leyenda de la presión (`pulido.spec.ts`), 10 casos | Pruebas | Leve | Desfasadas respecto a lo decidido: el aviso de novedades va dentro de «Europa ahora» (#87); la copia de la previsión se pide por `/almacen/…` (#193) y la prueba solo cortaba la dirección antigua, así que nunca fallaba; encender «Presión» ya no cambia el periodo (#98) | Arreglado, PR de este informe |

Lo que parecía un fallo y no lo era (comprobado por separado):

- Un toque justo después de desplazar rápido el contenido no hacía nada en Chromium sin pantalla.
  Pasa igual en una página vacía sin nada de la web: el desplazamiento por inercia del emulador no
  termina nunca y el toque solo lo detiene. Con el dedo quieto un momento antes de soltar, funciona.
- «Noche a noche» al primer clic, el QR de Avisos en el ordenador y la capa elegida al tocar el
  mapa responden bien en una prueba limpia; el recorrido exploratorio tenía otro desplegable
  abierto encima o miraba la imagen antes de cargar.
- La violación de la CSP de estilos en WebKit la provoca el estilo que inyecta Playwright para
  hacer capturas, no la web.
- En la tableta, abrir la ficha de un incidente de la mitad derecha aparta el mapa (el panel
  lateral lo taparía). Es lo decidido en `PanelLateral`; cerrar la ficha no lo mueve.
- En el teléfono, «Previsión» es una pestaña de «Europa ahora», no un botón propio (decidido).
- Los desplegables (Ayuda, Avisos) tapan lo que tienen debajo y la 404 da un 404 en la consola:
  es lo esperado.

## Decisiones para Lucas

No son errores; convendría decidir si se cambian:

- En la tableta (768 × 1024, disposición de escritorio) los botones de la cabecera y del mapa miden 28–32 px de alto: cómodos con ratón, justos con el dedo (44 px recomendado).
- En las páginas de texto, los plegables «Qué dice la fuente» de la tableta miden 16 px de alto.
- En el teléfono, el plegable «Regiones de Ucrania con ataques» de la hoja de Ucrania mide 32 px de alto.
- «Suscribirme» en Android usa `ntfy://`: si la aplicación no está instalada, Chrome no hace nada; con `intent://…;package=io.heckel.ntfy;S.browser_fallback_url=…` iría a Google Play (hoy lo cubre el enlace «¿No tienes la aplicación?»).
- En la tableta, abrir una ficha de la mitad derecha mueve el mapa para dejar el punto a la vista; se podría preferir que no se mueva nunca.
- Los enlaces dentro del texto de metodología y créditos miden 20 px de alto (permitido para enlaces en línea, pero pequeños con el dedo).

## Pruebas permanentes

`web/e2e/recorridos.spec.ts`, con los proyectos nuevos de `web/playwright.config.ts`:

| Proyecto | Motor | Dispositivo |
|---|---|---|
| android | Chromium | Pixel 7, toques y arrastres CDP |
| iphone | WebKit | iPhone 14 |
| tableta | Chromium | 768 × 1024 táctil |
| escritorio-chromium | Chromium | 1366 × 768 y 1920 × 1080 |
| escritorio-webkit | WebKit | 1366 × 768 y 1920 × 1080 |

En el teléfono: Filtros (subir la hoja, desplazar, el primer toque cambia el control; cerrar con
la X, Escape y arrastrando, y después responde al primer toque), Avisos (buscar un país, subir la
hoja, desplazar y el primer toque es «Suscribirme»: el toque llega, nadie lo anula y el enlace es
el de la aplicación en Android o el App Store en iPhone, con «Copiar»), Europa ahora y Previsión
(pestaña y plegables), y el menú (capas al primer toque y «Aplicar»). En tableta y escritorio:
Filtros y Avisos a la primera (QR en el ordenador, enlace de la aplicación en la tableta) sin mover
el mapa, y solo con teclado. En todos: tocar un incidente abre su ficha y cerrarla no mueve el
mapa. Cada prueba falla si hay errores de consola, excepciones o peticiones fallidas.

Contra producción antes del arreglo fallan Filtros y Avisos en Android y en iPhone; con el arreglo
pasan todas. WebKit se instala aparte: `npx playwright install webkit`. Cómo lanzarlas:

```sh
cd web
npx playwright test e2e/recorridos.spec.ts --project=android --project=iphone --project=tableta --project=escritorio-chromium --project=escritorio-webkit
# contra una vista previa: BASE=<url> BYPASS=<clave>
```

## Estado de la suite

Contra producción, tras fusionar el #204 (y con los arreglos de pruebas de este informe):

| Suite | Pruebas | Pasan | Omitidas por dispositivo | Fallan | Navegadores |
|---|---|---|---|---|---|
| e2e (Playwright), 26 ficheros | 458 | 276 | 182 | 0 | Chromium (escritorio, movil, android, tableta, escritorio-chromium) y WebKit (iphone, escritorio-webkit) |
| de ellas, `recorridos.spec.ts` | 40 | 20 | 20 | 0 | Chromium y WebKit |
| de ellas, `web.spec.ts` | 26 | 25 | 1 | 0 | Chromium |
| Unitarias (Vitest), 52 ficheros | 596 | 596 | 0 | 0 | jsdom |

Las omitidas lo son a propósito: cada prueba corre solo en los dispositivos que le tocan (por
ejemplo, las de la hoja del teléfono no corren en el escritorio). Lint y tipos, sin errores.

## Comprobaciones en un Android real

1. Avisos → busca «Polonia» → sube la hoja con el dedo → toca «Suscribirme»: se abre ntfy con «EODI · Polonia».
2. Filtros → sube la hoja con el dedo → toca «Notificado»: se marca en blanco al primer toque.
3. Filtros → arrastra la hoja hacia abajo hasta cerrarla → toca Filtros otra vez: se abre a la primera.
4. Menú → enciende «Ucrania» → «Lista» → sube la hoja → toca una región: se abre su ficha al primer toque.
5. Europa ahora → sube la hoja → pestaña «Previsión» → toca «Cómo se comprueba»: se despliega al primer toque.
