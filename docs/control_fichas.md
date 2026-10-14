# Control de calidad permanente de las fichas

Desde el 14 de octubre de 2026. El 13 de octubre salieron dos veces el ataque con drones a dos
barcos en la zona económica búlgara del mar Negro (EODI-2026-00513 y 00514, con fuentes rumanas y
finlandesas) y la alerta del aeropuerto de Núremberg (00515 y 00516, con fuentes alemanas y una
griega); el 00515 tenía el lugar a nivel de país, el dron «confirmado» aunque su propia fuente
dice que no se encontró ninguno («allerdings konnte eine Drohne nicht gefunden werden») y «2–10
drones» que no daba ninguna fuente; y las citas salían en griego y en alemán en la web en
español. Este control lo comprueba todo en cada recogida, antes de publicar, y otra vez cada
madrugada.

Código: [`recogida/control_fichas.py`](../recogida/control_fichas.py) (el paso, el repaso y el
estado), [`proceso/control_fichas.py`](../proceso/control_fichas.py) (pares candidatos y reglas
de corrección, sin llamar a nada), [`proceso/lugar_preciso.py`](../proceso/lugar_preciso.py),
[`modelo/control.py`](../modelo/control.py) (las tres llamadas al servicio), 
[`exportacion/citas.py`](../exportacion/citas.py) (lo que se añade al publicar) y la regla de
presencia de [`proceso/presencia.py`](../proceso/presencia.py). Pruebas:
[`tests/test_control_fichas.py`](../tests/test_control_fichas.py).

## Por qué no se unían

- **Sin punto no hay unión.** `proceso/incidentes.mismo_sitio` exige que los dos tengan punto, o
  que ninguno lo tenga y den el mismo nombre de lugar. El 00515 solo sabía el país (Alemania) y el
  00516 tenía el punto de la ciudad: nunca podían unirse. En Bulgaria, el 00513 era de nivel país
  («Biala») y el 00514 de región («Mustanmeren-rannikko», la costa del mar Negro en finés): sin
  punto y con nombres distintos.
- **Idiomas distintos.** Las noticias se agrupan en candidatos por el lugar que nombra el titular y
  el tipo de señal, que dependen del idioma; un titular griego y uno alemán del mismo aeropuerto
  acaban en candidatos distintos, y los titulares solo se comparan dentro de un idioma.

## Qué hace en cada recogida

En `recogida/horaria.py`, paso «control de fichas», después de la presencia del dron y antes de
publicar. Nunca impide publicar lo demás ni cambia el código de salida.

1. **Uniones ya decididas.** Las uniones del control siguen hechas: si la ficha que queda se
   vuelve a extraer y pierde las fuentes de la unida, las recupera.
2. **Lugar del titular** (`proceso/lugar_preciso.py`, sin llamar a nada). Si el titular nombra sin
   duda una instalación del nomenclátor (un aeropuerto, una base, un puerto, una central) del país
   del incidente, el lugar es esa instalación, con su código OACI, y el marcador va en ella. Sin
   duda quiere decir: una sola instalación, con su tipo de lugar en el titular, nombrada por su
   nombre o por una ciudad que no tiene otra del mismo tipo («aeropuerto de Varsovia» puede ser
   Chopin o Modlin), y ninguna otra localidad en el titular («cerca de Heathrow, sobre Marlow» es
   Marlow). Solo cambia fichas sin punto o con el punto genérico de la misma ciudad (el GKG de
   Núremberg); nunca un punto oficial, el de otra instalación o el de otra localidad. El punto
   anterior queda en `lugar.historial` con el motivo.
3. **Estado.** Confirmado o atribuido solo con un paso de una fuente oficial (una autoridad, leída
   o citada); si no, vuelve a notificado con el motivo en los dos idiomas.
4. **Duplicados** (también entre idiomas). Pares candidatos: del mismo país, con los inicios a 48
   horas como mucho (con la fecha de publicación, también la primera noticia), a menos de 60 km
   más los radios si los dos tienen punto (si alguno no lo tiene, basta el país: el lugar
   aproximado cuenta) y del mismo tipo de sitio (un aeropuerto y una base no, salvo que estén a
   10 km). Nunca los que una revisión separó (`relacionados`) ni dos cierres del mismo sitio en
   noches distintas. Cada par se compara con lo que dicen sus fuentes, en su idioma (llamada
   «comparar»): **mismo**, se unen con la fusión anotada como revisada y **se conserva el
   identificador más antiguo** (el enlace del otro lleva al que queda); **distinto**, no se vuelve
   a comparar salvo que lleguen fuentes nuevas; **dudoso**, se vuelve a comparar con cada fuente
   nueva y a las 6 horas se resuelve como distintos.
5. **Cada dato con su fuente** (llamada «verificar»). Las fichas nuevas o con fuentes nuevas se
   comprueban con sus fuentes (titular y primeras frases, como las lee el extractor, solo en
   memoria): para la presencia del dron, el número de drones, el cierre y su duración, el día, la
   hora y el lugar, qué dice cada fuente con la frase literal. **Una frase que no está, literal,
   en el texto de su fuente no cuenta.** Con lo que queda:
   - si una fuente dice que no se encontró el dron, que no se vio ninguno o que era otra cosa, la
     presencia no queda confirmada (salvo que la autoridad que confirmó el suceso lo atribuya a un
     dron en esa declaración, o haya pruebas físicas que confirma una autoridad, o la revisión a
     mano diga otra cosa);
   - el número de drones solo si una fuente lo da («dos drones», «varios»: 2-10, «un enjambre»:
     5-50); un plural sin cantidad o el número de pilotos no es un número de drones: sin dato;
   - el cierre solo con frase (o con la regla del cierre de pista); su duración, solo con frase;
   - la hora solo con frase (si no, queda el día); el día, con frase, si la ficha solo tenía la
     fecha de publicación;
   - el lugar de una ficha sin punto, el sitio que nombra la frase (una sola instalación o una
     sola localidad del país);
   - nunca sube un estado ni confirma una presencia: eso lo hacen las reglas de siempre con las
     fuentes oficiales.
   Si llegan fuentes nuevas antes de volver a verificar, solo se quita un valor si sigue siendo el
   mismo que se comprobó.
6. **Citas** (llamada «traducir»). Cada cita que enseña la web se traduce una vez al español y al
   inglés y se guarda (tabla `traducciones`, por la huella del texto). La publicación anota las
   que salen sin traducir y el control las traduce en su pasada siguiente: las de las fichas de
   Europa en cada recogida y las de la capa de Ucrania, las más recientes primero, de madrugada.
7. **Retención.** Una ficha nueva que todavía no ha pasado el control (un posible duplicado sin
   decidir, la verificación pendiente por el tope de gasto o por una caída del servicio) no se
   publica, como mucho 6 horas; después se publica con lo que haya y queda anotada. Lo que ya
   estaba publicado nunca se retiene: se corrige. Así un duplicado nuevo se une antes de salir y
   no genera un segundo aviso.

Todo es idempotente: una pasada sin nada nuevo no llama al servicio ni cambia nada. Cada decisión
es una fila nueva de la tabla `control_fichas` (nada se borra); cada corrección, una versión nueva
del incidente con el motivo en el historial («control de fichas: …»).

## Lo que se ve en la web

- **«Qué dice la fuente»** lleva, junto a cada dato verificado, la frase literal de la fuente que
  lo respalda (si casa con lo publicado), además de lo que ya daba cada fuente.
- **Citas en el idioma de la página.** Cada cita (la frase de cada fuente, «Qué dice la fuente»,
  el lugar según la autoridad, la atribución, la investigación, el tipo de dron y su razón, el
  recorrido, los daños, el desmentido; en la capa de Ucrania, las fuentes de ataques e impactos y
  los cruces) sale traducida al idioma de la página, con el original debajo, plegado: «Ver
  original» / «Show original» (`web/src/componentes/Cita.tsx`; en las páginas de texto,
  `citaTraducida` de `web/src/texto/paginas.ts`). Si no hay traducción o la cita ya está en ese
  idioma, el original tal cual.
- Los campos nuevos de lo publicado son opcionales: `traduccion` (junto a `frase_origen`),
  `cita_traduccion` (junto a `cita`), `frase_traduccion` (daños y cruces) y
  `motivo_desmentido_traduccion`, cada uno con `es` y `en`. El esquema de la base (1.18.0) y la
  exportación semanal para AEGIS (formato 1.11.0) no cambian: las traducciones viven en su tabla
  y solo se añaden a los ficheros de la web.

## Avisos

`recogida/avisos.py` cuenta lo avisado con el número de un registro que después se unió a otro
como avisado para el que queda: el mismo suceso no se avisa dos veces. Y como un duplicado nuevo
se retiene hasta que el control decide, normalmente ni llega a publicarse.

## Madrugada

`eodi-control.timer`, cada día a las 01:41 UTC (`servidor/control_noche.sh`, con el cerrojo de la
recogida, `MemoryMax=2G`, tope de 25 minutos): vuelve a comprobar todo lo publicado en las
últimas 48 horas (pares y verificación de lo que tenga fuentes nuevas) y traduce las citas
atrasadas de la capa de Ucrania con lo que sobra del día, sin pasar de 0,08 dólares para dejar el
resto a las recogidas horarias. Lo que corrige sale en la recogida siguiente.

```
sudo systemctl start eodi-control.service
journalctl -u eodi-control.service -n 30
sudo -u eodi bash -c 'cd /home/eodi/droneobservatory && .venv/bin/python -m recogida.control_fichas estado'
```

## Gasto

- Modo `control`: 0,15 dólares al día (recogidas horarias y madrugada), con el mismo registro de
  llamadas y el mismo freno que el extractor (`modelo/coste.py`): antes de cada llamada se suma lo
  gastado y el peor caso; si pasa, no se llama y lo pendiente espera (las fichas nuevas, como
  mucho 6 horas).
- Modo `control_repaso`: 4 dólares, una sola vez, para el repaso de todo lo publicado
  (`python -m recogida.control_fichas repaso --cerrojo …`), por lotes (a mitad de precio) y en
  dos rondas: los pares primero (las uniones) y después la verificación de cada ficha y las citas
  (las de Europa y, con lo que quede, las de Ucrania).

## Resumen diario y vigilancia

- `control.json` (`/home/eodi/.eodi/`) guarda cada pasada de los dos últimos días: fichas
  corregidas y por qué, duplicados unidos, retenidas y liberadas, gasto y paradas.
- El resumen de las 08:00 (`lucas-resumen`, sección SISTEMA) dice cuántas fichas corrigió el
  control y de qué clase (lugar, drones, presencia, cierre, hora, día, estado), los duplicados que
  unió, las que retuvo y lo que gastó, con hasta 5 ejemplos.
- La vigilancia solo abre incidencia («control_fichas») si el propio control falla 3 pasadas
  seguidas; lo que corrige o retiene no es un problema.

## Correcciones a mano

Siguen en `configuracion/incidentes_revisados.json` y mandan sobre el control: una presencia
revisada a mano no la cambia el control, una unión revisada no la deshace nadie. La sección
`titulares` admite ahora `drones` (`{"valor": "desconocido"}`) para quitar un número de drones que
no da ninguna fuente, como en el 00515.
