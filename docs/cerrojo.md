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
- **Lo que una frase no dice no está protegido.** Una frase respalda un dato solo si lo dice: el
  número en los drones y la hora en un inicio con hora (`dice_el_dato`). Un dato así que ninguna
  frase dice ni fija una revisión se puede corregir. En una ficha del nivel manual, el titular y el
  estado se guardan solo si los fija una revisión o el valor comprobado de la referencia.
- **El titular y el estado siguen a lo retenido.** Si se retiene la presencia, los drones, el lugar
  o el inicio, se quedan como estaban, salvo que los fije una revisión o una rectificación
  (`SIGUEN_A`).
- **La fuente nueva dice el valor nuevo.** No basta con que exista: su frase debe decir ese valor
  (`dice_el_valor_nuevo`). Un sin dato o una hora de publicación no los dice ninguna fuente.
- **Fichas del nivel manual que se funden.** Aunque no haya par prohibido, una ficha publicada del
  nivel manual solo la funde en otra una revisión a mano o una unión a mano anterior. Se mira la
  ficha que se funde, no la que queda: recibir un duplicado no le quita nada a la que queda, cuyos
  datos siguen protegidos uno a uno.
- **Retirada de una ficha publicada.** Solo pasa si sale de una decisión explícita: la barrera de
  titulares a las 6 horas, el repaso de entrada con decisión, una revisión a mano o el veredicto de
  que no es un suceso (`protegido.DECISIONES_RETIRADA`). Una retirada de una ficha del nivel manual o
  que cuenta una autoridad sigue pidiendo lo que pedía: una revisión a mano o una fuente nueva con
  su frase. Lo demás se apunta como `retenido:`; en `aplicar`, se queda la versión publicada entera.
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
  `observar` cuenta lo mismo que se habría retenido.
- **Vigilancia** (`recogida/vigilancia.py`): avisa si el cerrojo falla y, en `aplicar`, si una ficha
  aparece en una comprobación de protección de la auditoría (P, R, V, W, X).
- **Resumen diario** (`recogida/visitas.py`): la línea «Cambios retenidos: N (en observación)» con
  las fichas y los datos, y «Guardados fallidos de fichas publicadas: N» con las fichas.
- **Vigilancia**, también: incidencia si una misma ficha no se puede guardar 3 veces seguidas.

## Pruebas

`tests/test_cerrojo.py` intenta guardar por `guardar_incidente`, en `aplicar`, cada error real desde
el 20 de octubre de 2026 (`tests/cerrojo/errores_reales.json`), además de cadenas de uniones y
renumeraciones al azar con semilla fija, los cambios legítimos, que en `observar` la base queda como
sin cerrojo y que un fallo del cerrojo no para la escritura. `tests/test_retiradas_por_fallo.py`
reproduce el camino de EODI-2026-00130 y EODI-2026-00302, cada camino de fallo y la retirada en los
dos modos.
