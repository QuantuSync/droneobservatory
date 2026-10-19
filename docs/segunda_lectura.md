# Segunda lectura con un servicio secundario de modelos

Desde el 18 de octubre de 2026. Una capa **secundaria, gratuita y prescindible** que vuelve a leer
lo publicado con un servicio secundario de modelos y señala lo que conviene revisar. El
observatorio no depende de ella: si el servicio se cae, va lento o desaparece, todo sigue
exactamente igual que sin ella.

Código: [`modelo/secundario.py`](../modelo/secundario.py) (el cliente),
[`proceso/segunda_lectura.py`](../proceso/segunda_lectura.py) (las reglas, sin llamadas),
[`recogida/segunda_lectura.py`](../recogida/segunda_lectura.py) (las pasadas, su base y el paso de
la recogida) y [`configuracion/segunda_lectura.json`](../configuracion/segunda_lectura.json)
(márgenes, candidatos por recogida, ritmo y ventana de cada pasada). Pruebas:
[`tests/test_segunda_lectura.py`](../tests/test_segunda_lectura.py).

## Principios

1. **No decide nada.** Nunca publica, retira, une, separa ni cambia un estado, una presencia ni un
   dato. Solo marca candidatos, que pasan por el circuito de siempre: las reglas, el modelo
   experto ([`docs/modelos.md`](modelos.md)) y las declaraciones oficiales.
2. Un estado solo cambia por una declaración oficial; nada publicado se retira ni se rebaja sin el
   experto; nada desaparece del mapa. Lo que diga el modelo secundario nunca se aplica por sí solo.
3. **Independiente.** Proceso y temporizador propios y su propia base SQLite
   (`segunda_lectura.sqlite`, en su carpeta de datos). La base principal la abre **solo para
   leer** y nunca escribe en ella. La recogida horaria solo lee sus candidatos, en un paso aislado
   con un tope de 30 segundos: si el fichero no existe, está bloqueado o roto, lo ignora. El paso
   nunca cambia el código de salida de la recogida.
4. **Sin avisos.** Si el servicio secundario falla, se anota en el registro, se salta y se
   reintenta en la pasada siguiente. Nunca avisa y la pasada siempre termina con código 0.
5. **Gasto.** El servicio secundario es gratuito. Lo único que cuesta es el experto al revisar lo
   marcado: modo `segunda_lectura` de [`modelo/coste.py`](../modelo/coste.py), como mucho
   **0,30 dólares al día** (`LIMITE_SEGUNDA_EXPERTO_DIARIO_USD`), que cuentan dentro del dólar
   diario del experto y **nunca** salen de la reserva crítica. Desde el 19 de octubre de 2026,
   además, solo gasta lo que los escalados normales no necesitan: el gasto del experto en el día
   tiene que ir por debajo del ritmo de su tope (el dólar entero a las 00:00 UTC, la mitad a las
   12:00, `margen_escalados`). Así nunca se come de madrugada el tope que necesitan las recogidas
   del día. Lo que no cabe espera a otra recogida.
6. **Datos.** Solo se envía contenido público: los datos de las fichas publicadas y las citas,
   titulares y frases de sus fuentes públicas.

## Flujo

### La pasada (cada hora, de 45 a 10)

Un temporizador propio lanza una pasada cada hora en el minuto 45, que para sola como mucho en el
minuto 10 de la hora siguiente: nunca coincide con la recogida horaria. Si se lanza fuera de esa
ventana (por ejemplo, al arrancar el servidor), no hace nada. Ritmo: como mucho 8 peticiones por
minuto, 120 segundos de espera por petición y, ante un 429 o un error del servidor, espera
exponencial; con 3 fallos seguidos del servicio, la pasada termina (con código 0) y lo anota.

1. **Barrido diario de rectificaciones** (una vez al día, en la primera pasada desde las 02:00
   UTC). Con la selección del barrido mensual ([`docs/rectificaciones.md`](rectificaciones.md),
   punto 3): los titulares guardados posteriores al suceso que nombran su lugar en sus idiomas y
   suenan a rectificación (`configuracion/senales_rectificacion.json`), pero sobre **todos** los
   incidentes publicados con la presencia confirmada, no confirmada o no acreditada y al menos un
   día de antigüedad. El modelo secundario dice cuáles merecen la pregunta. Cada titular se le
   manda una sola vez; los que el experto ya decidió o ya están en la cola no se mandan.
2. **Posibles duplicados.** El generador de pares del control
   (`proceso/control_fichas.pares_candidatos`) con márgenes más amplios (72 horas y 30 km,
   configurables), sin los pares que el control ya compara o comparó, los que una revisión separó
   y los cierres del mismo sitio en noches distintas. El modelo secundario dice si parecen el
   mismo suceso, con una frase de las citas de cada ficha.
3. **Segunda lectura de las fichas publicadas** (solo la capa de Europa), en este orden: las
   nunca leídas, las que cambiaron desde su última lectura (una huella de los datos clave y de las
   citas) y después la lectura más antigua. A cada ficha se le mandan sus datos clave (es un
   incidente, tipo, país, lugar y nivel, fecha de inicio, presencia, número de drones, cierre y
   minutos de cierre, dron estatal) y las citas literales de sus fuentes, en su idioma original.
   La respuesta se pide en JSON con su esquema y el código la valida: una respuesta inválida se
   descarta y la ficha se vuelve a leer otro día. Para cada dato: «apoyado», «contradicho» o «sin
   apoyo», con la frase literal que lo justifica; y si la ficha parece resumir varios sucesos.

Es **candidato** una ficha con algún dato «contradicho», o «sin apoyo» en el lugar, la fecha, la
presencia o el número de drones, o que parece resumir varios sucesos; un par que parece el mismo
suceso; un titular que puede contar una rectificación. La frase que da el modelo tiene que estar,
literal, en las citas que se le mandaron (el código lo comprueba): si no está, el hallazgo no
cuenta. Un dato que la ficha no tiene no se valora.

### El paso de la recogida horaria

Antes de las rectificaciones y del control de las fichas, la recogida lee los candidatos de la
base de la capa (solo leyendo, 30 segundos como mucho) y:

- los de **datos** van a la verificación del control de las fichas
  ([`docs/control_fichas.md`](control_fichas.md)) hecha directamente por el **experto**; lo que
  decide se guarda como la verificación de la ficha y lo aplica el control con sus reglas, igual
  que hoy;
- los **duplicados** van a la comparación del control hecha por el **experto**; si decide que son
  el mismo suceso, se unen con las reglas de siempre (se conserva la ficha más antigua);
- las **rectificaciones** entran en la **misma cola** que lo elegido por el barrido mensual y las
  decide el experto con las reglas de siempre (`rectificaciones.decision_valida`,
  `MAX_POR_PASADA` y su tope).

Como mucho 2 candidatos de datos o duplicados por recogida (configurable), lo contradicho primero,
siempre con el modo y el tope del principio 5. Una ficha cuyo único hallazgo es la fecha de inicio
«sin apoyo» queda marcada pero **no va al experto** (`proceso/segunda_lectura.al_experto`): en los
primeros días fue el hallazgo más frecuente y casi siempre ruido. Cada decisión queda guardada (clave `segunda:…`
del control de las fichas) y no se repite.

Lo que hizo la última pasada, los candidatos y el gasto del experto del día en este modo se ven en
el estado interno del control (`control.json`, apartado `segunda_lectura`). Ninguna vigilancia
lo mira ni lo reinicia: la capa no es vital.

## Cómo desactivarla

Quitar la variable `EODI_SECUNDARIO_URL` (o cualquiera de `EODI_SECUNDARIO_CLAVE` y
`EODI_SECUNDARIO_MODELO`) del entorno del extractor. Sin ella, la pasada no hace nada y termina
con código 0, y la recogida no lee ningún candidato. Para volver a activarla, basta con ponerla
de nuevo. Lo ya decidido por el experto se queda como está, igual que cualquier otra decisión
suya.
