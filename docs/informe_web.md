# Informe de la web

Estado: web en producción en [droneobservatory.eu](https://droneobservatory.eu) y
[droneobservatory.eu/en](https://droneobservatory.eu/en), con `www` redirigiendo al
dominio principal. Puerta local en verde (pytest, ruff check, ruff format --check,
mypy --strict; en `web/`: npm audit, lint, TypeScript estricto, tests y build) y
comprobación en navegador real contra producción en escritorio y en móvil. Lo que
queda abierto está al final.

## Pila

- Vite 8, React 19, TypeScript 6 estricto (`strict`, `noUncheckedIndexedAccess`,
  `exactOptionalPropertyTypes`), Tailwind 4 y prerenderizado estático con
  vite-react-ssg en modo de una sola página. Se prerenderizan `/` y `/en`, y al
  final del build se escribe una página por incidente en cada idioma a partir de
  ellas. TypeScript va en la 6.0 y no en la 7 porque typescript-eslint todavía no
  admite la 7.
- Sin biblioteca de rutas: la dirección solo dice el idioma y la ficha abierta y se
  lleva con el historial del navegador (`src/navegacion.tsx`). react-router, que
  arrastraba el modo con rutas de vite-react-ssg, tenía tres avisos moderados de
  `npm audit` sin arreglo; sin él, `npm audit` da 0 vulnerabilidades.
- MapLibre GL JS 6.11 con el protocolo pmtiles y el trabajador empaquetado y servido
  desde el propio sitio (`setWorkerUrl`). Estilo base de Protomaps
  (`@protomaps/basemaps`) con la paleta del observatorio, sin puntos de interés ni
  escudos de carretera. Glifos Noto Sans y sprites `dark` autoalojados en
  `web/public/mapa`.
- Fuentes autoalojadas: Saira Condensed 600 y 700 e Inter variable, desde los
  paquetes de Fontsource.
- La página solo habla con su propio origen y con `tiles.droneobservatory.eu`
  (comprobado con Playwright en producción).

## Pantalla

Cabecera (galón, wordmark, nombre completo en inglés también en español,
contadores del periodo, metodología e idioma), barra de estado entre líneas
doradas, mapa con selector de capas, leyenda y atribuciones, ficha lateral (panel
inferior en móvil) y línea de tiempo a todo lo ancho.

- **Incidentes:** agrupados con contador hasta zoom 5; desde zoom 4,5 cada uno se
  dibuja además como área con su radio de precisión. Forma por tipo, color por
  estado, relleno a baja opacidad con contorno de 1,2 px, desmentido con contorno
  discontinuo gris; selección con anillo dorado de 1 px. Los incidentes de un
  episodio se unen con una línea fina dorada.
- **Ucrania:** contorno rojo discontinuo y sus 27 regiones (ISO 3166-2, Natural
  Earth) coloreadas en cinco escalones según los ataques que las citan en el
  periodo. Al pulsar una región, o desde la lista, se abren sus cifras: ataques por
  sentido, derribos desglosados por región (sin contar dos veces los tramos
  incluidos en otro parte), último ataque y los partes que la citan, cada uno con su
  ficha.
- **Densidad:** mapa de calor en la gama gris-crema del texto, sin dorado de relleno.
- **Ficha de incidente:** tipo, nombre del objetivo, título, estado con símbolo y
  texto, presencia de dron con marca y texto, fecha con su precisión, lugar con el
  radio, drones como rango (con «rango de las fuentes A–C» cuando no es exacto),
  duración, efecto, respuesta, atribución, motivo del desmentido, episodio, fuentes
  (enlace, medio, código del Almirantazgo, fecha, frase de origen con su atributo
  `lang`, réplicas y la marca de declaración oficial citada) e historial de estados.
  Las fuentes se ordenan por fiabilidad y se muestran de cinco en cinco: algún
  incidente tiene más de 700.
- **Ficha de ataque** de la capa de Ucrania, con el aviso de reivindicación de parte.
- **Línea de tiempo:** histograma por día, semana o mes; el periodo se elige
  arrastrando, con un clic (un tramo) o con el teclado sobre sus dos extremos
  (flechas, RePág, AvPág, Inicio, Fin). Con la capa de Ucrania, una línea roja da los
  drones lanzados contra Ucrania cada noche. Reproducir hace avanzar el final del
  periodo tramo a tramo y se para al llegar al último día.
- **Metodología:** diálogo modal nativo que se abre desde la cabecera en todas las
  resoluciones, en los dos idiomas, con todas las secciones pedidas y los datos
  abiertos.
- **Lista de incidentes** del periodo (botón «Lista» junto a las capas): da con
  teclado y lector de pantalla el mismo acceso a las fichas que el mapa, y a las
  regiones de Ucrania cuando la capa está activa.

## Funciones añadidas (bloque A)

1. **Barra de estado honesta.** Con la hora del navegador: verde con menos de 2
   horas desde la última actualización, ámbar de 2 a 6 y rojo desde 6, con el texto
   «DATOS AL DÍA», «DATOS CON RETRASO» o «DATOS DESACTUALIZADOS» y las horas. Se
   recalcula cada minuto. En el HTML prerenderizado el punto es neutro: nunca hay un
   verde fijo. Con los datos reales a las 17:30 UTC del 30 de septiembre marca
   **ámbar, «DATOS CON RETRASO (hace 4 h)»**: la última actualización publicada es
   de las 12:42 UTC (ver «Sigue abierto»).
2. **Enlace propio** para cada incidente (`/EODI-2025-00210`, `/en/EODI-2025-00210`)
   y cada ataque (`/EODI-UA-2026-1014`, `/en/…`). Abre la web con el mapa centrado y
   la ficha abierta, también al pegarlo en otra pestaña o al recargar. Los incidentes
   tienen página prerenderizada; los ataques (4597) se sirven con una reescritura a
   la portada de su idioma. Botón «Copiar enlace» en las fichas.
3. **Descarga de datos abiertos** en la metodología: incidentes en GeoJSON y CSV,
   ataques en JSON y CSV (`/datos/…`), generados en el build desde `publicacion/`,
   con la licencia CC BY 4.0, la fecha de la versión y una cita recomendada en cada
   idioma. En los CSV, un texto que empezaría una fórmula de hoja de cálculo se
   neutraliza con un apóstrofo.
4. **Vista previa al compartir:** título, descripción e imagen fija del mapa
   (`/compartir.png`, 1200×630, generada con `web/scripts/imagen-compartir.ts`) en
   Open Graph y Twitter, en cada idioma; las páginas de incidente llevan el título
   del incidente.

## Seguridad (bloque B)

1. **Texto externo solo como texto.** Ningún `dangerouslySetInnerHTML` ni inserción
   de HTML en `web/`: el lint lo prohíbe (también `innerHTML`, `outerHTML`,
   `insertAdjacentHTML`, `document.write`, `srcDoc`, `eval` y `new Function`) y un
   test comprueba que la regla salta y que ningún fichero la esquiva. Tests con
   etiquetas script, manejadores `on*`, SVG, entidades y atributos rotos por todas
   las filas de la ficha. Los títulos que van a los metadatos se escapan.
2. **Enlaces externos** solo con http o https (se descartan `javascript:`, `data:`,
   relativos y el resto), `target="_blank"`, `rel="noopener noreferrer"` y marca ↗
   con aviso para lectores de pantalla. Tests incluidos.
3. **Validación contra el esquema.** El build valida `publicacion/` con los campos
   públicos del esquema 1.0.0 (objetos cerrados, listas cerradas, patrones y rangos)
   y falla si no cumple. La web valida cada fichero al cargarlo; si no cumple, avisa
   y no pinta nada de él. El validador está escrito a mano para no generar código en
   el navegador (la política de contenido no admite `eval`); un test compara sus
   listas y patrones con `esquema/` y exige que todo campo público del esquema esté
   en el validador.
4. **Dependencias:** `npm audit --audit-level=high` en la puerta local y en el
   workflow de tests; resultado **0 vulnerabilidades** de cualquier nivel.
   Dependabot mensual para npm en `/web`. Versiones exactas y fichero de bloqueo.
5. **`/.well-known/security.txt`** con el contacto
   `192205734+QuantuSync@users.noreply.github.com`, caducidad a un año (se regenera
   en cada build) y dirección canónica.
6. **CAA.** Los certificados reales: `droneobservatory.eu` y `www` de Let's Encrypt
   (Vercel); `tiles.droneobservatory.eu` de Google Trust Services (Cloudflare).
   Creados: `droneobservatory.eu CAA 0 issue "letsencrypt.org"`,
   `droneobservatory.eu CAA 0 issue "pki.goog"` y
   `tiles.droneobservatory.eu CAA 0 issue "pki.goog"`. Después se pidió a Vercel un
   certificado nuevo para `droneobservatory.eu` y lo emitió (caduca el 29 de
   diciembre de 2026, renovación automática). El de teselas no se puede forzar con
   este token; su emisora es la única autorizada en su nombre.
7. **HTTP a HTTPS:** `droneobservatory.eu` y `www` redirigen con 308 (Vercel).
   **En `tiles.droneobservatory.eu` no:** responde 200 por http. Ver «Sigue
   abierto».
8. **Analizadores externos** (30 de septiembre de 2026, sobre producción):
   - Mozilla HTTP Observatory: **A+**, 115 puntos, 12 de 12 pruebas.
   - securityheaders.com: **A+**.
   - SSL Labs, `droneobservatory.eu`: **A** en sus dos direcciones (en una primera
     prueba, A+ en 216.150.16.1). La nota se queda en A porque la petición HTTP del
     analizador recibe un 403 de la protección de Vercel y no llega a ver la
     cabecera HSTS, que el sitio sí envía (la ven Mozilla Observatory,
     securityheaders.com y cualquier navegador). La configuración TLS no tiene
     avisos: TLS 1.2 y 1.3, secreto perfecto hacia adelante. `tiles.droneobservatory.eu`: **A** en sus cuatro
     direcciones; no llega a A+ porque R2 no envía HSTS y ponerlo pide un permiso de
     zona que el token no tiene.

### Cabeceras y política de contenido

`vercel.json` pone en todas las rutas Strict-Transport-Security, X-Content-Type-Options,
Referrer-Policy, X-Frame-Options, Permissions-Policy y Content-Security-Policy. La
política final es más estricta que la de partida: sin `blob:` ni `data:` en
`img-src`, `worker-src` y `child-src`, y sin `'unsafe-inline'`:

```
default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self';
connect-src 'self' https://tiles.droneobservatory.eu; worker-src 'self'; child-src 'self';
object-src 'none'; base-uri 'self'; form-action 'none'; frame-ancestors 'none'
```

MapLibre con el trabajador autoalojado no necesita `blob:`, y fija sus estilos por
el DOM, que la política no bloquea. Para que no haga falta `'unsafe-inline'`, el
prerenderizado se hace sin CSS crítico en línea, React no escribe atributos `style`
en el HTML prerenderizado y el build saca a ficheros los scripts en línea que deja
vite-react-ssg. Playwright en producción, en escritorio y móvil, recorriendo capas,
fichas, línea de tiempo, idioma y metodología: **ninguna violación de la política ni
ningún error en la consola**. Sin formularios, cuentas, cookies ni analítica.

## Teselas en Cloudflare R2

Medidas con `pmtiles extract --dry-run` del build de Protomaps del 30 de septiembre
de 2026 (`20260930.pmtiles`, 138 GB), recorte de Europa `-25,34,45,72`:

| Zoom máximo | Tamaño |
| ---: | ---: |
| 10 | 1,4 GB |
| 11 | 3,0 GB |
| **12** | **6,6 GB** |
| 13 | 13 GB |
| 14 | 25 GB |
| 15 | 48 GB |

Ni el 14 ni el 15 caben en 9 GB, así que se eligió el mayor que cabe: **zoom 12
(6 592 334 136 bytes)**. El 13 se pasa. Con zoom 12 el mapa se puede acercar hasta
14 (MapLibre sobreamplía las teselas vectoriales): se ven calles principales y
localidades, suficiente para situar áreas de precisión de 1 a 50 km.

- El servidor de Hetzner no era accesible con la clave de `servidor_ssh` y el
  usuario `eodi` (`Permission denied (publickey)`), así que la extracción se hizo en
  local, en `data/teselas` (fuera de git), y la subida desde aquí.
- Bucket `eodi-teselas` (Europa occidental) creado con la API; subida por partes
  con la API compatible con S3 (clave de acceso: ID del token; secreto: SHA-256 del
  token), a 60 MB/s.
- CORS: GET y HEAD desde `https://droneobservatory.eu` y
  `https://www.droneobservatory.eu`, cabecera Range, expone ETag, Content-Range y
  Accept-Ranges. Comprobado: otro origen no recibe `Access-Control-Allow-Origin`.
- Dominio personalizado `tiles.droneobservatory.eu` activo (certificado y
  propiedad), TLS mínimo 1.2.
- Petición `Range: bytes=0-99`: **206 Partial Content**, `Content-Range: bytes
  0-99/6592334136`.
- Para el desarrollo, un recorte de zoom 6 (10 MB) en `data/teselas`, fuera de git,
  que sirve el servidor local.

## Despliegue

- Proyecto `droneobservatory` en Vercel, creado con el token y **vinculado al
  repositorio con la integración de GitHub**, que ya tenía acceso: no hace falta
  workflow propio ni secretos. Rama de producción `main`; cada commit en `main` se
  despliega, también los de datos que sube el servidor.
- `vercel.json` (raíz): instalación con `npm ci`, build `cd web && npm run build`,
  salida `web/dist`, direcciones sin `.html`, reescrituras de los identificadores y
  cabeceras. El despliegue se salta si desde el último desplegado no cambió nada de
  `web/`, `publicacion/` ni `vercel.json`; si no hay despliegue anterior, construye.
- La decisión de omitir un despliegue la toma `web/scripts/omitir-build.ts`
  (`ignoreCommand` de `vercel.json`), con sus tests contra un repositorio real.
  Vercel solo entiende la salida 0 (omitir) y la 1 (construir); cualquier otra hace
  fallar el despliegue. La primera versión era una orden `git diff` en línea y el
  despliegue de la rama `web` del commit 992a9a3 falló con código 128 (`fatal: bad
  object aad9162…`): Vercel clona sin historial completo y, tras el push forzado del
  squash, el commit del despliegue anterior ya no estaba en el clon. El script
  construye siempre que no hay commit anterior, cuando no está en el clon o ante
  cualquier error de git, y solo omite cuando git confirma que no cambió nada de
  `web/`, `publicacion/` ni `vercel.json`.
- Los ficheros de datos se copian de `publicacion/` en el build.
- Antes de la fusión, producción se sirvió desde la rama `web` con despliegues de
  producción creados por la API, para comprobar todo en el dominio real.
- **DNS en Cloudflare, solo DNS (sin proxy):** los dos A antiguos (217.76.128.47)
  se sustituyeron por `droneobservatory.eu A 216.150.1.1` y `A 216.150.16.1` y
  `www CNAME 60d65e86c6f6416c.vercel-dns-016.com`, los que pidió Vercel. MX y TXT de
  SPF intactos; los CNAME `autoconfig`, `autodiscover` y `webmail` pasados a solo
  DNS. `tiles` sigue con proxy porque es el dominio de R2.
- Certificados válidos: Let's Encrypt en el dominio y `www`; `www` redirige con 308
  a `https://droneobservatory.eu/`.

## Comprobación

- **Despliegues tras el arreglo de la comprobación de omitir:** ver la sección
  «Verificación del despliegue» al final.

- **Tests:** 179 tests de la web (Vitest: datos, validación, CSV, rutas, textos,
  paleta y contraste AA, geometría, seguridad, regla de lint, componentes y
  aplicación con ficheros no válidos) y 632 de Python (8 omitidos). Playwright: 9 recorridos en
  escritorio y 9 en móvil contra producción, todos en verde.
- **Capturas** en `data/capturas` (fuera de git): `escritorio-*` y `movil-*` de
  inicio, capas, región, ficha, ataque, periodo, inglés y metodología.
- **Lighthouse 13.5** sobre producción:

| | Rendimiento | Accesibilidad | Buenas prácticas | SEO |
| --- | ---: | ---: | ---: | ---: |
| Escritorio | 97 | 100 | 100 | 100 |
| Móvil | 74 | 100 | 100 | 100 |

  Móvil: FCP 1,7 s, LCP 2,2 s, CLS 0,003 y TBT 1,15 s. El bloqueo es la
  inicialización de MapLibre con la CPU cuatro veces más lenta y WebGL por software
  del navegador sin pantalla. Para bajarlo, el mapa se carga cuando la página ya está
  pintada (pasó de 48 a 74) y la línea de tiempo y la barra de estado reservan su
  altura. La única auditoría que falla es la de mapas de fuente, que no se publican.

## Accesibilidad

Contraste AA comprobado por test para todos los textos y los colores de estado; el
estado va siempre con símbolo y texto; foco de teclado dorado visible; salto al mapa;
el mapa se mueve con el teclado y la lista da acceso a todas las fichas; la línea de
tiempo tiene dos controles deslizantes accesibles; la metodología es un diálogo
modal nativo; las frases de origen llevan su idioma; sin animaciones con
`prefers-reduced-motion`.

## Sigue abierto

1. **HTTP a HTTPS en `tiles.droneobservatory.eu`.** Hace falta activar «Always Use
   HTTPS» (o una regla de redirección) en la zona. El token no tiene permiso: `PATCH
   /zones/…/settings/always_use_https` responde `{"code":10000,"message":"Authentication
   error"}`, igual que la lectura de reglas. Con un token con «Zone Settings: Edit» es
   una sola llamada. Mientras tanto, la web solo pide las teselas por https y el
   HSTS de `droneobservatory.eu` con `includeSubDomains` fuerza https en el
   subdominio a quien haya visitado la web. Con el mismo permiso se podría poner HSTS
   en las teselas y subir su nota de SSL Labs de A a A+.
2. **CAA añadidos por Cloudflare.** Con SSL universal activo, Cloudflare sirve en
   `droneobservatory.eu`, además de los dos registros creados, los de sus otras
   emisoras (comodoca.com, digicert.com, ssl.com, también en `issuewild`). No se
   pueden quitar sin desactivar el SSL universal, que el token tampoco permite. En
   `tiles` sí queda solo `pki.goog`; si Cloudflare cambiara algún día de emisora para
   ese certificado, habría que añadirla ahí.
3. **Quién dice qué en las cifras discrepantes.** La ficha muestra el rango de las
   fuentes A–C, pero el reparto por fuente está en `afirmaciones`, que es interno: la
   lista de quién dice qué necesita un campo público nuevo en `exportacion/`.
4. **Antigüedad de los datos.** La barra mide la última actualización de un registro
   publicado, no la última ejecución de la recogida: en horas sin partes ni noticias
   nuevas se pone ámbar o roja aunque la recogida funcione. Publicar la hora de la
   última ejecución también pide un cambio en `exportacion/`.
5. **Regiones rusas.** La capa de Ucrania dibuja las regiones de Ucrania, como se
   pidió; los ataques ucranianos sobre regiones rusas (sentido UA_RU) están en las
   fichas de ataque y en las descargas, pero no en el mapa.
6. **Teselas sin actualizar.** El recorte es del build del 30 de septiembre de 2026 y
   no se renueva solo; el procedimiento está en este informe y en `web/README.md`.
   Podría hacerlo el servidor cada pocos meses.
7. **Fichero de bloqueo.** Tras cualquier `npm install` hay que ejecutar
   `npm run bloqueo`: npm añade los datos de patrocinio de las dependencias y uno
   de ellos es el nombre de una cuenta ajena que el gancho `pre-push` toma por un
   término prohibido. Los PR de Dependabot los volverán a traer.
8. **Nombres de objetivo.** Algunos vienen del extractor en otro idioma («Monaco di
   Baviera»); es cosa de los datos, no de la web.
9. **Nombre del proyecto en el README.** El título del README del repositorio sigue
   en español («Observatorio Europeo de Incidentes con Drones»); la web y su
   documentación usan siempre el nombre en inglés.

## Decisiones tomadas sin consultar

- «Confirmados» en los contadores suma confirmados y atribuidos (atribuir exige
  haber confirmado); la metodología lo dice.
- La intensidad de las regiones es el número de ataques del periodo que las citan,
  en cinco escalones relativos al máximo del periodo.
- Los lanzamientos de cada noche son el total declarado (máximo del rango) de los
  ataques contra Ucrania por día de inicio del periodo del parte, sin los tramos
  incluidos en otro parte ni los solapados.
- La tierra de Natural Earth va debajo de las teselas para que fuera del recorte de
  Europa el mapa no se corte en línea recta; los límites del desplazamiento son más
  anchos que Europa porque MapLibre no deja ver nada fuera de ellos y en una pantalla
  ancha obligarían a cortar el continente.
- La vista inicial encaja Europa de Portugal a los Urales en cualquier pantalla.
- El nombre de cada lugar del mapa base va en una sola línea, en el idioma de la web
  (la base de Protomaps añade el nombre local debajo).
