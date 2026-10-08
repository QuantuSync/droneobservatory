// @vitest-environment jsdom
// Foco térmico detectado por satélite (NASA FIRMS): datos, resúmenes, fichas y leyenda.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Ayuda } from "../src/componentes/Ayuda.tsx";
import { FichaAtaque } from "../src/componentes/FichaAtaque.tsx";
import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { FichaRegion } from "../src/componentes/FichaRegion.tsx";
import { VISOR_FIRMS, enlaceVisorFirms } from "../src/componentes/FocoTermico.tsx";
import {
  centroDe,
  centrosDeRegiones,
  detalleIncidente,
  resumirUcrania,
} from "../src/datos/derivar.ts";
import type { ContornosRegiones } from "../src/datos/derivar.ts";
import { centrosDeFocos, cifrasDeRegion, focosDelPeriodo } from "../src/datos/ucrania.ts";
import {
  validarColeccion,
  validarEstadoSistema,
  validarPublicacionUcrania,
  validarResumenUcrania,
} from "../src/datos/validar.ts";
import { textos } from "../src/i18n/index.ts";
import { focosDeRegiones, pilas } from "../src/mapa/geometria.ts";
import { ultimas24Horas } from "../src/estado/filtros.ts";
import { diaDeInstante } from "../src/tiempo/dias.ts";
import { ataque, coleccion, estadoSistema, focoTermico, incidente, publicacion } from "./ejemplos.ts";

const es = textos("es");
const en = textos("en");

afterEach(cleanup);

const CONTORNOS: ContornosRegiones = {
  features: [
    {
      properties: { iso: "UA-51" },
      geometry: { type: "Polygon", coordinates: [[[30, 46], [32, 46], [32, 48], [30, 48], [30, 46]]] },
    },
  ],
};

function ataqueConFoco() {
  return ataque({
    regiones: [{ region: "UA-51", foco_termico: focoTermico() }, { region: "UA-12" }],
  });
}

describe("datos", () => {
  it("valida el foco detectado en un incidente y en una región", () => {
    expect(validarColeccion(coleccion([incidente({ foco_termico: focoTermico() })])).ok).toBe(true);
    expect(validarPublicacionUcrania(publicacion([ataqueConFoco()])).ok).toBe(true);
  });

  it("rechaza lo que no es un foco detectado o trae campos internos", () => {
    for (const malo of [
      { ...focoTermico(), resultado: "no_detectado" },
      { ...focoTermico(), frp_max_mw: 12 },
      { ...focoTermico(), motivo: "sin_focos" },
      { ...focoTermico(), satelite: "Landsat" },
      { ...focoTermico(), distancia_km: 25 },
    ]) {
      const coleccionMala = coleccion([incidente({ foco_termico: malo as never })]);
      expect(validarColeccion(coleccionMala).ok).toBe(false);
    }
  });

  it("estado.json trae FIRMS como una fuente más", () => {
    expect(validarEstadoSistema(estadoSistema()).ok).toBe(true);
  });

  it("el centro de una región es el de su área", () => {
    expect(centroDe([[[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]])).toEqual([1, 1]);
    expect(centrosDeRegiones(CONTORNOS).get("UA-51")).toEqual([31, 47]);
  });

  it("el resumen de Ucrania lleva cada foco con el centro de su región", () => {
    const resumen = resumirUcrania(publicacion([ataqueConFoco()]), centrosDeRegiones(CONTORNOS));
    expect(validarResumenUcrania(resumen).ok).toBe(true);
    expect(resumen.focos).toEqual([
      {
        ataque: "EODI-UA-2026-1013",
        dia: diaDeInstante("2026-09-29"),
        region: "UA-51",
        foco: focoTermico(),
        centro: [31, 47],
      },
    ]);
    const dia = diaDeInstante("2026-09-29");
    expect(focosDelPeriodo(resumen, { desde: dia, hasta: dia }, "UA-51")).toHaveLength(1);
    expect(focosDelPeriodo(resumen, { desde: dia, hasta: dia }, "UA-12")).toHaveLength(0);
    expect(focosDelPeriodo(resumen, { desde: dia + 1, hasta: dia + 2 })).toHaveLength(0);
    expect(centrosDeFocos(resumen).get("UA-51")).toEqual([31, 47]);
  });

  it("el mapa marca los incidentes con foco y las regiones en su centro", () => {
    const conFoco = { ...incidenteResumen(), foco: true };
    expect(pilas([conFoco], { recientes: ultimas24Horas(0), novedades: new Set() }).features[0]?.properties.foco).toBe(1);
    const resumen = resumirUcrania(publicacion([ataqueConFoco()]), centrosDeRegiones(CONTORNOS));
    expect(focosDeRegiones(resumen.focos).features[0]?.geometry.coordinates).toEqual([31, 47]);
  });

  it("el enlace abre el visor de FIRMS en el día y la posición, sin cargar nada", () => {
    expect(enlaceVisorFirms("2026-04-25T00:47Z", 28.0512, 45.4353, 11)).toBe(
      `${VISOR_FIRMS}#d:2026-04-25..2026-04-25;@28.051,45.435,11.0z`,
    );
  });
});

function incidenteResumen() {
  return {
    id: "EODI-2026-00200",
    punto: { lon: 28.05, lat: 45.43, radio_km: 10 },
    imprecisa: null,
    aproximado: null,
    tipo: "incursion" as const,
    estado: "confirmado" as const,
    presencia: null,
    titulo: { es: "a", en: "b" },
    dia: 0,
    inicio: null,
    pais: "RO",
    objetivo: null,
    episodio: null,
    foco: false,
    atribucion: null,
    zona: null,
    dron: [],
  };
}

describe("fichas", () => {
  it("la ficha de un incidente dice la hora UTC, el instrumento, la distancia y enlaza", () => {
    const detalle = detalleIncidente(incidente({ foco_termico: focoTermico() }, [28.0512, 45.4353]));
    render(<FichaIncidente t={es} idioma="es" incidente={detalle} />);
    const fila = screen.getByText("Foco térmico detectado por satélite").closest("dd");
    expect(fila).not.toBeNull();
    const dentro = within(fila as HTMLElement);
    expect(fila?.textContent).toMatch(/00:47 UTC · VIIRS \(NOAA-21\) · a 7,4 km/);
    const enlace = dentro.getByRole("link", { name: /visor de NASA FIRMS/ });
    expect(enlace.getAttribute("href")).toBe(
      enlaceVisorFirms("2026-04-25T00:47Z", 28.0512, 45.4353, 11),
    );
    expect(enlace.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("en inglés", () => {
    const detalle = detalleIncidente(incidente({ foco_termico: focoTermico() }));
    render(<FichaIncidente t={en} idioma="en" incidente={detalle} />);
    expect(screen.getByText("Thermal hotspot detected by satellite")).toBeTruthy();
    expect(document.body.textContent).toContain("7.4 km away");
  });

  it("sin foco no hay línea", () => {
    render(<FichaIncidente t={es} idioma="es" incidente={detalleIncidente(incidente())} />);
    expect(screen.queryByText("Foco térmico detectado por satélite")).toBeNull();
  });

  it("la ficha de un ataque lo dice en su región", () => {
    render(
      <FichaAtaque t={es} idioma="es" ataque={ataqueConFoco()} centros={new Map([["UA-51", [31, 47]]])} />,
    );
    expect(screen.getAllByText("Foco térmico detectado por satélite")).toHaveLength(1);
    expect(screen.getByRole("link", { name: /visor de NASA FIRMS/ }).getAttribute("href")).toContain(
      "@31.000,47.000,8.0z",
    );
  });

  it("el panel de la región lo dice con su ataque", () => {
    const resumen = resumirUcrania(publicacion([ataqueConFoco()]), centrosDeRegiones(CONTORNOS));
    const dia = diaDeInstante("2026-09-29");
    const periodo = { desde: dia, hasta: dia };
    render(
      <FichaRegion
        t={es}
        idioma="es"
        codigo="UA-51"
        cifras={cifrasDeRegion(resumen, "UA-51", periodo)}
        periodo="29 sep 2026"
        focos={focosDelPeriodo(resumen, periodo, "UA-51")}
      />,
    );
    expect(screen.getByText("Foco térmico detectado por satélite")).toBeTruthy();
    expect(screen.getByText(/EODI-UA-2026-1013 ·/)).toBeTruthy();
  });

  it("la ayuda explica la marca", () => {
    render(<Ayuda t={es} abierta={false} onCerrar={() => undefined} />);
    expect(screen.getByText(/foco térmico detectado por satélite \(NASA FIRMS\)/)).toBeTruthy();
    expect(document.querySelector("[data-marca-foco]")).not.toBeNull();
  });
});
