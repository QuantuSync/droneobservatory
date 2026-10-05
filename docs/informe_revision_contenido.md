# Revisión del contenido delicado

European Observatory of Drone Incidents, 5 de octubre de 2026. Las horas son UTC. Esta revisión
solo corrige y afianza lo que ya existía: no añade funciones nuevas. La base solo se amplía: cada
corrección entra como versión nueva del incidente con su motivo en el historial, lo retirado queda
marcado como retirado con su motivo en español y en inglés, y lo unido queda fundido con su motivo.

Todas las correcciones hechas a mano están en un solo fichero,
[`configuracion/incidentes_revisados.json`](../configuracion/incidentes_revisados.json), que la
recogida horaria aplica en cada pasada ([`recogida/revisados.py`](../recogida/revisados.py)). Si
una reconstrucción rehiciera los incidentes, la recogida siguiente las vuelve a aplicar. Después
de la primera pasada no cambian nada: lo he comprobado con dos pasadas seguidas sobre una copia de
la base, y la segunda no guarda nada.

**En resumen.**

- Los 77 incidentes cuyo titular no respaldaba su cita están revisados uno por uno: 29 tenían la
  cita sin guardar, 14 tenían un titular que decía más que sus citas, 31 eran duplicados y 3 no
  eran sucesos. La comprobación da hoy **cero casos**, y es una barrera: un titular nuevo sin
  respaldo no se publica y la CI lo comprueba en cada cambio.
- Odesa casi no aparecía porque se leía un canal secundario que empezó en junio de 2025; el
  canal oficial del jefe de la administración, el de la ciudad y los de Volinia, Zhytómyr y
  Ternópil están entrando. Odesa pasa de 74 a 103 impactos con lo leído hasta las 17:17; el resto
  entra solo con las recogidas normales, hasta la madrugada del 6 de octubre.
- Polonia (EODI-2025-00295) tiene punto en Wyryki-Wola, con la fiscalía como fuente y 16 lugares
  más; otros 37 confirmados tienen ya el lugar que da la autoridad.
- La bandera de los atribuidos sale desde el primer dibujado y los números de los grupos se leen
  por encima de los marcadores.



## Bloque 1. Titulares que su cita no respalda

### Qué comprueba la prueba y qué ha cambiado en ella

La comprobación ([`proceso/cita_titular.py`](../proceso/cita_titular.py)) pide que alguna cita
publicada del incidente nombre su país, su lugar o un nombre propio de su titular. Tres cambios:

1. **Se comprueba sobre lo que se publica.** Antes se medía sobre el incidente interno, con citas y
   nombres de lugar que no salen en la web (el nombre del lugar tal como lo escribe la ficha, las
   frases internas de las afirmaciones). Ahora se mide sobre la ficha pública, con las mismas
   listas de campos que el mapa y que los incidentes sin punto. Así, lo que pasa la comprobación
   es lo que ve quien abre la ficha. Con este cambio aparecieron cinco casos más (Edimburgo dos
   veces, Weeze, Shannon y Marlow), que se revisaron igual que los demás.
2. **Otra escritura y otro nombre.** El cirílico y el griego se comparan también pasados al
   alfabeto latino («София» casa con «Sofía», «Бургас» con «Burgas»). Lo que así no casa va en
   [`configuracion/nombres_equivalentes.json`](../configuracion/nombres_equivalentes.json), con
   nombres comprobados en las citas revisadas: «Схипхол» es Schiphol, «Vilniaus» es Vilna,
   «Αιγαίο» es el Egeo, «roumain» es Rumanía. Es el caso «la comprobación falla por idioma o por
   escritura»: se corrige la prueba, no el titular.
3. **Es una barrera.** Un incidente cuyas citas publicadas no respaldan el titular no se publica
   (`exportacion/geojson.publicables`) y deja un aviso en el registro de la recogida, hasta que se
   revisa. Antes solo se paraba así a los que tenían solo partes de guerra. Si alguno es correcto
   y la prueba no puede verlo, se anota en `titular_justificado` con su motivo en los dos idiomas;
   hoy no hay ninguno. La misma comprobación corre en la integración continua sobre los ficheros
   publicados ([`tests/test_cita_titular.py`](../tests/test_cita_titular.py)): un titular nuevo
   sin respaldo no llega a publicarse ni pasa la CI.

### Cómo se revisó

Con la base del 5 de octubre (la sesión de atribuciones había cambiado 115 titulares), la
comprobación daba 72 incidentes; con la comprobación sobre la ficha pública, 77. Cada uno se miró
uno por uno: el titular, todas sus citas y sus fuentes abiertas en la página original (o en su
copia del archivo web si la original ya no respondía). Cada frase nueva se buscó después, por
programa, dentro del texto de la página: es literal y tiene 25 palabras como mucho. He vuelto a
abrir yo una muestra al azar de ocho citas y siete frases de lugar: todas están en su página,
salvo una publicación de X de la policía de Jutlandia del Norte que ya no es pública (ese punto no
se pone; ver bloque 3).

Lo que entra en la base por cada caso:

- **La cita existía y no se guardó**: la frase literal entra como fuente del incidente
  (`citas`), con su enlace, su medio, su fecha y dónde y cuándo se comprobó. Si es la palabra de
  una autoridad (la policía, un ministerio, el gestor del aeropuerto), entra como declaración
  citada y pasa por las reglas de siempre (`proceso/declaraciones.aplicar_fuentes`): confirma solo
  si la regla lo sostiene. Así han pasado a confirmados, por ejemplo, Bardufoss (policía de Troms),
  Gibraltar (Royal Gibraltar Police), Sofía (Ministerio del Interior búlgaro), Sundsvall (policía
  sueca), Bergen (policía del oeste), Burgas (Armada búlgara), Gilze-Rijen, Split, Budapest y
  Edimburgo (portavoz del aeropuerto).
- **El titular afirma lo que las citas no dicen**: titular nuevo en los dos idiomas (`titulares`)
  con su motivo. Pasa después por las mismas reglas que todos (coherente con la presencia del
  dron y sin nacionalidad ni autor si no está atribuido), para que la revisión horaria no lo
  vuelva a tocar.
- **Presencia y estado**: cuando la autoridad lo deja abierto o no lo da por hecho, la presencia
  del dron queda «sin confirmar» con la cita de la autoridad, y la regla horaria de presencia ya no
  la vuelve a confirmar. Un caso (Arna) estaba confirmado por una declaración de la policía que
  solo decía que había recibido avisos y que, al llegar, no vio drones: vuelve a «notificado» con
  un paso nuevo en el historial y su motivo en los dos idiomas (la retirada de una confirmación
  que no se sostiene es ahora, como la de una atribución, un paso permitido solo con motivo:
  `proceso/estados.RETIRADAS`).
- **No es un suceso**: retirado con su motivo en español y en inglés (`retirado.motivo` y
  `retirado.motivo_en`).
- **Es un duplicado**: unido al registro del mismo suceso (`unir`), con la regla de siempre para
  elegir cuál queda; sus citas pasan al que queda.

Resultado de los 77:

| Caso | Incidentes |
| --- | ---: |
| La cita existía y no se guardó: se guarda la frase literal | 29 |
| El titular afirma algo que las citas no dicen: titular nuevo | 14 |
| Duplicado de otro registro del mismo suceso: unido (sus citas pasan al que queda) | 31 |
| No es un suceso (una estadística de nueve meses, una opinión en televisión, un «hace hoy ocho años»): retirado | 3 |
| Falla solo por idioma o escritura: se corrige la prueba | 0 como caso principal; la prueba corregida sirve para Sofía (dos registros), Schiphol, Vilna, el Egeo y Rumanía |
| **Total** | **77** |

En 17 de ellos el titular publicado cambia: los 14 de titular nuevo; Edimburgo y Weeze, donde con la
cita nueva las reglas de siempre quitan o ponen el «posible»; y Poggioreale, que decía «Drone» en
el titular español. Tras la revisión, la comprobación da
**cero casos** sin justificar sobre la base de ensayo, y la lista de justificados está vacía.

Decisiones que conviene conocer:

- **Schiphol (EODI-2025-00058)**: la Marechaussee, responsable de la seguridad del aeropuerto,
  dijo que «muy probablemente no era un dron». No es un desmentido sin reservas, así que el
  incidente sigue notificado, con la presencia sin confirmar y el titular «Posible dron,
  probablemente un globo, cierra 45 minutos una pista de Schiphol».
- **Vilna, globos (EODI-2025-00102)**: se mantiene, con la cita que nombra los globos y el
  aeropuerto: el cierre ocurrió y la presencia ya figuraba como descartada.
- **Geilenkirchen (EODI-2025-00094)**: todas sus fuentes son del aeropuerto noruego de
  Brønnøysund; el titular y el lugar pasan a Brønnøysund. **Arna (EODI-2025-00140)**: está en
  Noruega, no en Suecia; el país y la región se corrigen.
- **Leipzig**: EODI-2026-00346, que decía Rzeszów, es una noticia polaca del dron de
  Leipzig/Halle; se une al atribuido EODI-2026-00134.

### Tabla

«Titular nuevo» es el que se publica tras la revisión (con las reglas de siempre aplicadas
encima); «sin cambio» si el titular era correcto. La cita es la que nombra lo que afirma el
titular, tal como se publica.

| Incidente | Titular anterior | Titular nuevo | Caso | Cita que lo respalda |
| --- | --- | --- | --- | --- |
| EODI-2025-00013 | Dos turistas detenidos por volar dron cerca del aeropuerto de Bardufoss | sin cambio | cita sin guardar | «To turister innbrakt etter mistanke om ulovlig droneflyvning i nærheten av Bardufoss lufthavn.» |
| EODI-2025-00034 | Dron interrumpe el aeropuerto de Vilna sin que se identifique su propietario | sin cambio | cita sin guardar | «trečiadienio naktį dėl minėto drono teko laikinai stabdyti skrydžius Vilniaus oro uoste.» |
| EODI-2025-00058 | Drones cierran una pista del aeropuerto de Ámsterdam Schiphol | Posible dron, probablemente un globo, cierra 45 minutos una pista de Schiphol | titular sin respaldo | «De Polderbaan op Schiphol is vanmiddag zo'n 45 minuten gesloten geweest, nadat piloten en vliegtuigspotters dachten dat ze een drone hadden gezien.» |
| EODI-2025-00059 | Hombre detenido por volar dron en zona prohibida del aeropuerto de Sandefjord | La policía para a un hombre que voló un dron en la zona prohibida del aeropuerto de Sandefjord Torp | titular sin respaldo | «En utenlandsk statsborger har innrømmet å ha fløyet ulovlig med drone ved flyplassen i Sandefjord søndag ettermiddag.» |
| EODI-2025-00060 | Dron avistado obliga a cerrar temporalmente el aeropuerto de Vilna | Posible dron obliga a suspender temporalmente la actividad del aeropuerto de Vilna | titular sin respaldo | «Dėl galimai pastebėto drono buvo laikinai sustabdyta Vilniaus oro uosto veikla, praneša Lietuvos oro uostų atstovas Tadas Vasiliauskas.» |
| EODI-2025-00065 | Cinco drones perturban el tráfico aéreo en el aeropuerto de Dresde | retirado | no es un suceso: retirado | «Es una estadística: la DFS cuenta cinco avistamientos en Dresde en los nueve primeros meses de 2025, sin fecha ni detalle de ningún suceso concreto.» |
| EODI-2025-00088 | Drones no autorizados retrasan vuelos en el aeropuerto de Gibraltar | sin cambio | cita sin guardar | «Dos vuelos comerciales quedaron temporalmente retenidos la noche del lunes en el aeropuerto de Gibraltar tras la detección de drones no autorizados» |
| EODI-2025-00091 | Sobrevuelos sospechosos sobre la base de Kleine Brogel en Bélgica | sin cambio | cita sin guardar | «În weekend, baza militară belgiană Kleine-Brogel, unde se află armament nuclear american, a fost survolată de trei ori» |
| EODI-2025-00094 | Drones cerca de la base aérea de Geilenkirchen causan desvío de vuelos | Drones avistados cerca del aeropuerto de Brønnøysund, en Noruega | titular sin respaldo | «POLICIJA je sinoć primila prijave o dronovima koji su se približili aerodromu Bronojsund u Norveškoj toliko da su mogli da ih uoče kontrolori leta,» |
| EODI-2025-00096 | Retrasos en el aeropuerto de Edimburgo por un posible dron no autorizado | Retrasos en el aeropuerto de Edimburgo por un dron no autorizado | cita sin guardar | «Flights were delayed at Edinburgh Airport on Friday night after an unauthorised drone was spotted within the exclusion zone.» |
| EODI-2025-00099 | Dron sobre el aeropuerto de Vilna obliga a desviar un vuelo | Objeto volador sospechoso sobre el aeropuerto de Vilna obliga a desviar un vuelo a Riga | titular sin respaldo | «Vilniuje ketvirtadienio naktį dėl virš oro uosto įtariamai skraidžiusio objekto negalėjus nusileisti lėktuvui, policija tikina gavusi pranešimą apie pastebėtą droną.» |
| EODI-2025-00102 | Globos meteorológicos cierran el aeropuerto de Vilna | sin cambio | cita sin guardar | «Lietuvos oro erdvę šeštadienio naktį pažeidė 25 meteorologiniai oro balionai, dėl kurių laikinai sutriko Vilniaus oro uosto veikla.» |
| EODI-2025-00114 | Posibles drones observados sobre el aeropuerto de Riga | retirado | no es un suceso: retirado | «Es una nota de opinión: un exministro en un programa de televisión critica al Gobierno y cuenta que cada semana pasa un dron sobre su casa; no describe ningún suceso con fecha.» |
| EODI-2025-00119 | Dron no identificado obliga a cerrar el aeropuerto de Gibraltar | sin cambio | cita sin guardar | «La presencia de un dron obligó en la noche del sábado a cerrar por precaución el aeropuerto de Gibraltar por segunda vez en diez días» |
| EODI-2025-00127 | Un dron bloquea seis vuelos en el aeropuerto de Sofía | sin cambio | cita sin guardar | «Собственикът на дрона, блокирал 6 полета на Летище София, все още е неизвестен» |
| EODI-2025-00132 | Vuelo retrasado en el aeropuerto de Bergen por un dron no autorizado | sin cambio | cita sin guardar | «Ulovlig droneflygning innenfor forbudssonen på Bergen Lufthavn Flesland førte til at én flyavgang måtte holdes tilbake tirsdag kveld.» |
| EODI-2025-00134 | Casi colisión entre un avión y un posible dron cerca del aeropuerto de Heathrow | sin cambio | duplicado: unido | «The Airbus A320 had just taken off from London’s Heathrow Airport and was at 9,000 ft during the near miss in May.» |
| EODI-2025-00140 | Múltiples avistamientos de drones sobre Arna, Suecia | Vecinos avisan a la policía de varios avistamientos de posibles drones sobre Arna, en Noruega | titular sin respaldo | «Politiet har de siste dagene mottatt en rekke tips fra folk i Arna som har observert omfattende droneaktivitet.» |
| EODI-2025-00142 | Posible dron casi colisiona con un Airbus A320 sobre Londres | unido en EODI-2025-00134 | cita sin guardar | «The Airbus A320 had just taken off from London’s Heathrow Airport and was at 9,000 ft during the near miss in May.» |
| EODI-2025-00143 | Incidente de posible dron cerca del aeropuerto de Southampton | retirado | no es un suceso: retirado | «La única fuente es una sección «On this Day» del Daily Echo que recuerda un cuasi choque de 2017; no hay ningún suceso en 2025 y la fecha del incidente (17-02-2025) es la de la nota, no la del hecho.» |
| EODI-2025-00145 | Dron detectado en el aeropuerto de Sundsvall Timrå obliga a desviar un vuelo | Dron detectado en el aeropuerto de Sundsvall Timrå obliga a un avión a esperar en vuelo | titular sin respaldo | «Vid 22-tiden på söndagskvällen upptäcktes en drönare vid Sundsvall Timrå Airport.» |
| EODI-2025-00146 | Cierre de pista en Bergen por un dron en zona prohibida | sin cambio | cita sin guardar | «Onsdag kveld ble en drone observert like sør for Bergen lufthavn.» |
| EODI-2025-00149 | Posibles drones sobrevuelan una base militar belga | unido en EODI-2025-00223 | duplicado: unido | «des gardes de la caserne de Marche-en-Famenne avaient repéré plusieurs drones survolant la base militaire» |
| EODI-2025-00150 | Investigación completada sobre posibles drones en RAF Lakenheath | unido en EODI-2025-00164 | duplicado: unido | «The National Police Air Service (NPAS) helicopter took action during a search for drone activity at RAF Lakenheath and RAF Mildenhall» |
| EODI-2025-00152 | Drones no identificados cerca del aeropuerto de Dublín durante visita de Zelenskyy | unido en EODI-2025-00294 | duplicado: unido | «The appearance of drones near Dublin Airport ahead of President Zelenskyy’s arrival» |
| EODI-2025-00156 | Varios drones paralizan el aeropuerto de Gibraltar y obligan a desviar un avión militar | sin cambio | cita sin guardar | «El aeropuerto de Gibraltar ha vuelto a vivir momentos de tensión este fin de semana después de que varios drones irrumpieran en el espacio aéreo» |
| EODI-2025-00164 | Actividad de drones cerca de RAF Lakenheath causa incidente con helicóptero policial | Avistamientos de posibles drones en RAF Lakenheath y Mildenhall movilizan un helicóptero policial | titular sin respaldo | «The National Police Air Service (NPAS) helicopter took action during a search for drone activity at RAF Lakenheath and RAF Mildenhall» |
| EODI-2025-00166 | Drones sobre el aeropuerto de Alta obligan a intervenir a la policía | sin cambio | cita sin guardar | «politiet at de har rykket ut til Alta lufthavn etter å ha fått melding om en drone som flyr i luftrommet til Alta lufthavn» |
| EODI-2025-00170 | Drones ilegales sobre el aeropuerto de Riga en enero | unido en EODI-2025-00176 | duplicado: unido | «izbeidzis no Valsts policijas pārņemto kriminālprocesu par šogad janvārī nelikumīgi pilotētajiem droniem Rīgas lidostas teritorijā» |
| EODI-2025-00179 | Avistamiento de dron en el aeropuerto de Weeze sin confirmación | Avistamiento de posible dron en el aeropuerto de Weeze sin confirmación | cita sin guardar | «am Montagabend auch einen Einsatz im Bereich des Flughafens Weeze: Ein Bürger hatte gegen 18:30 Uhr die Polizei angerufen» |
| EODI-2025-00184 | Drones sobre el aeropuerto militar de Bardufoss obligan a desviar vuelos | Drones vistos cerca del aeropuerto de Bardufoss obligan a un avión a dar la vuelta y cierran el aeropuerto | titular sin respaldo | «Die Norwegian-Maschine war auf dem Weg von Oslo nach Bardufoss.» |
| EODI-2025-00188 | Retrasos en el aeropuerto de Edimburgo tras avistamiento de dron | sin cambio | cita sin guardar | «Flights arriving at Edinburgh Airport were delayed on Tuesday, after a drone was discovered flying near the airport.» |
| EODI-2025-00202 | Posibles drones cierran el aeropuerto de Hannover y retrasan un transporte de órgano | unido en EODI-2025-00001 | duplicado: unido | «Am Abend des zweiten Weihnachtsfeiertages haben Drohnen den Reiseverkehr am Flughafen Hannover ausgebremst.» |
| EODI-2025-00256 | Sobrevuelo de dron sobre la pólvora Eurenco de Bergerac | unido en EODI-2025-00219 | duplicado: unido | «Un survol de drone non autorisé du site bergeracois de la société Eurenco a eu lieu, lundi 10 novembre» |
| EODI-2025-00259 | Drones penetran el espacio aéreo de Rumania durante ataque masivo | unido en EODI-2025-00263 | duplicado: unido | «Mai multe fragmente au căzut în centrul comunei Puiești, în curtea unui localnic» |
| EODI-2025-00290 | Dron entra en el espacio aéreo de Rumania y provoca el despegue de cazas de la OTAN | unido en EODI-2025-00316 | duplicado: unido | «radar prvi put primijetio signal drona kada je već prešao osam kilometara u rumunjskom zračnom prostoru blizu sela Periprava i Chilia Veche u županiji Tulcea» |
| EODI-2025-00334 | Drones cierran el aeropuerto de Berlín-Brandenburg durante dos horas | unido en EODI-2025-00221 | duplicado: unido | «Het vliegverkeer boven de luchthaven van Berlijn-Brandenburg is bijna 2 uur lang stilgelegd, door de aanwezigheid van een drone.» |
| EODI-2025-00346 | Posibles drones penetran en el espacio aéreo de la base aérea de Ramstein | sin cambio | cita sin guardar | «Ende November, Anfang Dezember sind offenbar Aufklärungsdrohnen in das Sperrgebiet der US Air Base Ramstein eingedrungen» |
| EODI-2025-00363 | Dron misterioso encontrado en la playa de Burgas | sin cambio | cita sin guardar | «A drone was discovered washed up on Burgas’ North Beach, in the Solnitske area, earlier on September 12.» |
| EODI-2025-00395 | Dron detonado cerca del Puerto de Constanza | sin cambio | cita sin guardar | «O dronă ucraineană, ajunsă în derivă în zona portului Constanța, a fost neutralizată în larg, de scafandrii militari.» |
| EODI-2025-00399 | Un dron obliga a paralizar el Aeropuerto de Lanzarote | sin cambio | cita sin guardar | «La presencia de un dron en la cabecera de la pista 03 del Aeropuerto César Manrique-Lanzarote causó la paralización de todas las operaciones» |
| EODI-2025-00401 | Un posible dron provoca el desvío de tres vuelos en el aeropuerto de Gran Canaria | sin cambio | cita sin guardar | «El avistamiento de un dron en las inmediaciones del aeropuerto de Gran Canaria provocó la madrugada de este miércoles el desvío de tres vuelos» |
| EODI-2026-00001 | Dron no autorizado detectado cerca del aeropuerto de Split | sin cambio | cita sin guardar | «osumnjičenog za nedopušteno upravljanje dronom u zabranjenim zonama na području Trogira i Kaštel Štafilića, uključujući područje u blizini Zračne luke Split» |
| EODI-2026-00011 | Dron incautado en la base aérea de Gilze-Rijen | La policía incauta un dron que volaba en la zona de control de la base aérea de Gilze-Rijen | titular sin respaldo | «Het gebied waarbinnen de drone vloog, valt binnen de gecontroleerde luchtverkeerszone rondom de vliegbasis Gilze-Rijen.» |
| EODI-2026-00013 | Dron en zona prohibida afecta al tráfico aéreo en el aeropuerto de Stavanger | sin cambio | cita sin guardar | «Like over klokken 14 melder politiet at de er ved Stavanger lufthavn, Sola.» |
| EODI-2026-00032 | Dron detectado en zona prohibida del aeropuerto de Vilna | sin cambio | cita sin guardar | «Viešojo saugumo tarnyba (VST) sulaikė prie Tarptautinio Vilniaus oro uosto droną skraidinusį asmenį.» |
| EODI-2026-00045 | Dron en la zona de vuelo prohibido del aeropuerto de Memmingen interrumpe operaciones | sin cambio | cita sin guardar | «Aufregung am Flughafen Memmingen: Urplötzlich taucht eine Drohne in der Flugverbotszone auf, der Flugbetrieb wird direkt eingestellt, die Polizei macht sich an die Arbeit.» |
| EODI-2026-00047 | Turista vuela un posible dron cerca del aeropuerto de Svolvær durante el despegue de un avión | Turista vuela un posible dron junto al aeropuerto de Svolvær antes del despegue de un avión | titular sin respaldo | «Medan Widerøe-piloten gjorde seg klar til å ta av frå Svolvær lufthamn, sende ein eldre turist opp ei drone rett ved rullebana.» |
| EODI-2026-00056 | Drone agricola bloquea el aeropuerto de Cuneo-Levaldigi | sin cambio | duplicado: unido | «Un quadricottero da 32 chilogrammi nello spazio aereo vicino allo scalo di Cuneo-Levaldigi, ha costretto alla sospensione dei voli.» |
| EODI-2026-00066 | Drones sobre el aeropuerto de Shannon durante la visita de Trump | sin cambio | cita sin guardar | «flying drones close to Trump’s Doonbeg golf resort and over Shannon Airport ahead of and during the President’s visit earlier this month.» |
| EODI-2026-00083 | Dron sobre el aeropuerto de Split obliga a cerrar la pista durante diez minutos | Un dron junto a las pistas del aeropuerto de Split obliga a suspender el tráfico aéreo unos diez minutos | titular sin respaldo | «péntek este drónt észleltek a spliti Szent Jeromos repülőtér futópályáinak közelében, ezért a hatóságok azonnal felfüggesztették a légiforgalmat.» |
| EODI-2026-00149 | Dron causa retraso en vuelo a Melilla sin cruzar la frontera | unido en EODI-2026-00146 | duplicado: unido | «Een Marokkaanse drone die aan de Marokkaanse kant van de grens bleef, heeft toch invloed gehad op een commerciële vlucht naar Melilla.» |
| EODI-2026-00154 | Posible dron detectado cerca de la frontera de Rumania en Suceava | unido en EODI-2026-00184 | duplicado: unido | «autoritățile au emis două alerte Ro-Alert în județele Botoșani și Suceava, după detectarea unei drone în apropierea frontierei cu România» |
| EODI-2026-00161 | Ataque con dron contra la base de Dhekelia | unido en EODI-2026-00162 | duplicado: unido | «the Cyprus News Agency reported that rumours circulating on social media about an alleged explosion in the Dhekelia area could not be verified.» |
| EODI-2026-00166 | Dron no autorizado vuela sobre el aeropuerto de Budapest | Dron volado sin autorización junto al aeropuerto de Budapest | titular sin respaldo | «Az eset Vecsésen történt, ahol egy férfi egy gyártelep épületéről reptette szabálytalanul drónját.» |
| EODI-2026-00174 | Dron derribado en el espacio aéreo de Letonia | unido en EODI-2026-00140 | duplicado: unido | «Fighter jets shot down a drone that entered Latvian airspace, the country’s military said Friday.» |
| EODI-2026-00176 | Dron no autorizado causa riesgo de colisión con avión en Londres | Dron no autorizado causa riesgo de colisión con un avión que se aproximaba a Heathrow sobre Marlow | titular sin respaldo | «an Airbus A321 passenger jet experienced a definite risk of collision when an unauthorised drone flew dangerously close during its approach over Marlow.» |
| EODI-2026-00189 | Dron derribado sobre base aérea en Rumania | unido en EODI-2026-00232 | duplicado: unido | «Un posibil punct de impact al resturilor dronei a fost identificat între localitățile Băleni și Cudalbi, județul Galați, într-o zonă nepopulată.» |
| EODI-2026-00216 | Drones atacan un depósito petroliero en Letonia | unido en EODI-2026-00302 | duplicado: unido | «Ministrul Apărării din Letonia a demisionat după ce două drone ucrainene au intrat dinspre Rusia și au lovit instalații petroliere.» |
| EODI-2026-00242 | Un dron entra en el espacio aéreo de Rumania y se estrella en el mar | unido en EODI-2026-00230 | duplicado: unido | «Od pet praćenih dronova, jedan je nakratko ušao u rumunski zračni prostor.» |
| EODI-2026-00246 | Posibles drones caídos en Letonia provocan la dimisión del gobierno de Riga | unido en EODI-2026-00302 | duplicado: unido | «Ministrul Apărării din Letonia a demisionat după ce două drone ucrainene au intrat dinspre Rusia și au lovit instalații petroliere.» |
| EODI-2026-00253 | Dos drones militares impactan contra una base de combustible en Rēzekne, Letonia | unido en EODI-2026-00302 | duplicado: unido | «Ministrul Apărării din Letonia a demisionat după ce două drone ucrainene au intrat dinspre Rusia și au lovit instalații petroliere.» |
| EODI-2026-00258 | Dron no autorizado en el espacio aéreo de Moldavia | unido en EODI-2026-00262 | duplicado: unido | «O nouă dronă a pătruns în spațiul aerian al R. Moldova, miercuri seara.» |
| EODI-2026-00264 | Tres drones violan el espacio aéreo de Moldavia | unido en EODI-2026-00263 | duplicado: unido | «MAE convoacă ambasadorul rus după ce trei drone au încălcat spațiul aerian al R. Moldova» |
| EODI-2026-00280 | Posibles drones sobre el aeropuerto de Luxemburgo obligan a cerrar el espacio aéreo | unido en EODI-2026-00127 | duplicado: unido | «Unbekannte Drohnen sorgen für Chaos am Flughafen Luxemburg.» |
| EODI-2026-00303 | Cierre temporal del aeropuerto de Múnich por avistamiento sospechoso | sin cambio | cita sin guardar | «Nach einer „verdächtigen Wahrnehmung“ sind die beiden Start- und Landebahnen des Münchener Flughafens kurzzeitig gesperrt worden» |
| EODI-2026-00320 | Dron se estrella en una central eléctrica de Estonia | unido en EODI-2026-00108 | duplicado: unido | «Un drone ukrainien visant des cibles en Russie a heurté la cheminée d’une centrale électrique en Estonie mercredi 23 mars» |
| EODI-2026-00346 | Dron detectado en el aeropuerto de Rzeszów causa desviación de vuelos | unido en EODI-2026-00134 | duplicado: unido | «Der Flugbetrieb wurde daraufhin sofort eingestellt, wie die Polizei Leipzig gegenüber BILD mitteilte.» |
| EODI-2026-00356 | Drones violan el espacio aéreo griego sobre el Egeo | sin cambio | cita sin guardar | «Έξι παραβιάσεις του ελληνικού εθνικού εναέριου χώρου και επτά παραβάσεις των κανόνων εναέριας κυκλοφορίας στο FIR Αθηνών καταγράφηκαν σήμερα στο Αιγαίο» |
| EODI-2026-00367 | Dos drones cierran temporalmente el aeropuerto de Vasil Levski en Sofía | unido en EODI-2026-00064 | duplicado: unido | «Два сигнала за летящи дронове доведоха до временно затваряне на летище „Васил Левски" - София, като два полета бяха отклонени към други градове.» |
| EODI-2026-00368 | Drone derribado sobre la cárcel de Poggioreale en Nápoles | Dron derribado sobre la cárcel de Poggioreale en Nápoles | cita sin guardar | «neutralizzato dai sistemi di difesa della Polizia Penitenziaria nel carcere di Napoli Poggioreale.» |
| EODI-2026-00379 | Dos drones explotan en Moldavia | unido en EODI-2026-00372 | duplicado: unido | «Cele cinci aparate de zbor care au survolat și explodat în R. Moldova sunt trei rachete și două drone» |
| EODI-2026-00381 | Múltiples drones de origen desconocido sobrevuelan el espacio aéreo de Moldavia | unido en EODI-2026-00372 | duplicado: unido | «Cele cinci aparate de zbor care au survolat și explodat în R. Moldova sunt trei rachete și două drone» |
| EODI-2026-00389 | Dron cruza el espacio aéreo de Lituania desde Bielorrusia y obliga a cerrar el espacio aéreo | unido en EODI-2026-00384 | duplicado: unido | «NATO fighter jets were scrambled over Lithuania after a drone crossed into the country’s airspace from Belarus» |
| EODI-2026-00427 | Drones y cohetes violan el espacio aéreo de Moldavia y explotan en el sur | unido en EODI-2026-00372 | duplicado: unido | «Cele cinci aparate de zbor care au survolat și explodat în R. Moldova sunt trei rachete și două drone» |
| EODI-2026-00428 | Drones sobre el aeropuerto de Berlín causan múltiples interrupciones | unido en EODI-2026-00116 | duplicado: unido | «Tylko w pierwszej połowie 2026 r. niemiecka kontrola ruchu lotniczego zarejestrowała na BER 28 przypadków zauważenia dronów.» |
| EODI-2026-00484 | Drones violan el espacio aéreo griego sobre el Egeo | sin cambio | cita sin guardar | «Οι παραβάσεις και παραβιάσεις σημειώθηκαν στο Βορειοανατολικό και Κεντρικό Αιγαίο.» |

### Pruebas añadidas

- `tests/test_cita_titular.py`: ningún incidente publicado sin respaldo (sobre `publicacion/`);
  otra escritura y otro nombre casan (Sofía, Schiphol, Vilna, el Egeo); una cita de otro lugar no
  respalda (Geilenkirchen frente a Brønnøysund); un titular sin respaldo no se publica.
- `tests/test_revision_contenido.py`: cita, titular, presencia, estado y lugar de Arna con su
  historial; la palabra de una autoridad confirma con las reglas de siempre; la retirada con su
  motivo en los dos idiomas; el lugar que da la autoridad (punto, radio, fuente y demás lugares) y
  un punto fuera del país que no se pone; nada se repite en la pasada siguiente; la configuración
  revisada (frases de 25 palabras como mucho, motivos en los dos idiomas).

## Bloque 2. Impactos en Odesa

### Por qué Odesa casi no aparecía

Revisado punto por punto con los 463 mensajes de Odesa guardados en el servidor y con el
analizador en local:

| Posible causa | Qué pasa |
| --- | --- |
| ¿Se recoge la fuente de Odesa? | **En parte, y la equivocada.** Se leía `t.me/odesaoda`, el canal que enlaza la web de la administración (788 suscriptores). Nació en junio de 2025: de enero a junio de 2025 no había nada. El canal operativo del jefe de la administración, `t.me/odeskaODA` («Олег Кіпер/Одеська ОДА (ОВА)», 38.500 suscriptores, con publicaciones desde 2022), no se leía: la web oficial no lo enlaza y por eso no pasó la comprobación de canal oficial |
| ¿El ayuntamiento? | No se leía. La web de la ciudad (omr.gov.ua) enlaza `t.me/odesacityofficial`, cuya descripción enlaza el canal oficial del jefe de la administración militar de la ciudad, `t.me/odesaMVA` |
| ¿El Mando Sur? | Las Fuerzas de Defensa del Sur publican en Facebook; no tienen un canal de Telegram oficial que se pueda comprobar |
| ¿El extractor no reconoce su forma de escribir? | **Sobre todo, no hay lugar que reconocer.** De los 463 mensajes, 280 no nombran ningún lugar más concreto que «el sur de Odesa», «la región» o un distrito («Одеському районі», «Ізмаїльського району», «Білгород-Дністровському районі»). Los distritos de 2020 de Odesa miden de 50 a más de 100 km de radio y, con el criterio de todas las regiones, no son un lugar concreto. Muchos son además reenvíos de los mensajes del presidente sobre otras regiones |
| ¿Topónimos que faltan o van a otra región? | No. Odesa, Izmaíl, Reni, Kilia, Chornomorsk, Yuzhne (Pivdenne), Bilhorod-Dnistrovskyi, Vylkove, Artsyz, Zatoka, Ovidiopol, Podilsk, Bolhrad y Tatarbunary se resuelven todos en Odesa (UA-51) |
| ¿Se pierden al deduplicar? | No. Los 83 mensajes con lugar dan 84 impactos y se publicaban 74: la diferencia son los mismos lugares de la misma noche, que se juntan |

**Causa y arreglo.** La causa principal es la fuente: el canal que se leía es secundario y
empezó en junio de 2025. Se añade el canal del jefe de la administración, cuya condición de
oficial la da la lista del Gobierno de Ucrania
([kmu.gov.ua](https://www.kmu.gov.ua/news/shchob-uniknuti-fejkiv-koristuyemos-oficijnimi-dzherelami):
«в кожній області створено офіційний телеграм-канал голови облдержадміністрації», con
`t.me/odeskaODA` para Odesa), y el de la administración militar de la ciudad (por la cadena web
de la ciudad → `odesacityofficial` → `odesaMVA`, que el lector comprueba en cada lectura, como la
de Kursk). Los dos son de la misma institución que lo que ya se leía o de la ciudad, con
fiabilidad B, como los demás. El lector baja su histórico desde el 1 de enero de 2025 en el
temporizador del minuto 50, y la recogida horaria lo lee con el mismo analizador y el mismo
criterio que el resto de regiones: no hace falta ningún reproceso aparte.

Lo que no cambia, porque es el criterio de todas las regiones: un distrito de más de 50 km no es
un lugar, y «el sur de la región» tampoco. La administración de Odesa casi nunca nombra el lugar
alcanzado: con las dos fuentes nuevas, Odesa seguirá teniendo muchos menos impactos que su número
real de ataques.

### Lo mismo en las demás regiones

Cuatro formas de escribir que el analizador no leía, en todas las regiones (versión
`mensajes-guerra/5`, que la relectura de la recogida horaria aplica sola a todo lo guardado):

- «прильоти», «приліт» (la forma ucraniana de «прилёт»): no se leía como un impacto;
- «тергромада», «територіальна громада» (Черкащина, Вінниччина, Львівщина): no se leía como una
  comunidad;
- «в обласному центрі», «на обласний центр»: ahora es la capital de la región del canal (salvo
  Donetsk, Luhansk y Kiev región);
- colectas y balances de la semana o del mes («Тижневий дайджест», «за минулий тиждень
  атакувала 32 населені пункти», «весільний донат»): ya no dan impactos (pendiente del informe de
  errores de datos, bloque 6).

Región por región (mensajes guardados en el servidor, leídos en local con el analizador de antes y
el de ahora; las tres últimas columnas, lo publicado):

En el analizador, con todos los mensajes guardados (antes y después del cambio de versión):
la comunidad escrita «тергромада» y el «обласний центр» suben Cherkasy de 10 a 28 impactos y
Jmelnytskyi de 2 a 8; «прильоти» y la capital, Volinia; Járkov gana 48 y Sumy 9. Los canales nuevos
dan, con el histórico leído hasta hoy, 9 impactos del de Odesa en una muestra de tres meses, y 3,
6 y 0 en Volinia, Zhytómyr y Ternópil (sus administraciones publican sobre todo alertas y
reenvíos).

Impactos rusos publicados por región (`publicacion/ucrania.json`, sentido Rusia → Ucrania): antes,
la publicación de las 15:17 del 5 de octubre, antes de la fusión; después, la de la recogida de
las 17:17 del mismo día. «Dibujados»: sin los partes diarios de primera línea, que se publican pero
no se pintan.

| Región | Antes | Después | Dibujados antes | Dibujados después |
| --- | ---: | ---: | ---: | ---: |
| Zaporiyia (UA-23) | 6089 | 6094 | 313 | 318 |
| Sumy (UA-59) | 2706 | 2707 | 462 | 463 |
| Járkov (UA-63) | 1267 | 1267 | 300 | 300 |
| Jersón (UA-65) | 1204 | 1204 | 1202 | 1202 |
| Dnipropetrovsk (UA-12) | 613 | 615 | 588 | 590 |
| Chernígov (UA-74) | 589 | 589 | 310 | 310 |
| Mykoláiv (UA-48) | 155 | 155 | 141 | 141 |
| Kiev ciudad (UA-30) | 127 | 127 | 127 | 127 |
| Odesa (UA-51) | 74 | 103 | 74 | 103 |
| Luhansk (UA-09) | 89 | 89 | 38 | 38 |
| Donetsk (UA-14) | 72 | 73 | 58 | 59 |
| Kirovohrad (UA-35) | 36 | 36 | 36 | 36 |
| Kiev región (UA-32) | 29 | 28 | 29 | 28 |
| Poltava (UA-53) | 26 | 26 | 26 | 26 |
| Leópolis (UA-46) | 24 | 24 | 24 | 24 |
| Cherkasy (UA-71) | 11 | 11 | 11 | 11 |
| Ivano-Frankivsk (UA-26) | 7 | 7 | 1 | 1 |
| Volinia (UA-07) | 0 | 6 | 0 | 6 |
| Vínnytsia (UA-05) | 4 | 4 | 3 | 3 |
| Zhytómyr (UA-18) | 0 | 4 | 0 | 4 |
| Jmelnytskyi (UA-68) | 2 | 2 | 2 | 2 |
| Chernivtsí (UA-77) | 2 | 2 | 2 | 2 |
| Rivne (UA-56) | 0 | 0 | 0 | 0 |
| Ternópil (UA-61) | 0 | 0 | 0 | 0 |
| Zakarpatia (UA-21) | 0 | 0 | 0 | 0 |
| **Total** | **13126** | **13173** | | |

**Lo que sigue entrando.** Estas cifras son las de la recogida de las 17:17, a mitad de camino:

- **Bajada del histórico** (lector del minuto 50, `servidor/guerra.sh`). Terminada para el canal
  del jefe de la administración de Odesa (`odeskaODA`, 328 páginas, 664 publicaciones con drones
  desde enero de 2025) y para Volinia (198 páginas, 42). A medias Zhytómyr (266 páginas, va por
  junio de 2025). Sin empezar la administración militar de la ciudad de Odesa (`odesaMVA`) y
  Ternópil, que van detrás en el orden del lector: entran en las lecturas de las 17:50 y las
  18:50.
- **Lectura en la recogida horaria.** Cada recogida dedica como mucho 150 s a lo antiguo, canal por
  canal en el orden de `configuracion/canales_guerra.json`: primero la relectura de los unos 40.600
  mensajes ya guardados con la versión nueva del analizador (`mensajes-guerra/5`), a unos 4.500–5.300
  por recogida, y después el histórico de los canales nuevos, que van al final de la lista. La
  recogida de las 17:17 ya leyó parte de Odesa (de 74 a 103 impactos).
- **Estimación**: el histórico bajado, hacia las 19:30 UTC del 5 de octubre; todo leído y
  publicado, entre las 00:30 y las 02:30 UTC del 6 de octubre (unas 7 a 9 recogidas más).

**Cómo se comprueba que ha entrado todo:**

1. *Bajado*: en el servidor, `/home/eodi/datos/guerra/control.json`, para `ova_odesa_jefe`,
   `mva_odesa`, `ova_volyn`, `ova_zhytomyr` y `ova_ternopil`, `historico.terminado` tiene que ser
   `true` (o `sudo -u eodi .venv/bin/python -m recogida.canales_guerra resumen` en el clon).
2. *Leído*: en el diario de la recogida (`journalctl -u eodi-recogida`), la línea
   `guerra: mensajes=… pendientes=False`. Mientras diga `pendientes=True`, queda relectura o
   histórico por leer.
3. *Publicado*: en `publicacion/ucrania.json`, los impactos con `"region": "UA-51"` y `"sentido":
   "RU_UA"`. Cuando la línea anterior diga `pendientes=False`, esa cifra deja de crecer salvo por
   los ataques nuevos (el script de este informe, `data/regiones_despues.py` en el clon de trabajo,
   da la tabla entera).

**¿Es creíble el número de cada región?** Mirado con los mensajes guardados de cada canal:

| Región | ¿Creíble? | Por qué |
| --- | --- | --- |
| Kiev ciudad | Sí, como cota baja | La administración de la ciudad nombra el distrito urbano o la ciudad; da lugar en 194 de sus 1.549 mensajes con drones |
| Kiev región | Bajo, por la forma de escribir | Su canal publica sobre todo alertas (1.230 de 3.174) y, al dar daños, el distrito («Бучанському районі»), que no es un lugar con el criterio de todas las regiones. Misma situación que Odesa en lo que no es de la fuente: anotado en pendientes («Distritos») |
| Poltava | Bajo, por la misma causa | Escribe el distrito («Кременчуцький район», «Миргородському районі») |
| Kirovohrad | Sí, como cota baja | Nombra comunidades y pocas localidades |
| Cherkasy | Era bajo por la forma de escribir: arreglado | «Бобрицькій тергромаді»: de 10 a 28 en el analizador |
| Vínnytsia | Bajo, por la fuente | Publica resúmenes semanales y alertas; casi nunca el lugar |
| Jmelnytskyi | Era bajo por la forma de escribir: arreglado en parte | De 2 a 8 |
| Zhytómyr, Volinia, Ternópil | Eran cero porque no se leía ningún canal (la misma causa que Odesa): arreglado | Se leen los canales oficiales de sus jefes de administración; sus históricos están entrando |
| Rivne | Sí (cero o casi) | Su canal da alertas y reenvíos del presidente; ningún mensaje nombra un lugar alcanzado |
| Leópolis | Sí | Pocos ataques con dron con lugar; los demás mensajes son colectas y homenajes |
| Ivano-Frankivsk, Chernivtsí | Sí | Pocos ataques; los que hay, sin lugar más concreto que la región |
| Donetsk (bajo control ucraniano) | Bajo, por la fuente | La administración publica memoria de caídos y partes sin arma; los ataques con FPV de primera línea no salen en su canal con lugar |

### Los puertos del Danubio

Los impactos de guerra nunca crean incidentes europeos: un incidente de Rumanía o de Moldavia se
enlaza con el ataque ruso de su noche (`proceso/cruces.py`) y el ataque lista sus impactos, así
que un impacto en Izmaíl y un incidente rumano de la misma noche quedan unidos por el ataque, sin
copias. Comprobado sobre la base de ensayo: ningún incidente europeo tiene solo fuentes de
guerra. Hoy solo hay dos impactos en los puertos del Danubio (Izmaíl), y ninguno coincide con un
incidente rumano enlazado: la administración de Odesa los nombra como «Ізмаїльський район», que es
un distrito de más de 50 km.

### Diez impactos de Odesa al azar

De los publicados a las 17:17 (semilla fija), con su fuente para comprobarlos a mano:

| Impacto | Lugar | Fecha (UTC) | Fuente | Frase |
| --- | --- | --- | --- | --- |
| EODI-IG-2025-03595 | Одеса | 2025-12-22 20:50 | [Одеська ОВА](https://t.me/odeskaODA/13099) | «❗️Сьогодні ввечері ворог знову атакував Одесу ударними БпЛА.» |
| EODI-IG-2025-03604 | Чорноморськ | 2025-08-31 04:39 | [Одеська ОВА](https://t.me/odeskaODA/11104) | «Найбільше постраждало місто Чорноморськ та його околиці.» |
| EODI-IG-2025-03605 | Ізмаїл | 2025-08-20 05:00 | [Одеська ОВА](https://t.me/odeskaODA/10957) | «В Ізмаїлі пошкоджено об'єкти інфраструктури та виробничі приміщення.» |
| EODI-IG-2025-03612 | Одеса | 2025-07-07 05:03 | [Одеська ОВА](https://t.me/odeskaODA/10410) | «Вночі росіяни атакували Одесу ударними безпілотниками.» |
| EODI-IG-2025-06767 | Одеса | 2025-04-21 21:40 | [Одеська ОВА](https://t.me/odeskaODA/9417) | «Ворог масовано атакував Одесу ударними безпілотниками.» |
| EODI-IG-2025-06769 | Одеса | 2025-04-13 20:01 | [Одеська ОВА](https://t.me/odeskaODA/9279) | «Ворог атакував Одесу ударними безпілотниками» |
| EODI-IG-2025-06783 | Одеса | 2025-01-28 06:51 | [Одеська ОВА](https://t.me/odeskaODA/8376) | «В одному із житлових дворів Одеси загорілися 10 легкових автомобілів, вогнеборці оперативно ліквідували пожежу.» |
| EODI-IG-2026-04435 | Одеса | 2026-05-20 04:24 | [Одеська ОВА](https://t.me/odeskaODA/16205) | «В Одесі безпілотник влучив в одноповерховий житловий будинок, повністю зруйнувавши його.» |
| EODI-IG-2026-04438 | Одеса | 2026-05-01 04:23 | [Одеська ОВА](https://t.me/odesaoda/8089) | «В Одесі ударними дронами пошкоджено два багатоповерхових житлових будинки.» |
| EODI-IG-2026-04439 | Одеса | 2026-04-30 12:14 | [Одеська ОВА](https://t.me/odeskaODA/15778) | «В Одесі були влучання по житлових будинках.» |

## Bloque 3. Polonia sin punto en el mapa

### EODI-2025-00295

Lugares que nombran las autoridades polacas esa noche, cada uno con su frase literal comprobada
en gov.pl:

- **Fiscalía Regional de Lublin** (10 de septiembre de 2025): Czosnówka, Cześniki, Krzywowierzba
  Kolonia, Wyhalew, Wohyń, Wielki Łan, Kolonia Zabłocie.
- **Fiscalía Provincial de Lublin** (11 de septiembre de 2025): Cześniki, Wyhalew, Bychawka
  Trzecia; y, en el archivo de la investigación de Wyryki-Wola (10 de septiembre de 2026), la casa
  alcanzada: «wystrzelona przez pilota myśliwca F-35 – w sposób niezamierzony uderzyła w dach
  budynku mieszkalnego w miejscowości Wyryki Wola».
- **Fiscalía Provincial de Cracovia** (11 de septiembre de 2025): Raków, Czyżów, Sobótka.
- **Ministerio del Interior** (comunicado del 10 de septiembre de 2025, publicado en gov.pl):
  Mniszków, Oleśno, Nowe Miasto nad Pilicą, Smyków y entre Radiany y Sewerynów.

**El punto principal es Wyryki-Wola**, el daño más relevante que nombra la autoridad esa noche:
una casa cuyo tejado destruyó, según la fiscalía, un misil de un caza polaco durante la operación
contra los drones. La ficha lo dice con la frase literal de la fiscalía («Lugar según»), de modo
que nadie lea que la casa la alcanzó un dron. Los otros 16 lugares van en «Otros lugares». Nivel
localidad, radio 2 km, geocodificación oficial, fuente: la nota de la fiscalía de Lublin.

Además, los cuatro registros sueltos del mismo suceso (EODI-2025-00270, 00311, 00313 y 00318:
«Drones derribados sobre el espacio aéreo de Polonia» y parecidos, todos del 10 de septiembre) se
unen en EODI-2025-00295, que queda atribuido a Rusia con su punto.

### Los demás incidentes sin ubicación

Había 179 incidentes publicados sin punto; 92 confirmados o atribuidos. Para cada uno se buscó la
nota oficial del suceso y se dio punto solo si la frase de una autoridad nombra el lugar (no el
periodista), con sus coordenadas de una referencia y un radio según el tipo de lugar.

| | Incidentes |
| --- | ---: |
| Confirmados o atribuidos sin punto antes | 92 |
| Con punto ahora, con la frase de la autoridad que nombra el lugar | 37 |
| Unidos a otro registro del mismo suceso (17 de ellos a uno que ya tiene punto) | 18 |
| Siguen sin punto | 37 |

Duplicados encontrados al buscar el lugar, y unidos (misma noche, mismo lugar, misma nota
oficial): Polonia del 10 de septiembre de 2025 (cinco registros), Moldavia del 3 de octubre de
2026 (cinco), Lituania del 15 de septiembre de 2026 (tres), Pardina del 13 de septiembre de 2025
(tres), Kardam (dos), Galați del 16 de agosto de 2026 (dos), Mihăileni del 8 de septiembre de 2026
(dos), Moldavia del 14 de marzo de 2026 (dos) y del 28 de noviembre de 2025 (dos).

Cada punto lleva en la ficha la fuente que lo da («Lugar según»: la autoridad, su frase, su fecha
y su enlace) y su precisión (nivel y radio); en los datos, `lugar.fuente_punto`,
`lugar.geocodificacion: oficial` y, si la autoridad nombra más, `lugar.otros_lugares`. Un punto
que no cae dentro del país del incidente no se pone (EODI-2026-00075: los ministerios sitúan la
caída en Moldavia y el incidente es de Rumanía; queda pendiente).

Lugares puestos (algunos registros de la tabla se unieron después a otro del mismo suceso, que se queda con el punto):

| Incidente | Lugar | Precisión | Autoridad | Frase |
| --- | --- | --- | --- | --- |
| EODI-2025-00295 | Wyryki-Wola | localidad, 2 km | Prokuratura Okręgowa w Lublinie | «wystrzelona przez pilota myśliwca F-35 – w sposób niezamierzony uderzyła w dach budynku mieszkalnego w miejscowości Wyryki Wola.» ([enlace](https://www.gov.pl/web/po-lublin/umorzenie-sledztwa-w-sprawie-uderzenia-rakiety-wojskowej-w-budynek-w-wyrykach-woli)) |
| EODI-2025-00020 | Base aérea de Kleine-Brogel | instalacion, 2 km | Theo Francken, ministro de Defensa de Bélgica | «Meerdere drones boven Kleine Brogel waargenomen. Detectiesysteem werkt.» ([enlace](https://x.com/FranckenTheo/status/1984615247651446844)) |
| EODI-2025-00059 | Aeropuerto de Sandefjord-Torp | instalacion, 3 km | Sørøst politidistrikt | «Vi rykket ut etter at vi ble varslet om denne personen. Han hadde stått ved Gjennestad gartnerskole på nordsiden av Torp» ([enlace](https://www.nrk.no/vestfoldogtelemark/floy-drone-i-forbudssonen-til-sandefjord-lufthavn-torp-1.17608598)) |
| EODI-2025-00109 | Aeropuerto de Fráncfort del Meno | instalacion, 3 km | Polizeipräsidium Frankfurt am Main | «Am gestrigen Freitagmorgen (03. Oktober 2025) kam es am Frankfurter Flughafen auf Grund eines kurzzeitigen Drohnenflugs zu einem Polizeieinsatz» ([enlace](https://www.presseportal.de/blaulicht/pm/4970/6130964)) |
| EODI-2025-00204 | Săiți (raionul Căușeni) | localidad, 5 km | Ministerul Apărării al Republicii Moldova | (la frase literal está en `configuracion/incidentes_revisados.json`) ([enlace](https://www.puterea.ro/?p=536506)) |
| EODI-2025-00255 | Base aérea de Kleine-Brogel | instalacion, 2 km | Theo Francken, ministro de Defensa de Bélgica | «Geen gewone overvlucht maar duidelijke opdracht met Kleine Brogel als onderwerp.» ([enlace](https://x.com/FranckenTheo/status/1984884386089652583)) |
| EODI-2025-00259 | Puiești (distrito de Vaslui) | localidad, 3 km | Alcalde de Puiești, Vasile Cezar Ticu | «Mai multe fragmente au căzut în centrul comunei Puiești, în curtea unui localnic» ([enlace](https://romania.europalibera.org/a/33603982.html)) |
| EODI-2025-00263 | Puiești (distrito de Vaslui) | localidad, 3 km | Alcalde de Puiești, Vasile Cezar Ticu | «Mai multe fragmente au căzut în centrul comunei Puiești, în curtea unui localnic» ([enlace](https://romania.europalibera.org/a/33603982.html)) |
| EODI-2025-00269 | Osiny (powiat łukowski) | localidad, 3 km | Prokuratura Okręgowa w Lublinie | «zakończyli oględziny oraz zabezpieczanie dowodów i śladów na miejscu eksplozji dronu w miejscowości Osiny pow. łukowskim» ([enlace](https://www.gov.pl/web/po-lublin/komunikat-rzecznika-prasowego-z-dn-22082025---zakonczenie-czynnosci-na-miejscu-eksplozji-dronu-w-miejscowosci-osiny-pow-lukowski)) |
| EODI-2025-00290 | Chilia Veche (distrito de Tulcea) | localidad, 5 km | Ministerul Apărării Naționale | «a pătruns aproximativ 8 km în spațiul aerian național, dinspre Vâlcov către Periprava și Chilia Veche, unde a dispărut de pe radar.» ([enlace](https://www.mapn.ro/cpresa/19065_x)) |
| EODI-2025-00303 | Cuhureștii de Jos (raionul Florești) | localidad, 3 km | Inspectoratul General al Poliției | «Acum câteva minute, într-o livadǎ din localitatea Cuhureştii de Jos, raionul Florești, pe casa paznicului a căzut o dronă.» ([enlace](https://adevarul.ro/stiri-externe/republica-moldova/autoritatile-din-republica-moldova-anunta-ca-o-2489552.html)) |
| EODI-2025-00306 | Pardina (distrito de Tulcea) | localidad, 5 km | Ministerul Apărării Naționale | «de la NE de Chilia Veche spre SV de Izmail, și a părăsit spațiul aerian național în dreptul localității Pardina» ([enlace](https://www.mapn.ro/cpresa/18970_x)) |
| EODI-2025-00307 | Base aérea de Skrydstrup | instalacion, 3 km | Forsvarskommandoen | «Drones have been observed at several military installations, including at Skrydstrup Air Base and the Jutland Dragoon Regiment.» ([enlace](https://www.forsvaret.dk/en/news/2025/dronesoverdenmark/)) |
| EODI-2025-00328 | Vărăncău (Stînga Nistrului) | localidad, 5 km | Policía de Fronteras de Moldavia, con datos del Servicio de Operaciones Aéreas del Ministerio de Defensa | (la frase literal está en `configuracion/incidentes_revisados.json`) ([enlace](https://www.protv.md/actualitate/spatiul-aerian-al-republicii-moldova-redeschis-complet-dupa-ce-doua-drone-au-survolat-teritoriul-tarii-noastre-politia-de-frontiera-vine-cu-detalii---2743793.html)) |
| EODI-2025-00344 | Base aérea de Kleine-Brogel | instalacion, 2 km | Theo Francken, ministro de Defensa de Bélgica | «Afgelopen nacht drie meldingen van drones boven Kleine Brogel, groter type op grotere hoogte.» ([enlace](https://x.com/FranckenTheo/status/1984884386089652583)) |
| EODI-2026-00075 | Mihăileni (Mihăileni Vechi), raionul Rîșcani | localidad, 3 km | Ministerul Apărării Naționale de Rumanía | «autoritățile române au fost informate că drona s-a prăbușit în zona localității Mihăileni Vechi, Republica Moldova» ([enlace](https://www.mapn.ro/cpresa/19394_x)) |
| EODI-2026-00085 | Padina (distrito de Buzău) | localidad, 5 km | Ministerul Apărării Naționale | «resturi din dronă și din racheta interceptoare au fost identificate în zona Padina, județul Buzău» ([enlace](https://www.mapn.ro/cpresa/19321_x)) |
| EODI-2026-00113 | Vasilcău (raionul Soroca) | localidad, 5 km | Ministerul Apărării al Republicii Moldova | «Drona a survolat spațiul aerian în proximitatea satului Vasilcău, raionul Soroca.» ([enlace](https://www.army.md/ro/comunicate-de-presa/informeaza-12)) |
| EODI-2026-00136 | Etulia (UTA Găgăuzia) | localidad, 5 km | Ministerul Apărării al Republicii Moldova | (la frase literal está en `configuracion/incidentes_revisados.json`) ([enlace](https://www.army.md/ro/comunicate-de-presa/informeaza-5)) |
| EODI-2026-00140 | Rugāji (municipio de Balvi) | localidad, 5 km | Fuerzas Armadas Nacionales de Letonia | «In the vicinity of Rugāji, Balvi Municipality, allied fighter jets successfully shot down the unmanned aerial vehicle.» ([enlace](https://www.mod.gov.lv/en/news/drone-shot-down-balvi-municipality-was-ukrainian-unmanned-aerial-vehicle)) |
| EODI-2026-00141 | Palanca (puesto fronterizo, raionul Ștefan Vodă) | localidad, 3 km | Inspectoratul General al Poliției de Frontieră | «a survolat, în noaptea de 18 martie, spațiul aerian al R. Moldova, în zona punctului de trecere a frontierei (PTF) Palanca.» ([enlace](https://zdg.md/stiri/stiri-sociale/o-noua-drona-de-tip-shahed-a-survolat-spatiul-aerian-al-r-moldova-autoritatile-spun-ca-a-fost-distrusa-in-afara-tarii/)) |
| EODI-2026-00148 | Novocotovsc (segmento transnistrio) | localidad, 5 km | Ministerul Apărării al Republicii Moldova | (la frase literal está en `configuracion/incidentes_revisados.json`) ([enlace](https://www.army.md/ro/comunicate-de-presa/informeaza-20)) |
| EODI-2026-00151 | Ceatalchioi (distrito de Tulcea) | localidad, 5 km | Ministerul Apărării Naționale | «ținta aeriană a intrat în spațiul aerian al României prin zona Ceatalchioi si a evoluat de-a lungul graniței» ([enlace](https://www.mapn.ro/cpresa/19417_x)) |
| EODI-2026-00158 | Insula Mare a Brăilei, frente a Gropeni (distrito de Brăila) | localidad, 5 km | Ministerul Apărării Naționale | «căzut pe un teren arabil din Insula Mare a Brăilei, în dreptul localității Gropeni, județul Brăila.» ([enlace](https://www.mapn.ro/cpresa/19419_x)) |
| EODI-2026-00160 | Lunga (raionul Dubăsari) | localidad, 5 km | Ministerul Apărării / Serviciul Operații Aeriene al Armatei Naționale | «survolarea spațiului aerian național, astăzi, 30 septembrie, la ora 10:26, de către un aparat de zbor fără pilot, loc.Lunga, Dubăsari» ([enlace](https://www.army.md/ro/comunicate-de-presa/informeaza-22)) |
| EODI-2026-00179 | Pratkūnai (Kaišiadorių rajonas) | localidad, 3 km | NKVC | «Bepilotis numuštas ties Pratkūnų kaimu.» ([enlace](https://kauno.diena.lt/naujienos/kaunas/miesto-pulsas/nkvc-nato-naikintuvai-sunaikino-drona-kauno-apskrityje-perspejimas-del-oro-pavojaus-atsauktas-1774735)) |
| EODI-2026-00193 | Tudora (raionul Ștefan Vodă) | localidad, 5 km | Ministerul Apărării / Serviciul Operații Aeriene al Armatei Naționale | (la frase literal está en `configuracion/incidentes_revisados.json`) ([enlace](https://www.army.md/ro/comunicate-de-presa/informeaza-14)) |
| EODI-2026-00209 | Kardam (Dobrich), junto al antiguo paso fronterizo GKPP «Kardam» | localidad, 3 km | Primer ministro Rumen Radev | «Това става в непосредствена близост от бившия Граничен контролно-пропускателен пункт (ГКПП) „Кардам“ между България и Румъния» ([enlace](https://www.bta.bg/bg/videos/38827)) |
| EODI-2026-00224 | Mihăileni (raionul Rîșcani), extrarradio | localidad, 5 km | Ministerul Apărării / Serviciul Operații Aeriene al Armatei Naționale | «în extravilanul localității Mihăileni Vechi, ar fi căzut un aparat zburător de mici dimensiuni asemănător unei drone» ([enlace](https://www.army.md/ro/comunicate-de-presa/informeaza-11)) |
| EODI-2026-00232 | Entre Băleni y Cudalbi (județul Galați), punto de impacto de los restos | localidad, 6 km | Ministerul Apărării Naționale | «Un posibil punct de impact al resturilor dronei a fost identificat între localitățile Băleni și Cudalbi, județul Galați, într-o zonă nepopulată.» ([enlace](https://www.mapn.ro/cpresa/19351_Informatie-de-presa_html)) |
| EODI-2026-00258 | Brănești (raionul Orhei) | localidad, 4 km | Ministerul Apărării / Serviciul Operații Aeriene al Armatei Naționale | «Obiectul a dispărut de pe sistemele de monitorizare în zona loc. Brănești, Orhei.» ([enlace](https://www.army.md/ro/comunicate-de-presa/informeaza-23)) |
| EODI-2026-00263 | Hîrbovăț (raionul Anenii Noi), extrarradio | localidad, 4 km | Ministerul Apărării / Serviciul Operații Aeriene al Armatei Naționale | «de către o dronă, care a căzut în extravilanul satului Hîrbovăț, raionul Anenii Noi, unde a explodat» ([enlace](https://www.army.md/ro/comunicate-de-presa/informeaza-21)) |
| EODI-2026-00268 | RAF Akrotiri | instalacion, 3 km | UK Government | «The Ministry of Defence can confirm that a drone targeted RAF Akrotiri on 2 March was not launched from Iran.» ([enlace](https://questions-statements.parliament.uk/written-questions/detail/2026-03-03/117492)) |
| EODI-2026-00276 | Fliegerhorst Wunstorf (Wunstorfer Moor) | instalacion, 2 km | Einsatzführungskommando der Bundeswehr | «Wie ein Sprecher des Operativen Führungskommandos der Bundeswehr bestätigt, lagen die Drohnentrümmer bloß 800 Meter vom Fliegerhorst entfernt.» ([enlace](https://wz-net.de/weltweit/panorama/800-meter-bundeswehr-fliegerhorst-unbekannte-drohne-wunstorf-id308687.html)) |
| EODI-2026-00281 | Tudora (raionul Ștefan Vodă) | localidad, 4 km | Inspectoratul General al Poliției de Frontieră | «Cu referire la depistarea unei drone în satul Tudora, raionul Ștefan Vodă, la aproximativ 2 km de linia de frontieră» ([enlace](https://border.gov.md/informare-45)) |
| EODI-2026-00285 | Mechernich (instalación de la Bundeswehr) | localidad, 5 km | Bundeswehr | «the drones were sighted at around 10 p.m. (2000 GMT) on Thursday at the base in Mechernich in the state of North Rhine-Westphalia» ([enlace](https://www.thestar.com.my/news/world/2026/08/08/drones-spotted-above-german-military-base-two-days-after-suspected-drone-attack)) |
| EODI-2026-00289 | Rugāji (Balvu novads) | localidad, 5 km | Nacionālie bruņotie spēki | «14. augustā Balvu novada Rugāju apkārtnē tika notriekts Ukrainas bezpilota lidaparāts» ([enlace](https://www.mil.lv/lv/zinas/balvu-novada-notriektais-drons-bija-ukrainas-bezpilota-lidaparats)) |
| EODI-2026-00302 | Rēzekne, depósito de petróleo | localidad, 5 km | Nacionālie bruņotie spēki / Aizsardzības ministrija | «Operatīvie dienesti šajā laikā saņēma vairākus ziņojumus par iespējamu ugunsgrēku naftas uzglabāšanas objektā Rēzeknē.» ([enlace](https://www.mil.lv/lv/zinas/latvijas-teritorija-nogazusies-divi-bezpilota-lidaparati-kas-ielidojusi-no-krievijas)) |
| EODI-2026-00325 | Vulcănești (UTA Găgăuzia) | localidad, 5 km | Ministerul Apărării / Serviciul Operații Aeriene al Armatei Naționale | (la frase literal está en `configuracion/incidentes_revisados.json`) ([enlace](https://www.army.md/ro/comunicate-de-presa/informeaza-7)) |
| EODI-2026-00372 | Crocmaz (raionul Ștefan Vodă), extrarradio | localidad, 5 km | Ministerul Apărării / Serviciul Operații Aeriene al Armatei Naționale | «au fost auzite mai multe explozii, în extravilanele satelor Crocmaz, Ștefan Vodă, Delacău, Puhăceni, Anenii Noi, Bozieni, Hîncești» ([enlace](https://www.army.md/ro/comunicate-de-presa/informeaza-24)) |
| EODI-2026-00381 | Crocmaz (raionul Ștefan Vodă), extrarradio | localidad, 5 km | Ministerul Apărării / Serviciul Operații Aeriene al Armatei Naționale | «au fost auzite mai multe explozii, în extravilanele satelor Crocmaz, Ștefan Vodă, Delacău, Puhăceni, Anenii Noi, Bozieni, Hîncești» ([enlace](https://www.army.md/ro/comunicate-de-presa/informeaza-24)) |
| EODI-2026-00410 | Portul Constanța, Dana 78 (junto a la sede de ARSVOM) | instalacion, 2 km | Ministerul Apărării Naționale | «în Portul Civil Constanța, în apropiere de sediul Agenției Române de Salvare a Vieții Omenești pe Mare, s-a autodetonat» ([enlace](https://www.mapn.ro/cpresa/19280_Drona-maritima-din-Portul-Constanta-nu-a-produs-victime_html)) |

Siguen sin punto, y por qué:

- **La frase de la autoridad no nombra el lugar; solo lo hace el periodista** (10): EODI-2025-00094
  (Brønnøysund), 00140 (Arna), 00222 (Carmanova), 00246 (Gaižiūnai), 00248 (Mechelen-Zuid),
  2025-00276 (Horodiște; además, el Ministerio de Defensa de Moldavia negó después el sobrevuelo:
  su estado confirmado queda pendiente de revisar), 00371 (escuela de Malinas), 2026-00050
  (Alexandrúpolis), 2026-00055 (Cracovia-Balice), 2026-00098 (Ucrainca, solo como dirección del
  vuelo).
- **La autoridad da una región, un mar o una zona amplia, no un lugar** (12): 2025-00257 (Delta del
  Danubio, recuento acumulado), 2025-00309 («varias instalaciones» danesas), 2026-00215 y 00236
  (municipios en alerta en Letonia), 00237 (al norte y al este de Kouvola), 00278 (bahía de
  Dublín), 00300 (perímetro Neptun Deep), 00317 y 00349 (Latgale), 00344 («zona Chilia»), 00356
  (el Egeo), 00384 (solo una alerta aérea en Lituania).
- **El punto sería un cálculo, no un lugar nombrado** (2): 2026-00114 y 00329, «16 km al sureste de
  Chilia Veche».
- **En alta mar, sin coordenadas de referencia de la plataforma** (1): 2026-00170 (Neptun Alpha).
- **No son sucesos con lugar** (3): 2026-00235 (declaración general sobre incursiones frecuentes),
  00260 (entrevista sobre drones que entran en Letonia), 00272 (informe anual danés). Quedan como
  pendiente de revisar si deben seguir publicados como incidentes.
- **Constanza** (7): 2026-00207, 00395, 00397, 00401, 00403, 00405 y 00408 llevan fechas de junio a
  agosto; la nota oficial con lugar (Dana 78) es la del 5 de junio, que ya tiene punto en
  EODI-2026-00410. No se ha comprobado si son la misma explosión contada más tarde o explosiones
  distintas: no se les pone ese punto.
- **La frase ya no se puede comprobar** (1): 2025-00372 (aeropuerto de Aalborg): la publicación de X
  de la policía de Jutlandia del Norte ya no es pública.
- **El país no casa** (1): 2026-00075 (arriba).

## Bloque 4. La bandera tarda en aparecer

La bandera no puede ir dentro del paquete de la web: tendría que ir como imagen `data:` o `blob:`,
y la política de seguridad de contenidos de la web no las admite (`img-src 'self'`). Lo que se
hace es lo otro que pedía el encargo: las banderas de los países atribuidos se piden en cuanto
llegan los datos, mientras el mapa termina de cargar, y la capa de atribuidos no recibe sus datos
hasta que sus banderas están en el mapa (`web/src/mapa/iconos.ts`, `trasBanderas`). El marcador
abierto al entrar por el enlace de un atribuido espera igual. Si una bandera fallara, se reintenta
tres veces y, si aun así no llega, ese marcador sale liso desde el principio y ya no cambia: nunca
se ve liso y luego con bandera.

Prueba nueva `web/e2e/bandera-primer-dibujado.spec.ts` (390×844 y escritorio), con la caché
desactivada y la red lenta simulada (150 ms en cada petición y 3 s en cada bandera): la primera vez
que la capa dibuja algo, el icono con bandera ya está en el mapa. Con el comportamiento anterior
puesto a propósito, falla.

## Bloque 5. El marcador de Leipzig tapa un número

El número de los grupos se dibuja ahora por encima de todas las capas de atribuidos (marcador, su
número, su foco y el abierto), con su halo oscuro (`web/src/mapa/estilo.ts`). Es general, vale en
cualquier zoom y no mueve ni esconde nada: desplazar el número lo separa de su círculo, y en Galați
a zoom 6 o más hay un grupo de cuatro justo en el punto del atribuido que ningún desplazamiento
arregla.

Prueba nueva `web/e2e/numero-de-grupo.spec.ts` (390×844 y escritorio, datos publicados reales):
recorre Leipzig, Galați y el Øresund a los zooms 3, 3,5, 4, 4,5, 5, 6, 7 y 8; donde la caja de un
número toca el círculo de un atribuido, compara los píxeles de las cifras con y sin las capas de
atribuidos (el 97 % tienen que quedar iguales). Con el orden anterior falla en 12 números en
escritorio y 9 en el teléfono (el 68 de Leipzig con 37 de 42 píxeles tapados).

## Bloque 6. Pendientes del informe de errores de datos

| Pendiente | Ahora |
| --- | --- |
| Colectas o balances guardados como impactos | **Resuelto** (bloque 2): el analizador los reconoce al principio del mensaje y no da impactos; la relectura de la recogida retira los que había. En lo guardado eran 16 mensajes con impactos |
| Odesa nombra pocos lugares | **Resuelto en lo que es de la fuente** (bloque 2): se lee el canal del jefe de la administración y el de la ciudad. Que la administración no nombre los lugares no tiene arreglo en el observatorio |
| Bélgorod sin canal probado | Sigue pendiente, es de otra naturaleza (prueba de canal oficial). Arreglo: buscar en la web del Gobierno de la región o en una lista oficial rusa el enlace al canal del gobernador y añadirlo como en Kursk |
| EODI-UA-2025-0008 junta dos noches | Sigue pendiente. Causa encontrada: el parte de la noche del 9 de enero de 2025 (t.me/kpszsu/26534) escribe «із 19.30 7 січня», una errata del propio parte (debía ser el 8), y quedó unido con el de la noche anterior. Arreglo: en `proceso/periodos.py`, si «у ніч на N» y el inicio escrito es de dos días antes, el inicio es la tarde del día N−1; y que la recogida separe el tramo en su propio ataque |
| Guardia Civil: autorización de reutilización | Sigue pendiente, es de otra naturaleza (trámite). Arreglo: pedirla por escrito a la Dirección General |
| Nota de Interior sobre SIGLO-CD | **Resuelto**: abierta el 5 de octubre con un navegador real, la frase está («Este sistema ha detectado en la última semana 112 vuelos de RPAS.»); anotado en `configuracion/cifras_contexto.json` |
| 73 incidentes con la cita que no respalda el titular | **Resuelto** (bloque 1) |
| Wunstorf en varios registros y noticias tardías de Leipzig | Ya estaba resuelto (#127). Esta revisión añade EODI-2026-00346, otra noticia de Leipzig con el lugar de Rzeszów |
| Tamaño de la base | Ya estaba resuelto: la base vive en el disco del servidor desde el 5 de octubre (#122) |

## Comprobación final

### Ensayo antes de fusionar

Paso c2 de [`fusiones.md`](fusiones.md), en el servidor, como `eodi`, con `systemd-run` (3 GB,
prioridad baja, `OOMScoreAdjust=1000`, sin el cerrojo de la recogida), sobre una copia propia de la
base del disco en `/home/eodi/ensayo-revision`, sin claves del extractor. Tres ensayos:

| Ensayo | Código | Resultado |
| --- | --- | --- |
| 1.º (14:53) | 1 | La exportación semanal no validaba: `lugar.localidad` sin origen en los puntos que da una autoridad. Arreglado: el lugar toma el origen de la fuente que lo nombra (`lugar.fuente_punto`) |
| 2.º (15:10) | 1 | Lo mismo en la localidad corregida a mano (Brønnøysund, Arna). Arreglado: regla de origen de `lugar.localidad`. La base de prueba de la CI cubre ahora los dos casos (sin el arreglo, falla) |
| 3.º (15:28) | **0** | 16 min 30 s, 3 GB de pico. «registros revisados unidos: 48», «revisión del contenido: retirados 3, con citas 66, titulares 17, ubicados 37, sin guardar []», «ficheros publicados con cambios: 3», «exportación semanal generada sin subir» |

La puerta local (pytest 1.833 pruebas, ruff, ruff format, mypy estricto, `python -m
tests.base_prueba`) y el workflow de tests pasaron en la rama rebasada. Los ficheros publicados
del PR son los del tercer ensayo: la prueba fija de cita y titular los lee, y la recogida
siguiente los rehízo.

### Fusión y recogidas siguientes

PR #130 fusionado a las 15:48 UTC (e789533), fuera de los minutos 12 a 40, con la lista de
ficheros comprobada antes y después del commit único y autor anónimo.

| Recogida | Resultado | Revisión del contenido | Publicada |
| --- | --- | --- | --- |
| 16:17 | Código 0 | 48 registros unidos; 3 retirados, citas en 66, 17 titulares, 37 lugares; nada sin guardar | «ficheros publicados en main» |
| 17:17 | Código 0 | Nada que repetir (0 en todo): la revisión es idempotente | «ficheros publicados en main» |

### En producción

En droneobservatory.eu, en 360 × 800, 390 × 844, 412 × 915 y escritorio
([`web/e2e/revision-contenido.spec.ts`](../web/e2e/revision-contenido.spec.ts),
`bandera-primer-dibujado.spec.ts` y `numero-de-grupo.spec.ts` contra producción, todo en verde), y
cada captura mirada una a una:

1. **Cinco titulares cambiados** (EODI-2025-00059 Sandefjord, 00094 Brønnøysund, 00140 Arna,
   2026-00083 Split y 00166 Budapest): el titular, el estado y la cita de la ficha dicen lo mismo
   que los datos publicados, y la cita nombra lo que afirma el titular. Capturas
   `revision-titular-<id>-<tamaño>.png`.
2. **Capa de Ucrania**: Odesa tiene impactos y su ficha se abre con la fuente del canal oficial de
   Odesa. Capturas `revision-odesa-{mapa,ficha}-<tamaño>.png`.
3. **Polonia**: punto en Wyryki-Wola con el marcador de atribuido y la bandera rusa; la ficha dice
   «Lugar según» la fiscalía de Lublin con su frase y enumera los otros 16 lugares. Capturas
   `revision-polonia-{mapa,ficha}-<tamaño>.png`.
4. **Primera carga con caché vacía y red lenta** (banderas retrasadas 3 s): la prueba comprueba
   que el primer dibujado de los atribuidos ya lleva la bandera, en el teléfono y en escritorio.
   Capturas `revision-primera-carga-<tamaño>.png` y `revision-primera-carga-4s-<tamaño>.png`.
5. **Alejando sobre Alemania** (zoom 4, 5 y 6): se leen todos los números, también el 2 junto a
   Leipzig y el 6 junto a Malmö. Capturas `revision-alemania-z<zoom>-<tamaño>.png`.

### Exportación semanal

Generada sin errores con los datos corregidos en el tercer ensayo (manifiesto
`b72b6aa474c660a2d41a105075387eb22069821fa714e10ef8bb7a24e466d684`) y en local sobre la base de
ensayo. La del lunes 12 de octubre a las 03:47 la genera el temporizador de siempre.

### Total de incidentes, antes y después

| | Incidentes publicados |
| --- | ---: |
| Antes (producción, 5 de octubre, 15:17) | 498 (319 en el mapa, 179 sin punto) |
| Registros unidos a otro del mismo suceso (31 del bloque 1 y 17 del bloque 3) | −48 |
| Retirados por no ser un suceso (Dresde, Riga, Southampton) | −3 |
| Tras la fusión (16:17) | 447 (335 en el mapa, 112 sin punto) |
| Unidos por la regla de fusión de siempre al tener punto («mismo sitio y misma ventana») | −13 |
| Tras la recogida de las 17:17 | 434 (322 en el mapa, 112 sin punto) |

Los 13 del final no los ha unido esta revisión a mano: al tener punto, la regla de fusión de la
recogida (`incidentes.misma_ventana`) los ha reconocido como duplicados de otros ya publicados en
el mismo lugar y la misma noche (Kleine-Brogel tres veces, Akrotiri, Constanza, Mechernich,
Kardam, Rugāji, Tulcea, Vaslui, Moldavia dos veces y Pardina). Cada fusión queda en la tabla de
fusiones con su motivo y la revisión horaria de fusiones (`revisar_fusiones`) la deshace si deja
de cumplirse. Ningún incidente ha quedado sin publicar por la barrera de cita y titular.


## Pendientes, con su arreglo

- **Orden de la lectura de lo antiguo en la recogida horaria** (decidido no aplicarlo ahora).
  Cada recogida dedica como mucho 150 s a lo antiguo, canal por canal en el orden de
  `configuracion/canales_guerra.json`, y mezcla dos cosas: la relectura de lo ya guardado cuando
  cambia la versión del analizador (unos 40.000 mensajes con `mensajes-guerra/5`) y el histórico
  que el lector acaba de bajar, que nunca se ha leído. Los canales nuevos van al final, así que
  esperan a la relectura de todos los demás (unas 8 recogidas). Arreglo: en
  `recogida/guerra.procesar`, dentro de la pasada de lo antiguo, leer primero en todos los canales
  las publicaciones sin registro y después las de otra versión. Se ganaría que el histórico de un
  canal nuevo entrara en las 1 o 2 recogidas siguientes a su bajada en vez de esperar a la
  relectura completa (hoy, unas 7 horas antes para Odesa); la relectura acabaría a la misma hora.
- **Distritos de Odesa.** La administración de Odesa nombra casi siempre el distrito
  («Ізмаїльський район»), que con el criterio de todas las regiones no es un lugar. Arreglo, si
  se decide: dar lugar a los distritos con su radio real cuando el mensaje solo nombra uno, como
  nivel aparte que la web dibuje distinto; cambia el criterio de todas las regiones y es una
  decisión, no una corrección.
- **Constanza, siete registros sin punto** (EODI-2026-00207, 00395, 00397, 00401, 00403, 00405 y
  00408). Arreglo: leer cada nota y decidir si es la explosión del 5 de junio contada más tarde
  (unirla con EODI-2026-00410) o otra explosión (buscar su nota oficial).
- **Tres registros que no son sucesos con lugar** (EODI-2026-00235, 00260 y 00272) y **Horodiște**
  (EODI-2025-00276, cuyo sobrevuelo negó después el Ministerio de Defensa de Moldavia). Arreglo:
  revisarlos uno por uno y retirarlos o desmentirlos con su cita en `incidentes_revisados.json`.
- **EODI-2026-00075**: los ministerios sitúan la caída en Mihăileni (Moldavia) y el incidente es
  de Rumanía. Arreglo: corregir el país con la nota oficial y darle el punto.
- **Aalborg (EODI-2025-00372)**: la frase de la policía estaba en una publicación de X que ya no
  es pública. Arreglo: buscar la nota en la web de la policía o en una copia del archivo web.
- **EODI-UA-2025-0008** junta dos noches por una errata del parte: arreglo en el bloque 6.
- **Bélgorod** sin canal probado y **autorización de la Guardia Civil**: arreglo en el bloque 6.
- **La comprobación de cita y titular no mira aún las cifras ni los hechos** (un número de
  drones, un cierre, unos explosivos), solo el lugar y los nombres propios: eso se ha revisado a
  mano en estos 77. Arreglo: añadir a `proceso/cita_titular.py` las palabras de cierre, derribo,
  explosivos y números en los idiomas de las fuentes, y revisar uno por uno lo que salga.
