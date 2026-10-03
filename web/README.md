# web

Web pública de una sola pantalla del European Observatory of Drone Incidents:
[droneobservatory.eu](https://droneobservatory.eu) (español) y
[droneobservatory.eu/en](https://droneobservatory.eu/en) (inglés).

Vite, React y TypeScript estricto, con Tailwind y prerenderizado estático
(vite-react-ssg). El mapa es MapLibre GL JS con el protocolo pmtiles; las teselas
de Protomaps y el estado de la recogida (`estado.json`) se sirven desde el almacén
público de Hetzner Object Storage, cuya dirección está en
[`configuracion/almacen_publico.json`](../configuracion/almacen_publico.json)
(`src/almacenPublico.ts` la lee en el build), y todo lo demás (trabajador del mapa, glifos, sprites, fuentes, geometrías de Natural Earth)
desde el propio sitio. Decisiones y resultados en
[`docs/informe_web.md`](../docs/informe_web.md).

## Órdenes

Requiere Node 22.18 o posterior (ejecuta los scripts `.ts` sin compilar).

```sh
npm ci
npm run datos       # valida ../publicacion y genera public/datos y src/generado
npm run dev         # servidor de desarrollo
npm run lint
npm run typecheck
npm test
npm run build       # web/dist, con una página por incidente
npm run servir      # sirve dist con las cabeceras de ../vercel.json
npm run e2e         # Playwright contra producción; BASE=http://localhost:4173 para local
npm run auditoria   # npm audit, falla con vulnerabilidades altas o críticas
npm run bloqueo     # tras cualquier npm install: limpia el fichero de bloqueo
```

Para desarrollar sin tocar producción, un recorte de teselas de zoom bajo va en
`../data/teselas/europa-z6.pmtiles` (fuera de git) y `web/.env.local` contiene
`VITE_TESELAS=/teselas/europa-z6.pmtiles`; el servidor local lo sirve con
peticiones Range. El recorte se saca con
`pmtiles extract https://build.protomaps.com/<fecha>.pmtiles europa-z6.pmtiles --bbox=-25,34,45,72 --maxzoom=6`. El de producción es `europa-z14.pmtiles` (zoom 14).

## Datos

El build (`scripts/datos.ts`) valida `publicacion/incidentes.geojson` y
`publicacion/ucrania.json` contra los campos públicos del esquema 1.8.0; si no
cumplen, el build falla y sigue publicada la versión anterior. Genera:

| Fichero | Contenido |
| --- | --- |
| `datos/incidentes.geojson`, `datos/ucrania.json` | Descargas: los ficheros publicados tal cual |
| `datos/incidentes.csv`, `datos/ucrania.csv` | Las mismas descargas en CSV |
| `datos/resumen.json` | Lo que necesitan el mapa, la línea de tiempo y los contadores |
| `datos/ucrania-resumen.json` | Ataques de la capa de Ucrania como filas de números |
| `datos/incidentes/<id>.json`, `datos/ataques/<id>.json` | Ficha completa, que se carga al abrirla |
| `.well-known/security.txt` | Contacto de seguridad, con caducidad a un año |

La web vuelve a validar cada fichero al cargarlo: si no cumple el esquema, avisa y
no lo pinta.

## Recursos autoalojados

| Carpeta | Origen | Licencia |
| --- | --- | --- |
| `public/mapa/fuentes` | Glifos Noto Sans de protomaps/basemaps-assets | OFL (`OFL.txt`) |
| `public/mapa/sprites` | Sprites `dark` v4 de protomaps/basemaps-assets, derivados de tangrams/icons | MIT |
| `public/mapa/ucrania-regiones.geojson`, `ucrania-contorno.geojson`, `tierra.geojson` | Natural Earth 5.1.2 (admin-1 10m y tierra 50m) | Dominio público |
| `public/compartir.png` | Captura del propio mapa (`scripts/imagen-compartir.ts`) | |

Las geometrías se regeneran con mapshaper desde los GeoJSON de Natural Earth:

```sh
npx mapshaper ne_10m_admin_1_states_provinces.geojson \
  -filter 'iso_3166_2.indexOf("UA-")===0' -each 'iso=iso_3166_2' -filter-fields iso \
  -simplify 12% keep-shapes -clean -o precision=0.001 ucrania-regiones.geojson \
  -dissolve -lines -o precision=0.001 ucrania-contorno.geojson
npx mapshaper ne_50m_land.geojson -clip bbox=-80,10,110,85 -simplify 25% keep-shapes \
  -clean -dissolve -o precision=0.01 tierra.geojson
```

## Seguridad

- Ningún texto de las fuentes se inserta como HTML: el lint prohíbe
  `dangerouslySetInnerHTML`, `innerHTML` y similares, y los tests pasan cargas
  hostiles por las fichas.
- Los enlaces externos solo se crean si son http o https, se abren en otra pestaña
  con `rel="noopener noreferrer"` y llevan la marca ↗.
- La política de contenido solo admite este sitio y el almacén público, sin
  estilos ni scripts en línea: el build saca a ficheros los scripts en línea del
  prerenderizado.
