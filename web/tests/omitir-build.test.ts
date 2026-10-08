import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { CONSTRUIR, OMITIR, decidir } from "../scripts/omitir-build.ts";
import type { Git } from "../scripts/omitir-build.ts";

const WEB = join(import.meta.dirname, "..");
const SCRIPT = join(WEB, "scripts", "omitir-build.ts");

describe("decisión de omitir el build", () => {
  const git =
    (respuestas: Record<string, number | null>): Git =>
    (argumentos) =>
      respuestas[argumentos[0] ?? ""] ?? null;

  it("sin commit anterior construye", () => {
    expect(decidir(undefined, git({}))).toBe(CONSTRUIR);
    expect(decidir("", git({}))).toBe(CONSTRUIR);
    expect(decidir("   ", git({}))).toBe(CONSTRUIR);
  });

  it("con un commit anterior que no está en el clon construye", () => {
    expect(decidir("aad9162", git({ "cat-file": 128, diff: 0 }))).toBe(CONSTRUIR);
  });

  it("omite solo si git dice que no hay cambios", () => {
    expect(decidir("aad9162", git({ "cat-file": 0, diff: 0 }))).toBe(OMITIR);
    expect(decidir("aad9162", git({ "cat-file": 0, diff: 1 }))).toBe(CONSTRUIR);
  });

  it("producción desde otra rama construye siempre; desde main, según los cambios", () => {
    const sinCambios = git({ "cat-file": 0, diff: 0 });
    expect(decidir("aad9162", sinCambios, { destino: "production", rama: "web-diseno" })).toBe(CONSTRUIR);
    expect(decidir("aad9162", sinCambios, { destino: "production", rama: "main" })).toBe(OMITIR);
    expect(decidir("aad9162", sinCambios, { destino: "preview", rama: "web-diseno" })).toBe(OMITIR);
  });

  it("el mismo commit del despliegue anterior (el gancho de la publicación) construye", () => {
    expect(decidir("aad9162", git({ "cat-file": 0, "merge-base": 0, diff: 0 }))).toBe(CONSTRUIR);
    expect(decidir("aad9162", git({ "cat-file": 0, "merge-base": 1, diff: 0 }))).toBe(OMITIR);
  });

  it("con los datos en el almacén, producción se construye siempre (el gancho de la recogida)", () => {
    const sinCambios = git({ "cat-file": 0, "merge-base": 1, diff: 0 });
    expect(decidir("aad9162", sinCambios, { destino: "production", rama: "main", datosDelAlmacen: true })).toBe(CONSTRUIR);
    expect(decidir("aad9162", sinCambios, { destino: "preview", rama: "x", datosDelAlmacen: true })).toBe(OMITIR);
    expect(decidir("aad9162", sinCambios, { destino: "production", rama: "main", datosDelAlmacen: false })).toBe(OMITIR);
  });

  it("cualquier otro error construye", () => {
    expect(decidir("aad9162", git({ "cat-file": 0, diff: 128 }))).toBe(CONSTRUIR);
    expect(decidir("aad9162", git({ "cat-file": null }))).toBe(CONSTRUIR);
    expect(
      decidir("aad9162", () => {
        throw new Error("git no está instalado");
      }),
    ).toBe(CONSTRUIR);
  });
});

describe("script con un repositorio real", () => {
  let repo: string;
  const commits: Record<string, string> = {};

  function en(...argumentos: string[]) {
    return execFileSync("git", argumentos, { cwd: repo, encoding: "utf-8" }).trim();
  }

  function confirmar(nombre: string, fichero: string) {
    mkdirSync(join(repo, fichero, ".."), { recursive: true });
    writeFileSync(join(repo, fichero), `${nombre}\n`);
    en("add", "-A");
    en("commit", "-q", "-m", nombre);
    commits[nombre] = en("rev-parse", "HEAD");
  }

  function salida(previo: string | undefined): number | null {
    const entorno = { ...process.env };
    delete entorno.VERCEL_GIT_PREVIOUS_SHA;
    if (previo !== undefined) entorno.VERCEL_GIT_PREVIOUS_SHA = previo;
    return spawnSync(process.execPath, [SCRIPT], { cwd: repo, env: entorno }).status;
  }

  beforeAll(() => {
    repo = mkdtempSync(join(tmpdir(), "omitir-build-"));
    en("init", "-q");
    en("config", "user.email", "prueba@example.org");
    en("config", "user.name", "prueba");
    en("config", "commit.gpgsign", "false");
    confirmar("inicial", "web/a.txt");
    confirmar("docs", "docs/informe.md");
    confirmar("datos", "publicacion/ucrania.json");
    confirmar("despliegue", "vercel.json");
    confirmar("almacen", "configuracion/almacen_publico.json");
    confirmar("otra_configuracion", "configuracion/fuentes.json");
  });

  afterAll(() => {
    rmSync(repo, { recursive: true, force: true });
  });

  it("un commit que solo toca docs/ se omite", () => {
    en("checkout", "-q", commits.docs ?? "");
    expect(salida(commits.inicial)).toBe(OMITIR);
  });

  it("un cambio de la dirección del almacén público construye", () => {
    en("checkout", "-q", commits.almacen ?? "");
    expect(salida(commits.despliegue)).toBe(CONSTRUIR);
  });

  it("otro fichero de configuración se omite", () => {
    en("checkout", "-q", commits.otra_configuracion ?? "");
    expect(salida(commits.almacen)).toBe(OMITIR);
  });

  it("un commit de datos del servidor construye", () => {
    en("checkout", "-q", commits.datos ?? "");
    expect(salida(commits.docs)).toBe(CONSTRUIR);
  });

  it("un cambio en vercel.json construye", () => {
    en("checkout", "-q", commits.despliegue ?? "");
    expect(salida(commits.datos)).toBe(CONSTRUIR);
  });

  it("sin commit anterior, o con uno que no existe en el clon, construye y nunca falla", () => {
    expect(salida(undefined)).toBe(CONSTRUIR);
    expect(salida("aad9162001d3b593266c0e04f8dbf7a2e5591e05")).toBe(CONSTRUIR);
    expect(salida("no-es-un-commit")).toBe(CONSTRUIR);
  });

  it("vercel.json usa este script", () => {
    const vercel = JSON.parse(readFileSync(join(WEB, "..", "vercel.json"), "utf-8")) as {
      ignoreCommand: string;
    };
    expect(vercel.ignoreCommand).toBe("node web/scripts/omitir-build.ts");
  });
});
