# Qué es un suceso

Desde el 11 de noviembre de 2026. Hasta entonces, qué era «el mismo suceso» se decidía con reglas
sueltas repartidas por el filtro de entrada, el control, la regla de fusión, las separaciones y
la auditoría: dos días en una frase, otro país nunca, otra alerta nunca, la nota de la noche y
sus alertas, el desacuerdo entre el filtro y el control… Cada una se añadió para tapar un caso y
abrió otro. Este documento es la única definición, y `proceso/suceso.py`, el único sitio del
código que la aplica. Lo demás pregunta ahí.

## La definición

**Un suceso es un episodio físico —los mismos drones o la misma oleada— en un país y en una
jornada.**

- **Episodio físico.** Lo que pasó, no lo que se publicó: el dron que cruza, la oleada de una
  noche, el cierre de un aeropuerto, el derribo, el barco alcanzado. Cuántas noticias lo cuenten,
  en qué idioma, con qué número o con qué detalle del lugar no cambia el suceso.
- **Un país.** Países distintos son sucesos distintos, aunque sea el mismo dron que cruza la
  frontera: cada país cuenta el suyo, con sus autoridades, y los dos se enlazan como un mismo
  episodio transfronterizo (el campo `episodio`).
- **Una jornada.** Un día local, o una noche que cruza la medianoche, que es una sola jornada:
  de la tarde de un día a la madrugada del siguiente. Dos días distintos son dos sucesos.

De ahí sale todo lo demás:

| Caso | Qué es |
|---|---|
| El dron o la oleada que recorre varias zonas del mismo país en una noche; cada alerta que la autoridad va dando por zonas y la nota con la que después cuenta esa noche entera | un suceso |
| Varios sitios que una misma comunicación oficial cuenta juntos, sin separar el día, la hora ni los drones de cada uno | un suceso |
| Una noticia posterior sobre un suceso ya contado (una reacción, un balance, la investigación, un recuerdo semanas después) | ese suceso: se une a su ficha o no crea ficha; su jornada es la del suceso, no la de la publicación |
| El mismo dron a los dos lados de una frontera | dos sucesos, uno por país, enlazados por un `episodio` |
| El mismo sitio en dos días o en dos noches («de nuevo», «otra vez», el sábado y el domingo) | dos sucesos |
| En la misma jornada y el mismo país, drones distintos en sitios u horas distintos que las fuentes cuentan por separado (otro dron horas después, otro aeropuerto, otro barco) | sucesos distintos, enlazados por un `episodio` si son varios objetivos de una noche |
| Una ficha que junta varios de esos (un balance de varias noches, un resumen de dos países) | ninguno: se separa o se retira |

**La ficha que queda** de una unión toma sus datos del suceso, no de la ficha con más fuentes:

- el **país** es el del suceso; una ficha de otro país no se une, se enlaza;
- la **fecha** es la del momento en que empieza: la hora, si alguna fuente la da; si solo se sabe
  «la noche hacia el X», la víspera. Una noticia sobre un suceso anterior, fechada por otro día,
  no le cambia el día a la ficha del suceso (`suceso.toma_el_tiempo`);
- el **lugar** y la **autoridad** son los del suceso: la declaración de una autoridad de otro
  país no llega a la ficha por una unión, porque esa unión no se hace.

## Cómo se aplica

`suceso.veredicto(a, b)` dice de dos fichas, sin leer sus fuentes, una de cuatro cosas:

- **mismo**: son el mismo suceso y se unen sin preguntar;
- **distintos**: no lo son y nadie las une, diga lo que diga quien lea las fuentes;
- **experto**: pueden serlo; lo decide quien lee las fuentes de las dos, con esta definición
  delante (`suceso.DEFINICION` va en todas las peticiones que lo preguntan);
- **ajenas**: ni se pregunta.

Las reglas firmes, en su orden (la primera que habla, decide):

1. **Una revisión a mano manda.** Lo que separó o dio por distinto no se une; lo que unió, unido
   está (`configuracion/incidentes_revisados.json`: `unir`, `separar`, `distintos`).
2. **Países distintos** son sucesos distintos si el país de alguna de las dos es firme: cita a
   una autoridad de su país. Sin eso (un buque en el mar entre dos países) el país de una de las
   dos puede estar mal, y lo decide el experto.
3. **La nota de una noche y sus alertas.** La nota con la que una autoridad que da sus alertas
   por zonas cuenta una noche y las alertas de esa noche, en el mismo país, son el mismo suceso,
   aunque el experto dijera otra cosa.
4. **Lo que el experto dio por distinto** leyendo las fuentes de las dos no se vuelve a unir
   solo.
5. **Dos cierres del mismo sitio en noches distintas**, o un cierre que las fuentes cuentan como
   repetido, son dos sucesos.
6. **El mismo sitio y la misma jornada**, sin nada de lo anterior, es el mismo suceso sin
   preguntar: con hora en las dos, inicios a menos de 6 horas; con día, el mismo día; con la
   fecha de publicación, ese día o la víspera. Dos días seguidos sin hora pueden ser una noche o
   dos sucesos: decide el experto.

Lo que no es firme lo decide el experto, y lo que decide se comprueba: un «mismo» que una regla
firme da por distintos no se une.

## Quién pregunta

| Paso | Qué pregunta | Dónde |
|---|---|---|
| Regla de fusión | une lo que el veredicto da por «mismo» (reglas 3 y 6) con una sola ficha anterior | `proceso/incidentes.fusionar` |
| Uniones vigentes | deshace las que el veredicto da por «distintos» (reglas 1, 2 y 5; de las que hizo el control, solo la 2) | `proceso/incidentes.revisar_fusiones` |
| Control: pares | compara con el experto los pares «experto» del mismo país (`suceso.pares_candidatos`) | `recogida/control_fichas.comparar_pares` |
| Filtro de entrada y medida | con qué fichas se compara una nueva (`suceso.conjunto`); un «mismo» del experto no vale si es «distintos» (`suceso.nunca_el_mismo`) | `recogida/entrada.py` |
| Toda unión del control | no se hace si el veredicto es «distintos»: queda como propuesta | `recogida/control_fichas.unir` |
| Dos días en una ficha | la ficha con una frase que da dos días que no son una noche cuenta dos sucesos: no se publica hasta que una revisión la separa | `suceso.dos_dias_sin_revisar` (filtro de entrada y letra AA) |
| Cerrojo | no deja unir lo que la definición da por distintos por las reglas 1 y 4, y deja deshacer lo que da por distintos | `proceso/protegido.par_prohibido`, `es_separacion` |
| Auditoría | letra **V**: uniones vigentes que el veredicto da por «distintos»; letra **AA**: dos días | `proceso/auditoria_fichas.py` |
| Invariantes | **I6**: ninguna unión vigente que `revisar_fusiones` tenía que haber deshecho | `proceso/invariantes.py` |
| Episodios | varios objetivos de un país en una noche; el mismo episodio a los dos lados de una frontera | `suceso.episodios_calculados` |
| Repaso de entrada (a mano) | lo que no puede ser el mismo al repasar una ficha publicada | `suceso.imposible_al_repasar` |

## El episodio transfronterizo

Dos sucesos de países vecinos son el mismo episodio físico si son de la misma jornada y las
fuentes de uno cuentan el paso al otro país (una frase suya lo nombra: «flew into Latvian
airspace», «pasiekė Estiją») o los dos comparten una noticia. No se unen: se enlazan con el mismo
`episodio`, aunque sus fichas solo digan el país. El dron de la noche del 10 al 11 de noviembre
de 2026 cruzó Lituania (EODI-2026-00792), Letonia (EODI-2026-00777) y llegó a Estonia
(EODI-2026-00801): tres sucesos, un episodio.

## Los casos reales

La batería está en `tests/test_definicion_suceso.py`, con las fichas reales
(`tests/fixtures/definicion_suceso.json`). Cada caso, con la decisión correcta según sus fuentes:

| Fichas | Qué pasó | Decisión |
|---|---|---|
| EODI-2026-00756, 00746, 00760 (Letonia) | «W łotewską przestrzeń powietrzną wkroczyły w niedzielę i wtorek dwa drony»: dos días en una ficha, y después la del martes perdida | dos sucesos (domingo 1 y martes 3 de noviembre); 00760 es el del martes |
| EODI-2026-00770, 00773 (Leipzig/Halle) | «am Samstag und Sonntag jeweils eine der beiden Landebahnen kurzzeitig gesperrt» | dos sucesos, sábado y domingo |
| EODI-2025-00106, 00049 (Otopeni) | dos noticias del expediente penal «acum două zile» | el mismo suceso, del domingo 28 de septiembre de 2025; la ficha que queda no toma el 30 |
| EODI-2026-00771 (Hamburgo) | «Am Abend…» en una nota de las 14:30 | la tarde de la víspera, el 8 de noviembre |
| EODI-2026-00765, 00134 (Leipzig) | la búsqueda de un sospechoso del atentado de agosto | una noticia de un suceso anterior: no es un suceso nuevo |
| EODI-2026-00778 | el resumen «Latvia and Lithuania» | ningún suceso: cada país tiene el suyo |
| EODI-2026-00777, 00784 (Letonia) | las alertas por municipios y la nota de la noche | el mismo suceso |
| EODI-2026-00218, 00230 | el dron derribado sobre Letonia el 14 de agosto, dentro de una ficha de Tulcea (Rumanía) | sucesos distintos; el de Letonia es EODI-2026-00140 |
| EODI-2026-00515 (Núremberg) | «in der Nacht auf Dienstag (13. Oktober)», «am frühen Dienstagmorgen (13. Oktober)» | la madrugada del martes 13 de octubre |
| EODI-2026-00739, 00719 (Iași) | una revista de prensa del día siguiente | el mismo suceso, del sábado 31 de octubre |
| EODI-2026-00262 y 00636, 00527 y 00263, 00160 (Moldavia, 30 de septiembre) | tres drones el mismo día, cada uno con su hora y su comunicado | tres sucesos; cada par citado, el mismo |
| EODI-2026-00544 y 00698, 00541, 00538 (Sulina, 14 de octubre) | un blanco a las 17:38, el petrolero hacia las 20:00 y un dron a la 01:34 | tres sucesos |
| EODI-2026-00772 (La Hague y Flamanville) | una sola comunicación de la prefectura, sin día, hora ni drones por sitio | un suceso |
| EODI-2026-00566 (Moldavia) | «on Thursday and Friday»: la noche del 15 al 16 de octubre | un suceso |
| EODI-2026-00792 y las fichas lituanas dentro de 00778 (00779, 00783, 00785 a 00791) | la noche del 10 al 11 de noviembre en Lituania | un suceso, EODI-2026-00792; nunca dentro de una ficha de Letonia |
| EODI-2026-00792, 00777, 00801 | el mismo dron en Lituania, Letonia y Estonia | tres sucesos, un episodio |

## Lo que queda fuera

- **Leer el día de una frase** es de `proceso/fechas.py` (qué es una tarde, una noche, «la noche
  hacia el 11»). La definición dice qué jornadas son la misma; `fechas.py`, qué día dice una
  frase.
- **Agrupar artículos en candidatos**, antes de que haya ficha (`proceso/noticias.py`), y enlazar
  una nota oficial a su ficha (`recogida/oficiales.posibles`): deciden a qué candidato o a qué
  ficha va un texto con el sitio y el día, y lo que sale de ahí pasa después por la definición.
- **La segunda lectura** (`docs/segunda_lectura.md`) no decide nada: marca candidatos.
- **Separar sola** una ficha que cuenta dos sucesos: la marca la definición (dos días, dos
  países) y la separa una revisión (`docs/sucesos_mezclados.md`).
