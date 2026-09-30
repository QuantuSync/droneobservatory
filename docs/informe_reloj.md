# Reloj propio de la recogida

30 de septiembre de 2026. Las horas son UTC.

*Retirado el mismo día: la recogida pasó a lanzarla un servidor propio y el reloj
(`reloj.yml`, `recogida/reloj.py`) se eliminó. Ver
[`informe_servidor.md`](informe_servidor.md).*

## 1. El problema

`recogida.yml` está programado cada hora en el minuto 17. Del 28 al 30 de septiembre
había 62 franjas programadas y GitHub lanzó 10, entre 9 y 49 minutos tarde y con huecos de
4 a 8 horas y media (tabla en [`informe_arreglo_horaria.md`](informe_arreglo_horaria.md)).
Las que faltan no aparecen como fallidas ni canceladas: no se lanzaron. Desde el
repositorio no se puede hacer que la programación de GitHub sea fiable.

## 2. Por qué un reloj dentro del repositorio

Dos hechos lo permiten:

- **Las ejecuciones lanzadas a demanda no se pierden.** Las siete lanzadas a mano del 28
  al 30 de septiembre arrancaron en segundos.
- **El token de una ejecución puede lanzar `workflow_dispatch`.** Lo que hace una
  ejecución con su `GITHUB_TOKEN` no dispara otros workflows, salvo dos excepciones
  documentadas por GitHub: `workflow_dispatch` y `repository_dispatch`. No hace falta
  ningún secreto ni ningún servicio externo.

Así que un trabajo que se queda esperando puede lanzar la recogida a su hora. Se ha
preferido a las otras dos opciones:

- *Programar más franjas por hora:* sigue dependiendo de la misma programación que falla;
  mejora la media pero no garantiza nada.
- *Un planificador externo:* necesita un token personal con permiso de escritura guardado
  fuera del repositorio y otra cuenta que mantener.

## 3. Cómo funciona

`reloj.yml` tiene dos trabajos y la lógica está en `recogida/reloj.py`.

**Turno.** Al arrancar calcula sus horas de lanzamiento: cada minuto 17 que cae dentro
de las cinco horas y media siguientes. Duerme hasta cada una (una sola espera, sin
consultas: solo ocupa el runner) y lanza `recogida.yml` con `workflow_dispatch` sobre
`main`. Justo después del último lanzamiento lanza el turno siguiente y termina.

**El límite de seis horas.** GitHub corta cualquier trabajo alojado a las seis horas. Un
reloj que quisiera durar más perdería, al cortarse, la ocasión de relevarse. Por eso el
turno dura cinco horas y media (`DURACION_TURNO`) y el trabajo tiene su propio tope de
345 minutos: un cuarto de hora de margen sobre el turno y un cuarto de hora por debajo
del corte.

**El relevo sale con el último lanzamiento**, no al agotar el tiempo. Un turno de relevo
arranca hacia el minuto 18 y tiene casi una hora hasta su primera recogida; si el relevo
saliera en un momento cualquiera, podría caer justo encima de un minuto 17 y perderlo.
Un turno de relevo hace cinco lanzamientos y dura algo menos de cinco horas.

**Antes de lanzar** consulta las ejecuciones de `recogida.yml`: si hay alguna en cola o
en marcha, no lanza otra. Si la consulta falla, lanza igual: el grupo de concurrencia de
la recogida impide que dos corran a la vez. Cada orden se intenta tres veces con 10 s
entre intentos. Una recogida que no se puede lanzar se anota y el turno sigue; un relevo
que no se puede lanzar deja el turno en rojo.

**Un solo reloj a la vez.** El trabajo del turno está en un grupo de concurrencia propio
(`reloj`) que no cancela al que está en marcha: el relevo espera ahí los segundos que
tarda en acabar el turno que lo lanzó.

**Guardia y respaldo.** `reloj.yml` conserva una programación horaria (minuto 47, a media
hora del lanzamiento). El trabajo de guardia decide si la ejecución arranca un turno: la
lanzada a demanda (a mano o como relevo), siempre; la programada, solo si no hay ningún
otro reloj en cola o en marcha. Si el reloj se para, el primer respaldo que GitHub lance
lo vuelve a arrancar. La guardia está fuera del grupo de concurrencia para poder mirar
mientras hay un turno en marcha.

**La programación de `recogida.yml` no cambia.** Cuando GitHub la lance habrá en esa hora
una recogida de más, que tarda unos 3 minutos si no hay novedades.

**Permisos y origen.** El workflow solo tiene `actions: write`. El repositorio es
público y el código se descarga sin permiso de contenidos (comprobado: ver la sección 5).
Solo se dispara con `schedule` y `workflow_dispatch`, que exigen estar en el repositorio
y tener permiso de escritura; no usa `pull_request` ni `pull_request_target`, y los dos
trabajos solo corren en `main` de `QuantuSync/droneobservatory`.

**Salud.** El trabajo `salud-recogida` del workflow de tests señala ahora también si no
hay ningún reloj en marcha ni lo ha habido en las dos últimas horas.

## 4. Manejo

| Para | Orden |
| --- | --- |
| Arrancar el reloj | `gh workflow run reloj.yml --ref main` |
| Ver si está en marcha | `gh run list --workflow reloj.yml --limit 3` |
| Pararlo de verdad | `gh workflow disable reloj.yml` y después `gh run cancel <id>` |
| Volver a ponerlo | `gh workflow enable reloj.yml` y arrancarlo |

Cancelar el turno sin desactivar el workflow no lo para: el respaldo lo arranca otra vez.

Un cambio en `recogida/reloj.py` o en `reloj.yml` entra en el turno siguiente: cada
turno descarga `main` al arrancar.

## 5. Comprobaciones

- Tests sin red ni esperas, con un reloj y unas órdenes falsos: horas de lanzamiento,
  duración del turno, relevo, recogida ya en marcha, fallos de la API, guardia y salud.
- Prueba real antes de fusionar, en una rama desechable con un workflow con solo
  `actions: write` (ejecución `prueba-reloj` del 30 de septiembre a las 14:48): descargó
  el código, consultó las ejecuciones y lanzó con su token la recogida número 23.

Lo que solo se puede ver con el reloj ya en `main` (dos lanzamientos seguidos a su hora
y el relevo de un turno a otro) no está en este informe.

## 6. Limitaciones

1. **Si el reloj muere, el respaldo depende de la programación que falla.** Un turno
   cortado por GitHub o un relevo que no sale dejan la recogida sin reloj hasta que
   GitHub lance un respaldo: con lo medido, hasta ocho horas y media. Mientras tanto queda
   la programación propia de la recogida, igual de irregular que antes.
2. **El relevo no se ha visto en producción.** El primero ocurre unas cinco horas después
   de arrancar el reloj.
3. **Un runner ocupado todo el día.** El reloj consume un trabajo de forma continua. En
   un repositorio público no tiene coste, pero cuenta para el límite de trabajos
   simultáneos de la cuenta.
4. **El lanzamiento es puntual; el arranque, casi.** El reloj lanza en el minuto 17 y la
   recogida espera a que haya un runner libre, normalmente unos segundos.
5. **Un lanzamiento a mano del reloj con otro en marcha** deja un segundo turno a la
   cola. No corren dos a la vez y GitHub solo guarda uno en espera por grupo, así que no
   se acumulan, pero no hace falta lanzarlo si ya hay uno.
6. **GitHub desactiva las programaciones de un repositorio público tras 60 días sin
   actividad.** Afectaría al respaldo, no a la cadena de relevos; los commits de
   publicación de la recogida cuentan como actividad.
7. **El aviso de salud solo se ve cuando corre el workflow de tests** (push o pull
   request).
