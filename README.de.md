# dina

Fragen an einen [Solid](https://solidproject.org/)-Datenraum in natürlicher
Sprache stellen.

dina erarbeitet zu einer Frage eine SPARQL-Query, führt sie gegen die Pods aus,
in denen die Daten liegen, und antwortet auf Basis des Ergebnisses. Jeder
Lesezugriff erfolgt mit den Zugangsdaten der fragenden Person; eigene Daten
hält die Anwendung nicht.

*[English version](README.md)*

## Funktionsweise

```
Browser ──SSE──▶ GET /api/v1/agent/chat
                   │
                   ├─ 1. Plan        Frage in Schritte zerlegen
                   ├─ 2. Suche       DCAT-Katalog des Datenraums durchsuchen
                   ├─ 3. Laden       semantische Modelle der besten Treffer holen
                   └─ 4. Erarbeiten  Daten abfragen, bis die Antwort trägt
                                    │
                   ◀────────────────┘  Query + Dataset-URLs
Browser ──────▶ Comunica führt die Query gegen die Solid-Pods aus
Browser ──POST─▶ /api/v1/agent/comunica-results
                   │
                   └─ 5. Antwort     zusammenfassen, rechnen oder visualisieren
```

Der vierte Schritt trägt den größten Teil der Schwierigkeit. Ein semantisches
Modell beschreibt die Struktur der Daten, nicht ihren Inhalt — ein Filter, der
aus der Formulierung der Frage abgeleitet wird, trifft daher häufig nichts:
Eine deutsch gestellte Frage findet keine englisch erfassten Werte. Statt ein
leeres Ergebnis zu melden, führt der Agent weitere Abfragen aus, sieht nach,
welche Werte eine Property tatsächlich enthält, und überarbeitet die Query, bis
sie trägt oder er feststellt, dass die Daten die Frage nicht beantworten
können. Im Chat erscheint nur das Ergebnis.

Die Katalogsuche ist bewusst günstig gehalten: Metadaten zu durchsuchen kostet
nichts, das Laden eines semantischen Modells dagegen einen Netzwerkzugriff. Der
Agent wird deshalb angehalten, erst zu suchen und nur das Nötige zu laden.

### Wo Daten gelesen werden

- **Die Zugriffskontrolle bleibt bei Solid.** Jeder Lesezugriff läuft mit den
  Zugangsdaten des Nutzers; erreichbar ist genau das, wofür seine WebID
  berechtigt ist.
- **Die finale Abfrage läuft im Browser**, direkt gegen die Pods.
- **In Schritt 4 liest das Backend die ausgewählten Datensätze.** Erst das
  wiederholte Abfragen erlaubt dem Agenten zu bemerken, dass ein Filter nichts
  gefunden hat. Die Daten laufen dabei durch den Server, gespeichert werden sie
  nicht. Wer diesen Kompromiss nicht eingehen will, sollte das Backend dort
  betreiben, wo den Daten ohnehin vertraut wird.

## Voraussetzungen

- Docker und Docker Compose
- Ein API-Schlüssel für einen Sprachmodell-Anbieter (DeepSeek, OpenAI oder
  Fireworks) oder eine lokale [Ollama](https://ollama.com/)-Instanz
- Eine WebID auf einem Solid Pod

## Loslegen

```bash
git clone https://github.com/JakobDch/dina_solid.git
cd dina_solid

cp .env.example .env
docker compose up --build
```

Die Oberfläche liegt unter <http://localhost:3000>, die API unter
<http://localhost:8002> mit generierter Dokumentation unter `/docs`.

Mit einem Solid Pod anmelden, dann eine Frage stellen. Der API-Schlüssel lässt
sich in der Oberfläche eintragen, siehe [API-Schlüssel](#api-schlüssel).

Das Frontend außerhalb von Docker starten:

```bash
cd frontend
npm install
npm run dev
```

## Einen anderen Datenraum anbinden

Zwei Variablen bestimmen, welcher Datenraum verwendet wird:

```bash
SOLID_POD_BASE_URL=https://solid-community-server.tmdt.info
DATASPACE_SLUG=dace
```

Alles Weitere wird daraus abgeleitet:

| Abgeleiteter Wert | Zusammensetzung |
|---|---|
| Katalog-Container | `{pod}/{slug}/catalog/ds/` |
| Federation-Registry | `{pod}/semanticdatacatalog/public/{slug}/` |

Pods mit abweichendem Aufbau können `CATALOG_API_URL` und
`FEDERATION_REGISTRY_URL` direkt setzen; beide haben Vorrang vor den
abgeleiteten Werten. `SOLID_OIDC_ISSUER` ist bewusst von der Pod-URL getrennt,
weil sich ein Nutzer mit einem anderswo gehosteten Pod anmelden kann.

Für ein bereits gebautes Frontend-Image genügt es, `frontend/public/config.js`
zu überschreiben, statt neu zu bauen:

```js
window.__DINA_CONFIG__ = {
  DINA_BACKEND_URL: "https://dina-api.example.org",
  SOLID_OIDC_ISSUER: "https://pod.example.org",
};
```

Die Datei wird vor dem Start der Anwendung gelesen; eine andere Fassung in den
Container zu mounten hängt eine Installation um.

### Föderation

Die Registry listet alle Pods des Datenraums, und der Agent fragt sie gemeinsam
ab. Nicht erreichbare Pods werden übersprungen, statt die ganze Anfrage
scheitern zu lassen — Registries überleben die eingetragenen Pods regelmäßig.
Mit `CATALOG_USE_FEDERATION=false` wird nur der konfigurierte Katalog abgefragt.

Registry-Einträge entstehen bei der Registrierung und werden nicht nachgezogen,
wenn der Server später umbenannt wird; dann erscheinen alle Pods als nicht
erreichbar. `POD_HOST_REWRITES=alt.example=neu.example` bildet den
eingetragenen Host auf den aktuellen ab.

## Konfiguration

Alle Variablen sind in [`.env.example`](.env.example) dokumentiert. Die
wichtigsten:

| Variable | Zweck |
|---|---|
| `SOLID_POD_BASE_URL` | Pod-Server mit Daten und Katalog |
| `DATASPACE_SLUG` | Pfadsegment, das den Datenraum bezeichnet |
| `SOLID_OIDC_ISSUER` | Identitätsanbieter für die Anmeldung |
| `DEEPSEEK_API_KEY` | Schlüssel für das voreingestellte Sprachmodell |
| `DINA_CORS_ORIGINS` | Zugelassene Browser-Origins für API-Aufrufe |

Das Modell wird pro Unterhaltung in der Oberfläche gewählt; die verfügbaren
Profile stehen in `backend/app/config.py`.

## API-Schlüssel

Der Assistent benötigt einen Schlüssel für einen Sprachmodell-Anbieter. Zwei
Wege stehen offen:

- **In der Oberfläche.** Das Schlüssel-Symbol im Header nimmt einen DeepSeek-,
  OpenAI- oder Fireworks-Schlüssel entgegen. Er bleibt im Browser und wird nur
  mit den Anfragen gesendet, die ihn brauchen — der Server speichert ihn nie,
  und jede Person nutzt ihr eigenes Kontingent. Für eine geteilte Instanz ist
  das der passende Weg.
- **In der Umgebung.** `DEEPSEEK_API_KEY`, `OPENAI_API_KEY` oder
  `FIREWORKS_API_KEY` in `.env` setzen. Für den Einzelbetrieb bequem, aber alle
  Nutzer der Instanz verbrauchen denselben Schlüssel.

Ein in der Oberfläche eingetragener Schlüssel hat Vorrang. Lokal über Ollama
betriebene Modelle brauchen keinen.

## Sprache

Die Oberfläche gibt es auf Deutsch und Englisch, ausgewählt anhand des Browsers
und im Header umschaltbar. Antworten richten sich nach der Sprache der Frage —
eine deutsch gestellte Frage wird deutsch beantwortet, ohne dass etwas
eingestellt werden muss.

## Sicherheit

Bitte vor einem öffentlichen Betrieb lesen.

**Diagramme und Berechnungen führen generierten Python-Code aus.** Die
bereitgestellten Globals sind eingeschränkt und offenkundige Ausbruchsversuche
werden abgewiesen, aber eine eingeschränkte Globals-Zuordnung ist in CPython
keine Sandbox. Die Funktion ist als Komfort für vertrauenswürdige Nutzer
gedacht. Ein stärker exponierter Betrieb sollte das Backend isolieren: ein
Container ohne ausgehende Netzwerkverbindung und ohne lohnende Zugangsdaten.

**Die API bringt keine eigene Authentifizierung mit.** Sie setzt voraus, dass
eine davorliegt oder dass sie in einem vertrauenswürdigen Netz steht. Die
Solid-Anmeldedaten dienen ausschließlich dem Lesen der Pods.

Sicherheitslücken bitte über ein privates Issue melden, nicht über einen Pull
Request.

## Projektstruktur

```
backend/
  app/
    catalog/                 DCAT-Katalog-Client, Retrieval-Agent, Modell-Cache
    routers/                 HTTP- und SSE-Endpunkte
    orchestrating_agent.py   Planung und Schrittausführung
    query_exploration.py     iteratives Abfragen der geladenen Datensätze
    sparql_generation.py     Query-Erzeugung und -Bereinigung
frontend/
  src/
    components/              Oberfläche
    hooks/                   SSE-Stream, Comunica-Ausführung
    i18n/                    Übersetzungen
```

## Mitwirken

Siehe [CONTRIBUTING.md](CONTRIBUTING.md). Fehlerberichte sind willkommen,
besonders aus Datenräumen, die anders aufgebaut sind als der, gegen den
entwickelt wurde.

## Lizenz

[Apache 2.0](LICENSE).

## Förderhinweis

Entwickelt am Lehrstuhl für Technologien und Management der Digitalen
Transformation (TMDT) der Bergischen Universität Wuppertal im Rahmen des
Projekts DACE, gefördert vom Bundesministerium für Forschung, Technologie und
Raumfahrt und der Europäischen Union unter dem Förderkennzeichen 16DKZ2056C.
