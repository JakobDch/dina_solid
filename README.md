# dina

Ask a [Solid](https://solidproject.org/) dataspace questions in plain language.

dina works out a SPARQL query for the question, runs it against the pods that
hold the data, and answers from the result. Every read uses the asking user's
own credentials; the application stores no data of its own.

*[Deutsche Fassung](README.de.md)*

## How it works

```
Browser ──SSE──▶ GET /api/v1/agent/chat
                   │
                   ├─ 1. plan       break the question into steps
                   ├─ 2. search     search the DCAT catalog of the dataspace
                   ├─ 3. fetch      load the semantic models of the best candidates
                   └─ 4. work out   query the data until the answer holds up
                                    │
                   ◀────────────────┘  query + dataset URLs
Browser ──────▶ Comunica runs the query against the Solid pods
Browser ──POST─▶ /api/v1/agent/comunica-results
                   │
                   └─ 5. answer     summarise, chart or calculate
```

Step 4 is where most of the difficulty sits. A semantic model describes the
shape of the data, not its contents, so a filter derived from the wording of a
question frequently matches nothing — a question asked in German will not find
values recorded in English. Rather than report an empty result, the agent runs
further queries against the data, inspects what a property actually contains,
and revises the query until it is satisfied or concludes that the data cannot
answer. Only the outcome reaches the conversation.

Catalog search is deliberately cheap: scanning dataset metadata is free, while
fetching a semantic model costs a network round trip. The agent is prompted to
search first and fetch only what it needs.

### Where data is read

- **Access control stays with Solid.** Every read carries the user's own
  credentials, so the application reaches exactly what their WebID permits.
- **The final query runs in the browser**, directly against the pods.
- **During step 4 the backend reads the selected datasets.** Querying them
  repeatedly is what allows the agent to notice a filter that found nothing.
  The data passes through the server; it is not persisted. If that trade does
  not suit your deployment, run the backend in the environment the data is
  already trusted to.

## Requirements

- Docker and Docker Compose
- An API key for one language model provider (DeepSeek, OpenAI or Fireworks),
  or a local [Ollama](https://ollama.com/) instance
- A WebID on a Solid pod

## Getting started

```bash
git clone https://github.com/JakobDch/dina_solid.git
cd dina_solid

cp .env.example .env
docker compose up --build
```

The interface is served at <http://localhost:3000>, the API at
<http://localhost:8002> with generated documentation at `/docs`.

Sign in with a Solid pod, then ask a question. An API key can be entered in the
interface; see [API keys](#api-keys).

To run the frontend outside Docker:

```bash
cd frontend
npm install
npm run dev
```

## Connecting a different dataspace

Two variables decide which dataspace is used:

```bash
SOLID_POD_BASE_URL=https://solid-community-server.tmdt.info
DATASPACE_SLUG=dace
```

Everything else is derived from them:

| Derived value | Composed as |
|---|---|
| Catalog container | `{pod}/{slug}/catalog/ds/` |
| Federation registry | `{pod}/semanticdatacatalog/public/{slug}/` |

Pods that arrange their containers differently can set `CATALOG_API_URL` and
`FEDERATION_REGISTRY_URL` directly; both take precedence over the derived
values. `SOLID_OIDC_ISSUER` is configured separately from the pod URL, because
a user may sign in with a pod hosted elsewhere.

For a frontend image that is already built, override `frontend/public/config.js`
instead of rebuilding:

```js
window.__DINA_CONFIG__ = {
  DINA_BACKEND_URL: "https://dina-api.example.org",
  SOLID_OIDC_ISSUER: "https://pod.example.org",
};
```

The file is read before the application starts, so mounting a different copy
into the container repoints a deployment.

### Federation

The registry lists every pod in the dataspace and the agent queries all of
them. Unreachable pods are skipped rather than failing the request, since
registries routinely outlive the pods they point at. Set
`CATALOG_USE_FEDERATION=false` to query only the configured catalog.

Registry entries are written when a pod registers and are not revised if the
server is renamed later, which can make every pod appear unreachable.
`POD_HOST_REWRITES=old.example=new.example` maps a recorded host onto the
current one.

## Configuration

All variables are documented in [`.env.example`](.env.example). The ones worth
knowing:

| Variable | Purpose |
|---|---|
| `SOLID_POD_BASE_URL` | Pod server holding the data and catalog |
| `DATASPACE_SLUG` | Path segment identifying the dataspace |
| `SOLID_OIDC_ISSUER` | Identity provider used for sign-in |
| `DEEPSEEK_API_KEY` | Key for the default language model |
| `DINA_CORS_ORIGINS` | Browser origins permitted to call the API |

The model is selected per conversation in the interface; the available profiles
are defined in `backend/app/config.py`.

## API keys

The assistant requires a key for one language model provider. Two options:

- **In the interface.** The key icon in the header accepts a DeepSeek, OpenAI
  or Fireworks key. It is held in the browser and sent only with the requests
  that need it — the server never stores it, and each user draws on their own
  quota. This is the appropriate choice for a shared instance.
- **In the environment.** Set `DEEPSEEK_API_KEY`, `OPENAI_API_KEY` or
  `FIREWORKS_API_KEY` in `.env`. Convenient for a single-user setup, but
  everyone sharing that instance spends the same key.

A key entered in the interface takes precedence. Models served by a local
Ollama require no key.

## Language

The interface is available in English and German, selected from the browser and
switchable in the header. Answers follow the language of the question, so a
question asked in German is answered in German without changing any setting.

## Security

Please read this before exposing an instance publicly.

**Charts and calculations run generated Python.** The globals available to that
code are restricted and obvious escape attempts are rejected, but a restricted
globals mapping is not a sandbox in CPython. Treat the feature as a convenience
for trusted users. A more exposed deployment should isolate the backend: a
container with no outbound network access and no credentials worth taking.

**The API has no authentication of its own.** It assumes it sits behind one, or
on a trusted network. Solid credentials are used solely to read pods.

Please report vulnerabilities through a private issue rather than a pull
request.

## Project layout

```
backend/
  app/
    catalog/                 DCAT catalog client, retrieval agent, model cache
    routers/                 HTTP and SSE endpoints
    orchestrating_agent.py   planning and step execution
    query_exploration.py     iterative querying against the loaded datasets
    sparql_generation.py     query generation and sanitising
frontend/
  src/
    components/              interface
    hooks/                   SSE stream, Comunica execution
    i18n/                    translations
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports are welcome, particularly
from dataspaces laid out differently from the one this was developed against.

## Licence

[Apache 2.0](LICENSE).

## Acknowledgements

Developed at the Chair of Technologies and Management of Digital Transformation
(TMDT), University of Wuppertal, as part of the DACE project, funded by the
German Federal Ministry of Research, Technology and Space and the European
Union under grant 16DKZ2056C.
