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

### Lo que falta (desde el 19 de octubre de 2026)

La lectura de arriba solo compara la ficha con sus citas: no ve lo que la ficha no tiene. En
España, Melilla 22/09/2026 seguía «notificado» aunque la Delegación del Gobierno lo había
reconocido en la prensa; Melilla 18/09/2026 no tenía ficha. Cuatro búsquedas más, con la misma
regla de la frase literal (en el texto numerado que se mandó: el titular y el comienzo de la
página de cada noticia) y cada una con su cupo por pasada (`busqueda.por_pasada`). Código:
[`proceso/segunda_busqueda.py`](../proceso/segunda_busqueda.py) y
[`recogida/segunda_busqueda.py`](../recogida/segunda_busqueda.py); pruebas:
[`tests/test_segunda_busqueda.py`](../tests/test_segunda_busqueda.py).

1. **Declaraciones oficiales que faltan.** Incidentes publicados «notificados», o con la presencia
   «no confirmada», de más de 48 horas: sus noticias y las posteriores que nombran su lugar (la
   selección del barrido de rectificaciones). ¿Alguna cita una declaración de una autoridad
   oficial que confirma, niega o rectifica el suceso o el dron, también en estilo indirecto?
2. **Incidentes que faltan.** Noticias recogidas en los últimos 14 días que no están en ninguna
   ficha publicada (ni en su candidato) ni esperan su primera extracción: descartadas por el
   filtro o sin agrupar. ¿Cuentan un suceso con drones dentro del alcance, con día y lugar? Se le
   manda también la lista de fichas del mismo país y fechas cercanas: si dice que coincide con
   una, no es candidato.
3. **Atribución.** Incidentes confirmados sin atribuir: ¿una autoridad oficial afirma
   expresamente quién es el responsable? Una frase que investiga, sospecha, no descarta o solo
   vincula o relaciona nunca es candidata (`configuracion/expresiones_duda.json`, la misma lista
   de la regla estricta de atribución).
4. **Lugar y duración.** Fichas con el lugar a nivel de país o de región cuyas noticias nombran la
   instalación o la localidad, y cierres sin duración cuyas noticias dan la duración o la hora de
   reapertura.

Una vez al día, en la primera pasada desde las 03:00 UTC, **el barrido de un país**: rotando por
los países con incidentes, de más a menos, las búsquedas 1, 3 y 4 sobre todos sus incidentes, sin
el filtro de antigüedad, y la 2 sobre todas sus noticias. La base de la capa guarda qué país se
hizo y cuándo. Lo que se manda se guarda con su huella y no se vuelve a preguntar mientras no
cambie.

En la recogida horaria, cada candidato va por el camino que ya existe y **nada se decide aquí**:

- declaraciones y atribución: la noticia entra en el candidato de la ficha, su frase va a la
  extracción y el candidato se repite con el experto con el motivo opcional `declaracion`
  ([`docs/modelos.md`](modelos.md), motivo 7: si el experto agotó su tope, vale el base, nunca la
  reserva crítica). El estado y la atribución los deciden las reglas de siempre;
- incidentes que faltan: la noticia vuelve a la extracción por el mismo camino interno que los
  artículos dirigidos (sin tocar `configuracion/articulos_dirigidos.json`); si su candidato ya se
  extrajo, se repite con el experto. Pasa por el control de duplicados como cualquier otra ficha;
- lugar y duración: la verificación del experto.

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
primeros días fue el hallazgo más frecuente y casi siempre ruido. Tampoco un tipo «contradicho»
cuya frase no cuenta otro tipo del esquema (un cierre de aeropuerto o una entrada desde fuera):
que un dron cayera, explotara o atacara sigue siendo un sobrevuelo o una incursión.

**Orden y reparto.** Primero las declaraciones y los incidentes que faltan; después lo
contradicho; después los duplicados; después la atribución, el lugar y la duración; al final, el
resto. Cada recogida entrega como mucho 2 candidatos a la extracción (`busqueda.por_recogida`, 8
al día, `por_dia`) y manda como mucho 2 al experto (`recogida.por_recogida`). Lo que revisa el
experto en el modo `segunda_lectura` cabe en sus 0,30 dólares al día y por debajo del ritmo de su
tope; las extracciones repetidas con el experto van con el motivo opcional `declaracion` y nunca
tocan la reserva crítica. Cada decisión queda guardada (clave `segunda:…`
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
