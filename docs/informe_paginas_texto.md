# Páginas de texto para buscadores y asistentes, y corrección del punto de Polonia

5 de octubre de 2026. Dos encargos: que la web del European Observatory of Drone Incidents se pueda
leer sin ejecutar código (bloque A, PR #133) y que el punto de Polonia deje de estar sobre un daño
que no causó un dron (bloque B, PR #132).

## Bloque B. El punto de Polonia

### Qué estaba mal

EODI-2025-00295 (drones rusos en el espacio aéreo de Polonia, noche del 9 al 10 de septiembre de
2025, atribuido a Rusia) tenía su punto en Wyryki-Wola. Según la fiscalía, esa casa la alcanzó un
misil disparado por un caza polaco durante la operación contra los drones, no un dron. En el mapa
se veía el marcador con la bandera rusa encima de ese daño.

### Qué se ha hecho

- **El punto pasa a Cześniki** (powiat zamojski, gmina Sitno), localidad, 2 km de radio,
  geocodificación oficial. Es el primer lugar con restos de dron que nombra la Fiscalía Regional
  de Lublin en su nota del 10 de septiembre de 2025 (actualización), comprobada hoy en la página
  original:
  «Cześniki pow. zamojski – oględziny w fazie końcowej – ujawniono co najmniej 32 elementy drona
  typu Gerbera, nie ujawniono materiałów wybuchowych.»
  ([Prokuratura Regionalna w Lublinie](https://www.gov.pl/web/pr-lublin/informacja-dotyczaca-czynnosci-procesowych-prokuratury-w-zwiazku-z-ujawnionymi-dronami-na-terenie-wojewodztwa-lubelskiego-aktualizacja)).
  El encargo citaba Czosnówka según el informe de la revisión anterior, pero en la nota original
  el primer lugar es Cześniki (Czosnówka va segunda, con un dron Gerbera «w całości bez silnika»).
  Se aplica el criterio escrito, no el nombre: Cześniki. Coordenadas comprobadas con
  OpenStreetMap (50,703 N, 23,441 E; el pueblo mide unos 4 km).
- **Wyryki-Wola pasa a «Otros lugares»** con la frase literal de la fiscalía que ya estaba
  guardada: «wystrzelona przez pilota myśliwca F-35 – w sposób niezamierzony uderzyła w dach
  budynku mieszkalnego w miejscowości Wyryki Wola.» (Prokuratura Okręgowa w Lublinie, 10 de
  septiembre de 2026). Los otros 15 lugares siguen igual.
- **Nada se sobrescribe.** El punto anterior queda en `lugar.historial` (lugar, punto, radio,
  fuente) con el motivo en español y en inglés; el incidente se guarda como versión nueva y el
  cambio queda en el historial de la base. La ficha del mapa y su página de texto muestran el
  «Punto anterior» con el motivo.
- **Regla general** (`configuracion/punto_principal.json`, `recogida/revisados.py`): el punto
  principal es un lugar donde estuvo o cayó el dron; un daño causado por la respuesta defensiva
  nunca es el punto principal. Si la frase de la autoridad que daría el punto habla de la defensa
  (misil, caza, munición) y no del dron, el punto no se pone. Un punto ya puesto solo cambia si la
  revisión trae el cambio con su motivo en los dos idiomas.
- **Esquema 1.12.0**, dos campos públicos opcionales: `lugar.otros_lugares[].fuente` (la fuente
  cuya frase explica ese lugar) y `lugar.historial` (puntos anteriores con su motivo). La
  exportación semanal los lleva con su procedencia.

### Otros incidentes revisados con la regla

Se miraron las 42 ubicaciones revisadas y todos los incidentes publicados con punto cuya frase de
lugar nombra a la defensa (misil, caza, interceptor): 13 frases en 11 incidentes. Solo Polonia
incumplía la regla. Los demás nombran el dron en el mismo lugar: Volkel (00084), Vilna (2026-00057),
Padina (2026-00085, «resturi din dronă și din racheta interceptoare»: hay restos del dron), Padina
(2026-00089), Rugāji (2026-00140), Kouvola (2026-00180, «unbemannte Flugkörper» son drones) y
Crocmaz (2026-00372: explosiones del ataque, no de la defensa). 2025-00125, 2026-00211 y
2026-00332 no tienen localidad.

### Ensayo y fusión

Ensayo completo en el servidor (copia propia de la base del disco y de las carpetas de datos, sin
el cerrojo, 3 GB, prioridad baja): código 0, «ubicados 1», «ficheros publicados con cambios: 3»,
exportación semanal generada sin subir, 17 min, 434 publicados (igual que producción). Fusionado
como c37d705 a las 18:46 UTC.

Recogidas siguientes: 19:17 (aplica el cambio, «ubicados 1») y 20:17, las dos con código 0 y publicadas en `main`.

## Bloque A. Que la web se pueda leer sin ejecutar código

### El problema

La web es una aplicación que se dibuja en el navegador. El servidor entregaba la portada
prerenderizada (la cabecera de la aplicación con las cifras y un mapa vacío) y, en cada
`/EODI-…`, una copia de esa portada con otro título. Quien pedía una página sin ejecutar código
no podía leer ningún incidente, ninguna cita ni la metodología. Además, cualquier dirección con
forma de identificador (también la de un incidente retirado o inventado) devolvía 200 con la
aplicación.

### Qué páginas hay y con qué direcciones

Todas en español y en inglés (la inglesa cuelga de `/en`), enlazadas entre sí con `hreflang`.

| Página | Español | Inglés | Qué contiene |
| --- | --- | --- | --- |
| Portada | `/` | `/en` | Qué es el observatorio, cifras (incidentes, confirmados, atribuidos, países, última actualización), los 20 últimos incidentes, enlaces por año, por país y a todo lo demás |
| Incidente | `/EODI-AAAA-NNNNN` | `/en/EODI-AAAA-NNNNN` | La misma dirección que abre su ficha en el mapa. Tipo, titular, identificador, estado y qué significa, atribución con la autoridad y su frase literal, presencia de dron y qué significa, definición del tipo, fecha y precisión, lugar y radio (o «ubicación imprecisa»), instalación, lugar según la autoridad con su frase, otros lugares con su explicación, punto anterior con su motivo, drones, duración, efecto (cierre, vuelos desviados, cancelados, retrasados, daños, heridos), respuesta, investigación en curso, foco térmico, motivo del desmentido, episodio, **todas** las fuentes con su medio, fecha, código, frase y enlace, historial de estados con sus motivos, fecha de la ficha y enlace al mapa |
| Listado completo | `/incidentes` | `/en/incidents` | Los 434 publicados, del más reciente al más antiguo, con enlaces por año |
| Por año | `/incidentes/2026`, `/2025`, `/2024` | `/en/incidents/…` | Cifras del año y su lista |
| Países | `/paises` | `/en/countries` | Los 28 países con su número |
| País | `/paises/pl` (código ISO en minúsculas) | `/en/countries/pl` | Cifras del país y su lista |
| Guerra en Ucrania | `/ucrania` | `/en/ukraine` | Qué muestra la capa (los textos de la ayuda), totales, tabla por región (partes que la citan y derribados), tabla por mes (partes, lanzados, derribados, derribados según el parte ruso), corredores de ataque, de dónde salen los partes y la sección «Guerra por satélite» de la metodología. No hay página por impacto |
| Metodología y datos abiertos | `/metodologia` | `/en/methodology` | Todas las secciones de la metodología de la web, con índice, y los datos abiertos: descargas, versión, licencia y cita recomendada |
| Ayuda | `/ayuda` | `/en/help` | «Cómo leer el mapa» y los atajos de teclado |
| No encontrada | (cualquier otra) | | 404 real, en los dos idiomas |
| `sitemap.xml`, `robots.txt`, `llms.txt` | raíz | | Ver abajo |

942 páginas en total (868 de incidentes). Los incidentes retirados no tienen página ni salen en
ninguna lista. Un identificador unido a otro redirige con un 308 (permanente) a la página del que
queda.

### Cómo lo ve cada uno

El mismo HTML para todo el mundo:

- **La portada y cada incidente** llevan la aplicación del mapa, como antes, y detrás el texto. La
  hoja de estilos, que el navegador carga antes de pintar nada, oculta el texto cuando el
  navegador ejecuta código (`@media (scripting: enabled)`) y oculta la aplicación cuando no
  (`@media (scripting: none)`). Con código, la persona ve exactamente el mapa de siempre y nunca
  el texto, ni siquiera un instante: no depende de que llegue ningún script. Sin código, ve el
  texto y navega por enlaces normales. Un navegador antiguo que no conozca esa consulta se queda
  como hoy.
- **Las listas, los países, Ucrania, la metodología y la ayuda** son solo texto, para todos, con
  la misma hoja de estilos y un enlace al mapa.
- Encabezados en orden (un `h1` por página), listas, tablas con cabeceras, enlaces normales,
  idioma declarado en `<html lang>` y en el enlace al otro idioma, contraste del texto
  secundario 7:1 sobre el fondo.

Cada página dice al pie la fecha y hora de los datos («Datos publicados a 05/10/2026 · 19:17
UTC»). Ninguna página redacta nada: los textos salen de los datos publicados (titular, estado,
presencia, citas literales con su fuente y su fecha, atribución con su autoridad) y de los
textos que ya tenía la web (metodología, ayuda, nombres de estados y tipos). Lo que significa
cada estado es el principio de su definición en la metodología (lo comprueba un test).

### Para buscadores y asistentes

- Título y descripción propios en cada página y en su idioma; dirección canónica; `hreflang`
  español e inglés; etiquetas de vista previa (Open Graph y tarjeta grande) con la imagen de
  siempre.
- Datos estructurados JSON-LD solo con campos de los datos: `WebSite` en la portada, `Dataset`
  en la metodología (licencia CC BY 4.0, creador, fecha de modificación, cobertura y las cinco
  descargas como `DataDownload`) y un `Event` por incidente (nombre, identificador, fecha de
  inicio y de fin con su precisión, lugar con país, región o localidad y coordenadas si hay
  punto).
- `sitemap.xml`: las 942 páginas, cada una con su `lastmod` (la fecha de la ficha en los
  incidentes, la de los datos en el resto) y su versión en el otro idioma. Se rehace en cada
  construcción.
- `robots.txt`: permite todo y apunta al sitemap.
- `llms.txt`: qué es el observatorio, cifras, cómo se leen los estados, enlaces a las páginas
  principales y a los datos abiertos, en inglés y en español.
- Códigos: 200 lo que existe; 404 real lo que no (`/EODI-2099-99999`, `/esto-no-existe`, un
  retirado); 308 para los identificadores unidos y para `/es` (que lleva a la portada española).

### Cómo se mantienen al día

Lo más simple que ya funcionaba: **las páginas se generan al construir la web**, y la web ya se
construye con cada commit «Actualiza los datos publicados» que hace la recogida cada hora
(Vercel construye cada push a `main` que toque `publicacion/`, `web/` o `vercel.json`). Las
páginas van, como mucho, unos minutos por detrás de los datos publicados. No hace falta ninguna
función ni tocar el servidor ni la recogida.

Topes del plan (Pro, consultado en la API y en la documentación de Vercel el 5 de octubre de
2026): 6.000 despliegues al día (se usan unos 25), 45 minutos por construcción (tarda unos 40 s;
la generación de las 942 páginas añade un par de segundos), 1 GB de ficheros estáticos por
despliegue (unos 90 MB), sin invocaciones de funciones. Muy por debajo de todo.

Redirecciones de los unidos: la recogida publica ahora, en `incidentes.geojson`, la lista
`unidos` (identificador unido → incidente publicado en que acaba, siguiendo la cadena de
fusiones; cambio en `exportacion/geojson.py`, ensayado). El build escribe con ella el fichero de
Bulk Redirects de Vercel (`bulkRedirectsPath` en `vercel.json`): 300 unidos, 600 redirecciones
con los dos idiomas, dentro de las 1.000 que incluye el plan Pro. Vercel rechaza un fichero de
redirecciones vacío, así que siempre lleva también `/es` → `/`.

### Ensayo y fusión

El cambio de la exportación (`unidos`) se ensayó como el del bloque B: recogida completa sobre
copias propias de la base y de los datos, sin el cerrojo, código 0, exportación semanal generada
sin subir, 16 min 47 s, 3 GB de pico, 300 unidos en su `incidentes.geojson`. Fusionado como
846b55b a las 19:56 UTC (la CI tuvo que relanzarse una vez: GitHub no asignó máquinas a los
trabajos durante 15 minutos). La recogida siguiente, de las 20:17, terminó con código 0 y
publicó; con su despliegue entraron las 600 redirecciones.

### Lo que recibe quien pide una página sin ejecutar código

Pedidas en producción el 5 de octubre de 2026 hacia las 20:05 UTC con un cliente que no ejecuta
código (cabecera de navegación quitada; principio del texto recibido). Atribuido:
EODI-2025-00295; confirmado: EODI-2026-00418; sin punto en el mapa: EODI-2026-00408.

#### `/` · 200 · text/html

```
# European Observatory of Drone Incidents
El European Observatory of Drone Incidents registra incidentes con drones en Europa: aparatos no tripulados que sobrevuelan una instalación, entran en un espacio aéreo desde fuera o interrumpen el funcionamiento de un aeropuerto.
Cada incidente lleva sus fuentes con la frase de origen y el enlace, su estado (notificado, confirmado, atribuido o desmentido) y el historial de cambios. Los datos se actualizan cada hora y se pueden descargar.
## Cifras
Incidentes
434
Confirmados
194
Atribuidos
4
Países
28
Última actualización
05/10/2026 · 19:17 UTC
## Últimos incidentes
04/10/2026 · Drones violan el espacio aéreo griego sobre el Egeo · Notificado · Grecia
03/10/2026 · Drone desde Bielorrusia viola el espacio aéreo de Lituania y obliga a cerrar el aeropuerto de Vilnius · Confirmado · Lituania
03/10/2026 · Cierre del aeropuerto de Vilna por detección de
```

#### `/en` · 200 · text/html

```
# European Observatory of Drone Incidents
The European Observatory of Drone Incidents records drone incidents in Europe: unmanned aircraft that fly over a facility, enter an airspace from outside or disrupt the operation of an airport.
Each incident carries its sources with the original sentence and the link, its status (reported, confirmed, attributed or denied) and the history of changes. The data are updated every hour and can be downloaded.
## Figures
Incidents
434
Confirmed
194
Attributed
4
Countries
28
Last update
05/10/2026 · 19:17 UTC
## Latest incidents
04/10/2026 · Drones violate Greek airspace over the Aegean · Reported · Greece
03/10/2026 · Drone from Belarus violates Lithuanian airspace and forces closure of Vilnius airport · Confirmed · Lithuania
03/10/2026 · Vilnius airport closure following drone detection · Confirmed · Vilnius, Lithuania
03/10/2026 · Multiple drones fly
```

#### `/EODI-2025-00295` · 200 · text/html

```
Incursión
# Drones rusos invaden el espacio aéreo de Polonia
EODI-2025-00295
Ver en el mapa
Estado del suceso
Atribuido · Rusia, según la Cancillería del primer ministro de Polonia (Kancelaria Prezesa Rady Ministrów) Qué significa: Un confirmado del que una autoridad competente (gobierno, ministerio, fuerzas armadas, fiscalía o policía) afirma expresamente, con sus propias palabras, quién es el responsable: un Estado o una persona.
Presencia de dron
Dron confirmado Qué significa: La autoridad competente atribuye el suceso a un dron.
Tipo
Incursión El dron entra desde fuera del país y su origen está demostrado por rastreo o por restos. Un avistamiento sin origen demostrado nunca es una incursión.
Fecha
09/09/2025 solo el día
Lugar
Cześniki, Polonia área de 2 km de radio
Lugar según
Prokuratura Regionalna w Lublinie
«Cześniki pow. zamojski – oględziny w fazie końcowej – ujawniono co najmni
```

#### `/en/EODI-2025-00295` · 200 · text/html

```
Incursion
# Russian drones penetrate Polish airspace
EODI-2025-00295
See on the map
Event status
Attributed · Russia, according to the Chancellery of the Prime Minister of Poland (Kancelaria Prezesa Rady Ministrów) What it means: A confirmed incident for which a competent authority (government, ministry, armed forces, prosecutor or police) expressly states, in its own words, who is responsible: a State or a person.
Drone presence
Drone confirmed What it means: The competent authority attributes the event to a drone.
Type
Incursion The drone enters from outside the country and its origin is proven by tracking or by debris. A sighting with no proven origin is never an incursion.
Date
09/09/2025 day only
Place
Cześniki, Poland area of 2 km radius
Location per
Prokuratura Regionalna w Lublinie
«Cześniki pow. zamojski – oględziny w fazie końcowej – ujawniono co najmniej 32 elementy drona typu
```

#### `/EODI-2026-00418` · 200 · text/html

```
Sobrevuelo
# Dron no autorizado detectado y neutralizado en el Puerto de Constanza
EODI-2026-00418
Ver en el mapa
Estado del suceso
Confirmado Qué significa: Una autoridad afirma que el incidente ocurrió.
Presencia de dron
Dron confirmado Qué significa: La autoridad competente atribuye el suceso a un dron.
Tipo
Sobrevuelo Cualquier otro vuelo de drones sobre una instalación o una localidad.
Fecha
04/05/2026 solo el día
Lugar
Rumanía área de 3 km de radio
Instalación
Portul Constanța · Puerto
Drones
1
Respuesta
inhibición
## Fuentes y citas (7)
Declaración de Poli&#539;&#105;a de Frontieră și Forțele Navale Române, citada en mediafax.ro · 06/05/2026 · B1
«Poli&#539;&#105;a de Frontieră și Forțele Navale Române au fost notificate oficial.»
https://mediafax.ro/social/sistemul-anti-drona-din-portul-constanta-testat-in-conditii-reale-23732286
ziuaconstanta.ro · 06/05/2026 · C3
«O dronă neidentificată, reperată
```

#### `/en/EODI-2026-00418` · 200 · text/html

```
Overflight
# Unauthorized drone detected and neutralized at Port of Constanza
EODI-2026-00418
See on the map
Event status
Confirmed What it means: An authority states that the incident happened.
Drone presence
Drone confirmed What it means: The competent authority attributes the event to a drone.
Type
Overflight Any other drone flight over a facility or a town.
Date
04/05/2026 day only
Place
Romania area of 3 km radius
Facility
Portul Constanța · Port
Drones
1
Response
jamming
## Sources and quotes (7)
Statement by Poli&#539;&#105;a de Frontieră și Forțele Navale Române, quoted in mediafax.ro · 06/05/2026 · B1
«Poli&#539;&#105;a de Frontieră și Forțele Navale Române au fost notificate oficial.»
https://mediafax.ro/social/sistemul-anti-drona-din-portul-constanta-testat-in-conditii-reale-23732286
ziuaconstanta.ro · 06/05/2026 · C3
«O dronă neidentificată, reperată în perimetrul terminalului de pasageri din P
```

#### `/EODI-2026-00408` · 200 · text/html

```
Sobrevuelo
# Dron explota en el Puerto de Constanza
EODI-2026-00408
Ver en el mapa
Estado del suceso
Confirmado Qué significa: Una autoridad afirma que el incidente ocurrió.
Presencia de dron
Dron confirmado Qué significa: La autoridad competente atribuye el suceso a un dron.
Tipo
Sobrevuelo Cualquier otro vuelo de drones sobre una instalación o una localidad.
Fecha
16/07/2026 fecha aproximada
Lugar
Rumanía ubicación imprecisa · solo el país
Drones
Sin dato Modelo: maritima
## Fuentes y citas (3)
Declaración de Nicușor Dan, citada en romaniatv.net · 16/07/2026 · B1
«Președintele Nicușor Dan a declarat că autoritățile ucrainene vor trimite răspunsuri complete la întrebările tehnice formulate de România după explozia unei drone maritime ucrainene în»
https://romaniatv.net/nicusor-dan-vine-cu-noi-clarificari-privind-drona-ucraineana-explodata-in-portul-constanta-este-o-situatie-noua-un-razb
```

#### `/en/EODI-2026-00408` · 200 · text/html

```
Overflight
# Drone explodes at Port of Constanza
EODI-2026-00408
See on the map
Event status
Confirmed What it means: An authority states that the incident happened.
Drone presence
Drone confirmed What it means: The competent authority attributes the event to a drone.
Type
Overflight Any other drone flight over a facility or a town.
Date
16/07/2026 approximate date
Place
Romania imprecise location · country only
Drones
No data Model: maritima
## Sources and quotes (3)
Statement by Nicușor Dan, quoted in romaniatv.net · 16/07/2026 · B1
«Președintele Nicușor Dan a declarat că autoritățile ucrainene vor trimite răspunsuri complete la întrebările tehnice formulate de România după explozia unei drone maritime ucrainene în»
https://romaniatv.net/nicusor-dan-vine-cu-noi-clarificari-privind-drona-ucraineana-explodata-in-portul-constanta-este-o-situatie-noua-un-razboi-cu-tehnologii-noi-si-nu-totd
```

#### `/paises/pl` · 200 · text/html

```
# Incidentes con drones en Polonia
Los 14 incidentes con drones publicados en Polonia, con su estado y sus fuentes.
## Cifras
Incidentes
14
Confirmados
4
Atribuidos
1
## Incidentes
30/09/2026 · Dron entra en Moldavia y explota; cierres en aeropuertos de Polonia · Notificado · Lublin, Polonia
06/07/2026 · Retrasos en el aeropuerto de Cracovia por avistamiento de posible dron · Confirmado · Polonia
12/03/2026 · Dron hallado en una mina de carbón en Polonia · Confirmado · Galczyce, Polonia
15/09/2025 · Dron neutralizado sobre edificios gubernamentales en Varsovia · Notificado · Warsaw, Polonia
13/09/2025 · Posible dron viola el espacio aéreo de Polonia durante ataque a Ucrania · Notificado · Polonia
13/09/2025 · Cierre del aeropuerto de Lublin por amenaza de ataques con drones · Notificado · Port Lotniczy Lublin, Polonia
12/09/2025 · Drones violan el espacio aéreo de Polonia, NATO inicia op
```

#### `/en/countries/pl` · 200 · text/html

```
# Drone incidents in Poland
The 14 published drone incidents in Poland, with their status and sources.
## Figures
Incidents
14
Confirmed
4
Attributed
1
## Incidents
30/09/2026 · Drone enters Moldova and explodes; airport closures in Poland · Reported · Lublin, Poland
06/07/2026 · Delays at Krakow airport due to possible drone sighting · Confirmed · Poland
12/03/2026 · Drone found at coal mine in Poland · Confirmed · Galczyce, Poland
15/09/2025 · Drone neutralized over government buildings in Warsaw · Reported · Warsaw, Poland
13/09/2025 · Possible drone breaches Polish airspace during attack on Ukraine · Reported · Poland
13/09/2025 · Lublin airport closure due to drone attack threat · Reported · Port Lotniczy Lublin, Poland
12/09/2025 · Drones violate Polish airspace, NATO launches defense operation · Reported · Poland
10/09/2025 · Drones shot down force closure of Warsaw airport · Repo
```

#### `/ucrania` · 200 · text/html

```
# La guerra en Ucrania
Ataques con drones de Rusia contra Ucrania y de Ucrania contra Rusia según los partes oficiales: cifras por región y por mes, impactos con lugar y corredores de ataque.
Partes del 01/10/2022 al 05/10/2026.
## Qué muestra la capa
En la capa de Ucrania, cada región se colorea de violeta según los ataques que la citan en el periodo: es el color de toda la capa de guerra, distinto del rojo y el naranja de los incidentes.
Las regiones rusas van en violeta apagado y con contorno discontinuo: sus cifras son las del Ministerio de Defensa ruso, una reivindicación de parte.
Un punto violeta pequeño es un lugar concreto alcanzado (una localidad o una instalación) según las administraciones regionales, el Estado Mayor ucraniano o los gobernadores rusos. Relleno: fuente oficial; solo el aro: reivindicación de parte. Al alejar se agrupan con su número. Los partes diarios de la l
```

#### `/en/ukraine` · 200 · text/html

```
# The war in Ukraine
Drone attacks by Russia against Ukraine and by Ukraine against Russia according to the official reports: figures by region and by month, located impacts and attack corridors.
Reports from 01/10/2022 to 05/10/2026.
## What the layer shows
In the Ukraine layer, each region is shaded violet by the attacks that name it in the period: the colour of the whole war layer, distinct from the red and orange of incidents.
Russian regions are muted violet with a dashed outline: their figures are those of the Russian Ministry of Defence, a claim by a party to the war.
A small violet dot is a specific place hit (a town or a facility) according to the regional administrations, the Ukrainian General Staff or Russian governors. Filled: official source; ring only: claim by a party. Zoomed out, they group with their count. Daily front-line reports are in the downloadable data.
## Totals
```

#### `/metodologia` · 200 · text/html

```
Incursión
El dron entra desde fuera del país y su origen está demostrado por rastreo o por restos. Un avistamiento sin origen demostrado nunca es una incursión.
Sobrevuelo
Cualquier otro vuelo de drones sobre una instalación o una localidad.
## Estados
Notificado
Lo cuentan las noticias. Es el estado inicial de todo incidente. En naranja.
Confirmado
Una autoridad afirma que el incidente ocurrió. En rojo.
Atribuido
Un confirmado del que una autoridad competente (gobierno, ministerio, fuerzas armadas, fiscalía o policía) afirma expresamente, con sus propias palabras, quién es el responsable: un Estado o una persona. No basta una noticia que lo cuente sin sus palabras, ni que la autoridad investigue, examine una posible relación, no lo descarte, lo vea posible o lo sospeche: eso va en la ficha como investigación en curso y el incidente sigue confirmado. El autor nunca es la autoridad que de
```

#### `/en/methodology` · 200 · text/html

```
Incursion
The drone enters from outside the country and its origin is proven by tracking or by debris. A sighting with no proven origin is never an incursion.
Overflight
Any other drone flight over a facility or a town.
## Statuses
Reported
The news reports it. It is the initial status of every incident. In orange.
Confirmed
An authority states that the incident happened. In red.
Attributed
A confirmed incident for which a competent authority (government, ministry, armed forces, prosecutor or police) expressly states, in its own words, who is responsible: a State or a person. A news report saying so without the authority's own words is not enough, nor is an authority investigating, examining a possible link, not ruling it out, finding it possible or suspecting it: that goes in the record as an investigation under way and the incident stays confirmed. The perpetrator is never the authorit
```

#### `/sitemap.xml` · 200 · application/xml

```
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
<url><loc>https://droneobservatory.eu/</loc><lastmod>2026-10-05T19:17Z</lastmod><xhtml:link rel="alternate" hreflang="es" href="https://droneobservatory.eu/"/><xhtml:link rel="alternate" hreflang="en" href="https://droneobservatory.eu/en"/></url>
<url><loc>https://droneobservatory.eu/EODI-2024-00003</loc><lastmod>2026-10-02T09:17Z</lastmod><xhtml:link rel="alternate" hreflang="es" href="https://droneobservatory.eu/EODI-2024-00003"/><xhtml:link rel="alternate" hreflang="en" href="https://droneobservatory.eu/en/EODI-2024-00003"/></url>
<url><loc>https://droneobservatory.eu/EODI-2025-00001</loc><lastmod>2026-10-05T16:17Z</lastmod><xhtml:link rel="alternate" hreflang="es" href="https://droneobservatory.eu/EODI-2025-00001"/><xhtml:link rel="alternate"
```

#### `/robots.txt` · 200 · text/plain

```
User-agent: *
Allow: /
Sitemap: https://droneobservatory.eu/sitemap.xml
```

#### `/llms.txt` · 200 · text/plain

```
# European Observatory of Drone Incidents
> Open map and record of drone incidents in Europe: overflights, incursions and airport disruptions, with their sources, status and level of confirmation.
The European Observatory of Drone Incidents records drone incidents in Europe: unmanned aircraft that fly over a facility, enter an airspace from outside or disrupt the operation of an airport. Each incident carries its sources with the original sentence and the link, its status (reported, confirmed, attributed or denied) and the history of changes. The data are updated every hour and can be downloaded.
Figures at 05/10/2026 · 19:17 UTC: 434 incidents, 194 confirmed, 4 attributed, 28 countries.
Every incident has its own page at /EODI-YYYY-NNNNN (Spanish) and /en/EODI-YYYY-NNNNN (English), with its status, drone presence, place, date, consequences, attribution with the authority's literal state
```

Direcciones que no existen y unidos:

| Petición | Respuesta |
| --- | --- |
| `/EODI-2099-99999`, `/esto-no-existe`, `/en/nothing` | 404 con la página «Página no encontrada / Page not found» |
| `/EODI-2025-00065` (retirado) | 404 |
| `/es` | 308 → `/` |
| `/EODI-2025-00270` (unido a EODI-2025-00295) | 308 → `/EODI-2025-00295` (y `/en/…` → `/en/…`), desde el despliegue de los datos de las 20:17 |
| `/EODI-UA-2026-1014` (un ataque de la capa de Ucrania) | 200, la portada con el mapa, como antes (los ataques no tienen página propia) |

### Pruebas añadidas (quedan en la integración continua)

- `web/scripts/comprobar-paginas.ts`, después del build: para la portada, un incidente
  atribuido, uno confirmado y uno sin punto, la lista, un año, los países, un país, Ucrania, la
  metodología y la ayuda, en los dos idiomas, el HTML trae el titular, el estado, al menos una
  cita con su fuente enlazada y la fecha de los datos; las cifras de la portada son las del
  marcador del mapa (`meta.json`); todos los publicados tienen página y están en el sitemap, y
  ninguno retirado (`configuracion/incidentes_revisados.json`) ni unido; los datos estructurados
  tienen los campos obligatorios de su tipo; el sitemap está bien formado, sin repetidos y cada
  dirección corresponde a un fichero; ninguna página tiene un apartado de límites o limitaciones
  ni menciones prohibidas; robots.txt, llms.txt y la 404 existen; cada redirección va a una página
  que existe y nunca sale de una que existe.
- `web/e2e/paginas-texto.spec.ts`, en Chromium contra el servidor local que imita el despliegue
  (ahora con la 404 y las redirecciones): sin código, de la portada a un incidente, a la lista, de
  vuelta y a la versión inglesa por enlaces; una dirección inventada da 404; con código y sin que
  llegue ningún script, el texto no se pinta y la aplicación sí; con la aplicación cargada, solo
  el mapa y sin desplazamiento.
- `web/tests/paginas-texto.test.ts`: escape del HTML, datos estructurados que no cierran su
  etiqueta, redirecciones, sitemap, direcciones en los dos idiomas y significado de los estados.
- `tests/test_exportacion.py`: la lista `unidos` sigue la cadena y omite lo que no se publica.
- Tres pruebas de navegador existentes buscaban `header` sin más y ahora encontraban también la
  cabecera del texto: acotadas a la de la aplicación (`#root header`).

### Primera carga, antes y después

`web/scripts/medir-carga.ts`, producción, caché vacía, mediana de 7 pasadas; móvil emulado con la
CPU cuatro veces más lenta.

| Página | Perfil | Antes: FCP / LCP / mapa listo | Después: FCP / LCP / mapa listo | HTML (sin comprimir) |
| --- | --- | --- | --- | --- |
| `/` | Escritorio | 268 / 268 / 2.008 ms | 292 / 292 / 1.649 ms | 64,5 → 72,2 KB |
| `/` | Móvil | 344 / 344 / 2.913 ms | 320 / 320 / 2.965 ms | |
| `/EODI-2025-00295` | Escritorio | 324 / 488 / 2.153 ms | 276 / 504 / 2.302 ms | 64,6 → 221,9 KB |
| `/EODI-2025-00295` | Móvil | 376 / 864 / 3.244 ms | 396 / 1.240 / 4.299 ms | |

La portada comprimida pasa de 15,8 a 17,7 KB. Polonia es la página más pesada (268 fuentes:
43,5 KB comprimida). Las medidas sueltas varían mucho de una tanda a otra con la red, así que
para separar el efecto del texto se hizo una comparación intercalada sobre la misma página
publicada, ocho pares, sirviendo la respuesta tal cual o sin el bloque de texto:

| Página | Perfil | Mapa listo con texto / sin texto | LCP con / sin |
| --- | --- | --- | --- |
| `/EODI-2025-00295` | Móvil | 3.937 / 4.126 ms | 1.260 / 1.208 ms |
| `/` | Móvil | 2.998 / 2.812 ms | 452 / 492 ms |
| `/EODI-2025-00295` | Escritorio | 1.901 / 1.968 ms | 628 / 640 ms |
| `/` | Escritorio | 1.934 / 1.916 ms | 416 / 400 ms |

El texto no cambia la primera carga: las diferencias van en los dos sentidos y son del tamaño
del ruido. `DOMContentLoaded` en móvil: 328 ms en Polonia, 591 ms en la portada. No hay
parpadeo: el texto lo oculta la hoja de estilos antes de la primera pintura.

### Comprobación en producción

- Peticiones sin código: arriba. Las 17 piden 200 con su contenido.
- En 360×800, 390×844, 412×915 y escritorio, con las pruebas de navegador contra producción:
  `telefono.spec.ts` (pantalla, menú, ficha, punto con varios, «Filtros» y «Europa ahora», en
  vertical y apaisado), `mapa-quieto.spec.ts` (abrir y cerrar fichas de incidentes, Ucrania y
  corredores por la equis, Escape y tocando fuera, sin que el mapa se mueva; diez fichas
  seguidas), `revision-contenido.spec.ts` (Polonia con su marcador y su ficha, primera carga con
  red lenta) y `paginas-texto.spec.ts`: todas pasan. Capturas revisadas una a una de la portada,
  Polonia en los dos idiomas, un país y la metodología, con y sin código, en los cuatro tamaños:
  con código, la web es la de antes; sin código, el texto se lee completo.
- Enlace directo a un incidente: `/EODI-2025-00295` abre el mapa sobre Polonia con su ficha.

## Polonia en producción (bloque B, punto 5)

Recogida de las 19:17 con el cambio: «revisión del contenido: … ubicados 1», código 0, publicada
en `main` a las 19:33. En producción:

- `/datos/incidentes/EODI-2025-00295.json`: punto 23,44111 E 50,705 N (Cześniki), sigue
  atribuido a Rusia, Wyryki-Wola primero en otros lugares con su fuente, punto anterior con su
  motivo. 434 publicados, igual que antes.
- En el mapa, el marcador de atribuido con la bandera está junto a Zamość, en Cześniki; la ficha
  dice «Lugar: Cześniki, Polonia», «Lugar según: Prokuratura Regionalna w Lublinie» con su frase y
  su enlace, y en «Otros lugares» Wyryki-Wola con la frase de la fiscalía sobre el misil (captura
  `docs/capturas/paginas-texto-polonia-ficha-escritorio.png`).
- La página de texto dice lo mismo (muestra arriba).

## Pendientes, con su arreglo

- **Ataques de la capa de Ucrania con dirección inventada.** `/EODI-UA-AAAA-NNNN` sigue
  reescribiéndose a la portada, también si el ataque no existe (200, no 404): no tienen página
  propia y son más de 4.600. Arreglo: añadirlos a Bulk Redirects no sirve (no son redirecciones);
  sí una regla de Vercel por año con la lista de identificadores, o una página por ataque si se
  quiere (más de 9.000 ficheros por despliegue).
- **Capacidad de Bulk Redirects.** Hoy 601 de las 1.000 incluidas en el plan. Si los unidos
  pasan de unos 499, hay que ampliar la capacidad en los ajustes del proyecto (0,002 USD al mes
  por cada 25.000) o el despliegue fallará: necesita la decisión de quien paga.
- **Registros de Polonia del 10 de septiembre sin unir.** En `/paises/pl` siguen varios
  notificados de esa noche (Varsovia, Rzeszów, «Drones derribados obligan a cerrar el aeropuerto
  de Varsovia») que parecen el mismo suceso que EODI-2025-00295. Arreglo: revisarlos en
  `configuracion/incidentes_revisados.json` (sección `unir`) con la nota oficial y ensayar.
- **`web/e2e/web.spec.ts` no se puede ejecutar fuera de Vite** (`import.meta.env` en
  `almacenPublico.ts`); ya pasaba antes. Arreglo: leer `VITE_ALMACEN` con
  `import.meta.env?.VITE_ALMACEN`.
- **Las pruebas de navegador escriben sus capturas en `docs/capturas`** y, ejecutadas en local,
  cambian ficheros versionados. Arreglo: escribirlas en `data/capturas` (fuera de git) y copiar a
  mano las que vayan a un informe.
