# Marcador de los atribuidos: círculo con la bandera del país

Fecha: 4 de octubre de 2026.

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

Esquema 1.10.0: la atribución lleva dos campos públicos más, `tipo` (`estado` o `persona`) y
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

## Los atribuidos de hoy

Corrección de lo guardado (`recogida/tipo_atribucion.py`): una vez, dentro de la recogida
horaria, como versión nueva de cada incidente con su motivo en el historial. Simulada sobre una
copia de la base de producción del 4 de octubre:

| Incidente | Autoridad | Frase guardada | Resultado |
| --- | --- | --- | --- |
| EODI-2025-00247 (Chisináu) | Presidenta Maia Sandu | «Prezydent Maia Sandu oskarżyła Moskwę o próbę destabilizacji.» | Estado, RU |
| EODI-2026-00074 (Chisináu) | Autoridades moldavas | «Молдавские власти сразу назвали аппарат «российским»» | Estado, RU |
| EODI-2026-00283 (base aérea alemana) | Gobierno federal | «die Bundesregierung von einem russischen Anschlagsversuch ausging» | Estado, RU |
| EODI-2026-00119 (Leipzig, fundido en EODI-2026-00391) | Gobierno federal | «…что Россия несет ответственность…» | Estado, RU |
| EODI-2026-00015 (aeropuerto de Iasi) | Prefecto de Iasi | «The drone entered Romanian territory from the Republic of Moldova» | **Sin atribución: vuelve a confirmado** |

EODI-2026-00015 no estaba atribuido a una persona. El «autor» guardado, Constantin
Dolachi-Pelin, es el propio prefecto de Iasi (el extractor puso el nombre de quien habla), y la
frase solo dice por dónde entró el dron, sin atribuirlo a nadie. Con la regla, la atribución no
se sostiene: el incidente queda confirmado (la declaración del prefecto sigue como fuente
oficial), sin el paso a atribuido, con el motivo en el historial. En la web quedan tres
atribuidos, los tres a Rusia, y ninguno a una persona: las variantes de persona se ven en las
capturas con datos de prueba locales (abajo).

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

## Comprobación

PENDIENTE_PRODUCCION
