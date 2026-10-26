// El lector delegado (../../api/lector.ts): solo descarga direcciones de su lista cerrada, respeta
// robots.txt y el tope por minuto, devuelve la página tal cual con su código, y tiene en la lista
// todas las fuentes delegadas de configuracion/fuentes_oficiales.json.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AGENTE,
  FUENTES,
  GET,
  TOPE_POR_MINUTO,
  Tope,
  admitir,
  olvidar,
  reglasRobots,
  robotsPermite,
} from "../../api/lector.ts";

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const oficiales = JSON.parse(
  readFileSync(join(RAIZ, "configuracion", "fuentes_oficiales.json"), "utf-8"),
) as {
  fuentes: { id: string; url: string; delegada?: boolean }[];
};
const vercel = JSON.parse(readFileSync(join(RAIZ, "vercel.json"), "utf-8")) as {
  functions: Record<string, { regions?: string[]; maxDuration?: number }>;
};

const LISTA = "https://www.mod.gov.lv/lv/zinas";
const NOTA =
  "https://www.mod.gov.lv/lv/zinas/latvijas-gaisa-telpa-notriekts-drons";
const CANAL =
  "https://www.csn.es/sucesos-notificados/-/asset_publisher/AhgtIexAjt0q/rss";

function pedir(fuente: string, url: string): Promise<Response> {
  const q = new URLSearchParams({ fuente, url });
  return GET(
    new Request(`https://droneobservatory.eu/api/lector?${q.toString()}`),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  olvidar();
});

describe("la lista cerrada", () => {
  it("admite las direcciones de sus fuentes", () => {
    for (const [fuente, url] of [
      ["mod_lv", LISTA],
      ["mod_lv", NOTA],
      ["mod_lv", "https://www.mod.gov.lv/robots.txt"],
      ["csn_sucesos", CANAL],
    ] as const) {
      expect(typeof admitir(fuente, url)).toBe("object");
    }
  });

  it("rechaza cualquier otra cosa", () => {
    expect(admitir("otra", LISTA)).toBe("fuente no admitida");
    expect(admitir(null, LISTA)).toBe("fuente no admitida");
    expect(admitir("mod_lv", null)).toBe("falta la dirección");
    expect(admitir("mod_lv", "no es una dirección")).toBe(
      "dirección no válida",
    );
    for (const url of [
      "https://example.org/lv/zinas",
      "http://www.mod.gov.lv/lv/zinas",
      "https://mod.gov.lv/lv/zinas",
      "https://www.mod.gov.lv:8443/lv/zinas",
      "https://usuario:clave@www.mod.gov.lv/lv/zinas",
      "https://www.mod.gov.lv/lv/zinas?url=https://example.org",
      "https://www.mod.gov.lv/lv/zinas#x",
      "https://www.mod.gov.lv/admin",
      "https://www.mod.gov.lv/lv/zinas/corta",
      "https://www.mod.gov.lv/lv/zinas/../../admin",
      CANAL,
    ]) {
      expect(admitir("mod_lv", url), url).toBe("dirección no admitida");
    }
  });

  it("tiene todas las fuentes delegadas de la recogida, con su dirección", () => {
    const delegadas = oficiales.fuentes.filter((f) => f.delegada === true);
    expect(delegadas.map((f) => f.id).sort()).toEqual(
      FUENTES.map((f) => f.id).sort(),
    );
    for (const fuente of delegadas)
      expect(typeof admitir(fuente.id, fuente.url), fuente.id).toBe("object");
  });

  it("corre en Estocolmo, cerca de Letonia, con tiempo para la fuente", () => {
    expect(vercel.functions["api/lector.ts"]).toEqual({
      regions: ["arn1"],
      maxDuration: 60,
    });
  });
});

describe("el tope por minuto", () => {
  it("deja pasar TOPE_POR_MINUTO peticiones y luego dice cuánto esperar", () => {
    let ahora = 0;
    const tope = new Tope(TOPE_POR_MINUTO, () => ahora);
    for (let i = 0; i < TOPE_POR_MINUTO; i++) expect(tope.pedir()).toBe(true);
    ahora = 20_000;
    expect(tope.pedir()).toBe(40);
    ahora = 60_000;
    expect(tope.pedir()).toBe(true);
  });
});

describe("robots.txt", () => {
  const TEXTO =
    "User-agent: *\nDisallow: /lv/zinas/privado\n\nUser-agent: OtroBot\nDisallow: /\n";

  it("aplica el grupo de «*» si no hay uno del observatorio", () => {
    const reglas = reglasRobots(TEXTO);
    expect(robotsPermite(reglas, "/lv/zinas")).toBe(true);
    expect(robotsPermite(reglas, "/lv/zinas/privado-1")).toBe(false);
  });

  it("aplica el grupo del observatorio si lo hay", () => {
    const reglas = reglasRobots(
      `${TEXTO}\nUser-agent: EODI-bot\nDisallow: /lv/\n`,
    );
    expect(robotsPermite(reglas, "/lv/zinas")).toBe(false);
    expect(
      robotsPermite(reglasRobots("User-agent: *\nDisallow:\n"), "/x"),
    ).toBe(true);
  });
});

describe("la descarga", () => {
  function fuenteFalsa(
    paginas: Record<string, Response | (() => Response)>,
  ): ReturnType<typeof vi.fn> {
    const falso = vi.fn((url: string, opciones: RequestInit) => {
      expect(new Headers(opciones.headers).get("user-agent")).toBe(AGENTE);
      const pagina = paginas[url];
      if (pagina === undefined)
        return Promise.resolve(new Response("no", { status: 404 }));
      return Promise.resolve(
        typeof pagina === "function" ? pagina() : pagina.clone(),
      );
    });
    vi.stubGlobal("fetch", falso);
    return falso;
  }

  it("devuelve la página tal cual, con su código, su fecha y la dirección final", async () => {
    fuenteFalsa({
      "https://www.mod.gov.lv/robots.txt": new Response(
        "User-agent: *\nDisallow:\n",
      ),
      [LISTA]: new Response("<html>zinas</html>", {
        headers: {
          "content-type": "text/html; charset=utf-8",
          date: "Tue, 27 Oct 2026 01:00:00 GMT",
        },
      }),
    });
    const r = await pedir("mod_lv", LISTA);
    expect(r.status).toBe(200);
    expect(await r.text()).toBe("<html>zinas</html>");
    expect(r.headers.get("x-lector")).toBe("origen");
    expect(r.headers.get("x-lector-url-final")).toBe(LISTA);
    expect(r.headers.get("x-lector-fecha")).toBe(
      "Tue, 27 Oct 2026 01:00:00 GMT",
    );
    expect(r.headers.get("content-type")).toBe("text/html; charset=utf-8");
  });

  it("pasa el código de la fuente (un 403 es de la fuente, no del lector)", async () => {
    fuenteFalsa({ [CANAL]: new Response("prohibido", { status: 403 }) });
    const r = await pedir("csn_sucesos", CANAL);
    expect(r.status).toBe(403);
    expect(r.headers.get("x-lector")).toBe("origen");
  });

  it("no descarga nada fuera de la lista", async () => {
    const falso = fuenteFalsa({});
    const r = await pedir("mod_lv", "https://example.org/");
    expect(r.status).toBe(400);
    expect(r.headers.get("x-lector")).toBe("propio");
    expect(falso).not.toHaveBeenCalled();
  });

  it("sigue una redirección solo dentro de la lista", async () => {
    fuenteFalsa({
      [CANAL]: new Response(null, {
        status: 301,
        headers: { location: "https://example.org/rss" },
      }),
    });
    const r = await pedir("csn_sucesos", CANAL);
    expect(r.status).toBe(502);
    expect(await r.text()).toContain("no admitida");
  });

  it("no lee lo que su robots.txt no deja", async () => {
    const falso = fuenteFalsa({
      "https://www.mod.gov.lv/robots.txt": new Response(
        "User-agent: *\nDisallow: /lv/\n",
      ),
    });
    const r = await pedir("mod_lv", LISTA);
    expect(r.status).toBe(403);
    expect(r.headers.get("x-lector")).toBe("propio");
    expect(falso).toHaveBeenCalledTimes(1);
  });

  it("dice 504 si la fuente no responde", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("fetch failed"))),
    );
    const r = await pedir("csn_sucesos", CANAL);
    expect(r.status).toBe(504);
    expect(r.headers.get("x-lector")).toBe("propio");
  });

  it("responde 429 con Retry-After al pasar del tope", async () => {
    fuenteFalsa({ [CANAL]: () => new Response("<feed/>") });
    for (let i = 0; i < TOPE_POR_MINUTO; i++)
      expect((await pedir("csn_sucesos", CANAL)).status).toBe(200);
    const r = await pedir("csn_sucesos", CANAL);
    expect(r.status).toBe(429);
    expect(Number(r.headers.get("retry-after"))).toBeGreaterThan(0);
  });
});
