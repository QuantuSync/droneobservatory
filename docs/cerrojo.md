# El cerrojo de lo decidido

Lo que se decide de una ficha, con una revisión a mano o con la frase de una fuente, no lo deshace
una regla, una reextracción ni una unión. Hasta ahora cada dato tenía su propia protección en cada
camino de escritura, y cada error nuevo era un camino que aún no la tenía. El cerrojo es un punto
único: `Almacen.guardar_incidente`, por el que pasa toda escritura de una ficha, compara la versión
guardada con la nueva antes de escribir. La lista de lo protegido está en `proceso/protegido.py` y
sale de lo que ya existe; no añade ficheros de datos protegidos.

## Qué está protegido

- **Nivel manual.** Las fichas de `configuracion/incidentes_revisados.json` y las del conjunto de
  referencia (`tests/referencia/fichas.json`). Sus datos publicados (estado, presencia, tipo,
  objetivo, lugar, inicio con su fin, número de drones, cierre con su duración, titular y si está
  retirada) solo cambian por una revisión a mano o por una rectificación oficial nueva.
- **Nivel con cita.** En cualquier ficha publicada, lo que `proceso/decididos.py` da por decidido
  con la frase de una fuente, más el estado y la presencia que decide una autoridad, y la retirada
  de una ficha que cuenta una autoridad. Solo cambian si una fuente que la ficha no tenía trae una
  frase que está literalmente en lo guardado de su artículo. Otra declaración sacada del mismo
  artículo no es una fuente nueva.
- **Uniones prohibidas.** Los pares separados por una revisión, las partes de una separación, los
  distintos del experto y los relacionados. Se miran entre grupos enteros: todas las fichas que
  cuelgan de la destinataria contra todas las que cuelgan de la absorbida, de modo que ninguna
  cadena las salte. Una unión hecha a mano manda sobre una marca anterior, y conservar el número más
  antiguo de un mismo grupo no es una unión nueva.
- **Lo que una frase no dice no está protegido.** Una frase respalda un dato solo si lo dice
  (`dice_el_dato`):
  - en los drones, el número; en un intervalo, sus dos extremos. «19 încălcări» no dice «de 9 a 19
    drones» (EODI-2026-00744);
  - en un inicio con hora, la hora;
  - en el modelo, su nombre.
  Un dato así que ninguna frase dice ni fija una revisión se puede corregir. En una ficha del
  nivel manual, el titular y el estado se guardan solo si los fija una revisión o el valor
  comprobado de la referencia. Decidido el 3 de noviembre de 2026: está bien así. Un titular
  manual sin revisión no tiene frase propia: sigue a lo que se retiene (abajo) y lo vuelve a
  escribir `decidir.decidir_titulo` a partir de los datos.
- **El modelo de dron.** El modelo que nombra la frase de una fuente está protegido como el
  número (con cita). Otra redacción del mismo nombre no es un cambio: «витлов самолет» y
  «безпилотен летателен апарат тип "витлов самолет"».
- **El cierre nuevo lo dice una frase que nombra el cierre** (`presencia.CIERRE_EN_FRASE`). Una
  alerta a la población no cierra nada: EODI-2026-00725, la alerta RO-Alert en Suceava.
- **El inicio no pierde su fin**, ni siquiera con una revisión del inicio (EODI-2026-00077).
- **Una fuente anterior al suceso junta dos sucesos.** Una versión que trae una fuente publicada
  más de 2 días antes del día del suceso (`fuentes_anteriores`), y que la guardada no tenía,
  cuenta otro suceso. Solo una revisión la deja pasar, y tampoco pasa una unión que la traiga.
  Ejemplo: EODI-2026-00079, el aviso de un piloto en Hannover el 17 de febrero de 2026, recibió
  la nota del 11 de agosto y acabó fundido en EODI-2026-00022.
- **El titular y el estado siguen a lo retenido.** Si se retiene la presencia, los drones, el
  lugar, el inicio, el cierre o el modelo, el titular y el estado se quedan como estaban, salvo
  que los fije una revisión o una rectificación (`SIGUEN_A`).
- **La fuente nueva dice el valor nuevo.** No basta con que exista: su frase debe decir ese valor
  (`dice_el_valor_nuevo`). Un sin dato o una hora de publicación no los dice ninguna fuente.
- **Fichas del nivel manual que se funden.** Aunque no haya par prohibido, una ficha publicada del
  nivel manual solo la funde en otra una revisión a mano o una unión a mano anterior. Se mira la
  ficha que se funde, no la que queda: recibir un duplicado no le quita nada a la que queda, cuyos
  datos siguen protegidos uno a uno.
- **Retirada de una ficha publicada.** Solo pasa si sale de una decisión explícita
  (`protegido.DECISIONES_RETIRADA`):
  - la barrera de titulares a las 6 horas;
  - el repaso de entrada con decisión;
  - una revisión a mano;
  - el veredicto de que no es un suceso.

  Hay además tres caminos de regla explícita que pasan por `extraccion.retirar`
  (`DECISIONES_RETIRADA_DIRECTAS`). Se reconocen por los dos pasos más cercanos de la pila, no por
  cualquier paso: un fallo dentro de una reconstrucción no es la decisión de retirar.
  - `incursiones.retirar`: el alta que salía solo del parte ucraniano (EODI-2026-00482);
  - `extraccion_oficial.revalidar_altas`: el alta oficial cuyo día no está en su frase
    (EODI-2024-00002);
  - `extraccion.reconstruir`: la copia numerada de más al reconstruir (EODI-2026-00254).

  Una ficha del nivel manual, o que cuenta una autoridad, no la retira ninguno de estos caminos:
  pide una revisión a mano o una fuente nueva con su frase. Lo demás se apunta como `retenido:`;
  en `aplicar`, se queda la versión publicada entera.

  Lo que el filtro de entrada retiene porque ninguna frase da la fecha del suceso se retira a las
  6 horas como no verificable (`control_fichas.resolver_sin_fecha`, `DECISIONES_SIN_PUBLICAR`).
  Nunca salió en la web, así que su retirada no quita nada publicado. Ejemplos: EODI-2026-00697,
  un dron hallado en un poste; EODI-2026-00744, un balance mensual.
- **Reaperturas.** Una ficha fundida solo deja de estarlo por una revisión a mano o por una
  separación, es decir, si el par es de los que no se unen. La renumeración que conserva el número
  más antiguo de un grupo no es una reapertura.

El alta de una ficha nueva no está protegida: de eso se ocupa el filtro de entrada. Tampoco lo está
la lista de fuentes de una ficha: la fuente ajena se quita con `quitar_fuentes` y la vigila la
auditoría.

El texto completo de los artículos no se guarda. La comprobación de la frase se hace, con
`control_fichas.frase_valida`, contra lo que queda de él: el titular y las frases literales de su
última extracción (`Almacen.texto_guardado`). Es mecánica, sin modelo.

## Qué hace

Después de `rectificaciones.mantener` y de `decidir.aplicar`, y antes de validar y escribir:

- un cambio a un dato protegido sin justificación se apunta y, en modo `aplicar`, no se hace: se
  conserva el valor guardado con su afirmación, dato a dato, y el resto de la versión nueva pasa;
- una ficha que se iba a marcar como fundida en otra con una unión prohibida se apunta y, en modo
  `aplicar`, no se marca, la destinataria vuelve a su versión anterior y la fusión no se anota;
- una reapertura sin justificación se apunta y, en modo `aplicar`, la ficha sigue fundida, la
  destinataria vuelve a su versión anterior y la fusión no se da por revertida;
- cada caso queda en `control_fichas` con el prefijo `retenido:`: ficha, dato, antes, después,
  módulo y función que lo intentó, y fecha. Lo que pasa con justificación queda con `permitido:`;
- si el propio cerrojo falla, la escritura pasa como antes y el fallo se apunta con
  `cerrojo_fallo:`. Nunca para la recogida.

El modo está en `configuracion/cerrojo.json`: `observar` solo apunta y no cambia nada de lo que se
guarda; `aplicar` retiene. Un modo desconocido o el fichero ausente equivalen a `observar`.
El 3 de noviembre de 2026 el cerrojo sigue en `observar`: la regla revisada y la red de la
publicación están en main y el paso a `aplicar` es un PR aparte que solo cambia ese fichero.

Para volver a `observar` basta un PR de una línea con `"modo": "observar"` en ese fichero. Se
aplica en la recogida siguiente; no hay nada más que deshacer, porque `observar` deja la base
como sin cerrojo.

## La red de la publicación

`exportacion/version_buena.py`, desde el 3 de noviembre de 2026. Antes de escribir
`incidentes.geojson` e `incidentes_sin_ubicacion.json`, la publicación pasa la auditoría de
protección: P, R, V, W y X. En X solo cuenta lo que la ficha aún tiene (ver «Cómo se vigila»).
El registro dice «publicada en su versión buena», «publicada en su versión anterior» o «no
publicada».

Cada ficha marcada sale:
- en su última versión buena, la última que se publicó sin marca (`versiones_buenas.json`, en una
  carpeta al lado de la publicación que no se sube);
- sin ella, como en la publicación anterior;
- si nunca se publicó, no sale, y queda apuntada.

Nada de esto para la publicación: si la auditoría o la sustitución fallan, sale lo de la base.

Lo sustituido queda en el cursor `publicacion_buena` y en `control.json`
(`cerrojo.version_anterior`). La vigilancia abre la incidencia `version_anterior` con la ficha, la
comprobación y lo que cambia, y el resumen diario cuenta «Fichas publicadas en su versión
anterior: N».

## El origen del lugar de una alerta

El control de las fichas no toma como lugar un aeropuerto cuya frase solo cuenta que reaccionó a
una alerta (`control_fichas.reacciona_a_una_alerta`). Ejemplo: EODI-2026-00719, «în urma
mesajului RO-Alert»: la alerta era para el distrito y el aeropuerto solo cerró su espacio aéreo.

## Un fallo no retira

Si la versión nueva de una ficha publicada no se puede guardar (cualquier excepción o documento
inválido, un lugar que no vale, una respuesta ilegible del experto, una ficha que ya no es
publicable), la ficha se queda como está: `proceso/extraccion.conservar_publicada` apunta en el
control `guardado_fallido:<ficha>:<fecha>` con la ficha, el camino y el error, y un guardado bueno
posterior corta la cuenta. Antes, ese fallo acababa en una retirada: así salieron de la web
EODI-2026-00130 y EODI-2026-00302 el 1 de noviembre de 2026.

## Cómo se vigila

- **Auditoría X** (`proceso/auditoria_fichas.py`): cambios a algo protegido guardados sin
  justificación. Con el cerrojo en `aplicar` vale 0; cualquier otro valor es un agujero. En
  `observar` cuenta lo mismo que se habría retenido. Desde el 3 de noviembre de 2026, la misma
  cuenta que la red de la publicación (`protegido.cambios_sin_permiso` con las fichas de ahora):
  solo lo que la ficha aún tiene. No cuenta un cambio que otro posterior ya deshizo (una
  revisión, el control), ni uno que vuelve al valor de antes de las 48 horas, ni un dato cuyo
  valor actual fija una revisión a mano o una rectificación oficial (también el tipo y el titular
  que salen de datos revisados), ni los datos de una ficha retirada o fundida, salvo la retirada.
  Ejemplo: EODI-2026-00079, cuyo cierre revisado coincidía con el de un cambio malo del 2/11 y
  quedaba fuera de la web.
- **Auditoría Z**: fichas publicadas con una fuente anterior al suceso, sin cambio de por medio.
- **Vigilancia** (`recogida/vigilancia.py`): avisa si el cerrojo falla y, en `aplicar`, si una ficha
  aparece en una comprobación de protección de la auditoría (P, R, V, W, X).
- **Resumen diario** (`recogida/visitas.py`): la línea «Cambios retenidos: N (en observación)» con
  las fichas y los datos, «Guardados fallidos de fichas publicadas: N» con las fichas y «Fichas
  publicadas en su versión anterior: N».
- **Vigilancia**, también: incidencia si una misma ficha no se puede guardar 3 veces seguidas.

## Pruebas

`tests/test_cerrojo.py` intenta guardar por `guardar_incidente`, en `aplicar`, cada error real desde
el 20 de octubre de 2026 (`tests/cerrojo/errores_reales.json`), además de cadenas de uniones y
renumeraciones al azar con semilla fija, los cambios legítimos, que en `observar` la base queda como
sin cerrojo y que un fallo del cerrojo no para la escritura. `tests/test_retiradas_por_fallo.py`
reproduce el camino de EODI-2026-00130 y EODI-2026-00302, cada camino de fallo y la retirada en los
dos modos. `tests/test_version_buena.py` reproduce una ficha marcada en cada comprobación de la
red de la publicación.

La regla se midió el 3 de noviembre de 2026, antes de pasar a `aplicar`, con los cambios a datos
protegidos de fichas publicadas desde el 1 de noviembre, clasificados leyendo la fuente:

| Lista | Cambios malos retenidos | Correcciones buenas que pasan |
|---|---|---|
| Ajuste (1 y 2 de noviembre) | 22 de 22 | 36 de 41 |
| Prueba (desde el 2 de noviembre) | 17 de 17 (3 en el origen) | 23 de 25 (1 en el origen) |

En `aplicar`, ninguna corrección cuya frase diga el valor nuevo queda retenida. Las dos con frase
que se retienen en la lista de ajuste deshacen un cambio malo que en `aplicar` no habría pasado.
