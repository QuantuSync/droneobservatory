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
   `/home/eodi/datos/nombres_lugar.json`): la recogida horaria busca en Wikidata los nombres de
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
