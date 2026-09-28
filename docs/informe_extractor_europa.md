# Informe: histórico de noticias, extractor y primeros incidentes europeos

Quinto PR del Observatorio Europeo de Incidentes con Drones (EODI): histórico
de noticias desde el 1 de enero de 2025 con los ficheros GKG de GDELT, el
extractor real, la fusión en incidentes y episodios, el campo público
`presencia_dron` y la primera publicación de incidentes europeos.

## Estado

- **Histórico de noticias**: hecho (60 846 franjas, 49 844 artículos únicos y
  6395 candidatos).
- **Extractor real**: funciona con el servicio desde que se añadió la cabecera
  del espacio de trabajo al secreto de cabeceras. Gastado en el histórico: 3,42
  USD de 5 (2,15 del primer lote, 1,27 de dos tandas con el nomenclátor ampliado),
  con 1 USD de reserva para el PR de confirmaciones.
- **Publicación**: 273 incidentes europeos publicados (338 dados de alta, 65
  fundidos en otro), 18 de los 25 sucesos de la lista de Wikipedia.
- **Pendiente**: 5457 candidatos sin ficha, casi todos de localidades con un solo
  artículo, que no caben en el límite (ver «Sigue abierto»).


## 1. Histórico de noticias

### Cómo se hizo

- **Workflow `historico-gdelt`** (`.github/workflows/historico-gdelt.yml`) con
  tres pasos: `preparar` parte el recorrido en tramos de franjas iguales y deja
  vacía la rama `historico-gdelt` del repositorio de datos; `tramo`, una matriz
  de hasta 20 trabajos en paralelo, lee cada uno sus franjas de 15 minutos (los
  dos flujos, en memoria) y sube a esa rama los artículos que pasan el filtro,
  cifrados con la clave age, con reintento si otro trabajo ha escrito a la vez;
  `incorporar` junta los parciales en orden de fecha y los incorpora a la base
  con el deduplicado y la agrupación de siempre, en la misma cola que la
  recogida horaria. Sin artefactos; el registro solo lleva recuentos.
- **Lanzamiento.** GitHub no deja lanzar con `workflow_dispatch` un workflow que
  aún no está en `main`; se lanzó con un push a la rama `lanzar-historico-gdelt`
  (un disparador que queda en el workflow para eso), borrada al acabar. Una vez
  en `main`, se lanza con `gh workflow run historico-gdelt.yml`.
- **Ejecución 36350426328** (27 de septiembre de 2026): 20 tramos del 1 de enero
  de 2025 a las 19:30 UTC del 26 de septiembre de 2026, donde empezó la recogida
  horaria desde GKG. Cada trabajo tardó entre 1,4 y 3,8 horas (unas 3000 franjas
  a unos 2,8 s por franja). 60 846 franjas y 204,6 millones de filas leídas;
  3375 ficheros no existían en GDELT (franjas perdidas, sobre todo del flujo
  traducido); ninguna franja falló tras los reintentos y ningún tramo se cortó
  por tiempo. Los 20 parciales se subieron al primer intento.
- **Paso final fallido y corregido.** `incorporar` falló al subir la base: con
  el histórico pesaba 107 MB y GitHub no admite ficheros de más de 100 MB. La
  base se comprime ahora antes de cifrar (107 MB → 14,4 MB; las bases antiguas
  se siguen leyendo). Como el código de `main` no sabe leer una base
  comprimida, la incorporación se repitió en local con este PR
  (`recogida.historico_gdelt incorporar` hace lo mismo) y la base se sube a la
  rama `estado` después del merge.
- **Nomenclátor corregido** con la muestra de candidatos: «lentokenttä»
  (aeropuerto en finés) era alias de Helsinki y algunas «ciudades» de
  OpenStreetMap eran palabras comunes («Militär», «wojskowa»), así que un
  artículo sobre Alicante acababa en el aeropuerto de Helsinki y cualquier
  titular con «militar» en una base de Berlín. Al incorporar se vuelven a
  buscar los lugares: de 1330 candidatos se pasa a 834. La búsqueda de lugares,
  además, pasa de 0,1 s a 0,5 ms por titular.

### Artículos y candidatos por mes

Artículos únicos del histórico (sin réplicas), réplicas sumadas a su original
y candidatos, por el mes del primer artículo, con el nomenclátor ampliado.
Incluye los días de recogida horaria que ya había en la base.

| Mes | Artículos | Réplicas | Candidatos |
| --- | ---: | ---: | ---: |
| 2025-01 | 1006 | 616 | 188 |
| 2025-02 | 992 | 583 | 161 |
| 2025-03 | 722 | 684 | 147 |
| 2025-04 | 625 | 369 | 147 |
| 2025-05 | 1023 | 546 | 188 |
| 2025-06 | 685 | 802 | 90 |
| 2025-07 | 991 | 495 | 197 |
| 2025-08 | 1267 | 728 | 183 |
| 2025-09 | 10468 | 7063 | 804 |
| 2025-10 | 4710 | 3723 | 511 |
| 2025-11 | 4157 | 2183 | 460 |
| 2025-12 | 1406 | 675 | 246 |
| 2026-01 | 696 | 313 | 152 |
| 2026-02 | 1161 | 576 | 208 |
| 2026-03 | 2881 | 1470 | 411 |
| 2026-04 | 1248 | 589 | 256 |
| 2026-05 | 3797 | 1872 | 442 |
| 2026-06 | 2133 | 1648 | 300 |
| 2026-07 | 1859 | 779 | 305 |
| 2026-08 | 4343 | 2171 | 524 |
| 2026-09 | 3674 | 2641 | 475 |
| Total | 49844 | 30526 | 6395 |

Septiembre de 2025 multiplica por diez los meses anteriores: son los
avistamientos de Copenhague, Oslo, Aalborg y Múnich y su cobertura.

### Muestra de 10 candidatos (semilla 1)

- **CAND-20250407T1745-loc:3178455-espacio_aereo** (espacio_aereo, 2025-04-07T17:45:00Z a 2025-04-07T17:45:00Z, 1 artículos)
  - Affaire de drone malien abattu: Colère de l'AES à l'égard d'Alger — https://afriquinfos.com/affaire-de-drone-malien-abattu-colere-de-laes-a-legard-dalger-vers-un-nouveau-bras-de-fer-entre-les-parties
- **CAND-20250707T1115-loc:2517500-militar** (militar, 2025-07-07T11:15:00Z a 2025-07-07T18:15:00Z, 4 artículos)
  - Ukraine-Inspired Drone Resupply Tactics Tested in EU Military Drills — https://united24media.com/latest-news/ukraine-inspired-drone-resupply-tactics-tested-in-eu-military-drills-9664
  - Los ejércitos europeos se inspiran en Ucrania y prueban cómo reabastecer a sus efectivos con drones — https://libertaddigital.com/defensa/2025-07-07/los-ejercitos-europeos-prueba-en-italia-como-reabastecer-a-sus-efectivos-utilizando-drones-7273765
  - En direct, guerre en Ukraine : un raid de drones mené contre une usine de munitions de l'oblast de Moscou, selon l'armée ukrainienne [Le Monde] — https://afropages.fr/le-monde/en-direct-guerre-en-ukraine-un-raid-de-drones-mene-contre-une-usine-de-munitions-de-loblast-de-moscou-selon-larmee-ukrainienne
  - Europa testa drones e robôs militares para acelerar inovação adquirida no conflito na Ucrânia — https://noticiabrasil.net.br/20250707/europa-testa-drones-e-robos-militares-para-acelerar-inovacao-adquirida-no-conflito-na-ucrania-41141598.html
- **CAND-20250728T1915-loc:680963-militar** (militar, 2025-07-28T19:15:00Z a 2025-07-28T19:15:00Z, 1 artículos)
  - O dronă ucraineană ajunsă în zona portului Constanța a fost neutralizată de scafandrii militari — https://ziuaveche.ro/top-secret/armata-2/o-drona-ucraineana-ajunsa-in-zona-portului-constanta-a-fost-neutralizata-de-scafandrii-militari-340125.html
- **CAND-20250930T1115-loc:2618425-avistamiento** (avistamiento, 2025-09-30T11:15:00Z a 2025-10-01T19:15:00Z, 7 artículos)
  - Politiet sender droner i luften over København under EU-topmøder — https://kristeligt-dagblad.dk/politiet-sender-droner-i-luften-over-koebenhavn-under-eu-topmoeder
  - Kopenhaga zamknięta dla dronów. Tusk: Polscy żołnierze zabezpieczą szczyt — https://bankier.pl/wiadomosc/Kopenhaga-zamknieta-dla-dronow-Tusk-Polscy-zolnierze-zabezpiecza-szczyt-9017110.html
  - After Drone Sightings, Copenhagen To Host EU Leaders For 'Acute' Security And Defense Summits — https://rferl.org/a/denmark-drones-europe-defense-security-ukraine/33545257.html
  - EU-Gipfel ohne Drohnenalarm? Merz & Co tagen in Kopenhagen - Politik-Nachrichten - Reutlinger General-Anzeiger — https://gea.de/welt/politik_artikel,-eu-gipfel-ohne-drohnenalarm-merz-co-tagen-in-kopenhagen-_arid,7077904.html
  - Aufrüstung: EU-Gipfel ohne Drohnenalarm? Merz & Co tagen in Kopenhagen - Politik — https://rhein-zeitung.de/deutschland-welt/politik/eu-gipfel-ohne-drohnenalarm-merz-co-tagen-in-kopenhagen_arid-4072599.html
  - Survols de drones au Danemark : à Copenhague, un sommet des 27 sous haute surveillance — https://lexpress.fr/monde/europe/survols-de-drones-au-danemark-a-copenhague-un-sommet-des-27-sous-haute-surveillance-3ARMWXYDOBD4RDGIC5WNDIGKYQ
  - Les énigmes du Boracay : l'histoire fascinante d'un vaisseau fantôme russe aperçu près de Copenhague lors de survols de drones — https://sixactualites.fr/culture-numerique/les-enigmes-du-boracay-lhistoire-fascinante-dun-vaisseau-fantome-russe-apercu-pres-de-copenhague-lors-de-survols-de-drones/67732
- **CAND-20260301T0000-loc:663941-aeropuerto** (aeropuerto, 2026-03-01T00:00:00Z a 2026-03-01T00:00:00Z, 1 artículos)
  - Valë e re sulmesh iraniane, aeroporti i Dubait goditet nga droni — https://telegrafi.com/vale-e-re-sulmesh-iraniane-aeroporti-i-dubait-goditet-nga-droni
- **CAND-20260312T2030-loc:3169505-espacio_aereo** (espacio_aereo, 2026-03-12T20:30:00Z a 2026-03-12T20:30:00Z, 1 artículos)
  - Reino Unido reconoce haber derribado múltiples drones iraníes — https://diariolibre.com/mundo/europa/2026/03/12/reino-unido-reconoce-haber-derribado-multiples-drones-iranies/3467213
- **CAND-20260329T0400-loc:2517500-militar** (militar, 2026-03-29T04:00:00Z a 2026-03-29T04:00:00Z, 1 artículos)
  - Ukraine-Krieg im Liveticker: +++ 05:43 Nach Drohnenabschüssen: Baltische Staaten fordern von der Nato mehr Schutz +++ — https://n-tv.de/politik/05-43-Nach-Drohnenabschuessen-Baltische-Staaten-fordern-von-der-Nato-mehr-Schutz-article23143824.html
- **CAND-20260522T0800-loc:6535611-espacio_aereo** (espacio_aereo, 2026-05-22T08:00:00Z a 2026-05-22T08:00:00Z, 1 artículos)
  - Estonian PM thanks president after Romanian Air Force F-16 downs drone in Estonian airspace — https://actmedia.eu/daily/estonian-pm-thanks-president-after-romanian-air-force-f-16-downs-drone-in-estonian-airspace/119717
- **CAND-20260918T0915-loc:2800320-aeropuerto** (aeropuerto, 2026-09-18T09:15:00Z a 2026-09-18T09:15:00Z, 1 artículos)
  - Zakaz posiadania dronów i strefa ograniczeń lotów wielkości Polski. Tak Chiny chronią stolicę — https://wnp.pl/bezpieczenstwo/zakaz-posiadania-dronow-i-strefa-ograniczen-lotow-wielkosci-polski-tak-chiny-chronia-stolice,1100460.html
- **CAND-20260919T1100-loc:3046446-militar** (militar, 2026-09-19T11:00:00Z a 2026-09-19T11:00:00Z, 1 artículos)
  - Peste 300 de incidente cu drone raportate în jurul obiectivelor militare britanice în ultimul an — https://stiripesurse.ro/peste-300-de-incidente-cu-drone-raportate-in-jurul-obiectivelor-militare-britanice-in-ultimul-an_3921409

La muestra enseña el límite del filtro sin modelo: de 10 candidatos, solo 2
son incidentes europeos (el dron neutralizado en el puerto de Constanza y el
derribado en el espacio aéreo de Estonia); el resto son noticias de otros
sitios o de política que nombran una ciudad europea. Por eso el extractor decide `es_incidente` y la validación descarta
lo que no encaja con el objetivo.

## 2. Extractor

### Servicio y secretos

- **Secretos del repositorio público**, creados con `gh secret set`:
  `EODI_EXTRACTOR_CLAVE`, `EODI_EXTRACTOR_URL`, `EODI_EXTRACTOR_URL_LOTES`,
  `EODI_EXTRACTOR_MODELO` y `EODI_EXTRACTOR_CABECERAS` (JSON con las cabeceras
  propias del servicio, su versión, el espacio de trabajo y el sitio de la clave,
  marcado como «{clave}»). Copia local en `%USERPROFILE%\.eodi\extractor.env`,
  fuera de cualquier repositorio y legible solo por el usuario. Nada que
  identifique al proveedor está en el repositorio.
- **Cliente** (`modelo/cliente.py`) con la biblioteca estándar (`urllib`), sin el
  paquete del proveedor: mensajes, lotes, consulta y resultados de lotes. 429 y
  5xx se reintentan 4 veces (10 s doblados, o lo que pida el servicio hasta 300
  s); los errores solo llevan el código y el tipo, nunca el texto ni la clave.
- **Espacio de trabajo.** La clave es de organización y el servicio exige la
  cabecera del espacio de trabajo; sin ella respondía 400 a todo. Con el
  identificador añadido a `EODI_EXTRACTOR_CABECERAS` (y a la copia local),
  responde 200 sin tocar el código.

### Ficha

- **Salida obligada por esquema** (`modelo/ficha.py`). La primera llamada real
  rechazó un esquema con un objeto por campo: el servicio admite como mucho 16
  parámetros con tipos unión y limita el tamaño de la gramática compilada. La
  ficha es una lista de datos: nombre del campo (lista cerrada de 21),
  valor como texto con formato fijo («3-4», «2025-09-22T18:30», «nombre;
  categoría; país; lat; lon»), fuente, frase de origen y confianza, más los
  títulos en español e inglés. Solo salen los datos que dicen las fuentes; el
  código interpreta cada valor y descarta con su motivo lo que no sigue el
  formato.
- **Qué recibe el modelo:** el objetivo conocido del candidato y, de como mucho
  tres fuentes (el primer artículo y los más replicados de otros medios), el
  medio, la fecha, el titular y las primeras frases de la página (hasta 600
  letras de sus párrafos), leídas en memoria y nunca guardadas; si la descarga
  falla, solo el titular.
- **Caché del servicio.** Las instrucciones van delante y marcadas para la
  caché, pero con este modelo el servicio solo cachea bloques de 4096 tokens o
  más y las instrucciones son unas 2000: las lecturas de caché fueron 0 en todas
  las llamadas. Rellenar el bloque hasta el mínimo encarecería cada llamada sin
  acierto; se deja la marca por si el bloque crece o cambia el modelo.
- **Una llamada por candidato nuevo**, y otra (hasta 3 por candidato) si recibe
  artículos nuevos cuando su ficha dejó sin saber la hora, el cierre o el número
  de drones. Las fuentes nuevas de más fiabilidad (autoridades) llegan con el
  PR de confirmaciones.

### Validación con código (`proceso/validacion_ficha.py`)

Nada del modelo se usa sin validar; lo que no valida se descarta y su motivo
queda en la tabla interna `extracciones`, con la ficha en bruto:

- la frase de origen está, tal cual, en el texto de la fuente que cita (si pasa
  de 25 palabras se recorta a las 25 primeras, que siguen siendo cita literal);
- confianza de 0 a 1 y al menos 0,5;
- rangos coherentes y con topes (100 drones, 2000 vuelos, 48 horas de cierre);
- fechas posibles: ni futuras, ni posteriores al primer artículo (con una hora de
  margen), ni más de una semana anteriores;
- país en la lista europea y coordenadas de un lugar nuevo dentro de la caja de
  su país (`configuracion/paises_europa.json`, de Nominatim);
- objetivo existente: el del nomenclátor o un lugar nuevo válido; y si la ficha
  nombra otra instalación que la conocida (sin palabras propias en común),
  no vale para ese sitio.

Sin fecha válida, el incidente toma la del candidato con precisión de día.

### Vocabularios que crecen

Tabla interna `vocabulario`: los lugares nuevos que propone el modelo (ya
validados) y los modelos de dron, reutilizando la grafía de uno ya visto. El
nomenclátor y el vocabulario se consultan primero; el modelo solo propone un
lugar si la noticia habla de otro sitio.

### Coste y límites

- Cada llamada anota tokens (entrada, salida, caché) y coste en la tabla interna
  `llamadas_extractor`. Tarifas del modelo configurado: 1 USD por millón de
  entrada, 5 de salida, lotes a mitad de precio.
- **Límites duros en código** (`modelo/coste.py`), compartidos por este PR y el
  de confirmaciones: 5 USD para todo el histórico y 0,30 USD al día para la
  recogida horaria. Antes de cada llamada, o antes de enviar un lote, se suma lo
  gastado y el peor caso (toda la entrada sin caché y los 1500 tokens de salida
  permitidos); si pasa del límite, no se llama. En la recogida horaria el límite
  diario está activo: el paso del extractor usa el modo horario.
- **Estimación antes del histórico**, con 10 llamadas directas de muestra
  (semilla 1): 0,00436 USD de media por llamada directa, 834 candidatos, lote
  previsto de 1,80 USD, 1,84 en total: cabía en el límite y se lanzó.
- **Coste real:** 1269 llamadas, 1258 por lotes: 4 540 896 tokens de entrada y 447 900 de
  salida, ninguno leído de la caché. **3,4191 USD** en total: 3,3613 de lotes
  (0,00267 USD por candidato), 0,0436 de la muestra de estimación y 0,0142 de las
  llamadas de prueba del servicio, registradas aparte. El primer lote (822
  candidatos, nomenclátor inicial) costó 2,094 USD; las dos tandas con el
  nomenclátor ampliado (285 y 151 candidatos, los de más artículos primero),
  1,267 USD. Una tercera tanda habría rebasado la reserva de 1 USD y se dejó.

### Incidencias

- El primer lote terminó bien pero la orden falló al publicar (usaba la hora de
  inicio, anterior a la última actualización de los incidentes) y la base no se
  guardó. Los resultados se recuperaron del servicio sin volver a pagar
  (`recogida.extractor recuperar --lote`), volviendo a leer las primeras frases;
  ahora la base se guarda antes de publicar y el identificador del lote va al
  registro.
- El motivo de descarte más frecuente es «la frase no está en la fuente»: a
  veces el modelo parafrasea y a veces, al recuperar el lote, una página se leyó
  de otra forma que la primera vez. Se prefiere perder la ficha a publicar una
  cita que no está en la fuente.

## 3. Fusión, estado y credibilidad (`proceso/incidentes.py`)

- **Fusión** con la regla del diseño: mismo objetivo o puntos a menos de la suma
  de radios más 10 km; con precisión de hora, inicios a menos de 6 horas; con
  precisión de día, el mismo día o el siguiente; más de 12 horas sin actividad,
  otro incidente. Un incidente que encaja con dos anteriores no se funde
  (dudosa). El absorbido queda en la base con `fusionado_en` y no se publica; la
  tabla `fusiones` guarda qué fuentes aportó y `revertir` deshace la fusión.
  Cada cambio queda en el historial.
- **Episodios:** dos o más objetivos distintos del mismo país en una noche (de
  16:00 a 06:00 UTC), solo con precisión de hora o minuto.
- **Estado:** las noticias notifican (`notificado`); confirmar es cosa de una
  autoridad (siguiente PR). **Credibilidad:** noticias de fiabilidad C, 3 por la
  regla.
- **Tipo** por las reglas del esquema: interrupción aeroportuaria si hay cierre
  del aeropuerto o vuelos afectados; incursión solo con origen demostrado por
  rastreo o restos; si no, sobrevuelo.

## 4. presencia_dron

Campo público nuevo del incidente: `confirmada` (restos, rastreo por radar o una
autoridad que lo afirma expresamente), `no_confirmada` (solo avistamientos) o
`descartada`. Es independiente del estado. En el esquema, la lista cerrada de
campos, la exportación y los tests.

## 5. Nomenclátor ampliado

Para no depender solo de aeropuertos con OACI, bases aéreas y centrales
nucleares:

1. **OpenStreetMap (ODbL)**, país a país (`recogida/instalaciones_osm.py` →
   `configuracion/instalaciones_europa.json`): aeródromos y helipuertos (con
   OACI si lo tienen), bases e instalaciones militares, puertos, centrales
   (menos solares y eólicas), subestaciones de 220 kV o más, presas y estadios,
   con todos los nombres de OpenStreetMap. Descargados 29 de los 42 países (19 097 instalaciones: 5417 centrales, 4382
   estadios, 3616 presas, 2555 aeródromos, 2024 subestaciones, 1577 bases, 428
   puertos, 123 helipuertos). El servidor público de Overpass respondió 504 de
   forma repetida con las consultas grandes: Francia no salió tras varios
   intentos y a las 11:40 del 28 de septiembre se cerró la descarga sin Reino
   Unido, Italia, Grecia, Croacia, Hungría, Irlanda, Islandia, Liechtenstein,
   Lituania, Luxemburgo, Letonia y Mónaco. En esos países siguen los aeropuertos
   con OACI, las bases aéreas y las centrales nucleares del nomenclátor inicial y
   las localidades; `python -m recogida.instalaciones_osm --desde data/osm`
   completa la descarga cuando el servidor responda.
2. **GeoNames (CC BY 4.0)**: 61 970 localidades europeas de más de 1000
   habitantes con sus nombres alternativos (`recogida/localidades_geonames.py` →
   `configuracion/localidades_europa.json`). Solo sitúan una noticia que no nombra
   instalación y trae una señal de incidente; el nombre tiene que ir con
   mayúscula («Police» no es la ciudad polaca en un titular sobre la policía); un
   nombre compartido es de la localidad más poblada; los nombres que son palabras
   del vocabulario de noticias se omiten. Radio por habitantes: 3, 5, 10 o 20 km.
3. **Coordenadas del propio GKG** cuando nada casa: el lugar geolocalizado más
   preciso en un país europeo (ciudad, 10 km; región, 50 km, el máximo del
   esquema; un país entero no vale). El candidato lleva `ubicacion: gkg` (o
   `localidad`) en el registro interno. Solo en la recogida horaria: los
   parciales del histórico no guardaron esas coordenadas y repetir el histórico
   (hasta 3,8 horas) no cabía.

Además: búsqueda por un índice de grupos de hasta 8 palabras (admite cientos de
miles de nombres), alias de una sola palabra solo con mayúscula («military
camp» no es el campo irlandés «Camp»), y un titular que nombra varias
instalaciones de un mismo país va a cada una (drones sobre Esbjerg, Sønderborg
y Skrydstrup).

### Re-incorporación con el nomenclátor ampliado

El histórico se volvió a incorporar desde los parciales con el nomenclátor
ampliado. Lo ya pagado se trasladó a la base nueva (llamadas, fichas y
vocabularios; 113 fichas pasaron al candidato nuevo que contiene su primer
artículo y 159 quedaron sin candidato) y los incidentes se reconstruyeron desde
las fichas guardadas, sin volver a llamar (`recogida.extractor reconstruir`), con
la fusión y los episodios recalculados.

| | Nomenclátor inicial | Ampliado |
| --- | ---: | ---: |
| Candidatos | 834 | 6395 (908 en instalaciones, 5487 en localidades) |
| Candidatos con ficha | 822 | 1001 |
| Incidentes dados de alta | 290 | 338 |
| Publicados (sin los fundidos) | 244 | 273 |
| Sucesos de Wikipedia cubiertos | 19 | 18 |

Las localidades multiplican los candidatos, pero son sobre todo ruido: noticias
de la guerra, de política o de fuera de Europa con el nombre de una ciudad (en
la muestra, 2 de 10 son incidentes). Por eso, cuando no caben todos, van primero
los de más artículos.

## 6. Publicación

`publicacion/incidentes.geojson` con los incidentes europeos que pasan todas las
validaciones (los fundidos en otro no salen), con su lista cerrada de campos. El
workflow horario tiene ahora el paso del extractor (secretos en el entorno del
paso), la fusión y los episodios, y publica los dos ficheros.

### Incidentes publicados

273 incidentes: 169 sobrevuelos, 95 interrupciones aeroportuarias y 9
incursiones; todos en estado `notificado` (las noticias notifican; las
confirmaciones oficiales llegan en el PR siguiente). presencia_dron: 179
no_confirmada, 91 confirmada y 3 descartada. Por país, Alemania (57), Rumanía
(31), Noruega (27), Bélgica (23), Lituania (18), Países Bajos (16), Dinamarca y
Reino Unido (15), y 20 países más. Solo 2 episodios: casi todas las fechas son de
día, y un episodio exige hora.

| Mes | Incidentes |
| --- | ---: |
| 2025-01 | 8 |
| 2025-02 | 15 |
| 2025-03 | 1 |
| 2025-04 | 4 |
| 2025-05 | 4 |
| 2025-07 | 5 |
| 2025-08 | 8 |
| 2025-09 | 37 |
| 2025-10 | 33 |
| 2025-11 | 46 |
| 2025-12 | 16 |
| 2026-01 | 6 |
| 2026-02 | 5 |
| 2026-03 | 11 |
| 2026-04 | 2 |
| 2026-05 | 14 |
| 2026-06 | 8 |
| 2026-07 | 11 |
| 2026-08 | 18 |
| 2026-09 | 21 |
| Total | 273 |

### Muestra de 10 incidentes publicados (semilla 1)

Con sus fuentes para comprobarlos:

**EODI-2025-00041** — Drones afectan a Copenhague, Aalborg y puerto de Køge. Inicio 2025-08-20T09:15Z (dia), sobrevuelo, presencia_dron no_confirmada, DK Københavns Lufthavn.

- ing.dk https://ing.dk/artikel/koege-havn-aalborg-og-koebenhavns-lufthavn-plaget-af-droner-nu-er-dansk-loesning-klar «Køge Havn, Aalborg og Københavns Lufthavn plaget af droner»

**EODI-2025-00068** — Dron caído cerca del aeropuerto de Varna. Inicio 2025-07-03T00:00Z (dia), sobrevuelo, presencia_dron confirmada, BG Летище Варна.

- focus-news.net https://focus-news.net/novini/regioni/Dron-e-padnal-v-blizost-do-letishteto-vuv-Varna-2619382 «По разказ на очевидци на 3 юли дронът е загубил височина, оплел се е в жиците и е паднал.»
- marica.bg https://marica.bg/balgariq/obshtestvo/taynstven-dron-padna-opasno-blizo-do-letishte-varna-policiqta-izvarshva-proverka «Тайнствен дрон падна опасно близо до Летище Варна! Полицията...»
- news.bg https://news.bg/regions/dron-padna-blizo-do-letishteto-vav-varna.html «Дрон падна близо до летището във Варна»

**EODI-2025-00083** — Cierre del aeropuerto de Múnich por avistamientos de drones no confirmados. Inicio 2025-10-03T22:00Z (hora), interrupcion_aeroportuaria, presencia_dron no_confirmada, DE Flughafen München.

- nzherald.co.nz https://nzherald.co.nz/world/munich-airport-reopens-after-second-drone-scare-disrupts-6500-passengers/JGQ7ONYKUFF5RHGX6NLV5Y5RRA «Flights have progressively resumed at Munich Airport, but delays were expected after a drone scare caused a second shutdown in as many days»
- lecourrier.vn https://lecourrier.vn/trafic-stabilise-a-laeroport-de-munich-apres-des-alertes-aux-drones/1292252.html «Trafic stabilisé à l'aéroport de Munich après des alertes aux drones»
- tribune.com.pk https://tribune.com.pk/story/2570687/drone-scare-shuts-munich-airport «Drone scare shuts Munich airport»

**EODI-2025-00091** — Vuelos sospechosos sobre la base aérea de Kleine Brogel. Inicio 2025-11-07T10:15Z (dia), sobrevuelo, presencia_dron no_confirmada, BE Luchtmachtbasis Kleine Brogel.

- evz.ro https://evz.ro/germania-va-sprijini-belgia-in-consolidarea-apararii-anti-drona-dupa-incursiunile-de-la-baza-nucleara-kleine-brogel.html «mai multe zboruri suspecte ale unor aparate neidentificate»

**EODI-2025-00150** — Investigación completada sobre drones sobre la base RAF Lakenheath en noviembre de 2024. Inicio 2025-11-22T08:00Z (dia), sobrevuelo, presencia_dron no_confirmada, GB RAF Lakenheath.

- eadt.co.uk https://eadt.co.uk/news/25641538.investigation-drones-raf-lakenheath-completed «swarm of unmanned aircraft at RAF Lakenheath and RAF Mildenhall»

**EODI-2025-00183** — Cierre del aeropuerto de Aalborg por sospecha de actividad de drones. Inicio 2025-11-16T22:10Z (hora), interrupcion_aeroportuaria, presencia_dron no_confirmada, DK Flyvestation Aalborg.

- bt.dk https://bt.dk/krimi/mistanke-om-droneaktivitet-lukker-luftrum-over-aalborg-lufthavn «politiets indsats på stedet blev afsluttet natten til mandag klokken 01.40.»
- bt.dk https://bt.dk/krimi/aalborg-lufthavn-genaabner-efter-mistanke-om-droneaktivitet «Aalborg Lufthavn genåbner efter mistanke om droneaktivitet»
- ekstrabladet.dk https://ekstrabladet.dk/krimi/begrundet-mistanke-om-droneaktivitet-ved-aalborg-lufthavn/11011232 «Vi har en begrundet mistanke om droneaktivitet ved Aalborg Lufthavn og har derfor lukket for starter- og landinger.»

**EODI-2026-00023** — Dron abatido cerca de la base aérea de Wunstorf con posible carga explosiva. Inicio 2026-09-22T17:15Z (dia), sobrevuelo, presencia_dron no_confirmada, DE Fliegerhorst Wunstorf.

- wz-net.de https://wz-net.de/weltweit/politik/fliegerhorst-wunstorf-sprengstoff-abgestuerzter-drohne-entde-id309386.html «Die nahe dem Fliegerhorst Wunstorf abgestürzte Drohne.»
- tagesspiegel.de https://tagesspiegel.de/politik/drohnenfund-bei-fliegerhorst-wunstorf-beamte-sollen-bei-ermittlungen-womoglich-sprengstoff-entdeckt-haben-16085546.html «Drohnenfund bei Fliegerhorst Wunstorf: Beamte sollen bei Ermittlungen womöglich Sprengstoff entdeckt haben»
- n-tv.de https://n-tv.de/politik/Sprengstoff-nahe-Bundeswehr-Flugplatz-Wunstorf-gefunden-id31336407.html «Lag Drohne schon länger dort?: Sprengstoff nahe Bundeswehr-Flugplatz Wunstorf gefunden»

**EODI-2026-00079** — Sighting de drones obliga a desviar vuelos en el aeropuerto de Hannover. Inicio 2026-02-17T00:00Z (dia), interrupcion_aeroportuaria, presencia_dron no_confirmada, DE Flughafen Hannover-Langenhagen.

- neuepresse.de https://neuepresse.de/lokales/hannover/flughafen-hannover-langenhagen-keine-landungen-nach-drohnensichtung-moeglich-QIKYZT2R65HU7LLTZ32TRDJRVE.html «Keine Landungen nach Drohnensichtung möglich.»
- haz.de https://haz.de/lokales/hannover/pilot-meldet-drohnensichtung-am-flughafen-hannover-maschinen-muessen-abdrehen-QIKYZT2R65HU7LLTZ32TRDJRVE.html «Pilot meldet Drohnensichtung am Flughafen Hannover: Maschinen müssen abdrehen»

**EODI-2026-00095** — Dos drones explotan en territorio rumano, promoviendo una reunión de urgencia de la OTAN. Inicio 2026-06-10T00:00Z (dia), sobrevuelo, presencia_dron no_confirmada, RO Poiana Vadului.

- realitatea.net https://realitatea.net/stiri/extern/reuniune-de-urgenta-la-nato-la-solicitarea-romaniei-discutii-cruciale-despre-securitatea-din-marea-neagra-si-incidentele-cu-drone-vnqr8b «după ce două drone au explodat pe teritoriul țării noastre»
- antena3.ro https://antena3.ro/externe/a-inceput-reuniunea-nato-in-care-romania-cere-echipamente-noi-ca-sa-doboare-drone-e-prezent-dan-neculaescu-dorit-la-aparare-791546.html «România a cerut capabilități suplimentare pentru apărarea aeriană și combaterea dronelor»

**EODI-2026-00118** — Fragment de dron encontrado en el mar cerca de Costineşti. Inicio 2026-08-13T06:15Z (dia), sobrevuelo, presencia_dron no_confirmada, RO Costineşti.

- digi24.ro https://digi24.ro/stiri/actualitate/fragment-dintr-o-posibila-drona-observat-in-mare-la-costinesti-3904527 «Resturi dintr-o dronă au fost descoperite în apa mării.»
- mediafax.ro https://mediafax.ro/social/drona-observata-la-costinesti-la-doar-15-metri-de-stabilopozi-au-intervenit-autoritatile-23789606 «Garda de Coastă a solicitat sprijinul Forțelor Navale Române, care au intervenit cu o echipă de scafandri.»
- bursa.ro https://bursa.ro/o-drona-a-fost-observata-in-apropierea-stabilopozilor-din-costinesti-69168958 «În jurul orei 8:15 a fost primit un apel 112 prin care se comunica o posibilă dronă.»

Revisión de la muestra, comparada con sus fuentes: siete son incidentes
correctos (Varna, Múnich, Aalborg, Wunstorf, Hannover, Costinești y Kleine
Brogel, este con la fecha de un resumen de días anteriores). Tres tienen fallos:
Lakenheath es un suceso de noviembre de 2024 fechado el 22 de noviembre de 2025
por el artículo que cuenta el fin de la investigación; el de Copenhague, Aalborg
y Køge es un reportaje sobre drones de agosto de 2025 más que un incidente; y el
de los dos drones que explotaron en Rumanía queda en Poiana Vadului, una
localidad que casó por su nombre y que no es donde cayeron.

## 7. Comparación con Wikipedia

Lista «2025 European drone sightings» (Wikipedia en inglés, revisión del 28 de
septiembre de 2026), versionada como referencia en
`configuracion/referencia_wikipedia_2025.json`: 25 sucesos, uno por lugar y
noche. Un suceso está cubierto si hay un incidente publicado en su aeropuerto o
base, o a menos de 20 km, del día anterior a tres días después
(`python -m recogida.comparacion`).

| Fecha | País | Lugar | Encontrado |
| --- | --- | --- | --- |
| 2025-09-22 | DK | Aeropuerto de Copenhague | EODI-2025-00135 |
| 2025-09-22 | NO | Aeropuerto de Oslo-Gardermoen | EODI-2025-00042 |
| 2025-09-24 | DK | Aeropuerto de Aalborg | EODI-2025-00128, EODI-2025-00172 |
| 2025-09-24 | DK | Aeropuerto de Billund | falta |
| 2025-09-24 | DK | Aeropuerto de Sønderborg | falta |
| 2025-09-24 | DK | Aeropuerto de Esbjerg | falta |
| 2025-09-24 | DK | Base aérea de Skrydstrup | falta |
| 2025-09-25 | DE | Astillero de TKMS en Kiel | falta |
| 2025-09-26 | DK | Base aérea de Karup | EODI-2025-00015 |
| 2025-09-27 | NO | Base aérea de Ørland | falta |
| 2025-09-28 | NO | Aeropuerto de Brønnøysund | EODI-2025-00021, EODI-2025-00069 |
| 2025-10-02 | DE | Aeropuerto de Múnich | EODI-2025-00055, EODI-2025-00083, EODI-2025-00210 |
| 2025-10-02 | BE | Campo militar de Elsenborn | EODI-2025-00237 |
| 2025-10-03 | DE | Aeropuerto de Múnich | EODI-2025-00055, EODI-2025-00083, EODI-2025-00210 |
| 2025-10-31 | DE | Aeropuerto de Berlín-Brandeburgo | EODI-2025-00221 |
| 2025-11-02 | DE | Aeropuerto de Bremen | EODI-2025-00007 |
| 2025-11-02 | BE | Base aérea de Kleine Brogel | EODI-2025-00020, EODI-2025-00255 |
| 2025-11-06 | SE | Aeropuerto de Gotemburgo-Landvetter | EODI-2025-00235 |
| 2025-11-06 | BE | Aeropuerto de Bruselas | falta |
| 2025-11-06 | BE | Puerto de Amberes | EODI-2025-00125, EODI-2025-00161, EODI-2025-00181 |
| 2025-11-09 | BE | Aeropuerto de Lieja | EODI-2025-00092 |
| 2025-11-09 | BE | Central nuclear de Doel | EODI-2025-00125, EODI-2025-00181 |
| 2025-11-22 | NL | Base aérea de Volkel | EODI-2025-00066 |
| 2025-12-01 | IE | Mar de Irlanda frente a Howth (Dublín) | EODI-2025-00195 |
| 2025-12-04 | FR | Base naval de Île Longue | EODI-2025-00206 |

**18 de 25.** Faltan, y por qué:

- **Billund, 24 de septiembre**: hay candidato, pero el modelo situó la noticia en
  otro aeropuerto y la ficha no vale para Billund.
- **Sønderborg, Esbjerg y Skrydstrup, 24 de septiembre**: con la regla nueva de
  varios objetivos tienen candidato (el titular «Drones Observed by Airports in
  Esbjerg, Sonderborg, Skrydstrup»), pero con dos artículos cada uno no entraron
  en el presupuesto (Sønderborg, además, no casa porque ese titular no pone la
  «ø»).
- **Kiel, 25 de septiembre**: ningún titular del histórico nombra Kiel; hablan de
  Schleswig-Holstein. En la recogida horaria, las coordenadas del GKG lo
  situarían.
- **Ørland, 27 de septiembre**: los titulares noruegos dicen «Ørlandet» o
  «kampflybasen på Ørland» y ningún nombre casa; Noruega sí está en OpenStreetMap,
  pero la base se llama allí «Ørland hovedflystasjon».
- **Bruselas, 6 de noviembre**: hay incidentes de Bruselas del 4 y el 5 de
  noviembre (los cierres del día 4), fundidos en uno que empieza el 4; la lista
  pone el suceso el día 6, fuera de la ventana.

## Valores justificados

| Valor | Dónde | Por qué |
| --- | --- | --- |
| 20 trabajos en paralelo | `historico_gdelt.py` | El máximo del plan gratuito de GitHub Actions |
| 5,5 horas por trabajo | `historico_gdelt.py` | Un trabajo dura como mucho 6 horas: deja margen para subir el parcial |
| 10 intentos con esperas de 5 s crecientes | `remoto.py` | Hasta 20 trabajos pueden subir a la vez; casi 4 minutos de margen |
| Nivel 6 de compresión | `cifrado.py` | Equilibrio habitual entre tamaño y tiempo: 107 MB a 14,4 MB |
| 120 s por llamada, 4 reintentos desde 10 s, tope de 300 s | `modelo/cliente.py` | Una ficha tarda segundos; supera cortes y respeta lo que pida el servicio |
| 1500 tokens de salida | `modelo/ficha.py` | Una ficha completa ocupa unos 800 |
| 600 letras de la página, párrafos de 40 letras y 6 palabras | `modelo/paginas.py` | Lugar, hora, cierre y cifras van al principio; lo más corto son firmas y avisos |
| 3 fuentes por candidato | `proceso/extraccion.py` | Lo pedido |
| 3 llamadas por candidato | `proceso/extraccion.py` | Un candidato que crece sin dar datos no gasta sin fin |
| 0,5 de confianza | `validacion_ficha.py` | Por debajo el modelo declara que supone |
| 100 drones, 2000 vuelos, 48 horas de cierre | `validacion_ficha.py` | Los mayores avistamientos de 2025 hablan de decenas; un gran aeropuerto mueve unos 1500 vuelos al día; un cierre dura horas |
| 1 semana antes del primer artículo, 1 hora después | `validacion_ficha.py` | La noticia sale el mismo día o pocos días después; la hora del artículo es la de su franja de GDELT |
| 1, 5, 1,25, 0,1 USD y lotes a la mitad | `modelo/coste.py` | Tarifas del modelo configurado |
| 5 USD y 0,30 USD al día | `modelo/coste.py` | Límites pedidos |
| 0,5 tokens por letra en el peor caso | `modelo/coste.py` | Unos 0,3 en idiomas europeos: el peor caso no se queda corto |
| 1 USD de reserva del límite | orden `lote --reserva` | Para las confirmaciones oficiales del PR siguiente, que comparte el límite |
| 3 días de ventana horaria del extractor | `recogida/extractor.py` | Lo anterior es del histórico, que va por lotes |
| 8 hilos para las páginas | `recogida/extractor.py` | Unas 4000 páginas en menos de una hora respetando la pausa por sitio |
| 16:00 a 06:00 UTC como noche | `proceso/incidentes.py` | 17:00 a 07:00 en Europa central en invierno, 18:00 a 08:00 en verano |
| 5 km aeródromos y bases, 3 km puertos, 2 km centrales y presas, 1 km estadios, helipuertos y subestaciones | `instalaciones_osm.py` | Tamaño del recinto y su entorno inmediato |
| 3, 5, 10 y 20 km por habitantes | `localidades_geonames.py` | Un pueblo, una ciudad media, una grande y una capital de más de un millón |
| 10 km ciudad, 50 km región del GKG | `proceso/noticias.py` | Una ciudad; una región, con el máximo del esquema |
| 8 palabras por nombre | `proceso/noticias.py` | Cubre los nombres largos de aeropuertos |
| 5 instalaciones por titular | `proceso/noticias.py` | Más es un resumen, no un suceso |
| 20 s entre países, 10 minutos por consulta, 5 reintentos desde 30 s | `instalaciones_osm.py` | El servidor público de Overpass pide no encadenar consultas pesadas y responde 504 cuando está saturado |
| 20 km y del día anterior a tres días después | `recogida/comparacion.py` | Dos radios del nomenclátor; las noticias de investigación salen días después |

## Decisiones tomadas aquí

- **Lanzar el histórico desde una rama.** Sin estar en `main`, el workflow no se
  puede lanzar con `workflow_dispatch`; se añadió un disparador por push a una
  rama de lanzamiento, que se borró.
- **Base comprimida.** Imprescindible para el histórico. Obliga a mergear antes
  de subir la base: el código de `main` no leía una base comprimida.
- **Ficha como lista de datos** y **frase literal obligatoria**: se prefiere
  perder una ficha a publicar una cita que no está en la fuente.
- **Caché del servicio sin rellenar** el bloque fijo hasta el mínimo.
- **Localidades solo con señal de incidente** y **con mayúscula**, y **nombres
  ambiguos** descartados: la cobertura sube sin que cualquier titular con una
  ciudad se vuelva candidato.
- **Prioridad por número de artículos** cuando los candidatos no caben en el
  límite, y **reserva de 1 USD** para el PR siguiente.
- **Reconstrucción** de incidentes desde las fichas guardadas al cambiar los
  candidatos, en lugar de volver a llamar al modelo.

## Sigue abierto

- **Candidatos sin ficha**: 5457 pendientes (1034 con dos o más artículos), que
  no caben en el límite de 5 USD. Con otros 2 USD, las tandas por número de
  artículos cubrirían los de dos o más; lo más barato sería filtrar mejor los
  candidatos de localidades antes del modelo (por ejemplo, exigir dos artículos
  de medios distintos o una señal de aeropuerto, militar o infraestructura).
- **OpenStreetMap**: faltan 13 países (ver punto 5).
- **Coordenadas del GKG en el histórico**: los parciales no las guardaron;
  repetir el histórico las añadiría.
- **Fechas de la noticia en vez del suceso**: el modelo a veces toma la fecha de
  un artículo que cuenta un suceso antiguo; la validación solo rechaza las de más
  de una semana antes.
- **Frases que no están en la fuente**: primer motivo de descarte (92 fichas);
  parte viene de haber recuperado el primer lote leyendo otra vez las páginas.
- **Caché del servicio**: sin aciertos con este modelo por el tamaño del bloque.
- **Estado**: todos los incidentes están notificados hasta que lleguen las
  confirmaciones oficiales (PR siguiente).
- **Recuperar y reconstruir** son órdenes locales: si una ejecución falla a mitad,
  hay que lanzarlas desde un equipo con la clave age.

