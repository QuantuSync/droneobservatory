# Informe: control de calidad permanente de las fichas (14 de octubre de 2026)

Cómo funciona el control: docs/control_fichas.md. Aquí, lo que se hizo y lo que salió.

## Los casos del 13 de octubre

- **Bulgaria, ataque a dos barcos (noche del 12 al 13)**: tres fichas del mismo suceso
  (EODI-2026-00512, 00513 y 00514) quedan en una, la más antigua (00512). Los enlaces 00513 y
  00514 llevan a ella. El ataque del 6 de octubre (00489) sigue siendo otra ficha.
- **Núremberg**: 00516 se une a 00515 (el enlace viejo redirige). El lugar es el aeropuerto
  (EDDN), no «Alemania» ni «otro lugar a 10 km». Sin «Dron confirmado»: una fuente dice
  «allerdings konnte eine Drohne nicht gefunden werden» (no se encontró el dron). Sin «2–10»
  drones: ninguna fuente da el número.
- **Citas en otro idioma**: cada cita sale traducida al idioma de la página, con «Ver original» /
  «Show original» para leer la frase de la fuente.
- **Avisos**: 00513 y 00514 se avisaron los dos (drones-europe y drones-bulgaria, 13 de octubre a
  las 08:34 UTC). Núremberg no se avisó. Una ficha unida ya no vuelve a avisar.

## Causas

- Los duplicados entre idiomas: la regla de unión pedía punto en las dos fichas; las fichas a
  nivel de país o región no se comparaban nunca.
- «Dron confirmado»: el cierre del aeropuerto contaba como presencia aunque la frase dijera que
  no se encontró el dron.
- «2–10»: el extractor convertía un plural («drones») en 2–10 sin un número escrito.

## Repaso de todo lo publicado

- Duplicados: 36 uniones del repaso (38 menos 2 deshechas, Bruselas con Lieja), 2 más en las
  pasadas siguientes (Moldavia, 28 de noviembre de 2025: tres fichas en una) y las revisadas a
  mano (Bulgaria, Núremberg, Bruselas 00072/00249, Elsenborn y Vilna). La primera ronda (80
  uniones con reglas demasiado amplias) se deshizo antes de publicarse.
- Fichas corregidas y publicadas: 108 (53 número de drones, 29 día, 19 lugar más preciso,
  17 duración del cierre, 1 hora, 1 presencia), más 3 notas de lugar sin nombre en otro idioma.
  En 43 de ellas el dato pasó a «sin dato» porque ninguna fuente lo daba.
- Citas traducidas: 6.642 (3.013 + 2.524 + 1.105).
- Separaciones del 13 de octubre: 22 parejas comparadas; 20 bien separadas y 2 eran el mismo
  suceso (Elsenborn 00287/00456 y Vilna 00376/00384), unidas.

## Gasto real

- Repaso: 3,46 dólares de 4 (2,18 + 0,83 + 0,45), por lotes.
- Pruebas en local: unos 0,45 dólares.
- Control diario: tope de 0,15 dólares al día.

## Pendiente

- Unas 600 fichas sin verificar con el modelo, sobre todo de Ucrania, y sus citas: el tope del
  repaso no alcanzó. Las va haciendo la madrugada (01:41 UTC) dentro de su tope diario.
- El ensayo 6 falló por una duración corregida sin afirmación de origen; arreglado antes de
  fusionar (ensayos 7 y 8 con código 0).

## Comprobación en la web

Recorridos `web/e2e/control-fichas-recorridos.spec.ts` contra producción, el 14 de octubre a las
06:40 UTC: 20 de 20 en Android, iPhone, tableta y escritorio (Chromium y WebKit), en español y en
inglés. Bulgaria y Núremberg unidas, enlaces antiguos que llevan a la ficha que queda, citas
traducidas con el original desplegable, fichas corregidas, sin errores de consola ni enlaces
rotos. Revisión a mano en 360×800, 390×844, 412×915 y escritorio, sin desbordes.

La primera recogida real con el código fusionado (06:17 UTC) terminó con código 0 y publicó.
