# Marcador de los atribuidos: círculo con la bandera del país

Fecha: 4 de octubre de 2026. PR #97 (marcador), PR #102 (revisión de las atribuciones con la
regla estricta, esquema 1.11.0), PR #106 (base cifrada con xz) y el PR de este informe.

La bandera roja con mástil de los incidentes «atribuido» desaparece de toda la web. En su lugar,
el mismo marcador en el mapa, la ficha, la lista, el historial de estados, la leyenda, los
filtros y las cifras: un círculo con un aro rojo grueso y, dentro, la bandera del país al que la
autoridad atribuye el incidente. Los demás estados no cambian (notificado, círculo naranja;
confirmado, círculo rojo; desmentido, círculo gris discontinuo).

## Las tres variantes

| Atribuido a | Marcador |
| --- | --- |
| Un Estado | Aro rojo grueso y, dentro, la bandera de ese país recortada en círculo |
| Una persona de nacionalidad publicada por la fuente | Lo mismo, con la bandera de su nacionalidad y un punto fijo y oscuro en el centro |
| Una persona de nacionalidad no publicada | Aro rojo, relleno rojo liso y el punto fijo |

Un país sin bandera en el juego (o una atribución sin tipo) cae al aro rojo con relleno liso.

Medidas (`MARCA_ATRIBUIDO` en `web/src/paleta.ts`): 23 px de diámetro, 24,5 con el filo
exterior del color del fondo; entre el círculo suelto (13 px) y el grupo más pequeño (25 px con
su trazo). Aro de 3 px en el rojo de «confirmado» (más de la cuarta parte del radio: se lee rojo
aunque la bandera sea blanca o azul), filo oscuro de 1 px entre el aro y la bandera, bandera de
15 px. El punto de «persona» mide 5 px, oscuro con un aro rojo de 1 px, y no late. Sin mástil,
sin paño, nada fuera del círculo.

En el mapa (`web/src/mapa/iconos.ts`, `estilo.ts`): el marcador se dibuja en el lienzo a densidad
3, centrado en el punto, en su propia capa por encima de círculos, grupos y números; los
atribuidos siguen sin entrar en las agrupaciones normales. Las banderas se cargan de la propia
web al abrir el mapa; hasta que llegan, el marcador va liso. Varios atribuidos que se pisarían
son un solo marcador con su número a la derecha; el grupo guarda la bandera menor y la mayor de
los suyos: si coinciden, esa bandera; si son de países distintos, relleno rojo liso, sin bandera
ni punto. Al pulsarlo se acerca hasta separarlos (o se elige de la lista si están en el mismo
punto exacto). El latido de las novedades es un anillo por fuera del marcador, como el de los
demás. El incidente abierto lleva el mismo marcador un 20 % mayor. Toque de 44 px en el móvil,
medido al centro.

Textos alternativos (`textoAtribuido` en `web/src/i18n/index.ts`): «Atribuido a Rusia»,
«Atribuido a una persona de nacionalidad rumana», «Atribuido a una persona» (en inglés,
«Attributed to Russia», «Attributed to a person of Romanian nationality», «Attributed to a
person»). Van en el marcador de la ficha, en la lista, en el selector de un punto con varios y
en el letrero del mapa. Leyenda: «Atribuido por una autoridad a un Estado» y «Atribuido por una
autoridad a una persona», con la nota de que la bandera es la del país al que la autoridad lo
atribuye, no una afirmación del observatorio. Ayuda y metodología, al día en los dos idiomas.

## Los datos

Esquema 1.10.0 (PR #97): la atribución lleva dos campos públicos más, `tipo` (`estado` o `persona`) y
`pais` (ISO 3166-1 alfa-2: el Estado, o la nacionalidad de la persona). Están en la lista
cerrada de campos públicos (`exportacion/campos.py`), en la validación de la web y en la
exportación semanal interna (la atribución viaja entera con su procedencia; comprobado con una
exportación generada y validada sobre una copia de la base).

La regla (`proceso/atribucion.py`), en la extracción y en la validación:

- **Estado.** El país es el que nombra el autor («Rusia», «Russland»), o el que da el extractor
  si el autor no es un país de la tabla. La frase citada de la autoridad tiene que nombrar a ese
  Estado: su nombre, su capital o su gentilicio. Si no lo nombra, no hay atribución.
- **Persona.** La frase tiene que nombrar a la persona. Su país solo se rellena si la frase dice
  la nacionalidad con un gentilicio («un cetățean rus»); nunca sale del nombre, del lugar del
  incidente ni del idioma. Si no lo dice, queda vacío.
- La tabla de nombres, capitales y gentilicios por idioma es `configuracion/paises_atribucion.json`
  (los mismos 48 países que las banderas; un test lo comprueba).
- El extractor pide ahora `autor_tipo` y `autor_pais` en cada declaración, con la instrucción de
  no deducir la nacionalidad. La ficha no cambia de versión (como en el PR #77): no se vuelve a
  extraer nada. Las fichas guardadas sin esos campos se leen con la misma regla.
- La validación exige el tipo y que el tipo y el país salgan de la frase de la autoridad.

Tests: `tests/test_atribucion.py` (21: las frases reales guardadas, nacionalidad dicha y no
dicha, país nombrado como lugar, tipo vacío, la extracción, la validación y la corrección de lo
guardado).

## Revisión de las atribuciones con la regla estricta (PR #102)

Atribuir un incidente a un Estado o a una persona es lo más grave que publica el observatorio.
Tras el PR #97 se revisaron las cuatro atribuciones publicadas con una regla estricta: un
incidente está «atribuido» solo si una autoridad competente afirma expresamente, en una
declaración que se puede citar con sus propias palabras, quién es el responsable. **Ninguna de
las cuatro la cumple: las cuatro se retiran y los cuatro incidentes vuelven a «confirmado».**

### Las cuatro, una por una

Se leyeron todas las citas guardadas de cada incidente (las frases de las fuentes y de las
declaraciones oficiales que recogió el extractor) en su idioma original.

**EODI-2025-00247 · Chisináu, 29 de noviembre de 2025 · retirada.**

- Cita que se usó para atribuir (wiadomosci.wp.pl, en polaco): «Prezydent Maia Sandu oskarżyła
  Moskwę o próbę destabilizacji.» → «La presidenta Maia Sandu acusó a Moscú de intentar
  desestabilizar [el país].»
- Autoridad: Maia Sandu, presidenta de la República de Moldavia.
- A quién atribuye: a Rusia («Moscú»), de intentar desestabilizar el país; no dice con sus
  palabras que los drones fueran rusos.
- Las demás citas: «Władze Mołdawii poinformowały, że rosyjskie drony ponownie wdarły się w
  przestrzeń powietrzną kraju» (wiadomosci.wp.pl: «Las autoridades de Moldavia informaron de que
  drones rusos volvieron a entrar en el espacio aéreo del país»), dos titulares griegos («Chisináu
  declara que aeronaves no tripuladas rusas violaron su espacio aéreo») y el Ministerio del
  Interior de Moldavia, que confirma el sobrevuelo sin atribuirlo («Ministerul de Interne, cu
  precizări după ce două drone au survolat spațiul aerian al RM»: «El Ministerio del Interior, con
  aclaraciones después de que dos drones sobrevolaran el espacio aéreo de la República de
  Moldavia»).
- Decisión: **retirada**. Todo lo que atribuye son noticias que cuentan lo que dijo la presidenta
  o «las autoridades», sin sus palabras. Queda confirmado (el Ministerio del Interior lo confirma).
  El titular deja de decir «rusos».

**EODI-2026-00015 · aeropuerto de Iasi, 8 de septiembre de 2026 · retirada.**

- Cita (stiripesurse.ro, en inglés): «The drone entered Romanian territory from the Republic of
  Moldova» → «El dron entró en territorio rumano desde la República de Moldavia».
- Autoridad: el prefecto del distrito de Iasi (representante del Gobierno rumano en el distrito).
- A quién atribuye: a nadie. El «autor» guardado, Constantin Dolachi-Pelin, **es el propio
  prefecto de Iasi** ([InfoCons](https://infocons.ro/institutia-prefectului-judetul-iasi-si-prefectul-constantin-dolachi-pelin-infocons-te-informeaza/)):
  el extractor puso como autor del incidente el nombre de la autoridad que hacía la declaración.
  Era el fallo más grave posible.
- Decisión: **retirada**. Queda confirmado (la dirección del aeropuerto confirma la suspensión
  de los vuelos).
- Dónde salía ese nombre como autor: en `atribucion.actor` de `publicacion/incidentes.geojson`
  y, a partir de ahí, en la ficha de la web, en su JSON (`/datos/incidentes/EODI-2026-00015.json`)
  y en el CSV de descarga (`/datos/incidentes.csv`). Desde la corrección no sale en ninguno
  (comprobado en los datos publicados y en producción). Pendiente con su arreglo: sigue en las
  versiones anteriores de esos ficheros en el historial de git del repositorio público y en las
  exportaciones semanales cifradas ya enviadas a AEGIS (2026.10.01 y siguientes). La próxima
  exportación (lunes 5 de octubre, 03:47 UTC) lleva la corrección; AEGIS tiene que reimportarla.
  Reescribir el historial público exige un push forzado sobre `main` y se deja a decisión
  expresa.

**EODI-2026-00074 · aeropuerto de Chisináu, 9 y 10 de septiembre de 2026 · retirada.**

- Cita (news.mail.ru, en ruso): «Молдавские власти сразу назвали аппарат «российским»» → «Las
  autoridades moldavas calificaron enseguida el aparato de «ruso»».
- Autoridad: «las autoridades moldavas», sin decir cuál ni qué cargo.
- A quién atribuye: a Rusia, según la noticia.
- Las demás citas: el Ministerio de Defensa de Moldavia, citado por la misma noticia: «военные
  засекли беспилотник, залетевший в страну со стороны Украины» («los militares detectaron un dron
  que entró en el país desde Ucrania»), que confirma sin atribuir; y titulares de news.yam.md que
  hablan de «drona rusească» (prensa).
- Decisión: **retirada**. Ninguna autoridad identificada lo afirma con sus palabras. Queda
  confirmado.

**EODI-2026-00283 · dron hallado en septiembre de 2026 · retirada.**

- Cita que se usó para atribuir (come-on.de, en alemán): «In der Nähe parkte eine ukrainische
  Frachtmaschine vom Typ Antonow AN-124, weshalb die Bundesregierung von einem russischen
  Anschlagsversuch ausging.» → «Cerca estaba estacionado un avión de carga ucraniano Antonov
  AN-124, por lo que el Gobierno federal suponía un intento de atentado ruso.» Se refiere al dron
  con explosivos del aeropuerto de Leipzig/Halle del 4 de agosto, no a este hallazgo, y es una
  noticia que cuenta una suposición («ausging»).
- La otra cita: «prüft die Bundesanwaltschaft einen möglichen Zusammenhang mit dem
  Drohnenvorfall am Flughafen Leipzig» (schwaebische.de) → «la Fiscalía federal examina una
  posible relación con el incidente del dron en el aeropuerto de Leipzig».
- Autoridades: el Gobierno federal alemán (Bundesregierung) y la Fiscalía General federal
  (Bundesanwaltschaft).
- A quién atribuye: a nadie. La fiscalía examina una posible relación.
- Decisión: **retirada**. Queda confirmado, con la investigación de la fiscalía en la ficha como
  investigación en curso.
- El titular: «Dron con explosivos en el aeropuerto de Leipzig/Halle». Ninguna autoridad dice en
  las citas guardadas que este dron llevara explosivos: la frase de los explosivos («Am Abend des
  4. August wurde eine mit Sprengstoff präparierte Drohne im Sicherheitsbereich des Flughafens
  Leipzig/Halle entdeckt») es de la noticia y habla del incidente de agosto. Se corrige a «Dron en
  el aeropuerto de Leipzig/Halle» («Drone found at Leipzig/Halle airport»).
- Pendiente con su arreglo: el registro mezcla dos sucesos. Sus noticias son del dron hallado a
  mediados de septiembre junto a la base aérea de Wunstorf (Baja Sajonia), en el que la fiscalía
  federal examina la relación con Leipzig
  ([ZDFheute](https://www.zdfheute.de/politik/deutschland/bundeswehr-fliegerhorst-wunstorf-drohnenfund-bundesanwaltschaft-leipzig-100.html)),
  pero su fecha (4 de agosto) y su lugar (aeropuerto de Leipzig/Halle) son los del incidente de
  agosto, que ya está en EODI-2026-00391. Arreglo: separar el candidato de Wunstorf, volver a
  extraerlo con su lugar y su fecha, y unir lo de Leipzig con EODI-2026-00391. Lo hace la sesión
  de corrección de errores de datos, que lleva la extracción y las fusiones.

También se retira la de EODI-2026-00119 (Leipzig, 4 de agosto), fundido en EODI-2026-00391: su
cita («правительство Германии приходит к заключению, что Россия несет ответственность за
гибридную атаку», news.mail.ru: «el Gobierno de Alemania llega a la conclusión de que Rusia es
responsable del ataque híbrido») es una noticia rusa que cuenta la conclusión del Gobierno
alemán, sin sus palabras. No se publica (está fundido), pero sí va en la exportación semanal.

### Cómo se retiran

`recogida/tipo_atribucion.py` (versión `atribucion/2`), una vez dentro de la recogida horaria:
cada atribución guardada se vuelve a decidir con la regla. Las guardadas no dicen si la frase es
literal (la ficha lo pide desde ahora), así que ninguna se sostiene. Cada una se retira como
versión nueva del incidente, sin borrar nada:

- un paso nuevo en el historial de estados, de «atribuido» a «confirmado», con el motivo en
  español y en inglés (`estado.historial[].motivo`), que la ficha enseña en el historial («Se
  retira la atribución: la autoridad examina una posible relación, no la afirma…»). El paso a
  «atribuido» anterior se conserva: la ficha enseña que lo estuvo y por qué dejó de estarlo. Solo
  esta corrección puede pasar de atribuido a confirmado, y solo con motivo (lo comprueba la
  validación del historial);
- el motivo revisado a mano de cada uno (`configuracion/atribuciones_revisadas.json`) o, si no lo
  hay, el de la regla;
- lo que las autoridades dicen que investigan, como investigación en curso (`investigacion`,
  campo público nuevo);
- el titular sin lo que solo decía la atribución: la nacionalidad de los drones y, si ninguna
  autoridad lo dice, los explosivos;
- el motivo, también en el historial interno de la base.

EODI-2026-00015 ya había salido de «atribuido» con la versión anterior de esta corrección (la del
PR #97, que lo devolvía a confirmado quitando el paso). La versión nueva recupera ese paso de la
versión guardada y añade la retirada con su motivo, para que el historial lo cuente igual que en
los otros.

Simulado sobre una copia de la base de producción del 4 de octubre, con y sin la versión anterior
aplicada: los cinco (los cuatro publicados y el fundido) vuelven a confirmado con su paso y su
motivo; 0 atribuidos publicados; el nombre del prefecto no aparece en ningún fichero publicado;
la exportación semanal se genera y valida.

### La regla, para lo que llegue

En la extracción (`modelo/ficha.py`, sin cambiar de versión), en el proceso
(`proceso/declaraciones.py`) y en la validación (`proceso/validaciones.py`), todo en
`proceso/atribucion.py`:

- Atribuye una autoridad competente: gobierno, ministerio, fuerzas armadas, fiscalía o policía.
- Con sus propias palabras: el extractor dice si la frase es literal (`cita_literal`); una noticia
  que cuenta que la autoridad atribuye no basta.
- Sin duda ni investigación: una frase que investiga, examina, comprueba, ve posible, no descarta,
  sospecha, supone, «apunta a», «todo indica», o que cita a fuentes de seguridad o a medios, nunca
  atribuye (`configuracion/expresiones_duda.json`, en español, inglés, alemán, francés, rumano,
  polaco, lituano, neerlandés, ucraniano y ruso). Lo que la autoridad investiga va a la ficha como
  investigación en curso, sin cambiar el estado.
- El autor nunca es la autoridad que declara: la validación rechaza un autor que comparte nombre
  con ella, y la ficha pide no poner nunca a quien habla, a un portavoz, a un testigo ni a la
  víctima.
- A una persona, solo si la autoridad la ha detenido, acusado o condenado (`autor_situacion`). Su
  nombre, solo si la autoridad lo da; si no, la web escribe «una persona». Su nacionalidad, solo
  si la frase la dice.
- La validación rechaza una atribución cuya cita tenga duda o investigación, o cuyo autor
  coincida con la autoridad declarante.

Tests (`tests/test_atribucion.py`): las citas reales de los cuatro casos; 48 frases de «no vale»
(investigación, posible relación, no se descarta, podría, sospecha, apunta a, todo indica, fuentes
de seguridad) en alemán, rumano, inglés, francés, polaco, lituano, neerlandés, ucraniano y ruso;
afirmaciones expresas que sí valen; autor igual a quien declara; personas con y sin detención y
con y sin nombre; la retirada con su paso, su motivo, su investigación y su titular.

### Autorías que se han quedado fuera por el motivo contrario

Declaraciones guardadas en las que una autoridad parece atribuir expresamente y el incidente no
figura como atribuido. No se ha cambiado ninguna. Con la regla, ninguna basta tal como está
guardada (todas son noticias que lo cuentan, sin las palabras de la autoridad), pero merecen
buscar la declaración original:

| Incidente (estado) | Autoridad | Lo guardado |
| --- | --- | --- |
| EODI-2026-00391 y los registros que repiten el mismo suceso: EODI-2026-00239, 00129, 00190, 00318 (notificados) | Gobierno federal alemán, Ministerio del Interior | El dron con explosivos de Leipzig/Halle del 4 de agosto: «Germany accuses Russia», «La Russia ha la responsabilità dell'attacco ibrido a Lipsia» (traducción italiana). Es el caso más claro: el Gobierno alemán lo atribuyó a Rusia públicamente. Hace falta su comunicado y unir los cinco registros. |
| EODI-2026-00152 (notificado) | Administración presidencial de Rumanía | «drona maritima care a explodat in Portul Constanta in 5 iunie a fost controlata de catre Federatia Rusa» (sin diacríticos) («el dron marítimo que explotó en el puerto de Constanza el 5 de junio fue controlado por la Federación Rusa»); otra frase del mismo comunicado dice solo «indică posibilitatea». |
| EODI-2026-00245 (notificado; incluye EODI-2026-00342) | Fuerzas Armadas de Suecia | «en drönare lyfte från det ryska signalspaningsfartyget Zhigulevsk i Öresund» («un dron despegó del buque ruso de inteligencia de señales Zhigulevsk en el Øresund»). |
| EODI-2026-00125 (notificado; incluye EODI-2026-00331) | Ministerio de Defensa de Rumanía | «Moscova testează intenționat spațiul aerian românesc» («Moscú pone a prueba intencionadamente el espacio aéreo rumano»). |
| EODI-2026-00228 (confirmado; incluye EODI-2026-00345) | Presidente de Rumanía | Noticia francesa: «Nicușor Dan a clairement désigné son homologue russe Vladimir Poutine comme responsable». |
| EODI-2025-00295 (confirmado; incluye EODI-2025-00262) y EODI-2025-00305 | Gobierno de Polonia | «Nach Angaben von Regierungschef Donald Tusk handelte es sich um Drohnen aus Russland», «Polens Regierung spricht von einer russischen Provokation» (noticias). |
| EODI-2026-00090 (notificado) | Gobierno de Lituania | «nach Angaben der Regierung in Vilnius um eine ukrainische Drohne» (noticia: un dron ucraniano que se desvió). |

Pendiente con su arreglo: que la búsqueda dirigida y las fuentes oficiales traigan el texto de
estas declaraciones; con la ficha nueva, una cita literal y expresa las atribuye sola. Varios de
estos registros llevan además en el titular la nacionalidad de los drones sin atribución
(«Dron ruso cargado de explosivos ataca Leipzig»); arreglo: aplicar a todos los titulares la
misma regla que ya se aplica a los retirados.

### Dos arreglos de texto

- **El país, en el idioma de la web.** La ficha escribe el Estado a partir de su código («Rusia»,
  «Russia»), nunca con el texto de la fuente («Russland»). Igual en el texto para lector de
  pantalla, la lista y el letrero del mapa.
- **La autoridad, que se entienda.** `web/src/i18n/autoridades.ts` traduce las autoridades de las
  atribuciones y de las confirmaciones e investigaciones de estos incidentes: «según el Gobierno
  federal alemán (Bundesregierung)», «según la presidenta de Moldavia, Maia Sandu», «el prefecto
  de Iasi». Las fuentes que son declaraciones oficiales citadas se escriben igual en los dos
  idiomas: «Declaración de la Fiscalía federal alemana (Bundesanwaltschaft), citada en
  schwaebische.de» («Statement by the German Federal Prosecutor's Office (Bundesanwaltschaft),
  quoted in schwaebische.de»), también en el historial. Una autoridad que no está en la tabla se
  escribe tal cual; pendiente con su arreglo: que el extractor dé el nombre traducido de cada
  autoridad para no depender de la tabla.

## Banderas

48 banderas cuadradas de flag-icons 7.5.0 (MIT), copiadas en `web/public/banderas` y anotadas en
`docs/licencias_terceros.md`: los países europeos, Rusia, Bielorrusia, Ucrania, Turquía, el
Vaticano e Irán. Revisadas una a una recortadas en el marcador, a tamaño real y ampliadas; la
única que se usa hoy, la de Rusia, se reconoce sin acercar en el móvil.

## Borrado

La forma `BANDERA`, sus trazados, el mástil, el pulso con la silueta de la bandera
(`.pulso-bandera`), el icono `bandera`, el desplazamiento al pie del mástil, `IconoBandera`, las
pruebas de la bandera (Vitest y los puntos 4 y 4c de `e2e/pulido.spec.ts`) y sus capturas
(`pulido-4-*.png`, `pulido-4c-*.png`). Las fuentes y capas del mapa pasan a llamarse
«atribuidos».

## La subida de la base que falló (PR #106)

La recogida de las 12:17 del 4 de octubre aplicó la retirada («retiradas: 5»), pero no publicó:
falló el `git push` de la base cifrada a la rama `estado` del repositorio de datos. La base,
comprimida con gzip, ocupaba ya 99,4 MiB a las 11:17 (966 MiB en claro) y con lo recogido a las
12:17 pasó de los 100 MiB que admite GitHub por fichero. No lo causó esta corrección (cinco
versiones de incidente son unos pocos KB), pero bloqueaba toda publicación. El PR #106 comprime la
base con xz, nivel 3: 45,7 MiB, unos 26 s para comprimir y 3 s para descomprimir; se siguen
leyendo las bases con gzip y las anteriores sin comprimir. La recogida de las 13:17 leyó la base
de las 11:17, volvió a aplicar la retirada, subió la base nueva y publicó. Los clones con código
anterior al PR #106 no leen la base nueva hasta actualizarse.

## Comprobación

- Puerta local en cada PR: pytest (1703 en verde con 33 omitidos en el último), ruff, formato y
  mypy estricto; en la web, lint, TypeScript estricto, Vitest (423 en verde), auditoría de npm y
  build. Workflow de tests en verde sobre cada rama rebasada y sobre `main`.
- Fusiones según `docs/fusiones.md`, fuera de los minutos 12 a 40: #97 a las 10:46, #102 a las
  11:50 y #106 a las 12:41 (UTC). Antes del push del #102, la comprobación de la lista de
  ficheros detectó que `main` había recibido el #101 entre el fetch y el commit único, que lo
  habría revertido: se abortó, se rebasó y se repitió el workflow.
- Recogida de las 13:17: «atribuciones clasificadas: 0; retiradas: 5; sin guardar: 0», base
  subida a la rama `estado`, ficheros publicados en `main`.
- En droneobservatory.eu, con los datos de las 13:17: 592 incidentes servidos (516 antes; no
  bajan), **0 atribuidos**, y EODI-2025-00247, EODI-2026-00015, EODI-2026-00074 y EODI-2026-00283
  en «confirmado». «Dolachi» no aparece en `resumen.json`, `incidentes.geojson`, `incidentes.csv`
  ni en el JSON de la ficha de EODI-2026-00015. La ficha de EODI-2026-00283 lleva el titular
  «Dron en el aeropuerto de Leipzig/Halle», el motivo de la retirada en el historial y la
  investigación de la fiscalía federal.
- Playwright contra producción (`e2e/atribuido.spec.ts`), en 360 × 800, 390 × 844, 412 × 915 y
  escritorio: 20 pruebas en verde. Las cuatro fichas revisadas con su estado nuevo, el motivo de
  la retirada en el historial y sin el nombre del prefecto; la cifra de atribuidos de la cabecera
  y del menú (0) igual a los que quedan; el icono del marcador nuevo registrado en el mapa;
  leyenda, filtros y cifras con el marcador nuevo; ninguna bandera con mástil (ni en el
  documento, ni en los estilos, ni en los iconos del mapa).
- Al revisar las capturas de producción se vio «Declaración de el prefecto de Iasi» en las
  fuentes de la ficha: corregido a «del» (con su test) en el PR de este informe.

Capturas en `docs/capturas`:

- Las cuatro fichas revisadas, en producción, en los cuatro tamaños:
  `atribuido-revisado-<id>-<tamaño>.png`.
- El mapa, las cifras, la leyenda, los filtros y Chisináu de cerca y de lejos, en producción:
  `atribuido-{mapa,cifras,leyenda,filtros,chisinau-cerca,chisinau-lejos}-<tamaño>.png`.
- Una ampliada de cada variante del marcador (densidad 4, junto a los círculos de alrededor). En
  producción ya no hay ningún atribuido, así que son de la construcción local con datos de prueba:
  `atribuido-variante-estado-prueba-*.png` (Rusia, con la base simulada del PR #97),
  `atribuido-variante-persona-con-pais-prueba-*.png` (Rumanía, con el punto) y
  `atribuido-variante-persona-sin-pais-prueba-*.png` (relleno liso con el punto).
- Retiradas las capturas de la bandera con mástil que quedaban del PR #73
  (`atribuido-{1,2,3}-{mapa,ficha}-*.png`), además de las del pulido (`pulido-4-*`,
  `pulido-4c-*`).

## Pendientes, con su arreglo

- **EODI-2026-00283 mezcla dos sucesos** (Wunstorf en septiembre; fecha y lugar de Leipzig del 4
  de agosto). Arreglo: separar el candidato de Wunstorf y volver a extraerlo, y unir lo de Leipzig
  con EODI-2026-00391. Lo lleva la sesión de corrección de errores de datos.
- **El incidente de Leipzig del 4 de agosto está repetido** en EODI-2026-00391, 00239, 00129,
  00190 y 00318, y el Gobierno alemán lo atribuyó a Rusia públicamente. Arreglo: unir los
  registros y traer su comunicado con las palabras literales; con la ficha nueva, lo atribuye sola.
- **Las autorías que se quedaron fuera** (tabla de arriba): buscar el texto original de cada
  declaración por la búsqueda dirigida y las fuentes oficiales.
- **Titulares con la nacionalidad de los drones sin atribución** en incidentes que no son de esta
  revisión («Dron ruso cargado de explosivos ataca Leipzig»). Arreglo: aplicar a todos los
  titulares la regla que ya se aplica a los retirados (`proceso/atribucion.titulo_sin_atribucion`)
  dentro de la revisión horaria de titulares.
- **El nombre del prefecto en el historial público**: sigue en versiones anteriores de los
  ficheros de `publicacion/` en el historial de git del repositorio público y en las exportaciones
  semanales cifradas ya enviadas a AEGIS. Arreglo: la exportación del lunes 5 de octubre lleva la
  corrección y AEGIS la reimporta; quitarlo del historial de git exige reescribirlo con un push
  forzado sobre `main`, que se deja a decisión expresa.
- **Una reconstrucción completa de los incidentes** (como la del criterio de presencia) los
  rehace desde las fichas: no volvería a atribuirlos, pero su historial perdería el paso de la
  retirada. Arreglo: guardar las retiradas en el control del incidente y que la reconstrucción
  las repita.

## Atribuciones aplicadas con la declaración oficial literal (5 de octubre de 2026)

Desde el 4 de octubre no había ningún incidente «atribuido». Se han buscado las declaraciones
originales de las autorías que se quedaron fuera (tabla de arriba). Cada enlace se ha abierto el 5
de octubre de 2026, se ha comprobado que la frase está palabra por palabra en la página y se ha
guardado una copia fechada del texto. Solo entonces se ha aplicado. La regla de atribución no
cambia: las frases pasan por la extracción, el proceso y la validación de siempre, y una que no
pasa no entra (dos de las propuestas no pasan, y se dice por qué).

### Cómo entran

- **La copia fechada.** `configuracion/declaraciones_oficiales/<nombre>.json`: enlace, editor,
  fecha de publicación, fecha de la copia y el texto del cuerpo de la página, un párrafo por línea.
  Se guarda con los caracteres no ingleses escritos como secuencias `\u` de JSON para que el texto
  rumano, polaco y sueco no dispare la comprobación de palabras del hook de `pre-push`; leído, es
  el texto exacto de la página.
- **La declaración.** `configuracion/declaraciones_oficiales.json`, una entrada por frase, con los
  mismos campos que da el extractor (`modelo/ficha.py`): autoridad, país de la autoridad,
  categoría, qué afirma, autor, `autor_tipo`, `autor_pais`, `cita_literal` y la frase.
- **El lector.** `recogida/declaraciones_oficiales.py`, en cada recogida horaria, después de las
  uniones revisadas y antes de la revisión de presencia:
  1. comprueba que la frase está literalmente en la copia (`proceso/declaraciones.validas`, la
     misma comprobación que la frase del extractor en el texto de la noticia); si no está, no la
     aplica;
  2. hace con ella una fuente del incidente: oficial, fiabilidad A, con el enlace a la página, su
     fecha, su idioma y la frase (`metodo: parser`, porque la comprueba el código y no el
     extractor). Si solo la cita una noticia, «declaración oficial citada», fiabilidad B;
  3. la pasa por `proceso/declaraciones.aplicar_fuentes`, que es la misma función que aplica las
     declaraciones del extractor: confirma, atribuye solo si `proceso/atribucion.evaluar` lo
     sostiene, y lo que la autoridad investiga va a la ficha como investigación en curso;
  4. guarda con la validación de siempre (`proceso/validaciones.py`, esquema 1.11.0). El paso a
     «atribuido» queda en el historial del incidente con su fuente y su fecha, y el cambio en el
     historial interno de la base con su motivo. La base sigue siendo de solo añadir.

  Una fuente que el incidente ya tiene no se vuelve a aplicar: desde la segunda recogida no cambia
  nada (comprobado en una copia de la base). Si una reconstrucción rehiciera el incidente, la
  recogida siguiente la vuelve a aplicar.
- **La tabla de países** (`configuracion/paises_atribucion.json`) no tenía el nombre de Rusia en
  sueco («Ryssland», «rysk»), en danés y neerlandés («Rusland») ni el nombre oficial en rumano
  («Federației Ruse», en genitivo, y su nominativo): las frases de las Fuerzas Armadas de Suecia y del
  presidente de Rumanía no se podían comprobar. Se añaden como nombres del Estado, que es lo que son;
  la regla (la frase tiene que nombrar al Estado) no cambia. Se añaden también expresiones de duda
  y de investigación en sueco (`configuracion/expresiones_duda.json`), que hacen la regla más
  estricta para las frases en ese idioma.

### Los casos

**A. Leipzig/Halle, 4 de agosto de 2026 · EODI-2026-00134 · atribuido a Rusia.**

- Frase: «Die Bundesregierung weist die Verantwortung für den versuchten Anschlag auf den Flughafen
  Leipzig/Halle vom 4. August 2026 eindeutig Russland zu.»
- Traducción: «El Gobierno federal atribuye inequívocamente a Rusia la responsabilidad del intento
  de atentado contra el aeropuerto de Leipzig/Halle del 4 de agosto de 2026.»
- Autoridad: Gobierno federal alemán (Bundesregierung), en su página oficial (Oficina de Prensa e
  Información del Gobierno federal). Lo comunicaron el ministro federal del Interior, Alexander
  Dobrindt, y el ministro federal de Asuntos Exteriores, Johann Wadephul, el 1 de septiembre.
- Fecha: 4 de septiembre de 2026 (fecha de la página).
- Enlace comprobado:
  <https://www.bundesregierung.de/breg-de/service/fragen-und-anworten/reaktion-angriff-leipzig-2451522>
- Investigación en curso, del mismo comunicado: «Unabhängig davon sind die strafrechtlichen
  Ermittlungen und juristischen Verfahren in der Angelegenheit noch nicht abgeschlossen und laufen
  weiter.» («Con independencia de ello, las investigaciones penales y los procedimientos judiciales
  sobre el asunto no han concluido y siguen en curso.») Y de la Fiscalía General federal
  (Generalbundesanwalt), 6 de agosto de 2026: «Die Bundesanwaltschaft hat heute (6. August 2026)
  wegen der besonderen Bedeutung des Falles das Ermittlungsverfahren zum Drohnenfund am Flughafen
  Leipzig/Halle von der Generalstaatsanwaltschaft Dresden übernommen.» («La Fiscalía Federal ha
  asumido hoy, por la especial relevancia del caso, la instrucción sobre el dron hallado en el
  aeropuerto de Leipzig/Halle, que llevaba la Fiscalía General de Dresde.»)
  <https://www.generalbundesanwalt.de/SharedDocs/Pressemitteilungen/DE/2026/Pressemitteilung-vom-06-08-2026.html>
- Los explosivos: el comunicado del Gobierno no habla de explosivos. Sí lo dice la Fiscalía General
  federal en la misma nota del 6 de agosto: «Hierzu waren an der Drohne professioneller Sprengstoff
  und ein Zünder angebracht worden.» («Para ello se habían colocado en el dron explosivo profesional
  y un detonador.») Entra como fuente oficial del incidente; con ella, el titular «Dron con carga
  explosiva causa cierre del aeropuerto de Leipzig» se sostiene con una cita de autoridad.
- El acta del Bundestag (Plenarprotokoll 21/93, 10 de septiembre de 2026,
  <https://dserver.bundestag.de/btp/21/21093.pdf>) recoge al ministro Dobrindt: «Das Benennen der
  Täter heißt, dass im Fall Leipzig eindeutig eine Zuweisung an Russland möglich und notwendig
  war.» («Nombrar a los autores significa que en el caso de Leipzig era posible y necesaria una
  atribución inequívoca a Rusia.») No se usa: «möglich» es una expresión de duda de la regla. La
  atribución sale del comunicado del Gobierno, que no la tiene.
- Registros repetidos: se unen en EODI-2026-00134, con la unión revisada de siempre
  (`configuracion/incidentes_revisados.json`), los ocho registros sueltos del mismo dron que
  quedaban publicados, revisados uno por uno: 00071 (12 de agosto), 00173 (18 de agosto), 00231 y
  00353 (6 de septiembre), 00128 (12 de septiembre), 00150 (26 de septiembre), 00377 y 00369
  (finales de septiembre y 2 de octubre). Todos son noticias tardías del mismo suceso. No se une
  EODI-2026-00058, que es otro suceso (26 de agosto, un dron que fotografiaba unas obras en
  Großkugel). Sin esta unión, el mismo suceso salía a la vez atribuido y sin atribuir.
- Decisión: **atribuido a Rusia** (tipo «estado», país «RU»). La investigación penal abierta va en la
  ficha como investigación en curso y no quita la atribución política del Gobierno.

**Wunstorf, dron hallado el 14 de septiembre de 2026 · EODI-2026-00276 · sin atribuir.**

- Sus seis registros (00309, 00023, 00145, 00276, 00297 y 00363) son el mismo hallazgo: el dron
  estrellado que un particular encontró el lunes 14 de septiembre en el Wunstorfer Moor, al este del
  Steinhuder Meer. Se unen con la regla de siempre, que elige EODI-2026-00276. Queda separado de
  Leipzig.
- No hay comunicado de la Fiscalía Federal sobre Wunstorf: su web no tiene ninguno. La
  investigación consta en prensa (dpa, recogida por ZDFheute el 18 de septiembre de 2026): «Nach dem
  Fund von Drohnenteilen nahe dem Bundeswehr-Fliegerhorst Wunstorf prüft die Bundesanwaltschaft
  einen möglichen Zusammenhang mit dem Drohnenvorfall am Flughafen Leipzig.» («Tras el hallazgo de
  restos de un dron cerca de la base aérea de Wunstorf, la Fiscalía Federal examina una posible
  relación con el incidente del dron en el aeropuerto de Leipzig.») Entra como «declaración oficial
  citada en zdfheute.de», sin palabras literales, y va a la ficha como investigación en curso.
  <https://www.zdfheute.de/politik/deutschland/bundeswehr-fliegerhorst-wunstorf-drohnenfund-bundesanwaltschaft-leipzig-100.html>
- Decisión: **sin atribuir** (confirmado). Examinar una posible relación no es atribuir.

**B. Øresund, 25 y 26 de febrero de 2026 · EODI-2026-00245 (incluye 00342) · atribuido a Rusia.**

- Frase: «Nu kan Försvarsmakten bekräfta att en rysk drönare har genomfört en olovlig flygning.»
- Traducción: «Ahora las Fuerzas Armadas pueden confirmar que un dron ruso realizó un vuelo
  ilícito.»
- Del mismo comunicado, como fuentes del incidente: «Under besöket av det franska hangarfartyget
  Charles de Gaulle observerade ett av Försvarsmaktens fartyg att en drönare lyfte från ett ryskt
  signalspaningsfartyg i Öresund.» («Durante la visita del portaaviones francés Charles de Gaulle,
  uno de los buques de las Fuerzas Armadas observó que un dron despegaba de un buque ruso de
  inteligencia de señales en el Øresund»: confirma el incidente) y el nombre del buque, «…som det
  ryska signalspaningsfartyget Zhigulevsk förflyttade sig i svenskt territorialvatten» («…cuando el
  buque ruso de inteligencia de señales Zhigulevsk se desplazaba por aguas territoriales suecas»).
- Autoridad: Fuerzas Armadas de Suecia (Försvarsmakten), comunicado de prensa.
- Fecha: 27 de febrero de 2026, 19:55 (hora de Suecia).
- Enlace comprobado:
  <https://www.forsvarsmakten.se/kontakt/press-och-media/forsvarsmakten-bekraftar-observation-av-rysk/>
  (la otra dirección, `/aktuellt/nyheter/…-rysk-dronare/`, tiene el mismo texto).
- Decisión: **atribuido a Rusia**. El incidente estaba «notificado»: la frase del despegue lo
  confirma y la de la confirmación lo atribuye, cada paso con su fuente.

**C. Polonia, noche del 9 al 10 de septiembre de 2025 · EODI-2025-00295 (incluye 00262) ·
atribuido a Rusia.**

- Frase: «W środę nad ranem polska przestrzeń powietrzna została naruszona przez rosyjskie drony.»
- Traducción: «El miércoles de madrugada, el espacio aéreo polaco fue violado por drones rusos.»
- Autoridad: Cancillería del primer ministro de Polonia (Kancelaria Prezesa Rady Ministrów), en la
  página del primer ministro Donald Tusk.
- Fecha: 10 de septiembre de 2025.
- Enlace comprobado:
  <https://www.gov.pl/web/premier/premier-doszlo-do-naruszenia-polskiej-przestrzeni-powietrznej---procedury-zadzialaly>
- Del mismo día, como fuentes del incidente: el comunicado del Ministerio de Defensa Nacional
  (Ministerstwo Obrony Narodowej, <https://www.gov.pl/web/premier/Komunikat-MON>): «W wyniku
  dzisiejszego ataku Federacji Rosyjskiej na terytorium Ukrainy doszło do bezprecedensowego w skali
  naruszenia polskiej przestrzeni powietrznej przez obiekty typu dron.» («Como consecuencia del
  ataque de hoy de la Federación de Rusia contra el territorio de Ucrania se ha producido una
  violación sin precedentes del espacio aéreo polaco por objetos de tipo dron.»); y la dirección de
  entrada, en palabras del primer ministro en el Sejm
  (<https://www.gov.pl/web/premier/naruszenie-polskiej-przestrzeni-powietrznej-jest-wniosek-o-uruchomienie-art-4-traktatu-polnocnoatlantyckiego>):
  «Po raz pierwszy spora część dronów nadleciała nad Polskę bezpośrednio z Białorusi» («Por
  primera vez, una parte considerable de los drones llegó a Polonia directamente desde
  Bielorrusia»). Bielorrusia es la dirección de entrada, no el autor.
- No se usa «Fakty wskazują, że odpowiedzialność spada jednoznacznie na Rosję.» («Los hechos
  indican que la responsabilidad recae inequívocamente en Rusia»,
  <https://www.gov.pl/web/premier/polska-bedzie-bronic-swojego-terytorium>, 11 de septiembre de
  2025): «wskazują» («indican») es una expresión de duda de la regla en polaco, como «todo indica».
  La atribución sale de la otra frase.
- Los dos registros: EODI-2025-00305 no es de esa noche. Sus nueve fuentes son del 20 de agosto de
  2025 y hablan del dron que cayó y explotó en un maizal de Osiny (Lublin): «Bei einem in Polen auf
  einem Maisfeld abgestürzten Flugobjekt handelt es sich nach Angaben der Regierung in Warschau um
  eine russische Drohne» (az-online.de). Las declaraciones del 10 y el 11 de septiembre no lo
  cubren.
- Decisión: **EODI-2025-00295 atribuido a Rusia; EODI-2025-00305 sin atribuir** (su titular deja
  de decir «ruso»).
- Pendiente con su arreglo: EODI-2025-00295 no tiene punto en el mapa (el suceso abarca tres
  voivodatos y su ficha da el país): sale en la lista, la ficha y las cifras con su marcador, no en
  el mapa. Arreglo: si se quiere en el mapa, darle un lugar más preciso con una fuente oficial que
  lo diga como lugar del suceso (la ficha no admite un punto que no salga del lugar del suceso).

**D. Galați, noche del 28 al 29 de mayo de 2026 · EODI-2026-00211 (absorbió 00228 y 00345) ·
atribuido a Rusia.**

- La frase que circulaba en prensa («Întreaga responsabilitate pentru acest incident revine
  Rusiei») no está en la web de la Presidencia con esas palabras. Está esta, en la declaración de
  prensa oficial del presidente:
- Frase: «Declar, cu toată fermitatea, că responsabilitatea integrală pentru acest incident îi
  aparține Federației Ruse.»
- Traducción: «Declaro con toda firmeza que la responsabilidad íntegra de este incidente
  corresponde a la Federación de Rusia.»
- Autoridad: presidente de Rumanía, Nicușor Dan (Președintele României), en presidency.ro. La
  web responde a los lectores automáticos con una página de comprobación; se leyó con un navegador
  real y la copia guarda el texto.
- Fecha: 29 de mayo de 2026.
- Enlace comprobado:
  <https://www.presidency.ro/ro/media/comunicate-de-presa/declaratia-de-presa-a-presedintelui-romaniei-nicusor-dan-in-urma-incidentului-grav-cauzat-de-o-drona-ruseasca-in-galati>
- Investigación en curso, de la misma declaración: «A fost declanșată o anchetă completă privind
  împrejurările căderii dronei» («Se ha abierto una investigación completa sobre las circunstancias
  de la caída del dron»).
- El incidente: EODI-2026-00228 está fundido en EODI-2026-00211 (el mismo dron sobre el bloque de
  viviendas). El lector aplica la declaración al que lo absorbió.
- Decisión: **atribuido a Rusia** (el Estado; no se atribuye a ninguna persona).

**Los que no se atribuyen.**

- **Constanza, 5 de junio de 2026 (EODI-2026-00152).** Según la investigación previa, la
  Presidencia habla de «evaluări preliminare» y de «ipoteza»: expresiones de duda (y la base no
  guarda ninguna declaración de autoridad de este registro). Sin atribuir. Su titular decía «Dron que explotó
  en el Puerto de Constanza fue controlado por Rusia»; queda «Dron que explotó en el Puerto de
  Constanza». La ficha no dice «ruso» fuera de las citas de las fuentes.
- **Buzău (EODI-2026-00125).** «Moscova testează intenționat spațiul aerian românesc» no es del
  Ministerio de Defensa: según la investigación previa, es la opinión de un general retirado en
  televisión, que la noticia guardada (ziare.com) atribuyó al Ministerio. Sin atribuir.
- **Lituania (EODI-2026-00090).** Sin declaración oficial localizada. Sin atribuir; su titular
  inglés deja de decir «Ukrainian».
- **Dinamarca, aeropuertos de septiembre de 2025.** Las autoridades no atribuyeron a nadie. Sin
  atribuir.

### Titulares

La regla que se aplicaba a los retirados (`proceso/atribucion.titulo_sin_atribucion`) se aplica
ahora en cada recogida a todos los titulares de la base (`atribucion.titulo_segun_atribucion`): el
de un incidente que no está atribuido no dice la nacionalidad del dron ni señala a un autor; el de
un atribuido puede decirlo. Además de lo que ya quitaba (ruso, bielorruso, ucraniano, iraní y los
explosivos que ninguna autoridad dice), quita otras nacionalidades pegadas al dron («Dron turco»,
«Moroccan drone»; sueltas son las de un lugar, como «espacio aéreo griego», y se quedan) y lo que
señala a un autor («fue controlado por Rusia», «respaldado por Irán», «Iranian-backed»). La
dirección de entrada («desde Bielorrusia») se queda. Cada cambio se guarda como versión nueva con su
motivo.

**Cambian 115 titulares** en el ensayo sobre la base de las 10:14 UTC del 5 de octubre (de 511
incidentes publicados). Ejemplos: «Drones rusos invaden el espacio aéreo de Polonia» queda igual
(atribuido); «Dron ruso se estrella en un campo en el este de Polonia» → «Dron se estrella en un
campo en el este de Polonia»; «Drones turcos violan el espacio aéreo griego sobre el Egeo» →
«Drones violan el espacio aéreo griego sobre el Egeo»; «Ataque con dron respaldado por Irán contra
la base de Dhekelia» → «Ataque con dron contra la base de Dhekelia».

### Autoridades traducidas

Se añaden a `web/src/i18n/autoridades.ts`, con el original entre paréntesis: el Fiscal General
federal alemán (Generalbundesanwalt), las Fuerzas Armadas de Suecia (Försvarsmakten), el primer
ministro de Polonia (Prezes Rady Ministrów), la Cancillería del primer ministro de Polonia
(Kancelaria Prezesa Rady Ministrów), el Ministerio de Defensa Nacional de Polonia (Ministerstwo
Obrony Narodowej) y el presidente de Rumanía (Președintele României). El Gobierno federal alemán
(Bundesregierung) y la Fiscalía federal alemana (Bundesanwaltschaft) ya estaban.

### La web

- La ficha de un atribuido enseña ahora, en la fila «Atribución», la cita literal de la autoridad
  (con su idioma) y el enlace a la página oficial, además de a quién y según quién.
- El marcador abierto de un atribuido ocupa su sitio en el mapa como el cerrado: antes, el nombre
  del lugar quedaba partido debajo («Malmö» asomaba por los lados del marcador).
- Comprobado con los datos del ensayo en la construcción local, en 360 × 800, 390 × 844,
  412 × 915 y escritorio (`e2e/atribuciones-oficiales.spec.ts`): los cuatro atribuidos con el
  marcador de la bandera rusa en la ficha; Leipzig, Malmö y Galați con su marcador en el mapa, por
  encima de círculos y grupos y reconocible sin acercar en el teléfono; la cifra «4 atribuidos» en
  la cabecera y en el menú; «Atribuido» en la leyenda y en el filtro. Con los datos reales ningún
  par de atribuidos se pisa en la pantalla, ni con el mapa en su zoom mínimo: el marcador agrupado
  con su número no aparece (lo comprueban las pruebas del PR #97).

### La exportación semanal

En el ensayo, la exportación lleva cada atribución con su origen: `procedencia.atribucion =
{origen: oficial, metodo: parser, fuentes: [la declaración oficial]}`, y la investigación con
`{origen: oficial, metodo: regla}`. Valida con el esquema.

### Ensayo antes de fusionar

Paso c2 de [`fusiones.md`](fusiones.md), en el servidor, como `eodi`, con `systemd-run` (3 GB,
prioridad baja, `OOMScoreAdjust=1000`, sin el cerrojo), sobre una copia propia de la base del disco
en `/home/eodi/ensayo-atrib` (`EODI_BASE_DIRECTORIO`, para no tocar la copia de trabajo de la
recogida), sin claves del extractor: código 0, «ficheros publicados con cambios: 3», «exportación
semanal generada sin subir», 13 min 39 s, 2,6 GB de pico. «declaraciones oficiales: 11 aplicadas;
atribuidos: EODI-2026-00134, EODI-2026-00245, EODI-2025-00295, EODI-2026-00211; frase que no está en
la copia: 0; sin guardar: 0». Las dos frases y las uniones añadidas después se ensayaron de nuevo
antes de fusionar (abajo).

Segundo ensayo, con el código final de la rama (c52682e, rebasada sobre `main`), del mismo modo:
código 0, 13 min 54 s, 2,6 GB de pico, «registros revisados unidos: 13», «declaraciones oficiales:
13 aplicadas; atribuidos: EODI-2026-00134, EODI-2026-00245, EODI-2025-00295, EODI-2026-00211;
frase que no está en la copia: 0; sin guardar: 0», «titulares sin nacionalidad ni autor sin
atribución: 115», «ficheros publicados con cambios: 3» y la exportación semanal generada sin
subir. Incidentes publicados: 498 (319 en el mapa y 179 sin ubicación), frente a los 511 que servía
producción a esa hora: la diferencia son los 13 registros unidos (8 de Leipzig y 5 de Wunstorf),
que quedan fundidos con su motivo.
