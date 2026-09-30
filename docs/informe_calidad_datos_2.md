# Calidad de los datos, segunda parte

30 de septiembre de 2026. Las horas son UTC. Continúa
[`informe_calidad_datos.md`](informe_calidad_datos.md).

## 1. Aviso de servidor parado sin falsas alarmas

El workflow `vigia-recogida` miraba el último commit de la rama `estado`, que no avanza
cuando una recogida no cambia la base: a las dos horas habría abierto una incidencia sin
que nada fallara. Ahora lee <https://tiles.droneobservatory.eu/estado.json>
([`recogida/salud.py`](../recogida/salud.py)):

- abre la incidencia si la última recogida correcta tiene más de 2 horas o si el fichero
  no responde en tres intentos separados un minuto;
- una recogida fallida o con avisos no abre nada mientras haya una correcta reciente;
- mantiene una sola incidencia mientras dure el problema y la cierra al recuperarse;
- permisos: leer el código e incidencias. Pide el fichero con la identificación del
  observatorio: al agente por defecto de Python, Cloudflare le responde 403.

El trabajo `salud-recogida` del workflow de tests hace la misma comprobación y la deja en
su resumen. Desde los ejecutores de GitHub el fichero se lee bien («la última correcta,
hace 0,4 h»).

Tests (`tests/test_salud.py`): estado reciente, estado antiguo, recogida fallida con una
correcta reciente, recogidas fallidas durante más de dos horas, fichero ausente en los tres
intentos (con sus dos esperas), un fallo pasajero y la salida del trabajo.

**La clave de despliegue de solo lectura** del repositorio de datos («droneobservatory:
salud (solo lectura)», secreto `EODI_DATOS_CLAVE_LECTURA`) ya no la usa ningún workflow.
Se retira del repositorio y de GitHub tras fusionar, cuando `main` ya no la necesita
(sección 7).

## 2. Nomenclátor más completo

### Localidades pequeñas

| | Antes | Después |
| --- | --- | --- |
| Localidades (1000 habitantes o más) | 61 970, con 297 631 nombres | igual |
| Localidades pequeñas y homónimas | — | 579 064, con 994 758 nombres (770 951 distintos) |
| Ciudades de instalaciones, con sus formas | 2212 | 2212 y 610 formas declinadas |

`configuracion/localidades_pequenas.json.gz` (13,8 MB), generado con
`python -m recogida.localidades_pequenas`. Contiene todas las localidades pobladas de
GeoNames de los países de la recogida que no están en el nomenclátor grande. Se excluyen
los lugares históricos, abandonados, destruidos o que forman parte de otra localidad
(PPLH, PPLQ, PPLW, PPLX y PPLCH). Lleva también los nombres que en el nomenclátor grande
se quedó una homónima más poblada: el Grindu de Tulcea solo conservaba allí «Pisica».

**Solo sitúan el lugar del suceso de una ficha, ya limitado a su país**, nunca un titular.
Lo mostró la medición con los 50 000 titulares de la base: de los 550 668 nombres nuevos
de una palabra, 2428 salen en minúscula en algún titular («para», «guerra», «strike»), y
casi todos los que salen solo con mayúscula son personas, organizaciones, regiones o
ciudades de fuera («Merz», «Reuters», «Bayern», «Moscou»). Cargarlas lleva 5,5 s y
unos 500 MB, y solo se hace cuando hay que situar una ficha. El servidor tiene 3,8 GB y
su pico era de 1 GB.

**Alias excluidos**, cada uno por su regla. Se suman a las del PR 20: vocabulario de
noticias, palabras omitidas y nombres de países.

| Regla | Nombres excluidos | Por qué |
| --- | --- | --- |
| Palabra corriente en el idioma del país | 3074 | Sale en minúscula en titulares de medios de ese país. Por país: «grindų» («suelos» en lituano) se normaliza como «grindu», un pueblo de Tulcea, y una regla general lo habría quitado |
| Ciudad de 15 000 habitantes o más de fuera de la recogida | 20 325 | «Moscou», «Odesa», «Engels»: la noticia habla de la ciudad, no de la aldea |
| Nombre de una región de primer nivel | 819 | «Bayern», «Niedersachsen» |
| Nombre de un país | 725 | Como en el PR 20 |
| Palabra del vocabulario de noticias | 143 | Como en el nomenclátor grande |

Además hay **85 605 nombres ambiguos** dentro de su país: los llevan varias localidades
pequeñas del mismo país (hay muchos «Neudorf»). No se descartan, pero solo se resuelven
con la región que da la ficha; sin ella, no sitúan nada. Otros 88 021 nombres son también
de una localidad grande. Se guardan, pero al situar se prueba antes la grande, y la
pequeña solo sale si la grande no vale (por ejemplo, porque es de otra región).

**Prioridad.** Al situar el lugar del suceso, el orden es: instalación del nomenclátor,
objetivo del candidato, vocabulario, localidad grande, localidad pequeña, lugar nuevo de
la ficha y GKG. Ninguna localidad nueva desplaza a una instalación. Test con los
aeródromos de Zborov (SK) y Weremień (PL), que tienen aldeas del mismo nombre en otro
sitio.

### Formas declinadas de las instalaciones

[`proceso/variantes.py`](../proceso/variantes.py) genera por regla, según la terminación
del nombre, las formas de la ciudad de cada instalación en el idioma del país. Van al
índice de ciudades, que solo casa si el titular nombra además el tipo de lugar.

| Idioma | Regla | Ejemplo con test |
| --- | --- | --- |
| Alemán (DE, AT, CH, LI, LU) | adjetivo en -er | «Düsseldorfer Flughafen», «Münchner Flughafen» |
| Polaco | genitivo y locativo | «lotnisko w Rzeszowie», «w Lublinie» |
| Lituano | genitivo | «Palangos oro uostas» |
| Letón | genitivo | «Liepājas lidosta» |
| Estonio | genitivo | «Tallinna lennujaam» |
| Finés | genitivo, con gradación | «Rovaniemen», «Turun», «Helsingin lentoasema» |
| Sueco, danés, noruego | genitivo en -s | «Visbys flygplats», «Aalborgs lufthavn», «Trondheims lufthavn» |

Una ciudad de varias instalaciones vale si el titular nombra el tipo de una sola. Entre
dos del mismo tipo, gana la que solo lleva el nombre de esa ciudad: «Düsseldorf» es el
aeropuerto de Düsseldorf, no el de Düsseldorf Mönchengladbach.

## 3. Incidentes sin país

De los 31 incidentes publicados antes del PR 20 y retirados porque la ficha no sabía el
país, **se recupera 1**: EODI-2026-00066, drones sobre el aeropuerto de Shannon (IE), que
ahora tiene punto. Los demás siguen retirados:

| Por qué | Incidentes |
| --- | --- |
| La ficha dice que no es un incidente: la noticia habla de equipos de detección del aeropuerto de Riga, del problema de los drones en Stuttgart… | 17 |
| La ficha dice que es un incidente, pero no trae ningún lugar ni país, tampoco al volver a extraerla | 9 |
| La frase de «es incidente» no está en la fuente: no se sabe si lo es | 4 |

Cómo se buscó:

1. **Sin llamadas.** El país se deduce del lugar del suceso que describe la ficha (su
   lugar, la instalación o la localidad que nombra), citado en su frase o en las fuentes,
   solo si el nomenclátor ampliado lo sitúa en un solo país (o si es el nombre de un país).
   Nunca con el país del medio. Si la ficha declara un país, aunque no valide, lo deducido
   tiene que coincidir con él. En una primera pasada sin esta condición, El Paso (Texas),
   el aeropuerto de Ramón (Israel) y el Reagan de Washington salían en España, Italia y el
   Reino Unido por pueblos que se llaman igual.
2. **Con las llamadas imprescindibles.** Los 17 incidentes retirados sin país cuya ficha
   dice que son incidentes (los 36 retirados sin país, no solo los 31 publicados) se
   volvieron a extraer, con un tope de 0,50 dólares. Salió publicable 1 (Shannon). Por el
   camino se recuperó además EODI-2026-00253, drones militares caídos en un depósito de
   combustible de Rēzekne (LV), que no estaba entre los 31 publicados.

## 4. Episodios y números

- **Purgados**: los 4 episodios deshechos (EODI-EP-2025-0001, EODI-EP-2026-0001,
  EODI-EP-2025-0003 y EODI-EP-2025-0004), que ningún incidente enlazaba. Es la única baja
  de la base: el disparador que impide borrar se quita y se vuelve a poner en la misma
  transacción, y antes cada episodio queda en el historial, con su documento, como cambio
  a una marca de purgado.
- **Sin reutilizar números**: la numeración cuenta también los purgados, que siguen en el
  historial, así que un número publicado no vuelve a usarse. Los publicados ahora,
  EODI-EP-2025-0002 y EODI-EP-2025-0005, conservan su número. El hueco del 0003 y el 0004
  queda, porque renumerar rompería sus enlaces.
- **Reconstruir no numera de más**: test con dos reconstrucciones seguidas.

Revisando esto apareció un fallo de fondo del PR 20. La reconstrucción no sabía qué
incidente era de cada candidato si lo había dado de alta ella misma: en cada pasada le
daba un número nuevo, y las copias se fundían entre sí. Dos parejas de copias llegaron a
publicarse a la vez: EODI-2026-00245 con 00247 (un dron ruso junto al portaaviones Charles
de Gaulle) y 00246 con 00248 (drones caídos en Letonia). Además, un incidente así ya no se
podía retirar cuando su ficha dejaba de valer. Ahora cada incidente guarda su candidato
(`control.candidato`, interno). Al reconstruir se reutiliza su número; para los
anteriores, el más bajo que contiene sus artículos. Las copias numeradas de más se
retiran con el motivo «copia de EODI-…». Tras el arreglo, dos reconstrucciones seguidas
dejan el mismo número de incidentes (530).

## 5. Lo aplicado en el servidor

Con `servidor/revision.sh calidad-datos-2 … --reextraer-sin-pais` y el mismo cerrojo que
la recogida horaria, tomado a las 21:45 y retenido hasta la fusión. Primero, la
reextracción y la reconstrucción. Después, con el cerrojo aún tomado, otra reconstrucción
con los dos arreglos de las secciones 3 y 4.

| | Antes | Después |
| --- | --- | --- |
| Publicados | 372 | 370 |
| En el mapa | 233 | 248 |
| Sin ubicación | 139 | 122 |
| Episodios | 2 | 2 |

- **Cambian de sitio 16**, todos porque ganan un punto que no tenían; ninguno pasa de un
  punto a otro. Trece se sitúan en localidades pequeñas: Cuhureștii de Jos, Grindu,
  Periprava, Pepeni, Valea Perjei, Auvere, Mingir, Padina, Etulia, Căplani, Hîrbovăț,
  Sauca y Palanca. Otro en Volintiri, otra aldea recién situada. El Charles de Gaulle, en
  Malmö. Y el aeropuerto de Düsseldorf, por «Düsseldorfer Flughafen».
- **Dejan de publicarse 4**:
  - EODI-2026-00159 (Anenii Noi) se funde en EODI-2026-00203: es el mismo dron, que
    explotó en Hîrbovăț, en el distrito de Anenii Noi, y ahora ese incidente tiene punto.
  - EODI-2026-00188 se funde en EODI-2026-00233 (Düsseldorf).
  - 00247 y 00248 se retiran: son las copias de la sección 4.

  Los cuatro enlaces dejan de llevar a un incidente propio. La web podría llevarlos al
  incidente en el que están.
- **Se publican 2**: Shannon (00066) y Rēzekne (00253).
- **Gasto**: 0,0515 dólares en las 17 llamadas de la reextracción, dentro del tope de 0,50.
  El total del modo revisión es 1,7739 dólares.

## 6. Muestra al azar

20 incidentes publicados, elegidos con semilla fija (`random.Random(1)`).

| Id | Título | Lugar del suceso | Nivel | País | Punto | Tipo | Enlace |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EODI-2025-00001 | Drones sobre el aeropuerto de Hannover obligan a desviar vuelos | Flughafen Hannover-Langenhagen | instalación | DE | 52,4615, 9,6801 | sobrevuelo | https://ndz.de/der-norden/drohnen-am-flughafen-hannover-mehrere-flugzeuge-umgeleitet-SBIPCZ2A6FBMBMDCCCTUWVKJH4.html |
| EODI-2025-00018 | Dron obliga a desviar un vuelo en el aeropuerto de Eindhoven | Eindhoven Airport | instalación | NL | 51,4518, 5,3779 | interrupción | https://drimble.nl/regio/noord-holland/amsterdam/105099810/vlucht-uit-alicante-wijkt-uit-naar-amsterdam-na-signalering-drone-bij-eindhoven-airport.html |
| EODI-2025-00050 | Avistamientos de drones desvían vuelos hacia el aeropuerto de Fráncfort | Frankfurter Flughafen | instalación | DE | 50,0244, 8,5448 | sobrevuelo | https://fnp.de/frankfurt/drohnensichtungen-mit-auswirkungen-auf-flughafen-frankfurt-93967889.html |
| EODI-2025-00073 | Dron obliga a desviarse al avión del presidente de Lituania en Vilna | Tarptautinis Vilniaus oro uostas | instalación | LT | 54,6349, 25,2876 | sobrevuelo | https://lrytas.lt/lietuvosdiena/aktualijos/2025/09/02/news/vilniaus-oro-uosto-darba-vel-sutrikde-dronas-ore-ratus-suko-ir-is-suomijos-griztantis-gitanas-nauseda-39352329 |
| EODI-2025-00091 | Sobrevuelos sospechosos sobre la base de Kleine Brogel en Bélgica | — | país | BE | sin punto | sobrevuelo | https://evz.ro/germania-va-sprijini-belgia-in-consolidarea-apararii-anti-drona-dupa-incursiunile-de-la-baza-nucleara-kleine-brogel.html |
| EODI-2025-00101 | Dron avistado cerca del aeropuerto de Vilna obliga a suspender vuelos | Vilnius | localidad | LT | 54,6349, 25,2876 | sobrevuelo | https://ve.lt/aktualijos/nakti-salia-vilniaus-oro-uosto-pastebejus-drona-laikinai-teko-sustabdyti-visus-skrydzius |
| EODI-2025-00167 | Reportes de drones cerca del aeropuerto de Keflavík | Keflavík Airport | instalación | IS | 63,9725, −22,6388 | sobrevuelo | https://icelandmonitor.mbl.is/news/news/2025/09/30/reports_of_drones_near_keflavik_airport |
| EODI-2025-00206 | Cinco drones sobrevuelan la base nuclear de Ile Longue en Brest | Ile Longue | instalación | FR | 48,2700, −4,6100 | sobrevuelo | https://tg24.sky.it/mondo/2025/12/05/droni-francia |
| EODI-2025-00311 | Drones rusos derribados sobre el espacio aéreo de Polonia | Poland | país | PL | sin punto | incursión | https://thestar.com.my/news/world/2025/09/10/ukraine039s-air-force-warns-that-russian-drones-entered-poland039s-airspace |
| EODI-2025-00317 | Dron derribado sobre base militar en Sajonia-Anhalt | Sachsen-Anhalt | región | DE | sin punto | sobrevuelo | https://berliner-zeitung.de/politik-gesellschaft/bundeswehr-bestaetigt-abschuss-einer-drohne-ueber-militaergelaende-in-sachsen-anhalt-li.2317013 |
| EODI-2026-00037 | Dron no autorizado sobre el aeropuerto de Palanga | Palangos oro uostas | instalación | LT | 55,9727, 21,0953 | sobrevuelo | https://lrt.lt/naujienos/verslas/4/2929281/vst-pastaraja-savaite-fiksavo-pazeidima-del-drono-skrydzio-virs-palangos-oro-uosto |
| EODI-2026-00047 | Turista vuela un dron cerca del aeropuerto de Svolvær durante un despegue | Svolvær lufthavn | instalación | NO | 68,2417, 14,6675 | sobrevuelo | https://nrk.no/nordland/turist-floy-drone-rett-ved-svolvaer-lufthavn-i-lofoten-da-et-fly-fra-wideroe-skulle-ta-av-1.17989917 |
| EODI-2026-00049 | Cierre del aeropuerto de Vilnius por posible observación de dron | Vilnius Lufthavn | instalación | LT | 54,6349, 25,2876 | interrupción | https://bt.dk/udland/nato-kampfly-sendt-i-luften-lufthavn-lukket-efter-mulig-observation-af-drone |
| EODI-2026-00071 | Incidente con drones en el aeropuerto de Leipzig/Halle | Flughafen Leipzig/Halle | instalación | DE | 51,4211, 12,2365 | sobrevuelo | https://zeit.de/news/2026-08/12/innenausschuss-des-landtages-beraet-ueber-drohnenvorfall |
| EODI-2026-00085 | Tres drones derribados sobre la base aérea de Borcea | — | país | RO | sin punto | incursión | https://adevarul.ro/securitate-si-aparare/cine-a-pilotat-avioanele-f-16-trimise-dupa-drone-2546141.html |
| EODI-2026-00090 | Dron ucraniano se estrella en Lituania tras desviarse de su objetivo | ice-covered lake | región | LT | sin punto | sobrevuelo | https://thestar.com.my/news/world/2026/03/24/drone-that-crashed-in-lithuania-came-from-ukraine-lithuanian-pm-says |
| EODI-2026-00154 | Dron detectado cerca de la frontera de Rumania en Suceava | Suceava | localidad | RO | 47,6191, 26,2442 | sobrevuelo | https://monitorulsv.ro/deputata-aur-veronica-grosu-ii-cere-premierului-bolojan-sa-spuna-cine-raspunde-pentru-siguranta-romanilor-dupa-incidentele-cu-drone-din-suceava_e07d13 |
| EODI-2026-00179 | Cazas de la OTAN derriban un dron sobre Lituania | Lituania | país | LT | sin punto | incursión | https://ansa.it/sito/notizie/topnews/2026/09/15/caccia-della-nato-abbattono-un-drone-sopra-la-lituania_0009593d-6491-408a-9480-af07927ee5a8.html |
| EODI-2026-00204 | Dron abatido en el espacio aéreo de Letonia por cazas de la OTAN | Lettonie | país | LV | sin punto | incursión | https://sudouest.fr/international/europe/ukraine/guerre-en-ukraine-un-drone-etranger-abattu-par-des-avions-de-chasse-allies-dans-l-espace-aerien-letton-30252100.php |
| EODI-2026-00234 | Caza de la OTAN derriba un dron sobre Rumania | — | país | RO | sin punto | incursión | https://welt.de/politik/ausland/article6a810e3ba87e8142c31d1677/ukraine-krieg-russland-greift-kiew-an-nato-jet-schiesst-drohne-ueber-rumaenien-ab.html |

Los 12 con punto están en el sitio del suceso. De los 8 sin punto, 5 son correctos por el
nivel que da la fuente (Polonia, Lituania, Letonia, Sajonia-Anhalt, un lago helado de
Lituania). Hay 3 que se podrían haber situado y no se situaron:

- Kleine Brogel y Borcea: su ficha no trae el lugar del suceso.
- El caza de la OTAN sobre Rumanía: la noticia no dice dónde.

## 7. Wikipedia «2025 European drone sightings»

20 de 25 sucesos, igual que tras el PR 20. Siguen faltando Sønderborg, Esbjerg y
Skrydstrup (24 de septiembre), el astillero de TKMS en Kiel y la base de Ørland. Los
incidentes sin punto no cuentan en esta comparación.

## 8. Lo que queda sin decidir

1. **Enlaces de incidentes fundidos o retirados** (00159, 00188, 00247, 00248): no llevan
   a ningún incidente publicado. La web podría redirigirlos al incidente en el que están,
   pero eso exige publicar las fusiones.
2. **Fichas sin lugar del suceso** de instalaciones conocidas (Kleine Brogel, Borcea):
   solo una nueva extracción con otras fuentes las situaría.
3. **Formas declinadas no cubiertas**: el plural polaco en «-ach» («w Katowicach») y el
   genitivo de nombres de varias palabras («Göteborg Landvetter»).
4. **Palabras corrientes medidas con los titulares de la base**: si se añaden medios de
   otros países, la regla hay que volver a medirla.
