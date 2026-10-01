import js from "@eslint/js";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

/**
 * Todo texto que viene de fuentes externas se muestra solo como texto: en web/ no se
 * inserta HTML de ninguna forma. Estas reglas lo impiden en el código.
 */
export const SIN_INSERCION_DE_HTML = [
  {
    selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
    message: "No se inserta HTML: el contenido se muestra como texto.",
  },
  {
    selector: "Property[key.name='dangerouslySetInnerHTML']",
    message: "No se inserta HTML: el contenido se muestra como texto.",
  },
  {
    selector: "Property[key.value='dangerouslySetInnerHTML']",
    message: "No se inserta HTML: el contenido se muestra como texto.",
  },
  {
    selector: "AssignmentExpression[left.property.name=/^(innerHTML|outerHTML|srcdoc)$/]",
    message: "No se inserta HTML: usa textContent o nodos.",
  },
  {
    selector:
      "CallExpression[callee.property.name=/^(insertAdjacentHTML|setHTMLUnsafe|parseHTMLUnsafe|createContextualFragment)$/]",
    message: "No se inserta HTML: usa textContent o nodos.",
  },
  {
    selector: "CallExpression[callee.object.name='document'][callee.property.name=/^write(ln)?$/]",
    message: "No se escribe HTML en el documento.",
  },
  {
    selector: "JSXAttribute[name.name='srcDoc']",
    message: "No se inserta HTML: el contenido se muestra como texto.",
  },
];

export default tseslint.config(
  { ignores: ["dist", "node_modules", "public", "src/generado", ".vite-react-ssg-temp"] },
  js.configs.recommended,
  ...tseslint.configs.strict,
  jsxA11y.flatConfigs.strict,
  {
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    plugins: { "react-hooks": reactHooks },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "error",
      "no-restricted-syntax": ["error", ...SIN_INSERCION_DE_HTML],
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
      "no-script-url": "error",
      eqeqeq: "error",
    },
  },
  {
    // El mapa se carga aparte, cuando hace falta: fuera de src/mapa/ solo se importan sus
    // tipos, porque un valor metería MapLibre en el paquete inicial y retrasaría la primera
    // pintura en móvil.
    files: ["src/**"],
    ignores: ["src/mapa/**"],
    rules: {
      "@typescript-eslint/no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["**/mapa/Mapa.tsx", "maplibre-gl", "maplibre-gl/**", "pmtiles"],
              allowTypeImports: true,
              message: "Solo tipos: el mapa se carga aparte con lazy().",
            },
          ],
        },
      ],
    },
  },
  {
    // Los tests escriben a propósito direcciones y textos hostiles.
    files: ["tests/**"],
    rules: {
      "no-script-url": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      // Quitar un campo con desestructuración deja una variable con guion bajo a propósito.
      "@typescript-eslint/no-unused-vars": ["error", { varsIgnorePattern: "^_" }],
    },
  },
);
