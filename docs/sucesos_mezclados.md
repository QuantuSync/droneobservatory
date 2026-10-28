# Sucesos mezclados

Un incidente publicado tiene que contar un solo suceso. El 13 de octubre de 2026 se vio que
EODI-2026-00072 juntaba el cierre del aeropuerto de Vilna del domingo 13 de septiembre de 2026
(un posible dron que resultó ser una bandada de pájaros) y el derribo de un dron llegado de
Bielorrusia por cazas de la OTAN la noche del 14 al 15, cerca de Pratkūnai. Este documento dice
por qué pasó, cómo se separan los incidentes así y cuáles se separaron.

## Por qué se juntaron

No fue una fusión de incidentes: los cuatro artículos estaban en un mismo candidato,
`CAND-20260914T0830-ETNG-aeropuerto`, situado en la base de la OTAN de Geilenkirchen (ETNG).
OpenStreetMap llama a esa base «NATO E-3A Airbase Geilenkirchen» y el nomenclátor sacaba de ese
nombre la ciudad «NATO»; con la palabra aeropuerto en el titular («aeroporti i Vilniusit»,
«close airport», «aerodrom u Vilniusu»), cualquier titular con «NATO» caía en Geilenkirchen. Las
noticias del cierre se publicaron el 14 y las del derribo el 15, a menos de 12 horas unas de
otras, y la regla de agrupación (proceso/noticias.agrupar) las encadenó en el mismo candidato.
El extractor hizo una sola ficha con las dos cosas.

Lo mismo pasaba con nombres alternativos de GeoNames que son palabras corrientes en otro idioma:
«Caccia» (cazas, en italiano) es un nombre de Xagħra (Malta), «Cazas» de Cazis (Suiza), «Încă»
(todavía, en rumano) de Inca (Mallorca), «Over», «More», «Drama», «Peste», «Roja», «Meer»,
«Deep», «Neagră», «Șase», «Maan», «Teren», «Policija»… y nombres de país en idiomas que Natural
Earth no trae («Litva», «Polija», «Rusko»). Noticias de Letonia y de Lituania acababan en un
candidato de Malta.

## La regla nueva

`configuracion/no_son_lugares.json` lista las organizaciones, los nombres de país en otros
idiomas y las palabras que nunca nombran un lugar. `proceso/noticias.nomenclator` las quita de
los alias de las instalaciones, de sus ciudades (también de sus formas declinadas) y de las
localidades (`nombra_lugar`). La base de Geilenkirchen sigue saliendo cuando se la nombra
(«base aérea de Geilenkirchen»), y dos aeropuertos del mismo país en un titular siguen yendo a
cada uno: el mismo cierre del 7 de octubre de 2026 en Lublin y Rzeszów (EODI-2026-00497 y
EODI-2026-00498) sigue unido. La prueba es `tests/test_sucesos_mezclados.py`: con la regla
anterior, los cuatro titulares de Vilna iban a un solo candidato de Geilenkirchen; con la nueva,
ninguno.

La regla vale para lo que llega. Lo ya agrupado se revisó a mano.

## Cómo se separa

Revisado a mano en `configuracion/incidentes_revisados.json`, sección `separar`: cada fuente del
incidente va a la parte del suceso del que habla (a las dos si cuenta las dos), con la fecha del
suceso, si es un suceso y, si ya tiene ficha, cuál (`coincide_con`). La recogida horaria lo
aplica una vez, antes del extractor (`recogida/revisados.separar`, cursor
`revisados:separar:<incidente>`):

- el identificador se queda con el suceso más temprano. Pierde las fuentes de los demás y lo que
  solo ellas sostenían (los registros que tiene fundidos no se publican y no cambian; al volver a
  extraerlo solo recupera de ellos las fuentes que conserva): sus afirmaciones, los pasos
  del estado que dieron (el estado vuelve al último paso que queda; siempre empieza en
  «notificado»), la atribución y la investigación que citan y la presencia del dron que
  afirmaban, y los valores que solo ellas daban (las medidas, los drones, la fecha, que vuelve a
  la de publicación de su primera noticia); y se aplican otra vez las reglas de tipo y de
  presencia. Si su candidato pierde
  artículos, se vuelve a extraer, para que su titular y sus datos sean solo los de su suceso;
- cada otro suceso abre un candidato propio («separado_de») con sus artículos y recibe un
  identificador por el camino normal de altas: lo extrae el extractor (en modo revisión, hasta 12
  por recogida; lo que quede, en las siguientes o con el extractor de la horaria, que lleva
  delante los candidatos separados). Nada se deduce: estado, presencia, tipo, fecha y lugar
  salen de sus fuentes con las reglas de siempre;
- lo que no es un suceso (una declaración política, un parte de la guerra, un ataque fuera de
  Europa) sale del incidente con un candidato anotado como «no es un suceso», sin formar otro;
- una fusión anterior cuyas fuentes son todas de otra parte se deshace (las revisadas a mano no);
- una parte que es el mismo suceso que otra ficha se une a ella con la regla de siempre para
  elegir cuál queda (`proceso/incidentes.destino_de`); su enlace lleva a la que queda;
- las fichas que quedan se enlazan entre sí: campo público `relacionados` (esquema 1.18.0), que
  la web enseña como «Suceso relacionado» / «Related incident» con la nota del motivo;
- con `"distintos": true` en la entrada de `separar`, la regla de fusión no vuelve a juntar las
  fichas enlazadas por esa separación (`incidentes.encajan`) y `incidentes.revisar_fusiones`
  deshace la que ya lo hizo. Solo con la marca: sin ella, `relacionados` enlaza también la parte
  que coincide con otra ficha (`coincide_con`) y los registros de una misma parte, que sí deben
  estar juntos. Desde el 19 de octubre de 2026, por el desvío del 19/10/2025 en Fuerteventura
  (EODI-2025-00468), que la regla volvió a unir con las esperas de la víspera (EODI-2025-00397)
  porque solo tenía la fecha de publicación.

Los sucesos separados son de semanas o meses atrás: los avisos de ntfy solo salen para sucesos
de las últimas 72 horas (recogida/avisos.clasificar), así que no se avisan.

## Vilna

- **EODI-2026-00072** se queda con el cierre (sot.com.al y humanevents.com). Es el mismo suceso
  que **EODI-2026-00007**, que ya lo contaba con 33 fuentes: se une a ella y su enlace lleva ahí.
- El derribo (delo.si con las declaraciones del presidente Nausėda y del Ministerio de Defensa, y
  klix.ba) recibe un identificador nuevo y se une a **EODI-2026-00179**, la ficha del derribo
  cerca de Pratkūnai con la nota oficial del centro de crisis.
- EODI-2026-00007 y EODI-2026-00179 se enlazan como sucesos relacionados.

## Los demás

Se revisaron los 451 incidentes publicados el 13 de octubre de 2026, fuente por fuente. Se
separan 43:

| Incidente | Qué juntaba | Partes |
| --- | --- | --- |
| EODI-2025-00066 | junta los disparos contra drones en Volkel del 21 de noviembre con el cierre de Eindhoven del 22 y nuevos drones sobre Volkel la noche del 22 al 23 | 2025-11-21T18:00Z (suceso, 25 fuentes); 2025-11-22 (suceso, 6 fuentes) |
| EODI-2025-00080 | Junta los avistamientos sobre Kleine-Brogel de noches distintas (domingo 2, lunes 3 y martes 4 de noviembre) y los cierres de los aeropuertos de Bruselas y Lieja del 4 de noviembre | 2025-11-02 (suceso, 9 fuentes); 2025-11-03 (suceso, 3 fuentes); 2025-11-04 (suceso, 4 fuentes) |
| EODI-2025-00131 | Junta sobrevuelos de Kleine-Brogel de noches distintas: del viernes 31 oct al sábado 1 nov, del sábado al domingo 2 nov y del domingo al lunes 3 nov | 2025-10-31 (suceso, 18 fuentes); 2025-11-01 (suceso, 4 fuentes); 2025-11-02 (suceso, ya en EODI-2025-00080, 1 fuentes) |
| EODI-2025-00154 | Junta el cierre del aeropuerto de Copenhague del 22 sep con un ataque de drones contra Moscú, drones vistos en Malmö el 23 sep y drones cerca de otros aeropuertos daneses la noche del 24 al 25 sep | 2025-09-22 (suceso, 60 fuentes); 2025-09-22 (no es un suceso, 1 fuentes); 2025-09-23 (suceso, 2 fuentes); 2025-09-24 (suceso, 4 fuentes) |
| EODI-2025-00172 | Juntaba el cierre de Copenhague del 22 de septiembre de 2025 con el cierre de Aalborg y los drones en otros aeropuertos daneses de la noche del 24 al 25, y una mención al cierre de Oslo. | 2025-09-22 (suceso, 15 fuentes); 2025-09-24 (suceso, 16 fuentes) |
| EODI-2025-00233 | Junta la incursión de drones rusos y el cierre del aeropuerto de Varsovia del 10 sep con el dron que sobrevoló edificios del Gobierno en Varsovia el 15 sep (operador ucraniano expulsado) | 2025-09-10 (suceso, 26 fuentes); 2025-09-15 (suceso, 4 fuentes) |
| EODI-2025-00261 | junta el dron Gerbera caído sobre una casa en Cuhureștii de Jos (norte) con el Shahed que cruza el sur de Moldavia hacia Rumanía | 2025-11-25 (suceso, 28 fuentes); 2025-11-25 (suceso, 34 fuentes) |
| EODI-2025-00268 | Junta el dron que entró en el espacio aéreo de Rumanía el 19 nov con el sobrevuelo de Moldavia de esa noche (otra ficha) y un reportaje sobre civiles ucranianos cazando drones | 2025-11-19 (suceso, 9 fuentes); 2025-11-19 (suceso, ya en EODI-2025-00204, 16 fuentes); 2025-11-20 (no es un suceso, 1 fuentes) |
| EODI-2025-00273 | Junta el dron ruso hallado en Lituania con noticias de la guerra en Ucrania (ataque en Lugansk, británico muerto por un dron) | 2025-08-05 (suceso, 4 fuentes); 2025-08-06 (no es un suceso, 1 fuentes); 2025-08-06 (no es un suceso, 1 fuentes) |
| EODI-2025-00274 | Juntaba reacciones a la incursión en Polonia del 9-10 de septiembre, el despegue preventivo de aviones polacos del 13 y el dron que entró en Rumanía el 13. | 2025-09-10 (suceso, 2 fuentes); 2025-09-13 (no es un suceso, 4 fuentes); 2025-09-13 (suceso, 30 fuentes) |
| EODI-2025-00284 | Junta el dron ruso en el cielo rumano del 19 nov con noticias de la guerra en Ucrania sobre otros ataques (Járkov, ataque ucraniano en Rusia) | 2025-11-19 (suceso, ya en EODI-2025-00268, 1 fuentes); 2025-11-18 (no es un suceso, 1 fuentes); 2025-11-19 (no es un suceso, 2 fuentes) |
| EODI-2025-00287 | Juntaba los drones sobre el campamento de Elsenborn con el cierre del aeropuerto de Múnich y un artículo sobre el petrolero Boracay | 2025-10-02 (suceso, 15 fuentes); 2025-10-02 (suceso, 2 fuentes); 2025-10-03 (no es un suceso, 1 fuentes) |
| EODI-2025-00306 | Junta la incursión del dron ruso en Tulcea (13 sep 2025) con el dron derribado sobre el barrio gubernamental de Varsovia (15 sep) | 2025-09-13 (suceso, ya en EODI-2025-00337, 34 fuentes); 2025-09-15 (suceso, 1 fuentes) |
| EODI-2025-00307 | Juntaba los drones sobre Skrydstrup y el Regimiento de Dragones de Jutlandia (noche del 25 al 26 de septiembre de 2025) con los nuevos drones sobre bases danesas de la noche del 27 al 28. | 2025-09-25 (suceso, 2 fuentes); 2025-09-27 (suceso, ya en EODI-2025-00309, 4 fuentes) |
| EODI-2025-00316 | Juntaba la incursión de un dron en Tulcea (Rumanía) del 19 de noviembre de 2025 con el dron que sobrevoló Moldavia ese día y con un parte del ataque ruso sobre Ucrania. | 2025-11-19 (suceso, 16 fuentes); 2025-11-19 (suceso, ya en EODI-2025-00285, 1 fuentes); 2025-11-18 (no es un suceso, 1 fuentes) |
| EODI-2025-00322 | Juntaba desvíos a Colonia/Bonn causados por un avistamiento en Bruselas y por otro en Hannover, en días distintos; no hubo dron en Colonia/Bonn. | 2025-11-04 (suceso, 1 fuentes); 2025-11-05 (suceso, 1 fuentes) |
| EODI-2025-00328 | Juntaba los dos drones que cruzaron Moldavia la noche del 28 de noviembre con una declaración francesa anterior sobre otras incursiones | 2025-11-28 (suceso, 28 fuentes); 2025-11-28 (no es un suceso, 1 fuentes) |
| EODI-2025-00335 | Juntaba el dron del aeropuerto de Bruselas del 6 de noviembre con la noticia de los vuelos ilegales de drones de la policía de Bruselas | 2025-11-06T20:20Z (suceso, 34 fuentes); 2025-11-07 (no es un suceso, 4 fuentes) |
| EODI-2025-00349 | Juntaba el cierre del aeropuerto de Aalborg con los avistamientos de drones en Esbjerg, Sønderborg y Skrydstrup. | 2025-09-24 (suceso, 1 fuentes); 2025-09-24 (suceso, 3 fuentes) |
| EODI-2026-00072 | juntaba dos sucesos distintos: el cierre del aeropuerto de Vilna del domingo 13 de septiembre de 2026 por un posible dron que resultó ser una bandada de pájaros (sot.com.al, humanevents.com) y el derribo de un dron llegado de Bielorrusia por cazas de la OTAN la noche del 14 al 15 cerca de Pratkūnai (delo.si, klix.ba) | 2026-09-13 (suceso, ya en EODI-2026-00007, 2 fuentes); 2026-09-14 (suceso, ya en EODI-2026-00179, 4 fuentes) |
| EODI-2026-00090 | Junta el dron ucraniano estrellado en Lituania (23 mar 2026) con el ataque de drones sobre Leningrado y los drones caídos en Estonia y Letonia el 25 mar | 2026-03-23 (suceso, 8 fuentes); 2026-03-25 (no es un suceso, 6 fuentes); 2026-03-25 (suceso, 5 fuentes); 2026-03-25 (suceso, 5 fuentes) |
| EODI-2026-00094 | Junta el dron que interrumpió Brussels Airport el viernes 11 sep 2026 con un nuevo avistamiento la noche del 12 sep | 2026-09-11T20:00Z (suceso, 11 fuentes); 2026-09-12 (suceso, 6 fuentes) |
| EODI-2026-00108 | Junta el impacto en la central de Auvere (Estonia) con los drones caídos en Letonia, el ataque ucraniano a un puerto ruso y un concurso antidrones de Brave1 y la OTAN | 2026-03-25 (suceso, ya en EODI-2026-00274, 36 fuentes); 2026-03-25 (no es un suceso, 4 fuentes); 2026-03-25 (no es un suceso, 1 fuentes) |
| EODI-2026-00112 | Junta dos drones Shahed distintos: uno que cruzó el norte de Moldavia la noche del 30 mar y otro que sobrevoló Transnistria la mañana del 31 mar | 2026-03-30 (suceso, 19 fuentes); 2026-03-31 (suceso, 15 fuentes) |
| EODI-2026-00130 | junta el derribo de un dron sobre Estonia del 19 de mayo con la alerta por dron en Lituania del 20 de mayo y noticias de la guerra sin suceso | 2026-05-19 (suceso, 10 fuentes); 2026-05-20 (suceso, ya en EODI-2026-00185, 1 fuentes); 2026-05-19 (no es un suceso, 7 fuentes) |
| EODI-2026-00168 | El título juntaba un dron que entra en Moldavia y explota (sin fuente) con los cierres de Lublin y Rzeszów; una fuente era solo la compra del sistema Merops. | 2026-09-30 (suceso, 1 fuentes); 2026-09-30 (no es un suceso, 1 fuentes) |
| EODI-2026-00180 | Juntaba los dos drones caídos cerca de Kouvola (Finlandia) el 29 de marzo de 2026 con los drones desviados que entraron en Estonia el 31 de marzo. | 2026-03-29 (suceso, 10 fuentes); 2026-03-31 (suceso, 3 fuentes) |
| EODI-2026-00182 | Juntaba el derribo del dron sobre Lituania con el ataque ruso a un tren en Ucrania y un dron pescado en el Báltico frente a Polonia | 2026-09-14T21:20Z (suceso, ya en EODI-2026-00179, 22 fuentes); 2026-09-13 (no es un suceso, 12 fuentes); 2026-09-14 (suceso, 1 fuentes) |
| EODI-2026-00185 | junta el dron caído en Lituania el 20 de mayo con el derribo sobre Estonia del 19, el dron en Letonia del 21 y una declaración política | 2026-05-20 (suceso, 1 fuentes); 2026-05-19 (suceso, ya en EODI-2026-00130, 1 fuentes); 2026-05-21T08:50Z (suceso, ya en EODI-2026-00215, 3 fuentes); 2026-05-22 (no es un suceso, 1 fuentes) |
| EODI-2026-00195 | Junta el dron que entró en Rumanía cerca de Chilia Veche la noche del 26 al 27 sep con un dron militar pescado por unos amigos y un ataque hutí contra Riad | 2026-09-26 (suceso, 3 fuentes); sin fecha (no es un suceso, 1 fuentes); 2026-09-27 (no es un suceso, 1 fuentes) |
| EODI-2026-00203 | junta el dron que explota junto a Hîrbovăț al amanecer con un segundo dron que cruza Transnistria hasta Arionești y provoca el cierre del espacio aéreo | 2026-09-30T02:43Z (suceso, 19 fuentes); 2026-09-30 (suceso, 13 fuentes) |
| EODI-2026-00204 | Juntaba el derribo del dron sobre Letonia con un dron estrellado en Rumanía y artículos de la guerra en Ucrania | 2026-08-14 (suceso, ya en EODI-2026-00219, 11 fuentes); 2026-08-14 (suceso, 1 fuentes); 2026-08-14 (no es un suceso, 2 fuentes) |
| EODI-2026-00217 | Junta los derribos rumanos de drones de varios días de finales de julio con noticias sin suceso (producción de drones en EE. UU., Ucrania como aliado, jefe del Ejército checo) | 2026-07-26 (suceso, ya en EODI-2026-00316, 3 fuentes); 2026-07-27 (no es un suceso, 5 fuentes); 2026-07-27 (no es un suceso, 1 fuentes); 2026-07-28 (no es un suceso, 1 fuentes) |
| EODI-2026-00218 | Junta el dron estrellado en Tulcea (20 ago 2026) con el dron derribado sobre Letonia el 14 ago | 2026-08-20 (suceso, 12 fuentes); 2026-08-14 (suceso, ya en EODI-2026-00310, 5 fuentes) |
| EODI-2026-00220 | Juntaba la alerta por drones que paró los trenes en Letonia con una acusación política rusa sin suceso | 2026-05-19 (suceso, 1 fuentes); 2026-05-19 (no es un suceso, 1 fuentes) |
| EODI-2026-00224 | Mezclaba el dron Shahed que cruzó Moldavia el 8 de septiembre con artículos sobre el plan de Ucrania de legalizar la pornografía para financiar drones. | 2026-09-08T13:20Z (suceso, 28 fuentes); 2026-09-09 (no es un suceso, 2 fuentes) |
| EODI-2026-00225 | Juntaba el derribo de un dron en Rumanía por un F-18 español (16 de agosto de 2026) con artículos del ataque ucraniano con cientos de drones sobre Moscú. | 2026-08-16 (suceso, 4 fuentes); 2026-08-16 (no es un suceso, 3 fuentes) |
| EODI-2026-00234 | Además del derribo sobre Galați del 16 de agosto, metía ataques entre Rusia y Ucrania, un informe sobre bases rusas de drones y el plan de muro antidrones de la OTAN. | 2026-08-16T01:44Z (suceso, ya en EODI-2026-00106, 12 fuentes); 2026-08-16 (no es un suceso, 7 fuentes); 2026-08-17 (no es un suceso, 3 fuentes); 2026-08-17 (no es un suceso, 1 fuentes) |
| EODI-2026-00237 | Junta los drones ucranianos caídos en Finlandia (29 mar 2026) con una disculpa por drones en los países bálticos y una noticia sobre la defensa antiaérea de Ucrania | 2026-03-29 (suceso, 8 fuentes); 2026-03-30 (no es un suceso, 1 fuentes); 2026-03-30 (no es un suceso, 1 fuentes) |
| EODI-2026-00268 | Junta el dron que alcanzó RAF Akrotiri (noche del 1 al 2 mar 2026) con drones iraníes derribados por el Reino Unido en Oriente Medio | 2026-03-01T22:00Z (suceso, 18 fuentes); 2026-03-01 (no es un suceso, 1 fuentes) |
| EODI-2026-00281 | Junta el Shahed visto en Tudora (Ștefan Vodă) el 17 mar 2026 con otro dron que cruzó la noche del 18 mar junto al paso de Palanca | 2026-03-17 (suceso, 7 fuentes); 2026-03-18T00:14Z (suceso, 8 fuentes) |
| EODI-2026-00327 | Junta la alerta del 27 feb 2026 (el dron no entró en Rumanía) con una incursión breve en el espacio aéreo rumano anunciada el 26 feb | 2026-02-27 (suceso, 4 fuentes); 2026-02-26 (suceso, 1 fuentes) |
| EODI-2026-00384 | Junto al dron de Bielorrusia sobre Lituania del 3 de octubre, metía drones y misiles rusos en Moldavia ese día y un ataque contra una base aérea en Rusia. | 2026-10-03 (suceso, 27 fuentes); 2026-10-03 (suceso, 2 fuentes); 2026-10-03 (no es un suceso, 1 fuentes) |
| EODI-2026-00541 | Juntaba el petrolero YARA J alcanzado frente a Sulina el miércoles 14 de octubre de 2026 hacia las 20:00 hora local (EODI-2026-00535, fundida por la regla de mismo sitio y misma ventana) con el dron detectado un minuto en el espacio aéreo rumano a las 01:34 del jueves 15, una nota de la noche del 9 al 10 sin entrada en Rumanía y tres declaraciones políticas sobre el mar Negro. Separada el 28 de octubre de 2026, con `distintos` | 2026-10-14 (suceso, 6 fuentes); 2026-10-15 (suceso, ya en EODI-2026-00544, 18 fuentes); no es un suceso (4 fuentes) |

EODI-2026-00541 se queda con el petrolero, que es el suceso más temprano, y EODI-2026-00535 sigue unida a ella. El dron de las 01:34 vuelve a su ficha por el camino normal: se deshacen las fusiones por regla cuyas fuentes son todas suyas (EODI-2026-00544 a EODI-2026-00547), y con `coincide_con` se unen en una sola, EODI-2026-00544. Sin `coincide_con`, la marca `distintos` las habría dejado como cuatro fichas del mismo suceso. El ensayo también mostró que el motivo es la nota de «relacionados» y no puede pasar de 600 letras (prueba en `tests/test_revisados.py`). EODI-2026-00538 (dos F-16 despegan de Borcea por un dron en el mar Negro, la tarde del 14) no se une a ninguna de las dos: cuenta una alerta en el espacio aéreo, y el ministro de Defensa dijo que el radar no vio ningún dron ir hacia el petrolero.

## Dudosos (no se tocan)

| Incidente | Motivo |
| --- | --- |
| EODI-2025-00005 | digi24.ro (6 de noviembre por la mañana, antes del cierre) trata de la serie anterior de cierres y de su atribución a Rusia por los servicios belgas, no del cierre de la noche del 6; además el objetivo dice Charleroi y las fuentes hablan de Bruselas (y Lieja) |
| EODI-2025-00010 | Cierre del aeropuerto de Lublin del 13 de septiembre de 2025; la frase citada de 20minutos es la violación del espacio aéreo de Rumanía por un dron ruso ese mismo día. |
| EODI-2025-00042 | solo se ve una muestra de 189 fuentes; no se pueden repartir con seguridad todas (en lo visto junta el cierre del 22-23 de septiembre con el dron incautado el 25, ficha EODI-2025-00325) |
| EODI-2025-00049 | Dron junto a la pista de Otopeni (28 de septiembre de 2025); una fuente trata de fragmentos de dron hallados en Tulcea, otro suceso. |
| EODI-2025-00051 | las cuatro fuentes de los disparos sobre Volkel cuentan también el cierre de Eindhoven: no queda ningún artículo solo del otro suceso |
| EODI-2025-00055 | Ficha del despliegue del sistema láser y de los cambios legales (7-8 oct 2025) que recoge también crónicas de los cierres del aeropuerto de Múnich de dos noches seguidas (2 y 3 oct) |
| EODI-2025-00072 | solo se ve una muestra de 169 fuentes |
| EODI-2025-00116 | Solo se ve una muestra de 70 de 1463 fuentes: no se pueden repartir con seguridad todas entre el primer cierre de Múnich (2-3 oct 2025) y el segundo (3-4 oct). |
| EODI-2025-00163 | Ficha del cierre de Lieja del viernes 7 de noviembre por la mañana con artículos de resumen que cuentan también los cierres de Bruselas y Lieja del jueves por la noche, Estocolmo y el puerto de Amberes. |
| EODI-2025-00176 | nra.lv (14 de enero) habla de drones sospechosos vistos en varios puntos de Riga, incluso el centro, distintos del dron del aeropuerto del 13 de enero |
| EODI-2025-00211 | Las fuentes cuentan juntos dos sobrevuelos de la base de Marche-en-Famenne en noches distintas: el sábado 25 de octubre y la noche del 28 al 29 de octubre de 2025 |
| EODI-2025-00219 | Una fuente (ladepeche.fr, 12 nov) trata de otro sobrevuelo: un dron sobre un convoy de carros Leclerc, no la fábrica Eurenco de Bergerac |
| EODI-2025-00226 | Solo se ve una muestra de 74 fuentes: no se pueden repartir con seguridad todas entre el cierre de Copenhague y el de Oslo. |
| EODI-2025-00228 | solo se ve una muestra de 70 de 246 fuentes; no se pueden repartir con seguridad todas entre las noches del 24-25 y 25-26 sep 2025 |
| EODI-2025-00295 | solo se ve una muestra de 273 fuentes |
| EODI-2025-00309 | El título dice «dos noches consecutivas» sobre objetivos militares daneses; las fuentes cuentan la noche del 27 al 28 de septiembre de 2025, pero el título junta también la anterior (Karup). |
| EODI-2025-00314 | Recopilación de avistamientos de drones sobre varias infraestructuras de Kiel y Schleswig-Holstein (central, clínica, astillero, Landtag), probablemente de días y lugares distintos |
| EODI-2025-00340 | Solo se ve una muestra de 70 de 440 fuentes: no se pueden repartir con seguridad todas entre el primer cierre de Múnich (2-3 oct 2025) y el segundo (3-4 oct). |
| EODI-2025-00348 | Inicio el 5 de octubre sin cierre ese día; las fuentes son reacciones (Söder, láser, Merz) a los cierres de Múnich del jueves 2 y del viernes 3 de octubre, que podrían ser dos sucesos. |
| EODI-2026-00020 | Resume tres derribos de drones en Rumanía en tres días distintos y un objeto luminoso caído en Buzău; no es un solo suceso. |
| EODI-2026-00038 | Una sola ficha («Cierres») para dos cierres del aeropuerto de Luxemburgo en días distintos; la única fuente es un artículo posterior sobre sanciones que habla de ambos. |
| EODI-2026-00066 | Varios drones en días distintos de la visita de Trump: sobre el aeropuerto de Shannon y junto al campo de golf de Doonbeg, antes y durante la visita. |
| EODI-2026-00085 | las seis fuentes cuentan los tres derribos (24, 25 y 26 de julio de 2026): ningún artículo es de uno solo |
| EODI-2026-00134 | junto al dron con explosivo junto al Antonov del 4 de agosto hay artículos del 25 de agosto sobre el hallazgo de otro (tercer) dron con explosivo cerca del aeropuerto, posible suceso aparte (solo se ve una muestra) |
| EODI-2026-00144 | Una fuente sobre Mechernich cita como hecho un dron con explosivos hallado cerca del aeropuerto de Leipzig/Halle, que es otro suceso |
| EODI-2026-00160 | focus-news.net habla de un segundo dron sobre Moldavia horas después; puede ser otro de los drones del 30 de septiembre (Hîrbovăț u Orhei) |
| EODI-2026-00179 | Un titular de leggo.it del 15 de septiembre sitúa el derribo en Letonia; puede ser un error del medio o un repaso del derribo letón del 14 de agosto |
| EODI-2026-00211 | solo se ve una muestra de 201 fuentes |
| EODI-2026-00222 | Dron de un ciudadano ucraniano en la zona prohibida de Vilna; la fuente de LRT habla de dos vuelos no autorizados, junto a Vilna y junto a Palanga. |
| EODI-2026-00261 | Varias infracciones de aficionados en la zona prohibida del aeropuerto de Múnich durante el Oktoberfest, probablemente en días distintos. |
| EODI-2026-00263 | las quince fuentes cuentan los tres drones del 30 de septiembre de 2026; Lunga y Orhei ya tienen ficha (EODI-2026-00160 y EODI-2026-00262) |
| EODI-2026-00292 | Balance de más de 100 drones detectados cerca de la frontera rumana en 96 horas y 7 despegues de cazas: agrupa varios días y sucesos. |
| EODI-2026-00312 | parece juntar dos alertas Ro-Alert en Tulcea el 2 de agosto: una por la mañana en que el blanco no entró en Rumanía y otra por la tarde con un dron que sí sobrevoló y cayó derribado en Ucrania con restos en Periprava |
| EODI-2026-00329 | además del dron que entra en Rumanía por Chilia Veche, incluye resúmenes de la guerra cuya parte citada trata de otros hechos en Ucrania (150 drones derribados por Ucrania; primer Shahed abatido por una empresa privada) |
| EODI-2026-00512 | Junta dos buques alcanzados por drones en el mar Negro la misma noche en lugares distintos: frente a Byala y frente a Krapets. |

Aparte, la revisión vio fichas duplicadas del mismo suceso que no mezclan nada (por ejemplo, la
explosión del puerto de Constanza en EODI-2026-00207, 00361, 00392, 00393, 00411 y 00416, o el
cierre de Bruselas del 4 de noviembre de 2025 en EODI-2025-00072 y 00249). No son mezclas y no
se tocan aquí.
