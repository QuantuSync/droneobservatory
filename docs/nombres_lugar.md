# Nombres de lugar en español y en inglés

La web tiene dos versiones. Cada nombre de lugar sale en la forma española habitual en la española
(Pafos, Lárnaca, Varsovia, Bucarest, Kiev, Constanza) y en la inglesa habitual en la inglesa (Paphos,
Larnaca, Warsaw, Bucharest, Kyiv, Constanța). Sin forma propia, el nombre local en alfabeto latino
como lo escribe la prensa. Nunca una transliteración académica, nunca el alfabeto original y nunca
un tercer idioma. Los aeropuertos, «Aeropuerto de X» / «X Airport» (o su nombre inglés habitual:
«Paphos International Airport»); las bases, por su nombre corriente (RAF Akrotiri, base aérea de
Volkel / Volkel Air Base).

## Dónde se deciden

`proceso/nombres_lugar.py`, por este orden (manda lo primero que se encuentra):

1. `configuracion/nombres_lugar.json`, revisado a mano: `textos` (el texto tal como lo guarda la
   ficha → cómo se escribe, con `sitio` si nombra una localidad), `aeropuertos` (por código OACI),
   `localidades` (ciudades con nombre propio en español o en inglés: Kiev, Moscú, Constanza…),
   `mares`, `paises`, `territorios`, `instalaciones` (patrones como «Flughafen X» → «Aeropuerto de
   X» / «X Airport»), `palabras_ajenas` y `formas_ajenas` (para revisar y corregir) y
   `flanco_este`.
2. `configuracion/nombres_lugar_wikidata.json.gz`, generado de Wikidata (comprimido): aeropuertos y bases por código
   OACI (P239) y las localidades de 5 km de radio o más por su número de GeoNames (P1566), con las
   formas con que las nombran las fuentes y la tabla `formas_ajenas` («Paphos» → «Pafos» en la
   versión española). No se edita a mano: se regenera con
   `python -m recogida.nombres_wikidata generar` (unos 5 minutos; `--filas fichero.json` guarda lo
   consultado para volver a generar sin consultar) y lo dudoso se corrige en la tabla manual, que
   también se aplica al generar.
3. La caché de lo buscado cada hora (`EODI_NOMBRES_CACHE`; en el servidor,
   `~/datos/nombres_lugar.json`): la recogida horaria busca en Wikidata los nombres de
   lugar de los incidentes que no están en las tablas (paso «nombres de lugar»,
   `recogida/nombres_wikidata.py`; 25 consultas y 60 segundos como mucho; lo no encontrado se
   vuelve a buscar a la semana). Si Wikidata no responde, se publica igual.
4. La regla: un nombre en alfabeto latino sin palabras de otro idioma se deja como está; si no, la
   localidad del aeropuerto o de la instalación, la región o el país.

## Qué se publica

Cada incidente publicado lleva el campo `nombres` (esquema 1.17.0, se genera al publicar y no se
guarda en la base): `lugar` (lo que dice la fila «Lugar»: «Pafos, Chipre», «RAF Akrotiri (base
británica), Chipre», «Gibraltar (Reino Unido)», «Saint-Denis, Reunión (Francia)»), `localidad`,
`objetivo`, `region`, `otros` y `anteriores` (en el orden de la ficha; null donde no se puede
escribir) y `pais_geografico` cuando no es el de los datos (Akrotiri y Dhekelia: CY; Gibraltar: GI;
ultramar: su código). El país de los datos no cambia (Akrotiri sigue en GB) y los filtros por país
tampoco. El titular publicado se escribe con los mismos nombres («aeropuerto de Paphos» →
«aeropuerto de Pafos»; «Drone» → «Dron» en la versión española). La exportación semanal para AEGIS
no lleva nada de esto: sale de la base, como siempre.

Los avisos de ntfy y el resumen diario usan lo mismo: el lugar del aviso es el de la ficha.

## Revisión

`nombres_lugar.problemas` revisa lo que la ficha enseña (titular, lugar, localidad, objetivo,
región, demás lugares): otro alfabeto, palabras de un tercer idioma (`palabras_ajenas`), la forma de
la otra versión (`formas_ajenas`, solo las de ciudades del mismo país: «Biala» es una aldea
búlgara, no Bielsko-Biała), español en la versión inglesa de un lugar de fuera de España y «Lugar»
con el país a secas cuando se conoce la localidad. La publicación no saca un nombre que no pasa la
revisión (la ficha cae en el titular, la localidad o el país) y lo deja en el registro. La prueba
`tests/test_nombres_publicados.py` la pasa por todos los incidentes publicados en el trabajo
«datos-publicados» de la integración continua, antes de cada fusión.

## Añadir o corregir un nombre

Un nombre mal escrito en la web se corrige en `configuracion/nombres_lugar.json` (en `textos` si es
el texto concreto de una ficha; en `localidades` o `aeropuertos` si es el nombre de una ciudad o de
un aeropuerto en general) y se publica en la siguiente recogida. Después de tocar `localidades`
conviene regenerar la tabla de Wikidata (con `--filas` para no consultar) para que sus formas
ajenas usen el nombre nuevo.

## Fechas coherentes

`proceso/coherencia.py`, también solo en lo publicado: un paso del historial nunca es posterior al
siguiente (toma la fecha y la fuente del siguiente: quien confirma también avisa) y un suceso cuyo
inicio es solo un día o una fecha aproximada no empieza después de su primer aviso. Un inicio con
hora no se toca. La prueba sobre los datos publicados comprueba además que el estado actual es el
último paso, que el fin no es anterior al inicio y que el primer aviso no es de más de un día antes
de un inicio con hora.

## En la web

La ficha (`web/src/componentes/FichaIncidente.tsx`) y las páginas de texto (`web/src/texto/paginas.ts`)
escriben los lugares con el campo `nombres` (`web/src/datos/nombres.ts`): el título es el nombre del
objetivo en cada versión o, si no se puede escribir bien, el titular; «Lugar» es `nombres.lugar`; los
demás lugares y los puntos anteriores, `nombres.otros` y `nombres.anteriores`. Con datos publicados sin
ese campo, la tabla de siempre (`web/src/i18n/nombresLugar.ts`), que ya nunca transcribe otra
escritura. Las listas, el buscador de canales de avisos, el mapa y los datos estructurados usan el
titular publicado y `nombres.lugar`; el CSV lleva al final `lugar_es`, `lugar_en`, `objetivo_es` y
`objetivo_en`.

«Frontera o interior» solo sale en la ficha en el flanco este (`FLANCO_ESTE`, la misma lista que
`flanco_este` de `configuracion/nombres_lugar.json`): países con frontera con Ucrania, Rusia (también
Kaliningrado) o Bielorrusia o con costa en el mar Negro, por el país geográfico (Akrotiri cuenta como
Chipre). El dato se sigue calculando y publicando igual y la exportación para AEGIS no cambia. El filtro
«Dónde» dice «Frontera este» y «Resto de Europa».

El modelo de dron solo sale si es un nombre de modelo («Shahed 136», «Gerbera»), no la descripción de la
fuente en su lengua; el motivo de un desmentido va como cita.

## Autoridades y fuentes oficiales

`configuracion/autoridades.json` (347, revisadas a mano el 13 de octubre de 2026) escribe en español y
en inglés quién declara, investiga o atribuye y el nombre de las fuentes oficiales sin medio, también
las de la capa de guerra (las administraciones militares regionales de Ucrania, el Ministerio de
Defensa ruso…). Las instituciones con nombre oficial en alfabeto latino llevan el original entre
paréntesis («el Gobierno federal alemán (Bundesregierung)»). La usan la web (`web/src/i18n/autoridades.ts`) y los
avisos (`proceso/autoridades.py`).

Desde el 14 de octubre de 2026 (la ficha EODI-2026-00532 decía en español «Declaración de Defense
Ministry of Romania»), en la web una autoridad sale **siempre en el idioma de la página**:

1. la de la tabla (366 desde ese día: las 17 publicadas que faltaban y dos de los ejemplos de las
   pruebas);
2. si no está, la traducción que trae la ficha publicada (`autoridades`: nombre -> {es, en}, esquema
   del incidente; también en los ataques y los impactos de la capa de guerra). El control de las
   fichas la traduce como las citas, con la marca «[autoridad]» para que el modelo la escriba como
   nombre con su artículo; las de las fichas nuevas, antes de publicarlas, y las demás en el lote de
   la recogida siguiente (`exportacion/citas.con_autoridades`, `recogida/control_fichas.citas_de`);
3. si aún no hay traducción, «una autoridad» / «an authority», nunca el nombre en otro idioma.

Cuentan como autoridad la de cada declaración citada, el nombre de una fuente sin dominio (un canal
oficial, un ministerio), la que atribuye y las que investigan. También se escriben así dentro de una
frase («según el Ministerio…», «Cifras del…»: tipo de dron, recorrido, valores de cada fuente, cifras
de la capa de guerra y páginas sin código). La prueba `web/tests/fichas.test.tsx` recorre todas las
fichas publicadas en los dos idiomas y falla si alguna enseña una autoridad con su nombre original
cuando en la página se escribe de otra forma; `web/tests/autoridades-idioma.test.tsx` prueba los tres
casos. Desde el 15 de octubre de 2026 los avisos de ntfy y el resumen diario privado siguen la misma
regla (`proceso/autoridades.py`, prueba `tests/test_avisos_autoridades.py`): la fuente del aviso, y
el nombre original de una autoridad que aparezca en un titular, se escriben con la tabla, con la
traducción que viaja con la ficha publicada (los avisos la leen de los ficheros publicados) o como
«una autoridad»; un periódico con dominio sale tal cual, como en la web. Los avisos ya enviados no
se reenvían. El fichero va en ASCII con escapes: el gancho del repositorio vería
sílabas sueltas en los nombres rumanos con letras con signo.

## Capa de guerra

La ficha de un impacto ya no lleva el nombre en cirílico: la ciudad con su nombre español o inglés
(Kiev / Kyiv, Járkov / Kharkiv), la comunidad («comunidad de Khotin» / «Khotin community»), el distrito
o el nombre en alfabeto latino de los datos; los pocos que solo vienen en cirílico, escritos a mano
(`web/src/datos/nombres.ts`). Sin nombre, la región.

## Prueba de las fichas

`web/tests/fichas.test.tsx` dibuja cada incidente publicado en las dos versiones y comprueba que fuera
de las citas no hay otro alfabeto ni palabras de otro idioma, que «Lugar» es el publicado y lleva su
localidad, que «Frontera o interior» solo sale en el flanco este y que no hay filas vacías; y que cada
lugar y cada fuente de la capa de guerra se escribe en el idioma de la página. Corre con los datos de
ejemplo y, en el trabajo «datos-publicados», con los publicados.
