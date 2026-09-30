# Calidad de los datos publicados

30 de septiembre de 2026. Las horas son UTC.

## 1. Los fallos, reproducidos

Todos se reprodujeron con la base de la rama `estado` y los ficheros publicados de ese
momento (288 incidentes en el mapa, 2 episodios).

| Fallo | Lo publicado | Causa |
| --- | --- | --- |
| Ibiza al sur de Madrid | EODI-2026-00073, en 39,772, −3,604 (La Guardia, Toledo), con «Un dron paraliza el aeropuerto de Ibiza durante 35 minutos» | El nomenclátor de instalaciones tiene un aeródromo llamado «La Guardia». El titular «…derribado por la Guardia Nacional» de record.com.mx y el de Diario de Ibiza («El equipo Pegaso de la Guardia Civil…») casaron con ese alias y formaron un candidato allí. El incidente tomaba el punto del objetivo del candidato, y la ficha no tenía cómo decir dónde ocurrió |
| Estonia en Andalucía | EODI-2026-00130, «Dron ucraniano derribado por un caza de la OTAN sobre Estonia», en 37,464, −5,346 (Fuentes de Andalucía) | GeoNames da «Ukraine» y «Ucrania» como nombres alternativos de Fuentes de Andalucía. Cada titular que decía «Ukraine» caía en ese pueblo. La ficha solo traía `es_incidente`: el país salió del objetivo (ES) y el punto, también |
| Moldavia en Rumanía | 14 incidentes de Moldavia en Fundu Moldovei (47,533, 25,4, Suceava, Rumanía), con país RO | GeoNames da «Moldova» como nombre de Fundu Moldovei |
| La validación no lo impidió | — | Comprobaba que el punto cayera en la caja del país que decía la ficha. Cuando la ficha no decía país, el país era el del objetivo, así que objetivo y punto coincidían siempre |
| Anenii Noi como sobrevuelo | EODI-2026-00159: sobrevuelo | La ficha decía `incursion`, pero el código exigía `origen_demostrado` (rastreo o restos) y la explosión no contaba |
| Anenii Noi con «dron no confirmada» | — | El modelo escribió «confirmata» (rumano) y el valor se descartó; ninguna regla usaba la confirmación del ministerio para el propio dron |
| Anenii Noi con «cierre sin confirmar» | `cierre: desconocido` | El dato es correcto (la fuente no habla de cierre). Es la web la que rotula «desconocido» como «Cierre sin confirmar» |
| Episodio en Rumanía | EODI-EP-2026-0001: EODI-2026-00111 (Tulcea) y EODI-2026-00136 (Fundu Moldovei, a 350 km) | El segundo era el Shahed que cruzó Moldavia el 20 de agosto, mal situado por el alias «Moldova». Era un incidente mal situado, no un episodio |

La causa de los fallos de ubicación no era el centro de país de GDELT. Eran nombres del
nomenclátor que casaban con palabras de la noticia y el uso del objetivo del candidato como
lugar del incidente. Hay 111 alias de localidades que son nombres de países («Włochy»,
«Siria», «Moldova», «India» para Inđija…).

## 2. Qué cambia

**Ubicación** (`proceso/ubicacion.py`, `proceso/fronteras.py`).

- La ficha del extractor (versión `ficha/5`) trae `lugar_suceso`: dónde ocurrió, con su
  nivel (instalación, localidad, región o país), su país y su región, más `dron_estatal`,
  `entrada_exterior` y `evidencia` (explosión, restos, caída, derribo, dron recuperado).
- El punto se busca por el nombre del lugar del suceso, en su país: instalaciones del
  nomenclátor, el objetivo del candidato solo si su nombre es ese, el vocabulario de
  lugares, las localidades, el lugar nuevo de la ficha y, por último, el lugar del GKG, solo
  si es una ciudad o un lugar con nombre (tipos 3 y 4) con ese nombre. Nunca los tipos de
  país o de región.
- Un suceso de nivel país o región, o que no se sitúa, no tiene punto: va a
  `publicacion/incidentes_sin_ubicacion.json` con su país y su región.
- El punto tiene que caer en el polígono de su país (Natural Earth 1:10 millones). Hay dos
  márgenes medidos sobre las 20 174 instalaciones del nomenclátor: 12 millas náuticas en el
  mar y 2,5 km de frontera en tierra, que cubren 113 de las 164 que caen en tierra de otro
  país. Si no, el incidente no se publica y el motivo queda en su extracción.
- Los nombres de países se quitan de los alias del nomenclátor. Cada localidad lleva su
  región de GeoNames, que descarta homónimos: el Grindu de Tulcea frente al de Ialomița.
- El nombre del lugar del suceso tiene que estar en su frase o en las fuentes, al menos
  sus palabras propias, sin contar las de tipo de lugar.
- Sin lugar del suceso no se usa el objetivo del candidato, aunque la ficha diga que es el
  conocido: así volvía Ibiza a La Guardia con su ficha antigua.
- Las incursiones de los partes ucranianos pierden la «zona fronteriza de referencia», que
  era un punto inventado, y se publican sin punto.

**Tipo** (`proceso/incidentes.py`, `aplicar_reglas`). Es incursión un dron militar o
estatal que entra desde fuera cuando lo demuestra una autoridad (el incidente está
confirmado o atribuido) o una prueba física (explosión, restos, caída, derribo, dron
recuperado o rastreo por radar). Un avistamiento sin eso nunca lo es. Una explosión o un
modelo militar (Shahed, Geran, Gerbera) demuestran que el dron era militar. La
interrupción aeroportuaria manda.

**Presencia del dron.** Si el incidente confirmado por una autoridad es el propio dron
(explosión, restos, caída, derribo o dron recuperado), la presencia queda confirmada. En
los demás casos, como antes.

**Cierre.** `si` o `no` solo valen si su frase habla de un cierre o, para `no`, de que
siguió todo con normalidad (`configuracion/cierres.json`). Si no, el dato no se rellena y
queda `desconocido`.

**Episodios.** Solo incidentes con punto, del mismo país y la misma noche. De varios
países, solo si una misma fuente los cuenta. Un incidente sin punto no entra en ninguno.
Los episodios que dejan de serlo se marcan como deshechos (nada se borra).

**Declaraciones.** Cada una lleva el país de la autoridad, y una autoridad de otro país no
cambia el incidente. El gobierno letón que dice que en Letonia no entró ningún dron desmentía
el derribo en Estonia.

**Otros.** Temperatura 0 en el extractor: dos llamadas sobre la misma nota daban fichas
distintas. Los valores de lista en otro idioma («confirmata») valen si solo casan con uno.
El país vale si la fuente lo nombra, aunque el modelo parafrasee la frase. Una ficha que
deja de ser publicable retira el incidente, sin borrarlo, y al rehacerlo se conservan las
fuentes oficiales que lo confirmaban.

## 3. La revisión de todo lo publicado

En el servidor, con `servidor/revision.sh` y el mismo cerrojo que la recogida horaria,
tomado a las 18:46 y retenido hasta la fusión. Las recogidas de las 19:17 y siguientes no
se lanzaron: el cerrojo estaba tomado.

- **Candidatos**: los 1076 que ya habían pasado por el extractor con una ficha anterior.
  Los 5219 que nunca se extrajeron quedan fuera: no estaban publicados y extraerlos todos
  habría costado unos 14 dólares.
- **Muestra y previsión**: 10 llamadas directas, a 0,0043 dólares de media. Con la mitad
  de precio del lote, se preveían 2,32 dólares en total, dentro del límite de 5.
- **Lotes**: el recorte al límite usa el peor caso de cada petición (toda la entrada sin
  caché y la salida máxima), unas dos veces lo real. Por eso entraron 676 peticiones en el
  primer lote (`msgbatch_01Xr6PC3syU65CgfDjMM9qzB`, 271 publicables) y las 390 restantes
  en un segundo (10 de muestra y 380 en `msgbatch_01SXCG6xjJLUip61zAYMkWqC`, 163
  publicables), con el cerrojo aún tomado por el primer proceso. No falló ninguna.
- **Reconstrucciones sin llamadas**: tres más, con arreglos hallados al revisar los
  resultados. La primera evita que Ibiza vuelva a La Guardia con su ficha antigua. La
  segunda acepta el país que nombra la fuente y reutiliza el episodio con los mismos
  miembros. La tercera acepta el nombre del lugar con sus palabras propias en las fuentes.
- **Coste**: 1,7225 dólares registrados en la base (modo `revision`). Hay que sumar unos
  0,11 de llamadas de prueba en local sobre una copia de la base, para ajustar la ficha
  antes del lote, que no quedaron registradas. En total, unos 1,83 dólares de 5.

## 4. Antes y después

Leído de los propios ficheros publicados (`recogida/revision.py`).

| | Antes | Después |
| --- | --- | --- |
| Incidentes publicados | 288 | 372 |
| En el mapa | 288 | 233 |
| Sin ubicación | 0 | 139 |
| Episodios | 2 | 2 |
| Sobrevuelo / interrupción / incursión | 179 / 98 / 11 | 203 / 82 / 87 |
| Notificado / confirmado / atribuido / desmentido | 272 / 13 / 2 / 1 | 230 / 136 / 3 / 3 |
| Dron confirmado / no confirmado / descartado | 103 / 182 / 3 | 174 / 194 / 4 |
| Cierre sí / no / desconocido | 89 / 11 / 187 | 71 / 1 / 299 |

Entre los 225 incidentes publicados antes y después:

- **Cambian de sitio 71**: 47 pierden el punto y 24 se mueven más de 1 km.
- **Cambian de tipo 46**: 21 interrupciones pasan a sobrevuelo (su cierre no tenía frase
  de cierre, o el incidente quedó sin punto y sin categoría de aeropuerto), 14 sobrevuelos
  pasan a incursión, 7 sobrevuelos a interrupción y 4 incursiones a sobrevuelo.
- **Cambian de estado 88**: 78 pasan de notificado a confirmado por las declaraciones
  oficiales citadas, ahora aplicadas a todo el histórico; 5 vuelven de confirmado a
  notificado (la ficha nueva no trae la declaración); 3 quedan desmentidos; 2 pasan a
  atribuidos.
- **Cambia la presencia del dron en 68**: 31 pasan a confirmada y 36 dejan de estarlo (la
  ficha antigua la daba por confirmada con solo una autoridad que hablaba del incidente); 1
  pasa a descartada.
- **Cambia el cierre en 39**: 24 «sí» y 9 «no» sin frase que hablara de cierre pasan a
  desconocido; 6 pasan a «sí».

Además, 63 de los publicados antes ya no salen: 17 están fundidos en otro y 46 retirados,
en su mayoría porque la ficha nueva no sabe su país. Salen 147 que antes no estaban:
incidentes que estaban fundidos en otro por su mismo sitio equivocado, o candidatos que
ahora son publicables. Sin punto hay 79 de nivel país, 29 de región, 27 de localidad y 4 de
instalación sin situar; son sobre todo de Rumanía (37) y Moldavia (33). Los 233 puntos
salen del nomenclátor (142), del objetivo del candidato con el mismo nombre (60), de
localidades (21), del vocabulario (9) y de un lugar nuevo (1).

**Episodios deshechos**: los 2 que había. EODI-EP-2026-0001 (Tulcea con Fundu Moldovei):
00136 es de Moldavia sin punto y 00111 está fundido en 00218, en Tulcea. EODI-EP-2025-0001:
uno de sus dos incidentes se retiró. Hay 2 nuevos, cada uno con incidentes de un mismo
país y noche: EODI-EP-2025-0002 y EODI-EP-2025-0005.

## 5. Los casos

| Caso | Después |
| --- | --- |
| Ibiza | EODI-2026-00028 en el aeropuerto de Ibiza (LEIB, 38,873, 1,372), interrupción aeroportuaria con cierre. El duplicado EODI-2026-00062 está fundido en él. EODI-2026-00073, el de La Guardia, está retirado: su ficha nueva no es publicable |
| Estonia | EODI-2026-00130 sin punto, país EE, en el fichero sin ubicación; incursión con dron confirmado (derribo) |
| Anenii Noi | EODI-2026-00159 en Anenii Noi (MD, 46,878, 29,235): incursión (explosión, caída y confirmación del Ministerio de Defensa), confirmado, dron confirmado, cierre desconocido |
| Episodio de Rumanía | Deshecho. EODI-2026-00136 (Shahed del 20 de agosto) es de Moldavia, sin punto, incursión confirmada. El de Tulcea está en Tulcea |

## 6. Muestra al azar

20 incidentes publicados, elegidos con semilla fija (`random.Random(1)`), para comprobarlos
a mano.

| Id | Título | Lugar del suceso | Nivel | País | Punto | Tipo | Enlace |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EODI-2025-00001 | Drones sobre el aeropuerto de Hannover obligan a desviar vuelos | Flughafen Hannover-Langenhagen | instalación | DE | 52,4615, 9,6801 | sobrevuelo | https://ndz.de/der-norden/drohnen-am-flughafen-hannover-mehrere-flugzeuge-umgeleitet-SBIPCZ2A6FBMBMDCCCTUWVKJH4.html |
| EODI-2025-00018 | Dron obliga a desviar un vuelo en el aeropuerto de Eindhoven | Eindhoven Airport | instalación | NL | 51,4518, 5,3779 | interrupción | https://drimble.nl/regio/noord-holland/amsterdam/105099810/vlucht-uit-alicante-wijkt-uit-naar-amsterdam-na-signalering-drone-bij-eindhoven-airport.html |
| EODI-2025-00050 | Avistamientos de drones desvían vuelos hacia el aeropuerto de Fráncfort | Frankfurter Flughafen | instalación | DE | 50,0244, 8,5448 | sobrevuelo | https://fnp.de/frankfurt/drohnensichtungen-mit-auswirkungen-auf-flughafen-frankfurt-93967889.html |
| EODI-2025-00073 | Dron obliga a desviarse al avión del presidente de Lituania | Tarptautinis Vilniaus oro uostas | instalación | LT | 54,6349, 25,2876 | sobrevuelo | https://lrytas.lt/lietuvosdiena/aktualijos/2025/09/02/news/vilniaus-oro-uosto-darba-vel-sutrikde-dronas-ore-ratus-suko-ir-is-suomijos-griztantis-gitanas-nauseda-39352329 |
| EODI-2025-00091 | Sobrevuelos sospechosos sobre la base de Kleine Brogel | — | país | BE | sin punto | sobrevuelo | https://evz.ro/germania-va-sprijini-belgia-in-consolidarea-apararii-anti-drona-dupa-incursiunile-de-la-baza-nucleara-kleine-brogel.html |
| EODI-2025-00101 | Dron avistado cerca del aeropuerto de Vilna obliga a suspender vuelos | Vilnius | localidad | LT | 54,6349, 25,2876 | sobrevuelo | https://ve.lt/aktualijos/nakti-salia-vilniaus-oro-uosto-pastebejus-drona-laikinai-teko-sustabdyti-visus-skrydzius |
| EODI-2025-00167 | Reportes de drones cerca del aeropuerto de Keflavík | Keflavík Airport | instalación | IS | 63,9725, −22,6388 | sobrevuelo | https://icelandmonitor.mbl.is/news/news/2025/09/30/reports_of_drones_near_keflavik_airport |
| EODI-2025-00206 | Cinco drones sobrevuelan la base nuclear de Ile Longue | Ile Longue | instalación | FR | 48,2700, −4,6100 | sobrevuelo | https://tg24.sky.it/mondo/2025/12/05/droni-francia |
| EODI-2025-00311 | Drones rusos derribados sobre el espacio aéreo de Polonia | Poland | país | PL | sin punto | incursión | https://thestar.com.my/news/world/2025/09/10/ukraine039s-air-force-warns-that-russian-drones-entered-poland039s-airspace |
| EODI-2025-00317 | Dron derribado sobre base militar en Sajonia-Anhalt | Sachsen-Anhalt | región | DE | sin punto | sobrevuelo | https://berliner-zeitung.de/politik-gesellschaft/bundeswehr-bestaetigt-abschuss-einer-drohne-ueber-militaergelaende-in-sachsen-anhalt-li.2317013 |
| EODI-2026-00037 | Dron no autorizado sobre el aeropuerto de Palanga | Palangos oro uostas | instalación | LT | 55,9727, 21,0953 | sobrevuelo | https://lrt.lt/naujienos/verslas/4/2929281/vst-pastaraja-savaite-fiksavo-pazeidima-del-drono-skrydzio-virs-palangos-oro-uosto |
| EODI-2026-00047 | Turista vuela un dron cerca del aeropuerto de Svolvær | Svolvær lufthavn | instalación | NO | 68,2417, 14,6675 | sobrevuelo | https://nrk.no/nordland/turist-floy-drone-rett-ved-svolvaer-lufthavn-i-lofoten-da-et-fly-fra-wideroe-skulle-ta-av-1.17989917 |
| EODI-2026-00049 | Cierre del aeropuerto de Vilnius por posible observación de dron | Vilnius Lufthavn | instalación | LT | 54,6349, 25,2876 | interrupción | https://bt.dk/udland/nato-kampfly-sendt-i-luften-lufthavn-lukket-efter-mulig-observation-af-drone |
| EODI-2026-00074 | Un dron confirmado vuela sobre el aeropuerto de Chisináu | Aeroportul Internațional Chișinău «Eugen Doga» | instalación | MD | 46,9296, 28,9290 | interrupción | https://news.yam.md/ro/story/62650046 |
| EODI-2026-00087 | Dron civil detiene vuelos en el aeropuerto de Vilna | Tarptautinis Vilniaus oro uostas | instalación | LT | 54,6349, 25,2876 | sobrevuelo | https://lrytas.lt/verslas/rinkos-pulsas/2026/03/14/news/vilniaus-oro-uoste-laikinai-stojo-skrydziai-pastebetas-dronas-41669078 |
| EODI-2026-00091 | Fragmentos de dron recuperados en el Mar Negro | Marea Neagră | región | RO | sin punto | sobrevuelo | https://adevarul.ro/stiri-interne/evenimente/posibil-fragment-de-drona-gasit-in-marea-neagra-2558679.html |
| EODI-2026-00155 | Dron detectado por radares militares al norte de Isaccea | nord de Isaccea | región | RO | sin punto | sobrevuelo | https://antena3.ro/actualitate/drona-detectata-de-radarele-armatei-la-nord-de-isaccea-langa-frontiera-cu-ucraina-mesaj-ro-alert-in-tulcea-804975.html |
| EODI-2026-00179 | Cazas de la OTAN derriban un dron sobre Lituania | Lituania | país | LT | sin punto | incursión | https://ansa.it/sito/notizie/topnews/2026/09/15/caccia-della-nato-abbattono-un-drone-sopra-la-lituania_0009593d-6491-408a-9480-af07927ee5a8.html |
| EODI-2026-00203 | Dron que entró en el espacio aéreo de Moldavia se estrella | Hîrbovăț | localidad | MD | sin punto | incursión | https://jurnalul.ro/stiri/externe/alerta-republica-moldova-drona-survolat-bender-explodat-hirbovat-1045526.html |
| EODI-2026-00233 | Dron privado interrumpe el tráfico aéreo en el aeropuerto de Düsseldorf | Düsseldorfer Flughafen | instalación | DE | sin punto | sobrevuelo | https://n-tv.de/regionales/nordrhein-westfalen/Drohne-unterbricht-Flugverkehr-am-Duesseldorfer-Flughafen-id31356407.html |

Los 13 con punto están en el sitio del suceso. De los 7 sin punto, 4 son correctos por el
nivel que da la fuente (Polonia, Lituania, el mar Negro, el norte de Isaccea). Otros 3 se
podrían haber situado:

- **Kleine Brogel**: la noticia es una nota general.
- **Hîrbovăț**: no está en el nomenclátor de localidades de más de 1000 habitantes.
- **«Düsseldorfer Flughafen»**: la forma declinada no casa con el alias «Flughafen
  Düsseldorf».

Tres de la muestra (Hannover, Fráncfort, Vilna 00087) hablan de vuelos desviados o
detenidos y figuran como sobrevuelo: la ficha no trae el número de vuelos, o su frase no
valida.

## 7. Comparación con la lista de Wikipedia «2025 European drone sightings»

`configuracion/referencia_wikipedia_2025.json`: un suceso está cubierto si hay un incidente
con punto a menos de 20 km, del día anterior a tres días después.

| | Antes | Después |
| --- | --- | --- |
| Sucesos encontrados | 18 de 25 | 20 de 25 |

Se ganan el aeropuerto de Billund (24 de septiembre) y el de Bruselas (6 de noviembre).
Siguen faltando Sønderborg, Esbjerg y Skrydstrup (24 de septiembre), el astillero de TKMS
en Kiel y la base de Ørland. Los incidentes sin punto no cuentan en esta comparación.

## 8. Servidor

- **Aviso si se para**: el workflow `vigia-recogida` se lanza cada hora en el minuto 41,
  con permiso solo para incidencias. Abre una («La recogida horaria no actualiza la base»)
  si el último commit de la rama `estado` tiene más de 2 horas, una sola mientras dure, y la
  cierra cuando la rama vuelve a actualizarse. Lee el repositorio de datos con la clave de
  despliegue de solo lectura que ya existía («droneobservatory: salud (solo lectura)»,
  secreto `EODI_DATOS_CLAVE_LECTURA`), creada con `gh` en la migración al servidor. No hacía
  falta otra.
- **Ministerio de Defensa de Finlandia**: retirado de `fuentes_oficiales.json`. Queda
  documentado en [`servidor.md`](servidor.md).
- La recogida de las 18:17, anterior a este cambio, terminó con avisos: las fuentes
  oficiales agotaron su tope de 240 s con 8 sin leer. No tiene que ver con este pull
  request.

## 9. Lo que la web tiene que cambiar

- **Leer `publicacion/incidentes_sin_ubicacion.json`**. Es `{"incidentes": [...]}`, con las
  mismas propiedades que las features del GeoJSON, sin geometría. En el lugar no hay
  `radio_km` y sí `nivel` (instalación, localidad, región o país) y `region` cuando se
  sabe. Esos incidentes no se dibujan como punto: van a la lista, a los filtros y al feed,
  marcados como «ubicación imprecisa», con su país (y su región, si la hay). Mientras la web
  no lo lea, 139 incidentes publicados no se ven.
- **No rotular `cierre: desconocido` como «Cierre sin confirmar»**: significa que la fuente
  no habla de cierre.

Las dos cosas están acordadas con la sesión que trabaja en la web.

## 10. Lo que queda sin decidir

1. **Candidatos nunca extraídos**: 5219, casi todos de un solo artículo. Extraerlos costaría
   unos 14 dólares.
2. **Incidentes retirados porque la ficha nueva no sabe su país**: 31. De las fuentes
   solo se guardan los titulares, así que no se puede comprobar si la página nombra el país
   sin descargarla otra vez.
3. **Nombres declinados de instalaciones** («Düsseldorfer Flughafen», «Vilniaus oro
   uostas»): el nomenclátor no los reconoce.
4. **Localidades pequeñas** (menos de 1000 habitantes, como Hîrbovăț): no están en el
   nomenclátor.
5. **Recorte del lote por el peor caso**: dobla lo real y obligó a dos lotes. Se podría
   recortar con el coste medio de la muestra y un margen.
6. **Interrupciones sin vuelos**: una ficha que habla de vuelos desviados sin número o sin
   frase válida queda como sobrevuelo.
7. **Episodios deshechos**: quedan en la base con la marca `deshecho`, como las fusiones
   revertidas. También hay dos numerados de más (EODI-EP-2025-0003 y 0004) de las primeras
   reconstrucciones, deshechos.
