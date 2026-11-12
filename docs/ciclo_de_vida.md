# El ciclo de vida de una ficha

Desde el 10 de noviembre de 2026. En la primera semana de noviembre el mismo tipo de fallo volvió
una y otra vez: fichas mezcladas, separadas mal, unidas al revés, que desaparecían de la web, que
cambiaban y volvían cada hora, o avisos con datos que la web no enseñaba (EODI-2026-00760, 00746,
00773, Otopeni, Leipzig). Cada arreglo tapaba un caso. Este documento dice cómo vive una ficha
para que esos fallos no puedan ocurrir por cómo está hecho el sistema, y qué comprueba que sea
así. Las reglas de qué está protegido no cambian: siguen en [`cerrojo.md`](cerrojo.md).

## Seis reglas

1. **Cerrado por defecto.** Nada se publica ni se avisa sin haber pasado el control de esa ficha
   en esa versión. Si el control no llega a terminar en una pasada, lo publicado no cambia.
2. **Una sola fuente de lo publicado.** La tabla `publicado` de la base. La web, los datos
   abiertos y los avisos salen de ella y de nada más.
3. **Lo revisado a mano con cita no se pierde** por una unión, una separación, una relectura o una
   reconstrucción, y una unión o una separación se deshace dejando todo como estaba.
4. **Ninguna dirección publicada acaba en 404.** Si una ficha se une, su dirección lleva a la que
   queda; si se retira, explica la retirada.
5. **Idempotente.** Dos recogidas seguidas sin noticias nuevas no cambian nada: ni versiones, ni
   motivos, ni avisos.
6. **Cada ficha, aislada.** Si una falla en un paso, se apunta y las demás siguen.

## Los estados

```
              extractor                control + puerta
 candidato ─────────────▶ NUEVA ─────────────────────────▶ PUBLICADA ◀──┐
                            │  (en la base, no en la web)      │  │      │ corrección
                            │                                  │  └──────┘ (versión nueva
                            ▼                                  │            que pasa la puerta)
                    retirada sin salir                         ├────▶ UNIDA     (su dirección redirige)
                    (no tiene dirección)                       └────▶ RETIRADA  (su dirección lo explica)
```

- **Nueva.** Está en la base y no en `publicado`. No sale en la web ni se avisa. El cerrojo solo
  le protege lo revisado a mano: el filtro de entrada puede corregirle el día, el lugar o una
  autoridad sin que nada se lo devuelva.
- **Publicada.** Tiene fila en `publicado`: la entrada pública tal como sale y el documento
  interno de esa misma versión. Desde aquí el cerrojo protege lo decidido con cita. La tabla se
  llena una vez con lo que ya estaba publicado (`puerta.sembrar`), lo primero de la recogida:
  antes de eso ninguna ficha se guarda, para que una ya publicada no parezca nueva.
- **Unida.** Fundida en otra (`fusionado_en`). Su fila pasa a «unida» cuando la ficha que queda
  está publicada; hasta entonces sigue saliendo como estaba. Su dirección lleva siempre a la
  ficha de su unión vigente: la puerta vuelve a mirar las filas unidas en cada publicación y, si
  la ficha cambió de unión (una se deshizo y se unió a otra) o la que quedaba se unió a su vez,
  pone el destino al día. Mientras la ficha de la unión nueva no esté publicada, la dirección
  sigue llevando adonde llevaba (no a un 404) y la invariante I7 lo dice.
- **Retirada.** Con `retirado` en la base por una decisión explícita. Su fila pasa a «retirada»
  con su fecha y su motivo en español y en inglés (el de la retirada si está escrito en los dos
  idiomas; el de una regla interna no se publica: sale un motivo general). Una ficha retirada no
  vuelve al rehacerla una extracción o una reconstrucción: solo por una revisión a mano o, si
  nunca llegó a salir en la web, con un artículo que la retirada no tenía (la nota oficial que
  llega después de que el filtro la retirase por falta de fecha).

## La puerta de la publicación

`exportacion/puerta.py`, en cada recogida, al publicar. De la base sale, como siempre, la versión
candidata de cada ficha activa. Una versión entra en `publicado` solo si se cumple todo esto:

| Condición | Si no se cumple |
|---|---|
| el control de las fichas terminó en esta pasada | ninguna ficha cambia en lo publicado |
| la ficha tiene el pase del control (filtro de entrada, verificación, duplicados) | la nueva no sale; la publicada queda como estaba |
| la auditoría de protección no la marca (P, R, V, W, X) | queda su última versión buena |
| cumple las invariantes de ficha (abajo) | queda su última versión buena |
| su entrada pública se puede generar y valida | queda su última versión buena |

«Queda como estaba» es literal: la fila de `publicado` no se toca. Una ficha que nunca salió no
sale. Lo que la puerta no deja pasar queda en el cursor `puerta` (ficha, condición y qué
cambiaba), en `control.json` y en el resumen diario; una invariante rota manda además un aviso
privado.

La puerta sustituye a dos mecanismos anteriores que hacían lo mismo a medias: la lista de
«retenidos» del control (lo que no estaba en la lista se publicaba: si el control fallaba, las
fichas nuevas de esa hora salían sin filtro) y la red de versiones buenas, que guardaba sus
copias en un fichero al lado de la publicación.

Los ficheros públicos (`incidentes.geojson`, `incidentes_sin_ubicacion.json`) se escriben con las
filas publicadas. `unidos` sale de las filas unidas y `retirados` (campo nuevo, opcional) de las
retiradas: identificador, fecha y motivo. La web sirve la dirección de una retirada con esa
explicación.

## Los avisos

`recogida/avisos.py` compone cada aviso con el documento interno que guarda la fila de `publicado`,
no con el de la base: lleva los mismos datos que la ficha que el enlace enseña. Un aviso pendiente
de que la web sirva su ficha caduca cuando su suceso sale de la ventana de avisos. Cada mensaje se
compone y se envía por separado: un fallo en uno no corta los demás.

## Escribir una ficha

Toda escritura pasa por `Almacen.guardar_incidente`, que decide (revisiones a mano,
rectificaciones, reglas), aplica el cerrojo y valida. Desde ahora, además:

- **no escribe una versión que solo cambia la fecha de actualización**, y devuelve si escribió.
  Los motivos del historial y los recuentos («corregidos», «unidos») se apuntan solo si escribió.
  Lo que el control propone cada hora y el cerrojo retiene cada hora ya no deja nada;
- **el cerrojo del nivel «con cita» mira si la ficha está publicada** (fila en `publicado`), no
  si está activa;
- **quien corrige comprueba que el cambio quedó**: si el cerrojo lo retuvo, la decisión lo dice
  («retenido») en vez de darlo por hecho.

## Unir, separar y deshacer

- **Unir.** Qué fichas son el mismo suceso, cuál queda y de dónde sale su fecha lo dice la
  definición de suceso ([`definicion_suceso.md`](definicion_suceso.md), `proceso/suceso.py`). La
  unión guarda la instantánea de las dos fichas antes de unirse y la de la que queda
  justo después (tabla `fusiones`). Antes de intentarla se pregunta al cerrojo si la retendría
  (también en `revisar_fusiones` y en las uniones del control): lo que no va a pasar no se intenta.
  La regla de fusión no une sola dos fichas que ya tienen su página en la web: eso lo decide
  quien lee las fuentes.
- **Deshacer una unión.** La absorbida vuelve con sus fuentes. La que queda pierde las fuentes y
  afirmaciones que la unión le trajo, y cada dato que la unión le copió (el día, el fin, la
  respuesta, la presencia, las pruebas, el cierre, los pasos del estado) vuelve a su valor de
  antes si sigue siendo el que la unión puso; lo que cambió después por otra vía se respeta. El
  cerrojo no retiene esos cambios: son lo que la unión trajo. Las uniones anteriores al 10 de
  noviembre de 2026 no guardaron su instantánea: se saca del historial de la ficha.
- **Separar.** Cada revisión de `separar` se aplica aislada: la que falla queda en el registro y
  no corta las demás.
- **La parte de una separación** se vuelve a extraer con su día y su descripción y **no está atada
  a lo que decidía la ficha mezclada**: las frases compartidas ya no «contradicen» los datos de su
  suceso. Lo revisado a mano sí manda.
- **Un candidato con parte está cerrado**: los artículos nuevos del mismo sitio no entran en él.
  Forman un candidato normal, cuya ficha pasa por el filtro de entrada, que la une a la parte que
  le corresponde.
- **Deshacer una separación** sigue siendo una revisión a mano (unir las partes con `unir`, que sí
  se deshace entera). El reparto de una separación no es atómico ni guarda su instantánea: cada
  escritura del almacén se confirma por separado. Queda pendiente; no se ha hecho a medias.

## Invariantes

`proceso/invariantes.py`. Las mismas funciones corren en la puerta (cada recogida), en el ensayo y
en la CI (sobre la base de prueba y sobre los casos reales de `tests/`).

| | Invariante | Si se rompe en producción |
|---|---|---|
| I1 | ninguna ficha publicada sin pase del control | la ficha no entra; queda la versión anterior |
| I2 | ninguna dirección publicada en 404: toda fila es publicada, unida a una publicada o retirada con motivo | la fila no cambia de estado |
| I3 | ningún dato revisado a mano distinto de su revisión | queda la última versión buena |
| I4 | ninguna versión nueva igual a la anterior salvo la fecha | se cuenta (no se puede publicar mal por esto) |
| I5 | ningún aviso con datos distintos de lo publicado | el aviso no sale |
| I6 | ninguna unión vigente entre fichas que la definición de suceso da por distintos ([`definicion_suceso.md`](definicion_suceso.md)) | se cuenta y se avisa: `revisar_fusiones` tenía que haberla deshecho |
| I7 | ninguna dirección publicada lleva a una ficha de otro suceso: la de una ficha unida lleva a una ficha de su unión vigente, que no es de otro país (con una autoridad del suyo) ni la separó de ella una revisión | se cuenta y se avisa: la puerta tenía que haber puesto la fila al día |

Cada rotura queda en el cursor `invariantes` y llega como aviso privado, una vez por ficha e
invariante.

El inicio que dice un aviso es el de la entrada publicada: la exportación lo pone de acuerdo con
el primer aviso (`proceso/coherencia.py`) y puede no ser el de la base. I5 compara después de
ese mismo paso.

## Qué fallo de la semana cierra cada regla

| Fallo | Regla |
|---|---|
| fichas nuevas publicadas sin filtro si el control no corría | la puerta: sin pase no hay fila |
| aviso con la versión que la red no dejó salir (00773) | avisos desde `publicado` |
| el cerrojo devolvía el día o el lugar que el filtro corregía | cerrojo «con cita» solo sobre lo publicado |
| una versión, un motivo y un «corregido» cada hora (00773, 00747 en 00743) | escritura idempotente; no se intenta lo que el cerrojo retiene |
| deshacer una unión dejaba el día del otro suceso | instantáneas de la unión |
| la parte que conserva el número no podía cambiar (00770) | la parte no está atada a lo mezclado |
| una ficha fallaba y cortaba a las de detrás | cada elemento, aislado |
| una ficha retirada volvía al reextraerse | retirada firme |
| dirección de una ficha unida a otra no publicada, o retirada, en 404 | estados de `publicado` |
| dirección de una ficha que cambió de unión y seguía llevando a la ficha anterior, de otro suceso (00218, 00522) | las filas unidas se ponen al día con su unión vigente; I7 |

## Cómo se prueba

- Las pruebas corren con el cerrojo en «aplicar», como producción (`tests/conftest.py`). Las que
  montan su caso con una ficha del nivel manual, o con un estado que el cerrojo ya no deja crear,
  piden «observar» con `cerrojo_en_observar`. Al pasar la batería a «aplicar» salieron tres fallos
  que en «observar» no se podían ver (están en `tests/test_ciclo_de_vida.py`).
- `tests/test_puerta.py` (la puerta y las invariantes), `tests/test_ciclo_de_vida.py` (la
  escritura, las uniones y la retirada), `tests/test_partes_cerradas.py` (las partes de una
  separación) y `tests/test_semana_noviembre.py` (los casos reales de la primera semana de
  noviembre de 2026).
- En el servidor, el ensayo de varias recogidas seguidas sobre la misma copia (`ENSAYO_RECOGIDAS`
  del guion de ensayo, con `recogida.horaria --conservar`) hace una foto de la base antes y
  después de cada una (`recogida/ensayo.py`) y escribe sus diferencias: fichas nuevas,
  desaparecidas, uniones, separaciones, cambios por campo, versiones nuevas, lo que entra o sale
  de lo publicado y los avisos que habrían salido. La segunda y las siguientes, sin noticias
  nuevas, no cambian nada.

## Lo que queda fuera

- El reparto atómico de una separación y deshacerla con su instantánea (arriba).
- La exportación semanal sigue saliendo de la base entera, no de la tabla `publicado`.
