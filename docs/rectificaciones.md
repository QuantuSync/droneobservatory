# Rectificaciones oficiales de la presencia del dron

Desde el 16 de octubre de 2026. Código: [`proceso/rectificaciones.py`](../proceso/rectificaciones.py)
(qué cambia y cómo queda), [`recogida/rectificaciones.py`](../recogida/rectificaciones.py) (de dónde
salen y quién decide) y [`modelo/rectificacion.py`](../modelo/rectificacion.py) (la pregunta al
modelo). Pruebas: `tests/test_rectificaciones.py`.

## Principios

- El observatorio registra lo que se notifica y lo que declaran las autoridades, cuando lo
  declaran, con su fuente y su fecha. «Confirmado» significa que una autoridad oficial declaró que
  ocurrió, no que exista una prueba física pública.
- El incidente ocurrió aunque después se rectifique la causa: si un aeropuerto cerró, cerró. Una
  rectificación cambia la **presencia del dron**, nunca el incidente, su estado ni su efecto
  (el cierre, los desvíos, la duración). Nada desaparece del mapa: queda con su historial.
- Solo cambia la presencia una autoridad oficial. Lo que digan periodistas o la comunidad OSINT
  puede quedar como contexto en las fuentes de la ficha, sin cambiar nada.
- No encontrar pruebas no es demostrar que no hubo dron.

## Los valores

| Valor | Cuándo |
|---|---|
| `confirmada` | una autoridad dice que lo que se vio, detectó, derribó o causó el efecto era un dron (una medida suya sin atribuirlo no basta) |
| `no_confirmada` | la autoridad lo deja abierto o solo lo cuentan la prensa o los testigos |
| `no_acreditada` | una autoridad oficial cierra su investigación sin pruebas del dron, o retira su afirmación sin decir que fuera otra cosa |
| `descartada` | una autoridad lo niega o dice que era otra cosa (un avión, un helicóptero) |

Una **corrección parcial** (la autoridad rectifica un episodio o una prueba concreta y mantiene
los demás) se anota en el historial con `parcial: true` y no cambia el valor.

Una **investigación cerrada sin cambiar la presencia** (`cierre_sin_cambio`, desde el 26 de
octubre de 2026) es la autoridad que cierra o archiva su investigación sin retirar lo que se sabía
del dron ni decir que fuera otra cosa: el dron sigue probado, pero, por ejemplo, no puede
determinar su origen ni su autor. Se anota en el historial con `cierre: true`, su fecha, su
fuente, quién lo declara y su motivo, en español y en inglés, y no cambia ni la presencia ni el
estado. La web lo escribe «Investigación cerrada el 23/10/2026 por la Fiscalía de Estonia…, sin
cambio en la presencia del dron» («Investigation closed on … with no change to the drone
presence»), y el CSV, `día:valor:cierre`. Primer caso: Auvere (EODI-2026-00108), que el
experto leía «ninguna» cuando estaba revisada como `parcial`. Si cambia el tipo de una
rectificación revisada a mano, el experto vuelve a leerla (`cambio_revisado`).

## El historial

`presencia_historial` (público, esquema 1.20.0) guarda la secuencia: el primer paso es el valor
que había, con la fuente y la fecha en que se declaró (la autoridad más temprana que lo afirma);
cada rectificación añade un paso con su valor, su fecha (el día en que lo declara la autoridad),
su fuente, quién lo declara y qué dijo, en español y en inglés. La web lo enseña en la ficha:
«Confirmado el 22/09/2025 por la policía de Copenhague · No acreditado el 25/06/2026 por la
policía danesa (Rigspolitiet), al cerrar la investigación…». Solo crece: nada se borra.

Lo rectificado no lo deshace la recogida. `Almacen.guardar_incidente` llama a
`rectificaciones.mantener` con la versión guardada: si una extracción nueva o una regla traen la
ficha sin historial, con otra presencia o sin la fuente oficial, se conservan el historial, sus
fuentes y el valor vigente (con su afirmación y el titular coherente). Para volver a cambiarla
hace falta otra rectificación. La validación (`rectificaciones.errores`) exige que cada paso cite
una fuente del incidente, que una nota (parcial o cierre) no cambie el valor y que el último paso
que no es una nota sea la presencia del incidente.

Si llega otra fuente que dice lo mismo que el valor vigente (la declaración oficial después de
la noticia que la contaba), no es un paso nuevo: la fuente entra en la ficha con su afirmación.
La frase de una fuente revisada tiene como mucho 25 palabras, como todas; el resto del documento
va en `contexto`, para el experto.

El titular de una presencia no acreditada da el dron como posible, como el de una no confirmada
(`proceso/titulares.py`). Los contadores de «confirmados por una autoridad» de la web no la
cuentan; el incidente sigue contando como incidente. El cambio no genera aviso
(`recogida/avisos.clasificar`).

## De dónde salen y quién decide

Todo pasa por el **experto** antes de cambiar nada (`docs/modelos.md`: nada publicado se rebaja
sin el experto). Sin experto configurado, o con su tope del día agotado, se espera a la recogida
siguiente y la ficha sigue como estaba. Las rectificaciones no usan la reserva crítica: pueden
esperar y no quitan sitio a lo urgente. La respuesta del experto solo vale si es el mismo suceso,
la declaración es de una autoridad oficial, su frase está literal en el texto que se le mandó, su
seguridad llega a 0,7 y, si la rectificación estaba revisada a mano, el tipo coincide
(`rectificaciones.decision_valida`). La decisión queda guardada (control de las fichas, clave
`rectificacion:…`) y no se repite.

1. **Revisadas a mano**: [`configuracion/rectificaciones_oficiales.json`](../configuracion/rectificaciones_oficiales.json).
   Cada entrada lleva la declaración literal de la autoridad con su enlace y su fecha, el tipo,
   quién y qué dijo en los dos idiomas y, si hace falta, quién declaró el valor de antes. Se
   aplican en cada recogida horaria, la primera vez con la decisión del experto. La declaración
   se lee en la página de la autoridad (`oficial`) o, si la autoridad no la publica, en un medio
   de fiabilidad A que la cita con el nombre de quien habla (`citada_en`, con el medio y su
   fiabilidad): es una declaración oficial citada, como las que encuentra el extractor (el
   cierre de la investigación de Auvere, EODI-2026-00108, que solo cuenta ERR citando al fiscal
   estatal Gardi Anderson).
2. **En cada recogida horaria**: las fuentes de los incidentes publicados (confirmados, no
   confirmados o no acreditados) que suenan a retractación o a cierre oficial de una
   investigación, en cualquier idioma, y son al menos de un día después del suceso. Las
   expresiones están en
   [`configuracion/senales_rectificacion.json`](../configuracion/senales_rectificacion.json)
   («no evidence», «cannot confirm», «investigation closed», «was a helicopter», «hverken
   kunnet bevise eller afvise», «Ermittlungen eingestellt», «classée sans suite»…): solo deciden
   qué se manda al experto. Como mucho cuatro preguntas nuevas por recogida (`MAX_POR_PASADA`),
   con las primeras frases de la página de cada fuente. Lo anterior a la última rectificación de
   un incidente (y de su mismo día) no se vuelve a mandar.
3. **Una vez al mes**: para cada incidente con la presencia confirmada de más de un mes, los
   titulares guardados posteriores al suceso que nombran su lugar (el objetivo, su código OACI o la
   localidad, en sus idiomas) y suenan a rectificación. El modelo base dice cuáles merecen la
   pregunta; lo elegido lo decide el experto en las recogidas siguientes. Tope: **0,30 USD por
   pasada** con el modelo base (modo `rectificaciones` de `modelo/coste.py`); la pasada que no
   termina por el tope o por el tiempo se repite en la recogida siguiente.

4. **Cada día, desde la segunda lectura** (desde el 18 de octubre de 2026,
   [`docs/segunda_lectura.md`](segunda_lectura.md)): la misma selección de titulares que el punto 3,
   pero sobre todos los incidentes publicados con la presencia confirmada, no confirmada o no
   acreditada y al menos un día de antigüedad, con el servicio secundario de modelos (gratuito).
   Lo que elige entra en la **misma cola** que lo del punto 3 y lo decide el experto igual, con el
   modo `segunda_lectura` (0,30 USD al día como mucho, nunca de la reserva crítica). El barrido
   mensual sigue tal cual: es el mecanismo independiente.

Nada de esto impide publicar ni retirar incidentes: el paso va aislado en la recogida horaria
(un fallo queda en el registro y la recogida sigue), con su propio tope de tiempo (150 s).

Para ver lo que se mandaría al experto sin llamar a nada:
`python -m recogida.rectificaciones senales --base <eodi.sqlite>`.

## Coste

- Revisadas a mano: una pregunta al experto por entrada, una sola vez (unos 0,02 USD cada una).
- Recogida horaria: solo cuando una fuente nueva suena a rectificación; como mucho cuatro
  preguntas por hora, dentro del tope diario del experto (1 USD, compartido con el resto).
- Búsqueda mensual: como mucho 0,30 USD al mes con el modelo base (unas 0,002 USD por incidente
  con titulares candidatos); el experto, solo para lo que elige.
