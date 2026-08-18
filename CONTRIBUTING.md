# Contributing

Thanks for taking a look. Bug reports are as useful as patches here, especially
from anyone pointing DINa at a dataspace laid out differently from the one it
was built against — that is where the assumptions are thinnest.

## Getting set up

```bash
cp .env.example .env      # add an API key for one model provider
docker compose up --build
```

Backend and frontend can also run directly:

```bash
cd backend && pip install -e ".[dev]" && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

The backend needs Postgres and Redis; the compose file is the shortest path to
both.

## Before opening a pull request

```bash
cd frontend && npm run build     # type check and production build
cd backend && ruff check app     # lint
```

There is no meaningful automated test suite yet. Adding one is welcome —
`backend/tests/` and pytest are already configured in `pyproject.toml`.

Until then, changes to the query path are best verified by hand:

1. Sign in with a Solid pod, so the token reaches the catalog.
2. Ask something that needs data, and confirm the browser receives a
   `comunica_execution_required` event carrying a query and dataset URLs.
3. Ask a follow-up, and confirm it reuses the cached models instead of
   searching the catalog again.

## When a change does not show up

The frontend container keeps `node_modules` in an anonymous volume, and Vite
caches transformed modules inside it. That cache survives `docker compose
restart`, so a deleted or renamed component can still be served after the
source is gone. If the interface disagrees with the code, clear it:

```bash
docker compose exec frontend rm -rf /app/node_modules/.vite
docker compose restart frontend
```

Backend containers read their environment from `.env` at creation time. After
editing that file, recreate rather than restart:

```bash
docker compose up -d --force-recreate backend
```

## Style

**Python** follows PEP 8 with a 100 character line limit; `ruff` enforces both.
Type hints on anything crossing a module boundary.

**TypeScript** uses functional components, `PascalCase` for components and
`camelCase` for hooks and helpers.

Comments should explain why something is the way it is. What the code does is
usually visible; the reason it does it that way often is not.

## Language

The interface is bilingual. Any user-visible string belongs in
`frontend/src/i18n/locales/`, in **both** `en.json` and `de.json` — a key
present in one and missing from the other falls back silently and is easy to
miss.

Prompts are written in English and instructed to answer in the language of the
question. Please do not add German-only prompts; it doubles what has to be kept
in sync.

## Things worth knowing before you change them

**The backend does not execute SPARQL.** Queries go to the browser, which runs
them against the pods with Comunica and posts the results back. Moving execution
into the backend would mean it needs the user's credentials and a copy of the
data — a deliberate non-goal.

**Prompt placeholders are load-bearing.** Names in `{braces}` are filled by
`.format()`. So are the JSON keys the model is asked to emit (`thought`,
`action`, `action_input`, and friends) — the parser matches them literally.
Rewording the prose around them is fine; renaming them breaks the agent quietly.

**Catalog cost is asymmetric on purpose.** Searching metadata is free, fetching
a model is not. The prompts lean on that distinction, so changes that make the
agent fetch eagerly will get slower and more expensive without looking broken.

## Security

Please report vulnerabilities through a private issue rather than a pull
request. The known sharp edge — running generated Python for charts and
calculations — is documented in the README; sharpening or blunting it further is
a conversation worth having first.
