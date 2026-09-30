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
2026 con el PR 9. Con la opción activada, además, GitHub usa la dirección anónima por
defecto en todo lo que la cuenta hace desde la web.

**Mientras la cuenta no tenga esa opción**, el mismo resultado se consigue sin la API de
merge, con los commits firmados por la configuración local del clon (la dirección
anónima, sin `--global`). Así se fusionó el PR 9:

```
git switch <rama> && git reset --soft origin/main
git commit -F <fichero con el mensaje>      # título «… (#<número>)» y el porqué
git push --force-with-lease origin <rama>   # y esperar al workflow de tests
git push origin <rama>:main                 # avance rápido: GitHub marca el PR como fusionado
git push origin --delete <rama>
```

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
