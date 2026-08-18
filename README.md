# DINa

Ask questions about a [Solid](https://solidproject.org/) dataspace in plain
language and get answers back from the data itself.

DINa translates a question into a SPARQL query, runs it against the pods that
hold the data, and answers from the result. It never copies the data: queries
are executed in the browser, directly against the pods the user is authorised
to read.

*[Deutsche Fassung](README.de.md)*

![The chat interface](docs/images/chat-interface.png)

## How it works

A question travels through the system like this:

```
Browser ──SSE──▶ GET /api/v1/agent/chat
                   │
                   ├─ 1. plan       the agent breaks the question into steps
                   ├─ 2. search     it searches the DCAT catalog of the dataspace
                   ├─ 3. fetch      it loads the semantic models of the best candidates
                   └─ 4. generate   a language model writes a SPARQL query
                                    │
                   ◀────────────────┘  query + dataset URLs
Browser ──────▶ Comunica runs the query against the Solid pods
Browser ──POST─▶ /api/v1/agent/comunica-results
                   │
                   └─ 5. answer     the agent summarises, charts or calculates
```

Two consequences follow from this shape:

- **The backend never executes SPARQL.** It only ever sees metadata and the
  results the browser sends back. The data stays in the pods.
- **Access control stays with Solid.** Queries run under the user's own
  credentials, so they can reach exactly what their WebID is allowed to reach.

Catalog search is deliberately cheap. Dataset metadata is free to scan, while
fetching a semantic model costs a network round trip, so the agent is prompted
to search first and fetch only what it needs.

## Requirements

- Docker and Docker Compose
- An API key for one language model provider (DeepSeek, OpenAI, or Fireworks),
  or a local [Ollama](https://ollama.com/) instance
- A WebID on a Solid pod to sign in with

## Getting started

```bash
git clone https://github.com/JakobDch/dina_solid.git
cd dina_solid

cp .env.example .env      # then add your API key
docker compose up --build
```

The interface is then at <http://localhost:3000> and the API at
<http://localhost:8002> (with generated documentation at `/docs`).

Sign in with your Solid pod, pick a catalog, and ask something.

To run the frontend outside Docker:

```bash
cd frontend
npm install
npm run dev
```

## Connecting a different dataspace

Two variables in `.env` decide which dataspace is used:

```bash
SOLID_POD_BASE_URL=https://solid-community-server.tmdt.info
DATASPACE_SLUG=dace
```

Everything else is derived from them:

| Derived value | Composed as |
|---|---|
| Catalog container | `{pod}/{slug}/catalog/ds/` |
| Federation registry | `{pod}/semanticdatacatalog/public/{slug}/` |

If a pod arranges its containers differently, set `CATALOG_API_URL` and
`FEDERATION_REGISTRY_URL` directly — they take precedence. `SOLID_OIDC_ISSUER`
is separate from the pod URL, because people may sign in with a pod hosted
somewhere else entirely.

For a frontend image that is already built, override
`frontend/public/config.js` rather than rebuilding:

```js
window.__DINA_CONFIG__ = {
  DINA_BACKEND_URL: "https://dina-api.example.org",
  SOLID_OIDC_ISSUER: "https://pod.example.org",
};
```

The file is read before the application starts, so mounting a different copy
into the container is enough to repoint a deployment.

### Federation

The registry lists every pod in the dataspace, and the agent queries all of
them. Pods that are unreachable are skipped rather than failing the request —
registries routinely outlive the pods they point at. Set
`CATALOG_USE_FEDERATION=false` to query only the configured catalog.

Registry entries are written when a pod registers and are not revised if the
server is renamed later, which makes every pod look unreachable. Set
`POD_HOST_REWRITES=old.example=new.example` to map the recorded host onto the
current one.

## Configuration

Every variable is documented in [`.env.example`](.env.example). The ones worth
knowing:

| Variable | Purpose |
|---|---|
| `SOLID_POD_BASE_URL` | Pod server holding the data and catalog |
| `DATASPACE_SLUG` | Path segment identifying the dataspace |
| `SOLID_OIDC_ISSUER` | Identity provider used for sign-in |
| `DEEPSEEK_API_KEY` | Key for the default language model |
| `DINA_CORS_ORIGINS` | Browser origins allowed to call the API |

Models are selected per conversation in the interface; the profiles live in
`backend/app/config.py`.

## API keys

The assistant needs a key for one language model provider. There are two ways
to supply one, and the interface is the better default for a shared instance:

- **In the interface.** Open the key icon in the header and paste a DeepSeek,
  OpenAI or Fireworks key. It is kept in your browser and sent only with the
  request that needs it - the server never stores it. Each person uses their
  own key and their own quota.
- **In the environment.** Set `DEEPSEEK_API_KEY` (or `OPENAI_API_KEY` /
  `FIREWORKS_API_KEY`) in `.env`. This is convenient for a single-user setup,
  but everyone sharing that instance then spends the same key.

A key entered in the interface takes precedence over the environment. Models
served by a local Ollama need no key at all.

## Language

The interface ships in English and German, chosen from the browser and
switchable in the header. Answers follow the language of the question, so
asking in German gets a German answer without changing any setting.

## Security

Please read this before exposing an instance publicly.

**Charts and calculations are produced by running generated Python.** The
globals given to that code are restricted and obvious escape attempts are
rejected, but a restricted globals mapping is not a sandbox in CPython. Treat
the feature as a convenience for people you already trust. If you expose the
service more widely, isolate the backend: a container with no outbound network
access and no credentials worth stealing.

**The API has no authentication of its own.** It assumes it sits behind one, or
on a trusted network. Solid credentials are only used to read the pods.

Found something? Please open an issue rather than a pull request.

## Project layout

```
backend/
  app/
    catalog/       DCAT catalog client, retrieval agent, model cache
    routers/       HTTP and SSE endpoints
    orchestrating_agent.py   planning and step execution
    sparql_generation.py     query generation and sanitising
frontend/
  src/
    components/    interface
    hooks/         SSE stream, Comunica execution
    i18n/          translations
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports are welcome, especially
about dataspaces whose layout differs from the one this was built against.

## Licence

[Apache 2.0](LICENSE).

## Acknowledgements

Developed at the Chair of Technologies and Management of Digital Transformation
(TMDT), University of Wuppertal, as part of the DACE project, funded by the
German Federal Ministry of Research, Technology and Space and the European
Union under grant 16DKZ2056C.
