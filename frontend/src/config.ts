// Application configuration.
//
// Values are resolved in three layers, most specific first:
//
//   1. Runtime   - window.__DINA_CONFIG__, injected by public/config.js
//   2. Build time - Vite environment variables (VITE_*)
//   3. Fallback  - the local development defaults below
//
// The runtime layer exists because Vite inlines VITE_* variables when the
// bundle is built. Without it, pointing a pre-built production image at a
// different dataspace would require rebuilding the image. Overwriting the
// small config.js file instead keeps deployments swappable.

declare global {
  interface Window {
    __DINA_CONFIG__?: Record<string, string>;
  }
}

const runtimeConfig: Record<string, string> =
  (typeof window !== 'undefined' && window.__DINA_CONFIG__) || {};

/** Resolve a single value across the runtime, build-time and fallback layers. */
function resolve(key: string, buildTime: string | undefined, fallback: string): string {
  return runtimeConfig[key] || buildTime || fallback;
}

export interface SolidProvider {
  name: string;
  url: string;
}

/**
 * Parse a provider list encoded as comma-separated "Label|https://url" pairs.
 *
 * Both configuration layers carry flat strings, so the list is encoded in a
 * single value. Malformed entries are skipped rather than thrown, so a typo in
 * a deployment variable cannot prevent the application from starting.
 */
export function parseProviders(raw: string): SolidProvider[] {
  return raw
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean)
    .flatMap((entry) => {
      const separator = entry.indexOf('|');
      const url = (separator === -1 ? entry : entry.slice(separator + 1)).trim();
      try {
        const label = separator === -1 ? new URL(url).hostname : entry.slice(0, separator).trim();
        return [{ name: label || url, url }];
      } catch {
        console.warn(`Ignoring malformed Solid provider entry: "${entry}"`);
        return [];
      }
    });
}

export const config = {
  // DINa Backend (this project)
  dinaBackendUrl: resolve(
    'DINA_BACKEND_URL',
    import.meta.env.VITE_DINA_BACKEND_URL,
    'http://localhost:8002',
  ),

  // Solid OIDC issuer offered as the primary login option.
  solidOidcIssuer: resolve(
    'SOLID_OIDC_ISSUER',
    import.meta.env.VITE_SOLID_OIDC_ISSUER,
    'https://solid-community-server.tmdt.info',
  ),

  // Human-facing dataspace web application. Used for outbound links only; it
  // serves HTML and is never queried as RDF.
  dataspaceUiUrl: resolve(
    'DATASPACE_UI_URL',
    import.meta.env.VITE_DATASPACE_UI_URL,
    'https://solid-dataspace-dace.tmdt.info',
  ),

  // Legacy standalone Semantic Data Catalog service. Only used by the older
  // external-catalog query path; the Solid dataspace integration does not
  // depend on it.
  semanticDataCatalogBackendUrl: resolve(
    'SEMANTIC_DATA_CATALOG_BACKEND_URL',
    import.meta.env.VITE_SEMANTIC_DATA_CATALOG_BACKEND_URL,
    'http://localhost:8000',
  ),

  // Additional login providers beyond the configured issuer.
  solidProviders: parseProviders(
    resolve(
      'SOLID_PROVIDERS',
      import.meta.env.VITE_SOLID_PROVIDERS,
      'solidcommunity.net|https://solidcommunity.net,Inrupt Pod Spaces|https://login.inrupt.com',
    ),
  ),
};
