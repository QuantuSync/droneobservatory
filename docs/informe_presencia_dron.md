# Presencia de dron, titulares coherentes y fechas de incidentes fusionados

European Observatory of Drone Incidents, 4 de octubre de 2026. Las horas son UTC. Cambios:
PR #77 (criterio de presencia, titulares, un incidente por noche de cierre, corrección de lo
guardado), PR #80 (intervención de la autoridad), PR #81 (un cierre que se repite no se funde en
el de la noche anterior; revisión de fusiones), PR #82 (titulares que ya dudan del dron) y PR #83
(la policía que acude, detiene o multa por un dron) PR #85 (cierre por dron aunque la frase no
repita el dron; la autoridad que lo deja abierto pesa más que la actuación contada por la prensa) y
PR #86 (vuelos desviados por el dron, más palabras de cierre y de duda, otra causa como los globos). Medido en producción: base del 3 de octubre a
las 18:45, antes de cambiar nada, y base del 4 de octubre a las 07:30, tras la corrección, la nueva extracción de los
candidatos separados y una recogida completa.

## 0. Resumen

| | Antes | Después |
| --- | ---: | ---: |
| Incidentes activos (los que sirve droneobservatory.eu) | 507 | 513 |
| Dron confirmado | 303 | 426 |
| Dron no confirmado | 195 | 78 |
| Descartada | 9 | 9 |
| Confirmados o atribuidos con «Dron no confirmado» | 41 | 5, todos con la autoridad que lo deja abierto |
| De ellos, con la fuente oficial que lo confirma nombrando el dron sin dejarlo abierto (lo que comprueba la validación) | 9 | 0 |
| Titulares que no dicen lo mismo que la presencia | 177 | 0 |
| Incidentes con el titular reescrito | — | 81 |
| Incidentes separados por noches o fechas distintas | — | 7 |

## 1. Criterio de presencia

Si la autoridad competente lo da por hecho, para el observatorio está confirmado. Dos valores para
los incidentes vigentes; descartada sigue como estaba.

- **Dron confirmado**: una autoridad competente (gestor aeroportuario, gestor de navegación aérea,
  policía, fuerzas armadas, ministerio, gobierno, fiscalía, autoridad de aviación civil) actúa o
  declara atribuyendo el suceso a un dron. Basta con eso: su declaración citada
  (`proceso/declaraciones.py`), un cierre por dron, una intervención (patrulla, cazas, derribo,
  inhibición, cierre del espacio aéreo), una detención o una multa por volarlo
  (`proceso/presencia.por_actuacion`), o su propio documento oficial (`proceso/detalle.py`). No se
  piden restos, grabación ni detección por sensor.
- **Dron no confirmado**: la propia autoridad lo deja abierto («posible dron», «objeto no
  identificado», «se investiga si era un dron», `declaraciones.ABIERTO`, en las lenguas que lee
  la recogida), o ninguna
  autoridad lo atribuye a un dron y solo lo cuentan la prensa o los testigos. La sospecha de una
  infracción («mistanke om ulovlig droneflyvning») no deja abierto que fuera un dron.

**Regla de coherencia** (`proceso/validaciones.errores_presencia`): un incidente confirmado o
atribuido cuya fuente oficial lo llevó a ese estado atribuyendo el suceso a un dron, sin dejarlo
abierto, tiene la presencia confirmada; si no, no valida y no se guarda. Lo que dice una autoridad
en su propio documento sobre la presencia manda.

Dónde está: esquema de la base 1.8.0 (`presencia_dron`, pública, con el criterio en su
descripción), prompt del extractor (sin cambiar de versión: lo guardado no se vuelve a extraer;
la regla del código decide), metodología de la web, y en la ficha el desplegable «Qué dice la
fuente» de la presencia con la cita literal que justifica el valor (`afirmaciones_publicas[].cita`,
campo público nuevo de la lista cerrada).

### 1.1 Antes y después

Paso de cada incidente que estaba activo antes y sigue activo:

| Antes → después | Incidentes |
| --- | ---: |
| no confirmado → confirmado | 118 |
| confirmado → confirmado | 302 |
| no confirmado → no confirmado | 77 |
| descartada → descartada | 9 |
| confirmado → no confirmado | 1 (EODI-2026-00278: «Gardaí investigating alleged sighting of large drone close to Dublin Bay», la policía lo deja abierto) |

Los 5 confirmados o atribuidos que siguen sin el dron confirmado son correctos con el criterio:
la autoridad lo deja abierto.

| Incidente | Lo que dice la autoridad |
| --- | --- |
| EODI-2025-00018, Eindhoven | «De vliegveiligheid staat voorop als wij een drone in het luchtruim denken te zien.» |
| EODI-2025-00183, Aalborg | «Vi har ikke fået hverken be- eller afkræftet, om det var droner, der blev observeret» |
| EODI-2026-00055, Cracovia | «Policja potwierdziła nam, że jeden z pilotów zgłosił obecność obiektu przypominającego drona» |
| EODI-2026-00272, Dinamarca | Las Fuerzas Armadas admiten errores en su informe inicial |
| EODI-2026-00278, Dublín | «Gardaí investigating alleged sighting of large drone close to Dublin Bay.» |

Reclasificación de lo ya guardado: `recogida/criterio_presencia.py`, una vez, dentro de la
recogida horaria del 3 de octubre a las 20:17, releyendo las fichas y las declaraciones guardadas,
sin descargar nada ni llamar al extractor; las reglas de #80 y #83 las aplicó la revisión horaria
(`presencia.revisar`). La base es de solo añadir: cada cambio entra como versión nueva del
incidente y su motivo queda en el historial (tabla `incidentes_motivos`): 200 por el criterio de
presencia, 45 por una actuación de la autoridad (cierre, desvío de vuelos, intervención, detención),
23 por el titular.

## 2. Titulares coherentes

`proceso/titulares.py`: con el dron confirmado el titular lo afirma; sin confirmar, lo da como
posible («Posibles drones sobre…», «Un posible dron obliga a…»); un titular que ya duda del dron
con otra palabra («posiblemente», «sospecha de», «unidentified») vale tal cual. Se ajustan al
construir el incidente y en la revisión horaria. Un test detecta los titulares que afirman el dron
sin confirmar y los de «posible dron» con el dron confirmado; en producción quedan 0 de cada.

81 incidentes con el titular reescrito (en español, en inglés o en los dos). Diez ejemplos:

| Incidente | Antes | Después | Presencia |
| --- | --- | --- | --- |
| EODI-2025-00036 | Posibles drones sobre la base aérea de Volkel obligan a desplegar cazas | Drones sobre la base aérea de Volkel obligan a desplegar cazas | confirmado |
| EODI-2025-00092 | Drones sobre el aeropuerto de Lieja interrumpen el tráfico aéreo | Dron obliga a cerrar el aeropuerto de Lieja | confirmado |
| EODI-2025-00116 | Cierre del aeropuerto de Múnich por avistamiento de drones | Cierre del aeropuerto de Múnich por avistamiento de drones afecta a 6500 pasajeros | confirmado |
| EODI-2025-00019 | Avistamientos de drones o UAP sobre Newmarket cerca de RAF Lakenheath | Avistamientos de posibles drones o UAP sobre Newmarket cerca de RAF Lakenheath | no confirmado |
| EODI-2025-00050 | Avistamientos de drones desvían vuelos hacia el aeropuerto de Fráncfort | Avistamientos de posibles drones desvían vuelos hacia el aeropuerto de Fráncfort | no confirmado |
| EODI-2025-00077 | Drones reportados cerca del Aeropuerto de Dublín durante visita de Zelensky | Posibles drones reportados cerca del Aeropuerto de Dublín durante visita de Zelensky | no confirmado |
| EODI-2025-00058 | Drones cierran una pista del aeropuerto de Ámsterdam Schiphol | Posibles drones cierran una pista del aeropuerto de Ámsterdam Schiphol | no confirmado (§6) |
| EODI-2025-00017 | Drones sobrevuelan la base militar de Beauvechain y otras ubicaciones en Bélgica | Posibles drones sobrevuelan la base militar de Beauvechain y otras ubicaciones en Bélgica | no confirmado |
| EODI-2025-00018 | Dron obliga a desviar un vuelo en el aeropuerto de Eindhoven | Posible dron obliga a desviar un vuelo en el aeropuerto de Eindhoven | no confirmado |
| EODI-2025-00085 | Drones no autorizados vuelan en la zona de exclusión del aeropuerto de Dublín | Posibles drones no autorizados vuelan en la zona de exclusión del aeropuerto de Dublín | no confirmado |

El de Volkel cambia porque la presencia pasa a confirmada (la Koninklijke Luchtmacht actúa); los
de Múnich (00116) y Lieja (00092) salen de la ficha que se volvió a extraer al separar sus noches.
Bardufoss (EODI-2025-00013), Alta (EODI-2025-00054), Hannover (EODI-2025-00001), Múnich
(EODI-2025-00012 y 00082) y Lanzarote (EODI-2025-00399) conservan su titular, que ya afirmaba el
dron: la detención, la policía que acude, los vuelos desviados o el cierre por dron lo confirman (PR
#83, #85 y #86). Vilna (EODI-2025-00112, globos) y Luxemburgo (EODI-2026-00048, «potenziell größerer
Drohnen») siguen sin el dron confirmado. En la ficha, la
etiqueta «Estado» se muestra ahora como «Estado del suceso»; «Presencia de dron» sigue igual.

## 3. EODI-2025-00092 y las noches de Lieja

Las citas guardadas de EODI-2025-00092 contaban dos cierres: el del sábado 8 de noviembre de 2025
hacia las 19:00 («Daraufhin wurde der Betrieb eingestellt», publicado el domingo por la mañana
sobre el «Samstag») y el del domingo 9 por la noche («ce dimanche soir», «Vliegverkeer luchthaven
Luik opnieuw stilgelegd na melding drone», 18 artículos del 9 y el 10). Con la fecha del sábado y
21 fuentes, el incidente era la fusión de dos noches.

| Incidente | Noche | Fuentes | Presencia | Titular |
| --- | --- | ---: | --- | --- |
| EODI-2025-00163 | viernes 7 de noviembre, 06:00 | 41 | confirmado | Dron avistado en el aeropuerto de Lieja interrumpe el tráfico aéreo |
| EODI-2025-00092 | sábado 8 de noviembre, 19:00-19:30 | 3 | confirmado (Skeyes) | Dron obliga a cerrar el aeropuerto de Lieja |
| EODI-2025-00408 (nuevo) | domingo 9 de noviembre, por la noche | 18 | confirmado (cierre por dron) | Cierre del aeropuerto de Lieja por avistamiento de drones |

Cómo: la repetición que separa un candidato se mide ahora desde el inicio del suceso y no desde la
primera noticia (`proceso/noticias.repeticion`): el «opnieuw» del domingo a las 19:30 está a 24 h
30 min del cierre del sábado, y el candidato se separó; las dos partes se volvieron a extraer
(los separados van delante en el extractor); y dos cierres del mismo sitio en noches distintas no
se funden nunca (`incidentes.cierres_de_noches_distintas`), tampoco si el segundo solo tiene la
fecha de publicación y sus fuentes dicen que se repite (`incidentes.repite_un_cierre_anterior`).
Las fusiones que las reglas de ahora no harían se deshacen en la recogida horaria
(`incidentes.revisar_fusiones`). Tests con el caso de Lieja en `tests/test_presencia_criterio.py`.

## 4. Fechas que no cuadran e incidentes de noches distintas en toda la base

Búsqueda automática en los incidentes activos: una fuente que dice que el suceso se repite
(«opnieuw», «de nouveau», «à nouveau», «erneut», «again», «de nuevo», «por segunda vez», «pour le
troisième jour consécutif») publicada un día o más después de la fecha del incidente, o un
incidente que empieza después de su primera fuente. Antes, 33 marcados; después, 29.

| Resultado | Incidentes |
| --- | --- |
| Dos noches en un incidente, ahora separadas | 7: Lieja (00092 y 00408), Múnich 2 y 3 de octubre de 2025 (00116 y 00342), Kleine-Brogel (00344 y 00131), Eurenco Bergerac (00256 y 00219), Moldavia 28 de noviembre (00351 y 00407), Bruselas (00005, «fermé pour la troisième fois en une semaine») y Zaventem (EODI-2026-00094, «pour le deuxième soir consécutif») |
| La palabra de repetición habla de una reapertura o de otro sitio (fecha correcta) | 15: Copenhague («åbnet igen»), Oslo («vėl atidaryti»), Karup, Aalborg («Paar dagen na Kopenhagen»), Berlín («l'Allemagne une nouvelle fois»), Malinas, bases danesas, Polonia, Rumanía, Múnich 00340, Moldavia 2026-00112, Luxemburgo («ponovno uspostavljeni»), Leipzig 2026-00391 |
| Por revisar: un cierre y su repetición la misma noche, o la repetición de otra noche | 7: Volkel 00066, Zaventem 00136 y 2026-00293, Aalborg 00228, Bruselas 00335 y 00072, Berlín 2026-00116 (§6) |
| Empieza un día después de su primera fuente | 6: 00284, 00311, 00372, 2026-00182, 2026-00229, 2026-00327 (§6) |

Lugares con cierres en noches seguidas: antes, Lieja (7 y 8 de noviembre) y Múnich (2 y 3 de
octubre), que ahora son incidentes distintos con sus noches; Lieja tiene además el del 9.

## 5. Número de incidentes

De 507 a 513 activos: 5 por separar noches (EODI-2025-00131, 00219, 00342, 00407 y 00408) y 1
nuevo de la recogida (EODI-2026-00425, Moldavia, 3 de octubre de 2026). Ninguno deja de publicarse.

Exportación para AEGIS: versión 2026.10.04 (manifiesto `fa4e9323…`), generada en el servidor con el
criterio nuevo y el origen de cada valor (presencia confirmada: oficial citado, oficial o prensa
según la fuente que la justifica); `tools/import_eodi.py` de AEGIS la importa y la activa sin
errores y sigue importando la 2026.10.03. Lo que cambiaron después #82, #83, #85 y #86 (8 titulares que repetían la duda
y 27 presencias confirmadas más) sale en la exportación semanal del lunes 5 de octubre.

## 6. Pendientes con su arreglo

| Pendiente | Arreglo |
| --- | --- |
| 7 incidentes con una fuente de repetición sin separar (Volkel 00066, Zaventem 00136 y 2026-00293, Aalborg 00228, Bruselas 00335 y 00072, Berlín 2026-00116). | Medir la repetición también con la hora de la fuente cuando el incidente tiene hora («rond middernacht opnieuw even gesloten» es la misma noche; «bereits den zweiten Abend» no) y separar solo cuando la fuente se publica después del fin de la noche del suceso. |
| 6 incidentes que empiezan un día después de su primera fuente. | Comparar la fecha con la noche local del suceso: son madrugadas que el extractor fecha al día siguiente en UTC. Corregir la fecha a la de la noche cuando la primera fuente es anterior. |
| Cierres de una pista o de parte de las operaciones que la ficha no registra como cierre (Schiphol, EODI-2025-00058: «Drones cierran una pista del aeropuerto de Ámsterdam Schiphol») siguen sin el dron confirmado. | Que el extractor registre el cierre de una pista como cierre (o la medida `cierre_espacio_aereo`) y que la frase de cierre parcial («pista», «runway», «Landebahn») cuente para `CIERRE_EN_FRASE`. |
| La presencia confirmada por un cierre o una intervención lleva la cita de la noticia que lo cuenta, no la de la autoridad, cuando la noticia no cita a nadie. | Pedir al extractor la declaración de la autoridad también cuando la noticia cuenta su actuación sin citarla («el aeropuerto cerró»), para que la ficha muestre la frase de la autoridad. |
| El cierre del domingo 9 de noviembre en Lieja (EODI-2025-00408) tiene el día y no la hora. | La fuente dice «ce dimanche soir»: que la regla de fechas admita la tarde o la noche relativa a la publicación cuando la frase nombra el día de la semana de la misma publicación. |
