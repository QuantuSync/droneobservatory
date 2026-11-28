# Segunda lectura con un servicio secundario de modelos (retirada)

**Retirada el 28 de noviembre de 2026.** Fue una capa secundaria, gratuita y prescindible (desde el
18 de octubre de 2026) que volvía a leer lo publicado con un servicio secundario de modelos y
marcaba candidatos para el experto; nunca decidió nada por sí sola. Desde el 4 de noviembre de 2026
el servicio rechazaba cada pasada («401 unauthorized») y la capa no aportaba nada.

## Qué se quitó

- El cliente del servicio secundario (`modelo/secundario.py`), las reglas sin llamadas
  (`proceso/segunda_lectura.py`, `proceso/segunda_busqueda.py`), las pasadas, su base propia y el
  paso de la recogida horaria (`recogida/segunda_lectura.py`, `recogida/segunda_busqueda.py`), su
  configuración (`configuracion/segunda_lectura.json`) y sus pruebas.
- Los comparadores que solo usaba ella en la definición de suceso (`suceso.cercanos` y
  `suceso.pares_amplios`, los márgenes amplios de los posibles duplicados).
- El apartado «segunda_lectura» del estado interno del control (`~/.eodi/control.json`), que no
  se publica.
- En el servidor: su temporizador y su servicio, y las variables `EODI_SECUNDARIO_*`.

## Qué se queda

- Lo que ya decidió el experto sobre lo que ella marcó, guardado en el control de las fichas
  (claves `segunda:…`), y todo lo que se aplicó con las reglas de siempre: no cambia ningún campo
  publicado.
- Los modos de gasto `segunda_lectura` y `segunda_busqueda` ([`modelo/coste.py`](../modelo/coste.py)):
  los usan lo que ella dejó en las colas (las rectificaciones con origen «segunda_lectura»,
  [`docs/rectificaciones.md`](rectificaciones.md), y los candidatos que esperan al experto con su
  cupo) y el historial del gasto.
- Las frases literales que encontró y que están en el cursor de los artículos dirigidos: siguen
  siendo la pista de su fuente en la extracción.
