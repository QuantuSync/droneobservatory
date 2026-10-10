# Posicionamiento en buscadores y asistentes

Qué se hizo el 10 de octubre de 2026 para que Google, Bing y los asistentes encuentren, lean y
citen bien droneobservatory.eu; cómo comprobarlo; y qué mirar en Search Console y en Bing Webmaster
Tools en los días siguientes. El dominio está dado de alta en los dos, verificado en Google por un
registro TXT del DNS de Hetzner que **no se toca nunca**.

## Qué se ha hecho

### Sitemap

- `https://droneobservatory.eu/sitemap.xml` lleva todas las páginas públicas en los dos idiomas:
  portada, cada incidente, listas por año, países, guerra en Ucrania, previsión, metodología,
  ayuda, avisos (`/avisos`, `/en/alerts`), páginas de servicio y versiones citables de los datos.
  No lleva la 404.
- Cada dirección trae su versión en español, en inglés y la de por defecto (`x-default`, la
  española), y su `lastmod`.
- `lastmod` va ahora en el formato completo que pide el esquema (W3C Datetime con segundos:
  `2026-10-10T07:17:00Z`). Antes salía sin segundos (`2026-10-10T07:17Z`), que el esquema
  `sitemap.xsd` no admite (`web/src/texto/salidas.ts`, `fechaSitemap`).
- Se sirve con `Content-Type: application/xml; charset=utf-8` (`vercel.json`). Se veía «como
  texto corrido» en el navegador porque los enlaces a la otra versión (`xhtml:link`) van en el
  espacio de nombres de XHTML y, con ellos, Chrome no usa su visor de XML: lo pinta como una página
  sin estilo. No era la política de seguridad (sin ella se ve igual) ni le pasaba nada al fichero.
  Ahora el sitemap enlaza una hoja de estilo propia (`<?xml-stylesheet type="text/css"
  href="/sitemap.css"?>`, `web/public/sitemap.css`): en el navegador sale una dirección por línea
  con su fecha. Los buscadores no la leen, y la política de seguridad de la web sigue igual.
- Sin índice de sitemaps: son unas 1 000 direcciones, muy lejos del límite de 50 000 por fichero,
  y la dirección dada de alta en Search Console y Bing sigue siendo la misma.

### robots.txt

`web/public/robots.txt` deja rastrear todo a Googlebot, Bingbot, Google-Extended, GPTBot,
OAI-SearchBot, ChatGPT-User, PerplexityBot, el rastreador de Anthropic, Applebot y
Applebot-Extended (cada uno nombrado en el grupo de arriba) y a cualquier otro, sin ningún
`Disallow`, e indica el sitemap.

### Protección de Vercel

Revisada con la API (token de `%USERPROFILE%\.eodi\vercel_token.txt`) en el proyecto
`droneobservatory`: no hay ninguna regla de cortafuegos, ni conjuntos gestionados (protección de
bots, reto a navegadores), ni modo de ataque activo; la protección de Vercel de las vistas previas
no afecta al dominio. Solo queda la mitigación automática de ataques de Vercel, que deja pasar a
los rastreadores verificados. No había nada que ajustar. Comprobado con peticiones con el
`User-Agent` de cada rastreador: todos reciben 200 y el contenido (ver «Cómo comprobarlo»).

### IndexNow

- Clave pública en `configuracion/indexnow.json`, publicada en la web como
  `https://droneobservatory.eu/<clave>.txt` (`web/public/`).
- `recogida/indexnow.py` corre al final de cada recogida que publica bien (`servidor/recogida.sh`,
  tope de 60 s; un fallo no cambia el código de la recogida). Lee el sitemap de la web en vivo: así
  solo envía lo que ya está publicado. La primera vez envía todas las direcciones, una sola vez;
  después, solo las de incidentes (español e inglés) nuevas o con otra fecha de modificación. Por
  lotes de 1 000, a `https://api.indexnow.org/indexnow`, que lo reparte a Bing, Yandex, Seznam,
  Naver y los demás. Lo enviado, dirección y fecha, queda en
  `/home/eodi/datos/indexnow/indexnow.json` y no se repite; un lote que falla se reintenta en la
  recogida siguiente.
- Un incidente nuevo entra en el sitemap cuando Vercel ha reconstruido la web, unos minutos después
  de publicar: se avisa en la recogida siguiente.
- El ensayo de la recogida (`servidor/ensayo.sh`) dice cuántas direcciones enviaría, sin enviar.
- Envío inicial: 10 de octubre de 2026, 17:35 UTC, 974 direcciones, respuesta 200. El primer
  intento, un minuto antes, recibió 403 («clave no válida»): IndexNow tarda un poco en dar por
  buena una clave nueva. No hace falta hacer nada: lo que no sale se reintenta en la recogida
  siguiente. El primer cambio de `recogida.sh` corre una recogida después de fusionar (bash lee
  el script antes de poner el clon al día), así que el envío inicial se lanzó a mano con
  `sudo -u eodi bash -c "cd /home/eodi/droneobservatory && .venv/bin/python -m recogida.indexnow
  enviar --datos /home/eodi/datos/indexnow"`.

### Cada tipo de página

| Página | Título y descripción | hreflang y canónico | Vista previa | Datos estructurados |
| --- | --- | --- | --- | --- |
| Portada | Propios en cada idioma | es, en, x-default; canónico propio | Imagen fija del observatorio (1200 × 630), en cada idioma | `WebSite` |
| Incidente | Su titular; la descripción con estado, fecha y lugar | es, en, x-default | La misma imagen | `Event` con lugar, coordenadas y fechas |
| Metodología | Propios | es, en, x-default | La misma imagen | `Dataset` (licencia, descargas, cita) |
| Versión de los datos | Propios | es, en, x-default | La misma imagen | `Dataset` con versión, ficheros y la cita (nuevo) |
| Avisos, países, años, ayuda, servicio | Propios | es, en, x-default | La misma imagen | `WebPage` del sitio (nuevo) |

Lo que se corrigió: faltaba `x-default` en todas las páginas y en el sitemap, y las páginas sin
datos estructurados no traían ninguno.

### ntfy.droneobservatory.eu

Caddy añade `X-Robots-Tag: noindex, nofollow` a todo el subdominio de los avisos
(`configuracion/ntfy/Caddyfile`, que instala `servidor/ntfy.sh`): no compite con la web.

### Velocidad

Lighthouse 13.5 contra producción, antes y después (rendimiento, accesibilidad, buenas prácticas,
SEO; LCP y TBT). Lo fácil sin cambiar el diseño: las páginas con el mapa piden ya desde la cabecera
el resumen de los datos y, la de un incidente, su ficha (`<link rel="preload" as="fetch">`), en
paralelo con el código, en vez de esperar a que el código los pida. Lo que más pesa en el móvil es
ejecutar el código del mapa (MapLibre, unos 2 s de CPU en el móvil simulado): no tiene arreglo
fácil sin cambiar cómo se carga el mapa. Las cifras están en «Medidas».

### llms.txt

Al día: qué es, cifras, cómo leer los estados, todas las páginas, un apartado de avisos (canales y
cómo suscribirse), la metodología y los datos abiertos con su licencia, las versiones citables y la
forma de citar, en inglés y en español.

## Cómo comprobarlo

```
# Sitemap: tipo, que es XML válido y cuántas direcciones lleva
curl -sI https://droneobservatory.eu/sitemap.xml | grep -i content-type
curl -s https://droneobservatory.eu/sitemap.xml | python -c "import sys, xml.etree.ElementTree as E; r = E.fromstring(sys.stdin.read()); print(len(r))"

# Contra el esquema oficial (lxml): python herramientas/validar_sitemap.py
# robots.txt
curl -s https://droneobservatory.eu/robots.txt

# Cada rastreador recibe 200 y el contenido
for ua in Googlebot Bingbot GPTBot OAI-SearchBot ChatGPT-User PerplexityBot Applebot; do
  curl -s -o /dev/null -w "$ua %{http_code} %{size_download}\n" -A "Mozilla/5.0 (compatible; $ua)" https://droneobservatory.eu/
done

# IndexNow: la clave publicada y lo último enviado
curl -s https://droneobservatory.eu/$(python -c "import json; print(json.load(open('configuracion/indexnow.json'))['clave'])").txt
ssh ... 'sudo cat /home/eodi/datos/indexnow/indexnow.json | head -c 300; journalctl -u eodi-recogida -n 40 | grep -i indexnow'

# El subdominio de avisos no se indexa
curl -sI https://ntfy.droneobservatory.eu/ | grep -i x-robots-tag
```

Datos estructurados: https://validator.schema.org/ (pegar la dirección de una página) y la prueba
de resultados enriquecidos de Google (https://search.google.com/test/rich-results).

## Qué mirar dentro de unos días

**Google Search Console** (https://search.google.com/search-console, propiedad del dominio):

1. *Sitemaps*: `https://droneobservatory.eu/sitemap.xml` debe pasar de «Couldn't fetch» a
   «Success» con unas 1 000 direcciones descubiertas. Si sigue igual tras 2 o 3 días, quitarlo y
   volver a enviarlo.
2. *Pages* (Indexación de páginas): que suban las «Indexed». Mirar los motivos de «Not indexed»:
   «Duplicate without user-selected canonical» o «Alternate page with proper canonical tag» en la
   versión inglesa son normales; «Blocked by robots.txt» o «Server error (5xx)» no deberían salir.
3. *Inspección de URL*: inspeccionar la portada y un incidente y pedir la indexación
   («Request indexing»).
4. *Enhancements / Mejoras*: «Datasets» con la metodología y las versiones, sin errores.
5. *Experiencia / Core Web Vitals*: tardará semanas en tener datos.

**Bing Webmaster Tools** (https://www.bing.com/webmasters):

1. *Sitemaps*: estado «Success» y número de direcciones.
2. *IndexNow*: deben verse las direcciones recibidas, primero todas (el envío inicial) y después
   las de los incidentes nuevos o cambiados de cada hora.
3. *URL Inspection*: la portada y un incidente, indexados.
4. *Site Explorer* y *Search Performance*: primeras impresiones y clics.

Si algo falla: `docs/posicionamiento.md` (esto) y el diario de la recogida (`journalctl -u
eodi-recogida | grep -i indexnow`).

## Medidas

Lighthouse 13.5 en este equipo (Chrome sin ventana, móvil simulado con la limitación de CPU y red
de Lighthouse, y escritorio), contra producción, el 10 de octubre de 2026 antes y después del PR
#202. Página de incidente: `/EODI-2026-00500`.

| Página | Rendimiento | LCP | TBT | Accesibilidad · Buenas prácticas · SEO |
| --- | --- | --- | --- | --- |
| Portada, móvil | 73 → 71 | 2,1 s → 2,4 s | 1 260 → 1 240 ms | 100 · 100 · 100 |
| Portada, escritorio | 100 → 99 | 0,5 s → 0,5 s | 20 → 100 ms | 100 · 100 · 100 |
| Incidente, móvil | **52 → 71** | **6,2 s → 2,8 s** | 1 220 → 1 150 ms | 100 · 100 · 100 |
| Incidente, escritorio | 99 → 99 | 0,9 s → 0,7 s | 0 → 20 ms | 100 · 100 · 100 |

La ficha del incidente se pintaba tarde porque su JSON se pedía después de cargar el código; con la
precarga llega en paralelo. Las diferencias de la portada y del escritorio están dentro de lo que
varía Lighthouse de una pasada a otra. El TBT del móvil (unos 1,2 s) es el arranque del mapa
(MapLibre) y queda como estaba.

Validador de schema.org (https://validator.schema.org) sobre la portada (es, en), un incidente, la
metodología, una versión de los datos, `/avisos` y una lista por año: 0 errores y 0 avisos.

Sitemap contra `sitemap.xsd` (`herramientas/validar_sitemap.py`): antes, errores en todos los
`lastmod` y sin `x-default`; después, 974 direcciones sin errores.
