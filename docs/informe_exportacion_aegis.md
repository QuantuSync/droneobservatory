# Exportación semanal para AEGIS

Fecha: 1 de octubre de 2026. PR #29 (código) y este (primera versión y comprobaciones); en AEGIS, PR #41.

Una vez por semana, el servidor de recogida genera una versión interna y completa de la base
del European Observatory of Drone Incidents, cifrada, que solo puede leer AEGIS, y la sube al
repositorio privado de datos. AEGIS la importa con su propia credencial de solo lectura
(`tools/import_eodi.py` en el repositorio de AEGIS). Con la exportación llegan tres cambios en
los datos: la presencia del dron que confirman las autoridades, el origen de cada dato y el
nivel de detalle de cada incidente.

Principio: la parte privada da a AEGIS datos de calidad. Un campo vacío es mejor que uno de
relleno, y cada valor dice de dónde sale para que AEGIS se quede solo con lo que le sirve.

## 1. Presencia del dron confirmada por una autoridad

**Regla.** Si una autoridad (gobierno, ministerio, fuerzas armadas, policía o gestor del
espacio aéreo) afirma expresamente que hubo drones, la presencia es «confirmada». También
cuando lo dice al atribuir el incidente. Antes solo la confirmaba una declaración que el
extractor clasificaba como «drones»; una confirmación del incidente que contaba los drones
(«dos drones sobrevolaron el espacio aéreo», del Ministerio del Interior de Moldavia en el
caso de referencia, EODI-2025-00247 de Chișinău) dejaba la presencia «no confirmada».

En código ([`proceso/declaraciones.py`](../proceso/declaraciones.py)): una declaración de
tipo «incidente» o «autoria» de una de esas autoridades confirma la presencia si su frase
literal nombra drones (el filtro de palabras de dron de las noticias, más las formas
declinadas que no recoge). No la confirma:

- la del aeropuerto (confirma el cierre, no el dron) ni la confirmación de un cierre que no
  nombra drones;
- la frase que duda o niega («sospecha fundada de actividad de drones», «no hemos confirmado
  ni descartado que fueran drones»), supone («si creemos ver un dron», «un objeto parecido a
  un dron») o cuenta un aviso recibido («recibimos información de que se vio un dron»);
- la de un incidente desmentido por una autoridad, ni contra un descarte expreso
  («sin_drones»), que sigue mandando.

Cada confirmación deja en el incidente una afirmación de `presencia_dron` con la fuente que
la provoca (la declaración citada), así que el cambio queda en el historial de la base con
esa fuente; nada se borra. Tests en
[`tests/test_declaraciones.py`](../tests/test_declaraciones.py): atribución que habla de
drones, confirmación del cierre sin drones que sigue «no confirmada», aeropuerto, frases que
dudan o cuentan avisos, desmentido y descarte, y la revisión de la base.

**Revisión de la base.** Las declaraciones ya guardadas se revisan con la regla nueva en cada
recogida horaria ([`proceso/presencia.py`](../proceso/presencia.py)), desde las extracciones
guardadas y sin llamar al extractor; una vez aplicada no cambia nada más. En la base del 1 de
octubre de 2026 (antes de aplicarla) cambian de «no confirmada» a «confirmada» estos 23
incidentes:

| Incidente | Título | Estado | Autoridad y declaración | Frase |
| --- | --- | --- | --- | --- |
| EODI-2025-00016 | Cuatro drones avistados sobre la base militar de Schaffen | confirmado | Burgemeester Geert Cluckers (gobierno), «incidente» | «Gisteravond zijn 4 drones gezien boven de militaire luchtmachtbasis van Schaffen (Diest).» |
| EODI-2025-00038 | Cierre temporal del espacio aéreo del aeropuerto de Oslo por avistamientos de drones | confirmado | Politiet Nordland (policia), «incidente» | «Etter en uke med mye uønsket droneaktivitet rundt flere flyplasser i både Norge og Danmark» |
| EODI-2025-00072 | Violación del espacio aéreo sobre el aeropuerto de Bruselas obliga a su cierre | notificado | serviciul belgian de control al traficului aerian (navegacion aerea), «incidente» | «în jurul orei locale 20:00, o dronă a fost observată în apropierea Aeroportului din Bruxelles» |
| EODI-2025-00080 | Cuatro drones sobre la base aérea de Kleine-Brogel de la OTAN en Bélgica | confirmado | Theo Francken (ministerio), «incidente» | «belgijski ministar obrane Theo Francken rekao da su dronovi viđeni preko noći» |
| EODI-2025-00101 | Dron avistado cerca del aeropuerto de Vilna obliga a suspender vuelos | confirmado | Policijos departamentas (policia), «incidente» | «… kam galėjo priklausyti dronas.» (la policía investiga de quién era el dron) |
| EODI-2025-00154 | Drones cierran el aeropuerto de Copenhague y desvían más de 35 vuelos | notificado | Københavns Politi (policia), «incidente» | «Lufthavnen er pt. lukket ned, og det er grundet to til tre droner, som flyver omkring lufthavnsområdet» |
| EODI-2025-00166 | Drones sobre el aeropuerto de Alta obligan a intervenir a la policía | confirmado | Politiet (policia), «incidente» | «Dronepiloten vil bli anmeldt for flyvningen, ilagt et forelegg og dronen vil bli inndratt.» |
| EODI-2025-00189 | Drones perturban el tráfico aéreo en el aeropuerto de Hannover | confirmado | Deutsche Flugsicherung (navegacion aerea), «incidente» | «An den Flughäfen Hannover und Bremen haben Drohnen in diesem Jahr bis Ende August den Flugbetrieb jeweils viermal…» |
| EODI-2025-00190 | Un dron obliga a desviar vuelos en el aeropuerto de Sevilla | confirmado | Controladores Aéreos de España (navegacion aerea), «incidente» | «El aeropuerto de Sevilla ha decretado este lunes rate cero ante la presencia de un dron en sus…» |
| EODI-2025-00204 | Dron sobrevuela el espacio aéreo de Moldavia; Rusia niega su origen | confirmado | Ministerul Afacerilor Externe al Republicii Moldova (ministerio), «incidente» | «o dronă a survolat Republica Moldova în noaptea de miercuri spre joi» |
| EODI-2025-00211 | Drones sobre la base militar de Marche-en-Famenne | notificado | Theo Francken (ministerio), «incidente» | «Boven de militaire basis van Marche-en-Famenne zijn afgelopen nacht meerdere drones gespot.» |
| EODI-2025-00228 | Drones cierran el espacio aéreo sobre Aalborg | confirmado | Flyvevåbnets afdeling for transportfly (fuerzas armadas), «incidente» | «Luftrummet over Flyvestation Aalborg er i øjeblikket lukket grundet uautoriseret droneflyvning.» |
| EODI-2025-00247 | Drones rusos sobre Chisináu cierran el espacio aéreo y desvían vuelos | atribuido | Ministerul de Interne (ministerio), «incidente» | «Ministerul de Interne, cu precizări după ce două drone au survolat spațiul aerian al RM.» |
| EODI-2025-00256 | Drones sobre la fábrica de pólvora Eurenco de Bergerac | notificado | Préfecture de la Dordogne (gobierno), «incidente» | «Un survol de drone non autorisé du site bergeracois de la société Eurenco a eu lieu, lundi 10…» |
| EODI-2025-00267 | Drones no identificados sobre el puerto de Køge | confirmado | Midt- og Vestsjællands Politi (policia), «incidente» | «nogle store droner, som har fløjet rundt derude, og som vi har været ude at undersøge» |
| EODI-2025-00271 | Drones ilegales interrumpen operaciones en el aeropuerto de Riga | confirmado | Satiksmes ministrija (ministerio), «incidente» | «pagājušajā nedēļā nelikumīgi pilotētajiem droniem Rīgas lidostas teritorijā» |
| EODI-2025-00307 | Avistamientos de drones sobre bases militares danesas | confirmado | Danish defense ministry (fuerzas armadas), «incidente» | «The Danish defense ministry confirmed drone activity was detected at Skrydstrup Air Base» |
| EODI-2026-00015 | Cierre del Aeropuerto Internacional de Iasi por alerta de dron | atribuido | Prefectul de Iasi (gobierno), «autoria» | «The drone entered Romanian territory from the Republic of Moldova» |
| EODI-2026-00057 | Drones sobre Lituania cierran el aeropuerto de Vilnius y activan la defensa aérea de la OTAN | confirmado | Lithuanian Defence Ministry (ministerio), «incidente» | «the drone entered the country's airspace from neighbouring Belarus on Wednesday and was tracked near Lentvaris» |
| EODI-2026-00088 | Drones sobre el aeropuerto de Colonia/Bonn afectan al tráfico aéreo | confirmado | Bundespolizei (policia), «incidente» | «Bis zu fünf Drohnen wurden im Bereich des Flughafens gesichtet, wie ein Sprecher der Bundespolizei mitteilte.» |
| EODI-2026-00190 | Ataque con dron en el aeropuerto de Leipzig; Alemania acusa a Rusia | notificado | Bundesregierung (gobierno), «autoria» | «Η Γερμανία δείχνει ευθέως τη Ρωσία ως υπεύθυνη για την επίθεση με drone» |
| EODI-2026-00193 | Dron no identificado atraviesa el espacio aéreo de Moldavia | confirmado | Ministerul Apărării (ministerio), «incidente» | «O dronă neidentificată a traversat în această dimineață spațiul aerian al Republicii Moldova» |
| EODI-2026-00235 | Incursiones frecuentes de drones rusos en Moldavia | confirmado | Premierul Republicii Moldova (gobierno), «incidente» | «incursiunile tot mai frecvente ale dronelor rusești pe teritoriul moldovean» |

La primera regla que se probó, solo con la frase, alcanzaba 33: se quedan fuera siete frases
que dudan o cuentan un aviso recibido (EODI-2025-00018, 2025-00073, 2025-00094,
2025-00178, 2025-00183, la de Aalborg, cuya autoridad habla de «sospecha fundada»,
2026-00040 y 2026-00055) y dos incidentes desmentidos (EODI-2025-00124 y 2025-00206). La
comprobación de que la recogida horaria los aplicó está en el apartado 7.

## 2. Qué se exporta

Una versión por semana, nombrada por la fecha UTC en que se genera (`AAAA.MM.DD`) e
inmutable, en `exportaciones/AAAA.MM.DD/` de la rama `main` del repositorio privado
`QuantuSync/droneobservatory-datos`, con la etiqueta `eodi-AAAA.MM.DD`. Código en
[`exportacion/semanal.py`](../exportacion/semanal.py) y
[`exportacion/procedencia.py`](../exportacion/procedencia.py).

| Fichero | Contenido |
| --- | --- |
| `manifiesto.json` | En claro: versión, fecha de corte (último cambio de la base), versión del esquema (1.2.0), del formato de la exportación (1.0.0), de la lógica de extracción (`ficha/5`) y del vocabulario; destinatario age; por fichero, registros, bytes, esquema y huella SHA-256 en claro y cifrado |
| `incidentes.jsonl` | Un incidente por línea con todos sus campos, públicos e internos, más `procedencia` y `nivel_detalle`. Van también los fundidos y los retirados, que lo dicen en su documento |
| `afirmaciones.jsonl` | Cada dato por fuente: las afirmaciones del extractor (con su confianza, también las que ya no están en su incidente) y lo que respalda cada fuente que no pasa por el extractor (partes de la Fuerza Aérea de Ucrania y del Ministerio de Defensa ruso, declaraciones y notas oficiales). Con la fuente, su código del Almirantazgo, si es pública o interna, su origen y el método. Ninguna fuente se filtra |
| `episodios.jsonl` | Los episodios |
| `ucrania_ataques.jsonl`, `ucrania_regiones.jsonl` | La capa de guerra, con su procedencia |
| `frecuencias.json` | Incidentes activos por categoría de objetivo, país y mes, con estado, tipo, presencia confirmada y nivel de detalle; y el sesgo de cobertura declarado |
| `descartes.jsonl` | Noticias rechazadas (última ficha sin incidente, con sus motivos), partes que no se entienden, duplicados (fusiones), fusiones no hechas por dudosas, desmentidos con su motivo y retirados |
| `vocabulario.json` | La tabla con AEGIS (apartado 4) |
| `esquema/` | `esquema/eodi/`: los JSON Schema de la base, con la marca `x-visibilidad` de cada campo; `esquema/exportacion/`: los propios de la exportación |

**Cifrado.** Todo salvo el manifiesto va comprimido con gzip y cifrado con age con la clave
pública de la base. La compresión no estaba pedida: sin ella cada versión ocupa unos 22 MB y
el repositorio crecería más de 1 GB al año; con ella, unos 2,6 MB. Es gzip sin fecha, así que
no rompe el determinismo.

**Sesgo de cobertura.** `frecuencias.json` no corrige las frecuencias: no hay una tasa de
notificación conocida por país ni por instalación con que hacerlo sin inventarla. Declara qué
cubre cada fuente (noticias de GDELT en todos los países, fuentes oficiales solo en los que se
leen, cruces de los partes de Ucrania) y su sesgo, y da por país los artículos recogidos, los
medios con dominio propio en la lista de GDELT y las fuentes oficiales leídas, para que quien
las use normalice.

**Reglas.**

- Una versión que no valida contra sus esquemas no se publica: se valida registro a registro
  antes de cifrar nada (los de la base contra `esquema/1.2.0`, los propios contra
  `esquema/exportacion/1.0.0`). Un valor sin origen también la invalida.
- Nunca se modifica una versión: si la carpeta o la etiqueta ya existen, no se sube nada.
- Salida determinista: registros y claves en orden estable y nada que dependa de la hora de
  la exportación dentro de los ficheros. Dos exportaciones de la misma base dan los mismos
  bytes en claro y las mismas huellas en claro (comprobado con la base real); las cifradas
  cambian, porque age usa una clave efímera.
- Campos internos nuevos: los documentos se exportan enteros, así que un campo nuevo del
  esquema entra sin tocar el código de la exportación, siempre que se sepa su origen. Para el
  bloque `foco_termico` de FIRMS el origen ya está previsto (`medido`, método `parser`); un
  campo nuevo sin origen deducible de sus fuentes invalida la versión hasta que se le dé uno,
  porque la calidad manda sobre la inclusión automática. FIRMS se fusionó antes que este PR:
  la primera versión ya trae `foco_termico` (apartado 7).

## 3. Origen de cada dato, sin relleno y nivel de detalle

**Origen.** Cada valor de un incidente o de un ataque lleva en `procedencia["<ruta>"]` su
`origen`, su `metodo` y las fuentes; cada afirmación lleva los suyos. El origen sale de la
tabla de fuentes:

| Fuente | origen |
| --- | --- |
| declaración de una autoridad citada por un medio (`…-declaracion-N`) | `oficial_citado` |
| interna fuera de la capa de guerra (Ministerio de Defensa ruso) | `parte` |
| autoridad o fiabilidad A (notas oficiales leídas) y canal de la Fuerza Aérea de Ucrania | `oficial` |
| noticias | `prensa` |
| foco térmico de FIRMS | `medido` |

`deducido` está en el esquema y en el vocabulario, reservado para el motor de deducción, y
hoy no se usa. Con varias fuentes, el origen del valor es el de mayor rango (medido, oficial,
oficial_citado, parte, prensa). `metodo`: `extractor` para lo que da la ficha, `parser` para
partes y notas oficiales, `regla` para lo que calcula el código (tipo, geocodificación,
duración, estado, presencia por declaraciones), que toma el origen de mayor rango de los
valores de que sale. La fecha y el lugar que salen del propio candidato de noticias (fecha del
primer artículo, lugar que nombran los titulares) son `prensa` por `regla`.

**Sin relleno.**

- Un valor que el extractor dio sin frase de origen o con confianza por debajo de 0,5 (el
  umbral de la validación) no se exporta como valor: se quita del documento y su procedencia
  dice `sin_respaldo` con la confianza y el motivo; en `afirmaciones.jsonl` el valor pasa a
  ser `"sin_respaldo"`. En la base real ningún valor vigente de un incidente está en ese
  caso, porque la validación ya los descarta al guardarlos.
- «desconocido» (ninguna fuente lo dice) se conserva y su procedencia lo marca. Los booleanos
  y listas de `pruebas`, que el esquema no deja escribir «desconocido», llevan esa marca
  cuando son el falso o la lista vacía que pone la regla sin fuentes.
- Vacío sigue queriendo decir «no procesado». Nunca se pone un valor por defecto.
- Test: `test_ningun_valor_exportado_carece_de_origen` en
  [`tests/test_procedencia.py`](../tests/test_procedencia.py), y la propia exportación falla
  si un valor no tiene origen.

**Frase de las afirmaciones.** La frase de origen está en las extracciones guardadas, no en
las afirmaciones. Las fichas más antiguas no guardaban qué noticia respaldaba cada campo, y
algunos candidatos se reagruparon después: para unas 400 afirmaciones no se encuentra ya la
extracción que las dio. Todas pasaron la validación al guardarse (frase literal en la fuente y
confianza de 0,5 o más), así que se tratan como respaldadas; la confianza se vuelve a
comprobar en todas. Las afirmaciones `objetivo_conocido` falsas que pone la reconstrucción
cuando la ficha nombra otra instalación no tienen frase: son de una regla y salen con
método `regla`.

**Nivel de detalle** (`nivel_detalle`, calculado por código; el primero que se cumple):

- **A**: trayectoria, altura o velocidad del dron con origen medido u oficial.
- **B**: hora con precisión de minuto u hora, radio del lugar de 5 km o menos y confirmación
  de origen oficial.
- **C**: confirmado con origen oficial u oficial_citado, sin la precisión de B.
- **D**: el resto, sin confirmación de una autoridad: solo prensa o solo parte.

**Esquema 1.2.0.** `procedencia` y `nivel_detalle` (en incidentes y, la procedencia, en
ataques) y `origen` y `metodo` (en afirmaciones) son campos internos del esquema; nada pasa a
la web. La base no los guarda: los calcula la exportación. La versión menor sube de 1.0.0 a
1.2.0 porque FIRMS (PR #27) ya había tomado la 1.1.0; las configuraciones escritas con una versión
anterior de la misma mayor siguen valiendo (`esquema.compatible`, la misma regla que FIRMS).

## 4. Vocabulario con AEGIS

[`configuracion/vocabulario_aegis.json`](../configuracion/vocabulario_aegis.json), versión
1.0.0, sale del código de AEGIS (commit 0615fa9): los sectores de sus emplazamientos
(`aegis/sim/sites_data/*.json`) y las clases de tamaño de dron de su simulador
(`SIZE_CLASSES` de `aegis/demo/sensors.py`: mini 249 g, phantom 1 kg e inspire 3 kg, todos
multirrotores).

| Categoría del observatorio | AEGIS | Equivalencia |
| --- | --- | --- |
| aeropuerto | aeropuerto | exacta |
| puerto | puerto | exacta |
| energia | energia (AEGIS: una termosolar; aquí también nucleares, refinerías, gas) | parcial |
| presa | agua | parcial |
| estadio | espacio_publico | parcial |
| base_militar, industrial, gubernamental, otra | — | sin equivalente |

| Clase de dron | AEGIS | Equivalencia |
| --- | --- | --- |
| multirrotor_pequeno | mini, phantom o inspire (el tamaño no se sabe) | parcial |
| ala_fija, ataque_largo_alcance, desconocido | — | sin equivalente |

Además declara los valores de origen (con su rango), método y nivel de detalle. AEGIS copia
la tabla en `tools/vocabulario_eodi.json` y un test falla si no coincide con la de la versión
importada; otro comprueba que cada valor de AEGIS que nombra existe en su código.

## 5. Servidor, temporizador y vigilancia

- `eodi-exportacion.timer`, los lunes a las 03:47 UTC, lanza `servidor/exportacion.sh` como
  `eodi`, con el mismo cerrojo que la recogida horaria (espera como mucho una hora a que
  termine la que esté en marcha). No escribe en la base, ni en el clon, ni en la rama
  `estado`, y tiene su propia unidad: si falla, la recogida horaria sigue igual. Detalle en
  [`docs/servidor.md`](servidor.md), «Exportación semanal».
- Sube con la clave de despliegue del servidor para el repositorio de datos, en un único
  push atómico de la rama y la etiqueta; si `main` avanzó a la vez, vuelve a clonar y
  reintenta.
- `estado.json` lleva `ultima_exportacion` (la hora de la última exportación correcta, del
  registro que deja la exportación) y la web lo acepta como campo opcional sin mostrarlo.
- La comprobación de salud (`recogida/salud.py`) da aparte el estado de la exportación, y el
  workflow `vigia-recogida` abre la incidencia «La exportación semanal no se genera» si pasan
  más de 8 días sin una correcta, y la cierra cuando vuelve a haberla.
- Los tests de los scripts del servidor solo corren en Linux: se pasaron también en el propio
  servidor, en una carpeta temporal (16 de 16).

## 6. Importador en AEGIS

`tools/import_eodi.py` en AEGIS: descarga una versión (por defecto la última) con la clave de
despliegue de solo lectura «aegis-lectura» (`%USERPROFILE%\.eodi\aegis_lectura_ssh`, con la
clave de host de GitHub fijada en `%USERPROFILE%\.eodi\github_known_hosts`, sin tocar la
configuración global de SSH ni de git), comprueba huellas, descifra (paquete opcional
`pyrage`, extra `eodi`, o el binario age) y deja la versión en `data/droneobservatory/`, fuera
de git, con su huella en `control.json`. Documentación en `docs/eodi.md` de AEGIS.

## 7. Primera versión, importación y fusión

**Fusión.** PR #29, fusionado el 1 de octubre de 2026 a las 10:30 UTC (f51fb8d) con el
procedimiento de `docs/fusiones.md`: fetch, rebase sobre `main`, que ya traía FIRMS (PR #27
y #28, esquema 1.1.0), con el esquema reconstruido como el 1.1.0 de FIRMS más lo de este PR
y llevado a la 1.2.0; tests y workflow otra vez sobre la rama rebasada (verde); un commit con
el autor anónimo; `git diff --name-only origin/main HEAD` sin ningún fichero de
`publicacion/`; avance rápido. Producción servía 374 incidentes antes de fusionar y 374
después (`/datos/resumen.json`).

**Servidor.** `bash servidor/reconstruir.sh` desde `main`, como pide `docs/servidor.md`
cuando cambia `instalar.sh`: instaló `eodi-exportacion.service` y su temporizador (siguiente:
lunes 5 de octubre de 2026, 03:47 UTC). La recogida que se lanzó a las 10:43 UTC, ya con el
código fusionado, aplicó la regla de presencia: «presencia del dron confirmada por
declaraciones: 23», los mismos 23 incidentes del apartado 1, cada uno con la afirmación que
nombra su declaración en el historial de la base. Las recogidas horarias siguientes (11:17 y
una lanzada a mano a las 11:31) terminaron bien y ya no cambiaron nada («0»).

**Primera versión: 2026.10.01**, lanzada a mano en el servidor a las 11:28 UTC
(`sudo systemctl start eodi-exportacion.service`): 48 s, sin esperar al cerrojo. Subida a
`exportaciones/2026.10.01/` con la etiqueta `eodi-2026.10.01`.

- Huella del manifiesto: `a97bf0d2467609ce78b6efe81602b4ad7e2430bb184c48700970879031ff28d8`.
- Fecha de corte 2026-10-01T10:47:29Z; esquema 1.2.0, formato 1.0.0, lógica `ficha/5`,
  vocabulario 1.0.0. 3,0 MB cifrados (unos 66 MB en claro).

| Fichero | Registros | Bytes en claro | Huella en claro (inicio) |
| --- | ---: | ---: | --- |
| `incidentes.jsonl` | 537 (376 activos) | 6.974.666 | `9fad5d35f3c4020a` |
| `afirmaciones.jsonl` | 47.786 | 23.166.240 | `5ed45f5a984e71b4` |
| `episodios.jsonl` | 2 | 198 | `b325ce4e00b5646f` |
| `ucrania_ataques.jsonl` | 4.601 | 16.847.847 | `fb4309aa5427146c` |
| `ucrania_regiones.jsonl` | 16.275 | 2.591.598 | `66f09df12dbde586` |
| `frecuencias.json` | 198 filas | 63.902 | `41ae65c3ef2c8c5e` |
| `descartes.jsonl` | 1.378 | 1.072.234 | `d30aa772588ddb36` |
| `vocabulario.json` | 13 entradas | 5.466 | `8be42accab636c6b` |
| `esquema/` | 14 esquemas | | |

Cifras principales:

- Incidentes activos: 376 (204 sobrevuelos, 90 incursiones, 82 interrupciones de aeropuerto;
  232 notificados, 138 confirmados, 3 atribuidos, 3 desmentidos). Presencia del dron: 201
  confirmada, 171 no confirmada, 4 descartada. EODI-2025-00247 sale con presencia
  confirmada y nivel C.
- Afirmaciones: 28.644 del Ministerio de Defensa ruso (`parte`, `parser`, fiabilidad D),
  9.359 de la Fuerza Aérea de Ucrania (`oficial`, `parser`), 9.267 de noticias (`prensa`,
  `extractor`), 486 de declaraciones citadas (`oficial_citado`, `extractor`), 23 de la regla
  de presencia (`oficial_citado`, `regla`) y 7 de la reconstrucción (`prensa`, `regla`).
  Ninguna sin respaldo. La base no tiene hoy ninguna fuente de fiabilidad E o F: la
  exportación las llevaría sin filtrar (lo prueban los tests), pero en esta versión no hay.
- Descartes: 646 duplicados, 641 noticias rechazadas, 65 retirados, 22 partes que no se
  entienden y 4 desmentidos; ninguna fusión dudosa pendiente.
- Capa de Ucrania: de sus valores, 62.726 de origen `parte`, 18.615 `oficial` y 24
  `medido` (focos térmicos de FIRMS en regiones).
- FIRMS se fusionó antes que este PR y su bloque `foco_termico` entra en la exportación sin
  tocar código, como `medido`: 46 incidentes y 24 valores de la capa de Ucrania lo llevan.

**Completitud** de la versión exportada (no de la base): `python -m exportacion.completitud`
sobre los ficheros cifrados de la versión, con las huellas comprobadas. Porcentaje de los 376
incidentes activos con el campo lleno y, de esos, cuántos por origen. «desconocido», el falso
o la lista vacía de `pruebas` sin fuentes y lo que queda sin respaldo no cuentan como llenos.
`foco_termico` cuenta cualquier resultado del cruce (detectado o no).

Versión 2026.10.01: 537 incidentes exportados, 376 activos (ni fundidos ni retirados); los porcentajes son sobre los activos.

| Campo | Lleno | medido | oficial | oficial_citado | parte | prensa | Sin respaldo |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `atribucion` | 0.8 % (3) | 0 | 0 | 3 | 0 | 0 | 0 |
| `consecuencias.cierre.minutos` | 9.0 % (34) | 0 | 0 | 0 | 0 | 34 | 0 |
| `consecuencias.danos` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `consecuencias.fallecidos` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `consecuencias.heridos` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `consecuencias.vuelos_cancelados` | 1.3 % (5) | 0 | 0 | 0 | 0 | 5 | 0 |
| `consecuencias.vuelos_desviados` | 7.7 % (29) | 0 | 0 | 0 | 0 | 29 | 0 |
| `consecuencias.vuelos_retrasados` | 5.1 % (19) | 0 | 0 | 0 | 0 | 19 | 0 |
| `drones.altura_m` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.clase` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.luces` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.modelo` | 6.6 % (25) | 0 | 0 | 0 | 0 | 25 | 0 |
| `drones.numero` | 75.3 % (283) | 0 | 1 | 0 | 0 | 282 | 0 |
| `drones.patron` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.trayectoria` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `drones.velocidad_ms` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `estado` | 100.0 % (376) | 0 | 1 | 144 | 0 | 231 | 0 |
| `foco_termico` | 12.2 % (46) | 46 | 0 | 0 | 0 | 0 | 0 |
| `lugar.geocodificacion` | 66.5 % (250) | 0 | 0 | 0 | 0 | 250 | 0 |
| `lugar.localidad` | 18.4 % (69) | 0 | 0 | 0 | 0 | 69 | 0 |
| `lugar.nivel` | 100.0 % (376) | 0 | 1 | 0 | 0 | 375 | 0 |
| `lugar.nuts2` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `lugar.pais` | 100.0 % (376) | 0 | 1 | 0 | 0 | 375 | 0 |
| `lugar.punto` | 66.5 % (250) | 0 | 0 | 0 | 0 | 250 | 0 |
| `lugar.radio_km` | 66.5 % (250) | 0 | 0 | 0 | 0 | 250 | 0 |
| `lugar.region` | 71.0 % (267) | 0 | 0 | 0 | 0 | 267 | 0 |
| `lugar.suceso` | 92.3 % (347) | 0 | 0 | 0 | 0 | 347 | 0 |
| `objetivo.categoria` | 67.8 % (255) | 0 | 0 | 0 | 0 | 255 | 0 |
| `objetivo.nombre` | 67.3 % (253) | 0 | 0 | 0 | 0 | 253 | 0 |
| `objetivo.oaci` | 41.5 % (156) | 0 | 0 | 0 | 0 | 156 | 0 |
| `objetivo.uso` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `origen_demostrado_por` | 23.9 % (90) | 0 | 1 | 52 | 0 | 37 | 0 |
| `presencia_dron` | 100.0 % (376) | 0 | 1 | 45 | 0 | 330 | 0 |
| `pruebas.dron_estatal` | 60.1 % (226) | 0 | 1 | 0 | 0 | 225 | 0 |
| `pruebas.entrada_exterior` | 38.8 % (146) | 0 | 1 | 0 | 0 | 145 | 0 |
| `pruebas.evidencia` | 27.7 % (104) | 0 | 1 | 0 | 0 | 103 | 0 |
| `respuesta.deteccion` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `respuesta.medidas` | 34.3 % (129) | 0 | 0 | 0 | 0 | 129 | 0 |
| `respuesta.resultado_contramedidas` | 0.0 % (0) | 0 | 0 | 0 | 0 | 0 | 0 |
| `tiempo.duracion_min` | 11.4 % (43) | 0 | 0 | 0 | 0 | 43 | 0 |
| `tiempo.fin` | 11.7 % (44) | 0 | 1 | 0 | 0 | 43 | 0 |
| `tiempo.inicio` | 100.0 % (376) | 0 | 1 | 0 | 0 | 375 | 0 |
| `tipo` | 100.0 % (376) | 0 | 1 | 6 | 0 | 369 | 0 |

| Nivel de detalle | Incidentes | % |
| --- | ---: | ---: |
| A | 0 | 0.0 % |
| B | 0 | 0.0 % |
| C | 141 | 37.5 % |
| D | 235 | 62.5 % |

Lo que dice la tabla para decidir fuentes nuevas: casi todo es `prensa`; las autoridades
aparecen en el estado (144 confirmaciones citadas por la prensa y ninguna leída
directamente) y en la presencia; no hay ningún incidente de nivel A ni B porque ninguna
fuente leída directamente confirma incidentes fuera de la capa de guerra y ninguna da
trayectoria, altura o velocidad; las consecuencias humanas, los daños, el uso del objetivo y
los campos de detección y contramedidas están vacíos. Las fuentes que más subirían el nivel
son las que confirman directamente (notas oficiales leídas, que hoy no enlazan ningún
incidente) y las que miden (tráfico aéreo para cierres y desvíos; datos de radar o de
rastreo, que no son públicos).

**Importación en AEGIS.** PR #41 de AEGIS, fusionado como un commit con el autor anónimo
(0c332c7) tras pasar la suite completa en local (784 tests; AEGIS no tiene minutos de
GitHub Actions). Desde `C:\dev\aegis-importador`, `python tools/import_eodi.py` importó la
2026.10.01 con la misma huella del manifiesto (`a97bf0d2…`) y este resumen: 376 incidentes
activos; por emplazamiento de AEGIS, 165 aeropuerto, 7 energia, 3 espacio_publico, 80 sin
equivalente (72 «otra» y 8 bases militares) y 121 sin objetivo; por nivel de detalle, 141 C y
235 D. La primera importación dio otra huella del manifiesto: git en Windows convertía los
finales de línea del manifiesto al sacarlo (`core.autocrlf`). El importador desactiva esa
conversión solo para su clon y un test lo comprueba; se volvió a importar desde cero con la
huella correcta. El clon habitual de AEGIS (`C:\dev\aegis`) estaba limpio y en `main`: se
actualizó por avance rápido, se instaló el extra `eodi` en su entorno y la importación dio la
misma versión y la misma huella.

**Estado y vigilancia.** La recogida de las 11:17 se lanzó antes de la primera exportación
y publicó `ultima_exportacion: null`; para que la vigilancia no abriera una incidencia
falsa, se lanzó una recogida más a las 11:31, que publicó `ultima_exportacion:
2026-10-01T11:28Z`. `python -m recogida.salud` da las dos comprobaciones en verde.

## 8. Qué faltaría en AEGIS para cada uso

Sin construir nada; lo que habría que añadir para usar la versión importada en cada caso.

- **Biblioteca de escenarios reales.** Un traductor de incidente a escenario
  (`scenarios/*.yaml`): emplazamiento de AEGIS por categoría (hoy hay uno por sector y cinco
  sectores; las bases militares, la industria y las sedes de gobierno no tienen ninguno),
  número de drones, clase de tamaño y comportamiento. El observatorio casi nunca da
  trayectoria, altura ni velocidad, así que el movimiento tendría que salir de los
  comportamientos sintéticos de `aegis/sim/behaviors.py` con la hora, la duración y el número
  reales; y una regla de selección por nivel de detalle fijada como las semillas.
- **Perfil de amenaza por tipo de instalación.** Un análisis fuera del núcleo que agregue
  `frecuencias.json` por sector de AEGIS con el vocabulario, con intervalos y con la
  corrección de cobertura que se decida (el observatorio no corrige: da con qué); faltan en
  AEGIS sectores para lo que no tiene equivalente y una clase de ala fija.
- **Cobertura del kit frente a la amenaza real.** Cruzar la capa de cobertura
  (`aegis/demo/coverage.py`) con los lugares y radios reales de los incidentes de cada
  emplazamiento; falta un emplazamiento con incidentes reales cerca (los cinco de AEGIS están
  en España, con pocos incidentes en el observatorio) y clases de ala fija y de largo alcance
  en el modelo de sensores, cuyas firmas hoy son solo de multirrotores.
- **Planificación de despliegue y enjambres a partir de las oleadas de Ucrania.** Leer
  `ucrania_ataques.jsonl` (lanzados por tipo, horas de llegada, duración de la oleada,
  derribados, regiones) para dimensionar enjambres en `tools/enjambre.py`; faltan una clase
  tipo Shahed o Gerbera (ala fija, otra velocidad y otra firma radar), escalas de cientos de
  blancos en lugar de siete, y separar las cifras ucranianas (`oficial`) de las rusas
  (`parte`), que la procedencia ya distingue. El alcance de AEGIS (detección, no respuesta) se
  mantiene: esto serviría para medir detección y saturación.
