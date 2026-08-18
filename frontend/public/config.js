// Runtime configuration.
//
// This file is served as-is and is read before the application bundle starts.
// It lets an operator repoint a pre-built deployment - for example at a
// different Solid dataspace - by editing or mounting this single file, with no
// rebuild required.
//
// Any key left out falls back to the build-time VITE_* variable and then to the
// development default in src/config.ts.
//
// Example:
//
//   window.__DINA_CONFIG__ = {
//     DINA_BACKEND_URL: "https://dina-api.example.org",
//     SOLID_OIDC_ISSUER: "https://pod.example.org",
//     DATASPACE_UI_URL: "https://dataspace.example.org",
//     SOLID_PROVIDERS: "Example Pod|https://pod.example.org,solidcommunity.net|https://solidcommunity.net"
//   };

window.__DINA_CONFIG__ = {};
