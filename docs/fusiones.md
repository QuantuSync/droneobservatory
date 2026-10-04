# Cómo se fusiona un pull request

Los pull requests se fusionan con squash desde la línea de órdenes, indicando como autor
la dirección anónima de la cuenta:

```
gh pr merge <número> --squash --delete-branch \
  --author-email 192205734+QuantuSync@users.noreply.github.com \
  --subject "<título en español> (#<número>)" \
  --body-file <fichero con el mensaje>
```

**Condición.** GitHub solo acepta en `--author-email` una dirección que la cuenta pueda
usar en sus commits hechos desde la web: sus correos verificados y, si la cuenta tiene
activada la opción de mantener privado el correo (*Settings → Emails → Keep my email
addresses private*), la dirección anónima. Sin esa opción la orden falla con `Invalid
email address (mergePullRequest)` y no fusiona nada: así falló el 30 de septiembre de
2026 con los PR 9, 10 y 11. Con la opción activada, además, GitHub usa la dirección anónima por
defecto en todo lo que la cuenta hace desde la web.

**Mientras la cuenta no tenga esa opción**, el mismo resultado se consigue sin la API de
merge, con los commits firmados por la configuración local del clon (la dirección
anónima, sin `--global`), siguiendo estos pasos en este orden:

```
# a. traer main justo antes de fusionar
git fetch origin
# b. rebase sobre main; en un conflicto en publicacion/ gana siempre main
git switch <rama> && git rebase origin/main
# c. puerta local y workflow de tests sobre la rama rebasada
git push --force-with-lease origin <rama>        # y esperar al workflow en verde
# c2. si el cambio toca la recogida: ensayo de punta a punta sobre una copia de la base real
python -m recogida.horaria --correo <correo> --base <copia de db.age> --ensayo <carpeta>
# d. un solo commit con el autor anónimo
git reset --soft origin/main
git commit -F <fichero con el mensaje>            # título «… (#<número>)» y el porqué
# e. comprobación obligatoria antes de publicar
git diff --name-only origin/main HEAD             # solo lo que el PR cambia a propósito
# f. avance rápido, nunca forzado sobre main
git push --force-with-lease origin <rama>
git push origin <rama>:main
git push origin --delete <rama>
# g. el número de incidentes publicados no baja
```

Por qué existe cada paso:

- **a y b. Fetch y rebase justo antes.** El servidor de recogida publica cada hora en `main`
  un commit «Actualiza los datos publicados» (`publicacion/ucrania.json`,
  `publicacion/incidentes.geojson` y `publicacion/incidentes_sin_ubicacion.json`). El commit
  único del paso d lleva el árbol de la rama: si la rama no tiene esos commits, el commit
  único deshace los datos que entraron en `main` mientras la rama vivía. Al fusionar el PR
  #26 se vio que el commit de datos 14e7a02 se habría revertido así; se detectó al comparar
  con `main` antes de publicar. Durante el rebase, un conflicto en `publicacion/` se resuelve
  siempre con la versión de `main` (en un rebase, `main` es «ours»:
  `git checkout --ours publicacion/<fichero>` y `git rebase --continue`), salvo que el PR
  cambie a propósito esos ficheros.
- **c. Tests sobre lo rebasado.** Lo que se fusiona es la rama ya rebasada, no la que pasó
  los tests antes: los datos nuevos de `main` también tienen que validar (la build de la web
  valida `publicacion/` contra el esquema).
- **c2. Ensayo de la recogida.** Todo cambio que toque la recogida (`recogida/`, `proceso/`,
  `almacen/`, `exportacion/`, `esquema/`, `configuracion/`) se ensaya antes de fusionar con
  una recogida completa sobre una copia de la base real de la rama `estado`: `--base` la lee
  de un fichero local y `--ensayo` publica en una carpeta aparte y no sube nada. Sin la clave
  del extractor en el entorno no gasta. Tiene que terminar con «ficheros publicados» y salida
  0 o 2 (avisos). El 4 de octubre de 2026 tres recogidas no publicaron (12:17, 15:17 y 16:17)
  por límites y cambios que solo se habían probado por partes: el de 100 MiB de GitHub por
  fichero, el tope de 1 GiB de la base en memoria y una ficha guardada con la hora del reloj,
  que la publicación rechazó como fecha futura.
- **d. Un commit, autor anónimo.** Como hasta ahora (ver más abajo).
- **e. Comprobar la lista de ficheros.** `git diff --name-only origin/main HEAD` tiene que
  listar solo ficheros que el PR modifica de verdad. Las rutas de los datos publicados son las
  que salen en `git log --name-only --grep="Actualiza los datos publicados" origin/main`. Si
  aparece alguna que el PR no toca a propósito, se aborta, no se publica y se vuelve al paso
  a.
- **f. Solo avance rápido.** Si `main` avanza entre la comprobación y el push (la recogida
  publica en el minuto 17 de cada hora más unos minutos), `git push origin <rama>:main` falla:
  se vuelve al paso a. Nunca se fuerza un push sobre `main`. Para no chocar, no se fusiona
  entre el minuto 12 y el 40 de la hora: desde el 1 de octubre de 2026 (capa de guerra con
  lugar, tráfico aéreo medido) la recogida tarda unos 12 minutos y publica hacia el minuto
  29, y más tras un cambio que la haga reprocesar.
- **g. Comprobar producción.** Después del push, el número de incidentes que sirve
  droneobservatory.eu (la lista `incidentes` de `/datos/resumen.json`) no puede haber bajado
  respecto al de antes de fusionar; si baja, se restauran los ficheros de datos desde el
  último commit «Actualiza los datos publicados» del servidor.

En `main` queda un commit por pull request con autor anónimo, igual que con el squash.
Las diferencias: los commits atómicos de la rama se sustituyen por ese único commit
antes de fusionar (GitHub conserva el enlace a los anteriores en el aviso de push
forzado del pull request) y el commit no lleva la firma de GitHub.

Por qué:

- **`--author-email`.** Sin esta opción, GitHub firma el commit del squash con el correo
  principal de la cuenta, que es el personal, y queda para siempre en el historial de un
  repositorio público. Los commits del workflow de recogida ya usan la dirección anónima;
  los merges tienen que usar la misma. Los anteriores al 30 de septiembre de 2026 (hasta
  el del PR 8) salieron con el correo personal y no se han reescrito.
- **Squash.** Un commit por pull request en `main`, con el porqué en el mensaje. Los
  commits atómicos de la rama se quedan en el pull request.
- **Mensaje en español y sin líneas de atribución** al final.
- **`--delete-branch`.** La rama se borra al fusionar.

Antes de fusionar: la puerta local (`pytest`, `ruff check`, `ruff format --check` y
`mypy --strict`, comando a comando) y el workflow de tests, en verde.

Después de fusionar conviene comprobar el autor:

```
git log -1 --format='%an <%ae>' origin/main
```

La configuración global de git de la máquina no se toca. En el clon de trabajo, los
commits de la rama llevan la misma dirección anónima con la configuración local del
repositorio (`git config user.email`, sin `--global`).
