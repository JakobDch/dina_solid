from langchain_core.prompts import ChatPromptTemplate


OUTPUT_SEPARATOR = "### ANTWORT ###"


# --- FEW-SHOT EXAMPLES FÜR JEDEN PIPELINE-SCHRITT ---
FEW_SHOT_EXAMPLES = {
    "IdentifyModels": '''
Hier sind einige Beispiele, wie die Aufgabe zu lösen ist:
--- Beispiel 1 ---
Nutzeranfrage: "Zeige mir alle Baustellen in Wuppertal und Düsseldorf."
Antwort:
{
  "required_models": [
    "Baustellen_Wuppertal",
    "Baustellen_Duesseldorf"
  ]
}
--- Ende Beispiel 1 ---
''',
    "DetermineConcept": '''
Hier sind einige Beispiele, wie die Aufgabe zu lösen ist:
--- Beispiel 1 ---
Modellbeschreibung: "Semantisches Modell über Ampeln in Köln"
Antwort: Ampel Koeln
--- Ende Beispiel 1 ---
''',
    "ValidateModels": '''
Hier sind einige Beispiele, wie die Aufgabe zu lösen ist:
--- Beispiel 1 ---
Nutzeranfrage: "Gibt es Baustellen in Köln?"
Tripel der als relevant identifizierten semantischen Modelle:
Modell: Baustellen_Koeln.ttl
local:Baustelle a rdfs:Class.
Antwort:
JA
Begründung: Das Modell 'Baustellen_Koeln.ttl' enthält die Klasse 'local:Baustelle' und ist für die Stadt Köln, was zur Beantwortung der Anfrage ausreicht.
--- Ende Beispiel 1 ---
''',
    "SPARQLGeneration": '''
Here are some examples of how to solve the task:
--- Start Example 1 ---
User query: "Give me all suspended railway stops in Wuppertal that contain 'Straße' or 'Strasse' in their name"
Semantic models:

Model: 099.ttl
```
local:Schwebebahnstation local:angefahren_von local:Wuppertaler_Schwebebahn .
local:Schwebebahnstation local:befindet_sich_an local:Geographischer_Punkt .
local:Schwebebahnstation local:hat local:Bezeichnung .
local:Schwebebahnstation local:ist_ein_e_ local:Haltestelle .
local:Schwebebahnstation local:located_in "Wuppertal"^^xsd:string .
local:Geographischer_Punkt local:besteht_aus local:Geographische_Breite .
local:Geographischer_Punkt local:besteht_aus local:Geographische_L_nge .
local:Geographischer_Punkt local:koordinatenreferenzsystem xsd:string .
```

Notes from the model check: The model is suitable.
Answer:
PREFIX owl:    <http://www.w3.org/2002/07/owl#>
PREFIX plasma: <http://plasma.uni-wuppertal.de/ontology#>
PREFIX plcm:   <http://plasma.uni-wuppertal.de/cm#>
PREFIX plsm:   <http://plasma.uni-wuppertal.de/sm/>
PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:    <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?Name
WHERE {{
  ?station a local:Schwebebahnstation ;
        local:hat ?Bezeichnung ;
        local:located_in "Rostock"^^xsd:string .
  ?Bezeichnung plasma:hasValue ?RoherWert .
  BIND(LCASE(?RoherWert) AS ?NameLower)
  FILTER (CONTAINS(?NameLower, "straße") || CONTAINS(?NameLower, "strasse"))
  BIND(?RoherWert AS ?Name)
}}
--- End Example 1 ---



--- Start Example 2 ---
User query: "Give me all park-and-ride facilities in Rostock with at least 10 parking spaces including location designation. Return the instance, the number of parking spaces, and the location designation (total of 3 columns)."

Semantic models:

Model: 033.ttl
```
local:Park_and_Ride_Anlage local:anzahl local:Stellplatz .
local:Park_and_Ride_Anlage local:befindet_sich_an local:Geographischer_Punkt .
local:Park_and_Ride_Anlage local:hat local:Adresse .
local:Park_and_Ride_Anlage local:hat local:Anbindung .
local:Park_and_Ride_Anlage local:hat local:Bezeichnung .
local:Park_and_Ride_Anlage local:hat local:Standortbezeichnung .
local:Park_and_Ride_Anlage local:hat local:Zusatzinformation .
local:Park_and_Ride_Anlage local:hat local:_ffnungszeit .
local:Park_and_Ride_Anlage local:identifiziert_durch local:Identifikator .
local:Park_and_Ride_Anlage local:located_in "Rostock"^^xsd:string .

local:Adresse local:besteht_aus local:Postleitzahl .
local:Adresse local:besteht_aus local:Stadt .

local:Geographischer_Punkt local:besteht_aus local:Geographische_Breite .
local:Geographischer_Punkt local:besteht_aus local:Geographische_L_nge .
local:Geographischer_Punkt local:koordinatenreferenzsystem xsd:string .

local:Website local:ist_vom_Typ local:Uniform_Resource_Locator__URL_ .

local:Zusatzinformation local:dargestellt_auf local:Website .


Notes from the model check: The model is suitable.

Answer:

PREFIX owl:    <http://www.w3.org/2002/07/owl#>
PREFIX plasma: <http://plasma.uni-wuppertal.de/ontology#>
PREFIX plcm:   <http://plasma.uni-wuppertal.de/cm#>
PREFIX plsm:   <http://plasma.uni-wuppertal.de/sm/>
PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:    <http://www.w3.org/2001/XMLSchema#>
PREFIX local:  <https://local.ontology#>

SELECT DISTINCT
  ?anlage
  (xsd:integer(?stellplatzWert) AS ?Anzahl_Stellplaetze)
  ?Standortbezeichnung
WHERE {
  ?anlage a local:Park_and_Ride_Anlage ;
          local:located_in "Rostock"^^xsd:string ;
          local:anzahl ?stellplatzEntity ;
          local:hat ?standortbezEntity .

  # Get parking space count as value (filter by type)
  ?stellplatzEntity a local:Stellplatz ;
                    plasma:hasValue ?stellplatzWert .

  # Get location name as value (filter by type)
  ?standortbezEntity a local:Standortbezeichnung ;
                     plasma:hasValue ?Standortbezeichnung .

  FILTER( xsd:integer(?stellplatzWert) >= 10 )
}
```
--- End Example 2 ---
'''
}




# Dein interner Reasoning Block
INTERNAL_REASONING_BLOCK_WITH_SEPARATOR = """
#################### Interne Reasoning-Phase ####################
Bevor du deine endgültige Ausgabe erzeugst, nimm dir intern Zeit, Schritt für Schritt über die Aufgabe nachzudenken (Chain-of-Thought/Scratchpad).

WICHTIG:
- Schreibe deine internen Überlegungen (Reasoning) zuerst hier im Prompt auf.
- Sobald du fertig bist, gib die finale Antwort AUSSCHLIESSLICH nach der folgenden Trennlinie aus:

### ANTWORT ###

[Hier NUR die geforderte Endausgabe im gewünschten Format.]

Hinweis:
- Schreibe NIEMALS Text nach der Trennlinie oder außerhalb des geforderten Formats!
"""

# --- ANGEPASSTE MASTER-PROMPTS ---
# Die Grundlage bilden eine Vielzahl einzelner Datensätze. Jeder dieser Datensätze bezieht sich genau auf ein bestimmtes Thema in genau einer Stadt.
#Zu jedem Datensatz existiert ein eigenes, separates semantisches Modell,das die zugrunde liegende Datenstruktur beschreibt.

# Prompt SCHRITT 1: Modelltypen identifizieren
OUTPUT_INSTRUCTIONS_IDENTIFY_MODELS = (
    "Gib deine Antwort ausschließlich im folgenden JSON-Format aus - ohne Begrüßung, Erklärung oder sonstigen Text:\n"
    "{\n  \"required_models\": [\n    \"Erstes benötigtes semantisches Modell\",\n    \"Zweites benötigtes semantisches Modell (nur falls nötig)\"\n  ]\n}"
)


IDENTIFY_KEYWORDS_PROMPT_TEMPLATE = ChatPromptTemplate.from_template("""
Das hier ist der erste Teilschritt in einem Prozess, bei dem eine natürlichsprachige Nutzeranfrage in eine SPARQL-Query umgewandelt wird.
Das System basiert auf Datensätzen und zugehörigen semantischen Modellen.
Die Semantischen Modelle wurden in ein Embedding überführt.
Deine Aufgabe ist es, Keywords aus der Nutzeranfrage zu extrahieren, die für die Suche im Embedding relevant sind.
Nenne jedes Keyword, dass relevant ist um die benötigten semantischen Modelle bei der Suche im Embedding zu identifizieren.
Überlege genau, was Keywords sind die relevant sind für die Anfrage und was zum Beispiel Anweisung innerhalb der Anfrage oder sonstige irrelevante Elemente sind.
Mache bei den Keywords aus Mehrzahl Einzahl, falls zutreffend.
Gib nur die für die Suche wichtigen Keywords aus.

{optional_internal_reasoning_block}

Nutzeranfrage: "{query}"

{optional_few_shot_examples}

{final_output_instructions}


Gib deine Antwort ausschließlich im folgenden JSON-Format aus, ohne zusätzlichen Text:
{{
  "keywords": ["keyword1", "keyword2", "keyword3"]
}}
""")

SELECT_RELEVANT_MODELS_PROMPT_TEMPLATE = ChatPromptTemplate.from_template("""
Das hier ist der zweite Teilschritt in einem Prozess, bei dem eine natürlichsprachige Nutzeranfrage in eine SPARQL-Query umgewandelt wird.
Das System basiert auf Datensätzen und zugehörigen semantischen Modellen.
Es wurde eine Sammlung potentieller semantischer Modelle auf Basis einer Embedding-Suche erstellt.
Deine Aufgabe ist es, aus einer Liste von potenziell relevanten semantischen Modellen diejenigen auszuwählen, die tatsächlich benötigt werden, um die Nutzeranfrage zu beantworten.

{optional_internal_reasoning_block}

Nutzeranfrage: "{query}"

Inhalt der Modell-Kandidaten:
{candidate_models_content}

Deine Aufgabe:
Analysiere die Nutzeranfrage und den INHALT der oben bereitgestellten Modelle. Wähle aus der Liste die Dateinamen der Modelle aus, die zwingend erforderlich sind, um die Anfrage zu beantworten.

Regeln für die Auswahl:
- Wähle nur Modelle aus, deren Inhalt (Tripel) direkt zur Beantwortung der Anfrage beiträgt.
- Ignoriere Modelle, die thematisch zwar ähnlich klingen, aber nicht die spezifischen Entitäten oder Beziehungen enthalten, die für die Anfrage benötigt werden.
- Sei minimalistisch: Wähle so wenige Modelle wie möglich, aber so viele wie nötig. Das heißt: Wenn mehrere Modelle in Frage kommen, prüfe ob die Anfrage nicht auch mit einer Teilmenge der Modelle beantwortet werden kann. 


Gib deine Antwort ausschließlich im folgenden JSON-Format aus, ohne zusätzlichen Text:
{{
  "selected_models": [
    "dateiname_des_ersten_ausgewaehlten_modells.ttl",
    "dateiname_des_zweiten_ausgewaehlten_modells.ttl"
  ]
}}
""")

# IDENTIFY_REQUIRED_MODEL_TYPES_PROMPT_TEMPLATE = ChatPromptTemplate.from_template("""
# Das hier ist der erste Teilschritt in einem Prozess, bei dem eine natürlichsprachige Nutzeranfrage in eine SPARQL-Query umgewandelt wird.




# Die Grundlage bilden eine Vielzahl einzelner Datensätze. Zu jedem Datensatz existiert ein eigenes, separates semantisches Modell,das die zugrunde liegende Datenstruktur beschreibt.

# {optional_internal_reasoning_block}

# Deine Aufgabe ist es, die semantischen Modelle nennen, die benötigt werden, um die folgende Nutzeranfrage vollständig beantworten zu können:
# "{query}"

# Beachte dabei:
# - Gib nur die Modelle an, die wirklich notwendig sind, um die Anfrage zu beantworten.
# - Wenn sich die Anfrage auf mehrere Themen oder Städte bezieht, müssen entsprechend
#   mehrere Modelle genannt werden - jeweils eins pro Konzept und Stadt.
# - Verallgemeinerungen sind nicht ausreichend. Die Modelle müssen so benannt sein, dass eindeutig
#   ist, auf welchen Datensatz sie sich beziehen.
# - Verwende so wenige Modelle wie möglich, aber so viele wie nötig.

# {optional_few_shot_examples}



# {final_output_instructions}
# """)




# Master-Template für Schritt 2: Retrieval-Konzept bestimmen
# DETERMINE_CONCEPT_MASTER_PROMPT = ChatPromptTemplate.from_template("""
# Das hier ist der zweite Teilschritt im Prozess eine Nutzeranfrage in eine SPARQL-Query umzuwandeln.

# Die Grundlage bilden eine Vielzahl einzelner Datensätze. 
# Zu jedem Datensatz existiert ein eigenes, separates semantisches Modell, das die zugrunde liegende Datenstruktur beschreibt.

# {optional_internal_reasoning_block}

# Deine Aufgabe ist es, einen prägnanten Schlüsselbegriff/Konzept aus der gegebenen Modellbeschreibung zu extrahieren, der für die
# Suche bzw. das Retrieval benutzt wird. Der Index basiert auf den Tripeln der semantischen Modellen.
# Mache aus Mehrzahl Einzahl, falls zutreffend.
# Wichtig: Der Suchbegriff darf keine Sonderzeichen, keine Umlaute (ä, ö, ü) und KEIN scharfes S ('ß') enthalten. Ersetze Umlaute (ae, oe, ue) und ß (ss).
# Bedenke, dass der Suchbegriff nicht zu allgemein sein sollte und ermöglichen sollte das gesuchte semantische Modell herauszufiltern. Er sollte also möglichst präzise sein.
# Bedenke, dass es Datensätze zum gleichen Thema aus verschiedenen Städten gibt, nutze die Stadt entsprechend immer im Suchbegriff, wenn vorhanden.
# {optional_few_shot_examples}

# Hier ist die zu analysierende Modellbeschreibung:
# Modellbeschreibung: {model_type_description}



# {final_output_instructions}
# """)

# # Ausgabeanweisung für Schritt 2 (bleibt gleich)
# OUTPUT_INSTRUCTIONS_DETERMINE_CONCEPT = """
# Antworte NUR mit diesem einen Schlüsselbegriff/Konzept.
# """


# Master-Template für Schritt 3: Modellprüfung (Combined Model Validation)
# Prompt für schrittweise Modell-Validierung
INCREMENTAL_MODEL_VALIDATION_PROMPT = ChatPromptTemplate.from_template("""
Du bewertest semantische Modelle schrittweise für eine SPARQL-Query und eliminierst nur echte Redundanzen.

{optional_internal_reasoning_block}

Nutzeranfrage: "{query}"

{validation_context}

Deine Aufgabe: Bewerte das folgende Modell:
{current_model}

Bewertungskriterien:
1. Relevanz: Enthält dieses Modell Daten/Strukturen die für die Nutzeranfrage benötigt werden?
2. Komplementarität: Ergänzt es die bereits validierten Modelle um fehlende Aspekte der Query?
3. Echte Redundanz: Sind die relevanten Daten bereits durch validierte Modelle vollständig abgedeckt?

WICHTIGE REGELN:
- Ein Modell sollte HINZUGEFÜGT werden wenn es relevante Daten für die Query enthält, auch wenn es alleine die Query nicht vollständig beantworten kann!
- Multi-Modell-Queries sind normal: Verschiedene Modelle können verschiedene Aspekte derselben Query abdecken
- Nur bei echter Redundanz (gleiche/überlappende Daten) entfernen
- Im Zweifel: Modell behalten (konservativ)

{final_output_instructions}
""")

# Output-Anweisungen für schrittweise Validierung
OUTPUT_INSTRUCTIONS_INCREMENTAL_VALIDATION = """
Antworte im JSON-Format:
{{
  "hinzufügen": true/false,
  "begründung": "Deine detaillierte Begründung der Entscheidung",
  "relevanz_für_query": "hoch/mittel/niedrig",
  "neue_aspekte": "ja/nein", 
  "überschneidung_mit_validierten": "keine/teilweise/vollständig"
}}
"""

# Neuer Prompt für erste Validierungsphase (nur Instanzen-Check)
VALIDATE_MODELS_INSTANCE_NEED_PROMPT = ChatPromptTemplate.from_template("""
Erste Validierungsphase: Entscheide, ob für die Nutzeranfrage mit den vorgefilterten semantischen Modellen beantwortbar ist oder ob eine Suche nach spezifischen Instanzdaten erforderlich ist.

{optional_internal_reasoning_block}

Nutzeranfrage:
"{query}"

Verfügbare semantische Modelle:
{combined_model_triples}

KRITISCHE REGEL: Prüfe ZUERST systematisch die semantischen Modelle auf BEREITS VORHANDENE Begriffe. Nur Begriffe, die DEFINITIV NICHT im Modell stehen, gehören in "gesuchte_begriffe".

OBLIGATORISCHER 3-SCHRITT PRÜFVORGANG:

SCHRITT 1: Extrahiere alle spezifischen Begriffe aus der Nutzeranfrage
SCHRITT 2: Suche JEDEN Begriff systematisch in den semantischen Modellen:
  - Als Klasse (z.B. local:Material, local:Prozess, local:Transport)
  - Als Eigenschaft (z.B. local:hasName, local:co2Emission, local:hatGewicht)
  - Als Literal-Wert (z.B. "Stahl", "Berlin", "100kg")
  - Als Teil eines Prädikats oder Subjekts
SCHRITT 3: Nur Begriffe, die in KEINEM der obigen Formen gefunden wurden, gehören in "gesuchte_begriffe"

POSITIVE Beispiele (vollständig_möglich):
- "Zeige alle Materialien" → Material-Klasse existiert im Modell
- "CO2-Emission von Materialien" → local:co2Emission Eigenschaft existiert
- "Gewicht der Prozesse" → local:hasGewicht Eigenschaft existiert
- "Transport-Informationen" → local:Transport Klasse existiert

NEGATIVE Beispiele (NICHT in gesuchte_begriffe, da im Modell vorhanden):
- Query: "Material-Daten anzeigen" → "Material" NICHT in gesuchte_begriffe (Klasse local:Material existiert)
- Query: "CO2-Werte abrufen" → "CO2" NICHT in gesuchte_begriffe (Eigenschaft local:co2Emission existiert)
- Query: "Prozess-Informationen" → "Prozess" NICHT in gesuchte_begriffe (Klasse local:Prozess existiert)
- Query: "Transport-Details" → "Transport" NICHT in gesuchte_begriffe (Klasse local:Transport existiert)

Beispiele für filter_instanzen_nötig (nur diese gehören in gesuchte_begriffe):
- "Material mit ID 'X-7789'" → "X-7789" (spezifische ID nicht im Modell)
- "Prozess namens 'Schweißvorgang-Alpha'" → "Schweißvorgang-Alpha" (spezifischer Name nicht im Modell)
- "Transport nach 'München-Ost'" → "München-Ost" (spezifischer Ort nicht als Literal im Modell)

VALIDIERUNGSCHECK vor Antwort:
- Ist jeder Begriff in "gesuchte_begriffe" WIRKLICH nicht in den semantischen Modellen zu finden?
- Sind es wirklich nur die spezifischsten Begriffe?

Bewertungskriterien:
- "vollständig_möglich": Alle relevanten Konzepte/Eigenschaften existieren im Modell ODER Query ist generisch
- "filter_instanzen_nötig": Query enthält spezifische Begriffe, die definitiv nicht im Modell stehen
- "nicht_möglich": Grundlegende Konzepte fehlen komplett

Regeln für die Antwort:
- Deine Antwort muss IMMER ein valides JSON-Objekt sein
- Bei "filter_instanzen_nötig" MUSST du die Felder "gesuchte_begriffe" und "konzept_zuordnung" ausfüllen

Struktur der JSON-Antwort:
- "bewertung": (string) Einer von "vollständig_möglich", "filter_instanzen_nötig" oder "nicht_möglich"
- "begruendung": (string) Detaillierte Begründung mit expliziter Auflistung der im Modell gefundenen/nicht gefundenen Begriffe
- "gesuchte_begriffe": (array, nur bei "filter_instanzen_nötig") Liste der spezifischen Begriffe/Werte aus der Nutzeranfrage, die NICHT als Konzepte in den semantischen Modellen vorhanden sind und in Instanzdaten gesucht werden müssen
- "konzept_zuordnung": (object, nur bei "filter_instanzen_nötig") Zuordnung der gesuchten Begriffe zu den entsprechenden Konzepten aus dem semantischen Modell, unter denen sie als Instanzen zu finden sein könnten. Format: {{"spezifischer_begriff": "local:KonzeptName"}}

{final_output_instructions}
""")

VALIDATE_MODELS_MASTER_PROMPT = ChatPromptTemplate.from_template("""
Zweite Validierungsphase: Entscheide, ob die semantischen Modelle (mit potentiell gefundenen Instanzdaten) ausreichend sind, um die Nutzeranfrage vollständig zu beantworten.
Die Grundlage bilden eine Vielzahl einzelner Datensätze.

{optional_internal_reasoning_block}

Analysiere die folgende Nutzeranfrage und die bereitgestellten semantischen Modelle.
Nutzeranfrage:
"{query}"

Tripel der als relevant identifizierten semantischen Modelle:
{combined_model_triples}

Aufgabe:
Bewerte, ob man mit den bereitgestellten Informationen eine SPARQL-Query generieren kann, die die Nutzeranfrage beantwortet. Es gibt drei mögliche Ergebnisse:

1. vollständig_möglich: ALLE explizit genannten Parameter, Spalten und Datenelemente können eindeutig mit den Modellen abgedeckt werden.

2. teilweise_möglich: MINDESTENS ein explizit genannter Parameter fehlt und hat keinerlei Verbindung zu den Konzepten, Properties oder Literalen im semantischen modell, ABER mindestens ein anderer Parameter ist verfügbar.

3. nicht_möglich: Die Modelle sind ungeeignet, um die Anfrage sinnvoll zu beantworten, oder KEINE der explizit genannten Parameter sind verfügbar.

STRENGE BEWERTUNGSKRITERIEN:
- Jeder explizit genannte Parameter MUSS durch eine eindeutige Klasse oder Eigenschaft in den Modellen repräsentiert sein
- Bei zusammengesetzten Anfragen (z.B. "Name UND Baujahr UND Adresse") müssen ALLE Teile vollständig abgedeckt sein für "vollständig_möglich"
- Wenn auch nur EIN explizit genannter Parameter fehlt oder unklar ist → "teilweise_möglich"
- Bei unspezifischen Anfragen (z.B. "Informationen über X") prüfe, ob die GRUNDLEGENDEN Eigenschaften von X vorhanden sind

BEISPIELE für "teilweise_möglich":
- Nutzer fragt nach "Name und Baujahr von Gebäuden" → nur "Name" ist in den Modellen, "Baujahr" fehlt
- Nutzer fragt nach "Adresse und Telefonnummer" → nur "Adresse" ist verfügbar
- Nutzer fragt nach "CO2-Werte und Energieverbrauch" → nur CO2-Daten sind vorhanden
- Nutzer fragt nach "Materialien und deren Kosten" → Materialien sind da, Kostendaten fehlen

ABER:
- Bedenke, dass dies nur die semantischen Modelle sind, die die Grundlage für eine SPARQL-Query bilden. Die Instanzdaten sind in der Datenbank hinterlegt.
- SPARQL kann zählende, aggregierende oder ordnende Operationen durchführen (z.B. COUNT, SUM, ORDER BY), aber das Modell muss die nötige Struktur bieten.

Regeln für die Antwort:
- Deine Antwort muss IMMER ein valides JSON-Objekt sein.
- Bei `bewertung: "teilweise_möglich"` MUSST du das Feld `rueckfrage_an_nutzer` ausfüllen. Formuliere eine präzise Frage, die SPEZIFISCH benennt, welche Parameter verfügbar sind und welche FEHLEN, und frage, ob die Query mit den verfügbaren Daten erstellt werden soll.

Struktur der JSON-Antwort:
Deine Antwort MUSS ein JSON-Objekt sein und die folgenden Schlüssel (Keys) enthalten:
- `"bewertung"`: (string) Einer von "vollständig_möglich" oder "teilweise_möglich".
- `"begruendung"`: (string) Eine detaillierte Begründung für deine Bewertung mit konkreten fehlenden/vorhandenen Parametern.
- `"rueckfrage_an_nutzer"`: (string, optional) NUR bei "teilweise_möglich" ausfüllen. Format: "Ich kann [verfügbare Parameter] finden, aber [fehlende Parameter] sind nicht in den Daten vorhanden. Soll ich die Query nur mit den verfügbaren Informationen ([spezifische Liste]) erstellen?"

{final_output_instructions}
""")

# Ausgabeanweisung für Schritt 3 (bleibt gleich)
OUTPUT_INSTRUCTIONS_VALIDATE_MODELS = """
Antworte strikt mit "JA" oder "NEIN" in der ersten Zeile. Gib ZUSÄTZLICH eine kurze, prägnante Begründung für deine Entscheidung in einer neuen Zeile an, beginnend mit "Begründung:".
Stelle sicher, dass deine Antwort genau diesem Format folgt.

Format deiner Antwort:
JA
Begründung: [Deine Begründung hier]


"""


# Master template for Step 4: Generate SPARQL query
SPARQL_GENERATOR_PROMPT_MULTI_MODEL = ChatPromptTemplate.from_template("""
This is the fourth sub-step in the process of converting a user query into a SPARQL query.

The basis is a multitude of individual datasets. For each dataset, there is a separate semantic model that describes the underlying data structure.
Your task is to use the collected information to generate a SPARQL query that answers the user query.

{optional_internal_reasoning_block}

Step 1: You receive the user query and a list of semantic models that have been identified as relevant for the query.
Analyze the semantic models in relation to the query and first identify the sought results of the query and which variables must therefore be the output.
Step 2: Then consider whether a calculation operation (e.g., COUNT, SUM, ORDER BY) is necessary to answer the query or whether it is only about the extraction of filtered instance data. Only use calculation operations if the calculation is really necessary and there are no data points that can be extracted directly. Make sure to always convert string values to numbers if necessary for calculations (e.g., SUM). Boolean expressions are also represented as strings with "1" for True and "0" for False.
Step 3: Identify classes whose instances must be stored in a variable via a class assignment (e.g., ?variable a local:Klasse) to avoid confusion with classes that are connected to a parent class through the same property.
Step 4: Connect the target variables with the auxiliary variables by meaningfully connecting them with the properties from the given semantic models. CAUTION: DO NOT USE CLASSES AS AN OBJECT OR SUBJECT OF A TRIPLE, ONLY VARIABLES. Only use classes for type declarations of variables (i.e., ?variable a prefix:class).
Step 5: If you also need information from the RDF data that is not mapped via the mapping or the semantic model, use a FILTER clause to extract this information.

Rules:
- Caution: Only create ONE single query that answers the user query by combining information from the provided triple blocks.
- If necessary, use `UNION` to combine results from different semantic models. But only do this if it is not possible in one query because the models differ too much.
- Only use correct designations from the respective triple blocks of the associated models, both for classes, predicates, and objects.
- Do not shorten the query to keep it clear and error-free.
- Use the correct prefixes and make sure to always name classes correctly and filter by classes if necessary, e.g., always ?XY a local:Fahrradabstellanlage, as otherwise there may be too many entries.
- All actual values are stored as the type depicted in the semantic model (e.g. xsd:string -> string) and may need to be explicitly converted to numbers, for example when SUM is used. Boolean expressions are also represented as strings with "1" for True and "0" for False.
- IMPORTANT: For numeric types (xsd:decimal, xsd:integer, xsd:double, xsd:float), write values as plain numbers WITHOUT quotes, e.g., use `32.0` or `32` instead of `"32"^^xsd:decimal`. For strings use quotes with type annotation, e.g., `"value"^^xsd:string`.
- IMPORTANT: If a predicate can have multiple target objects, ALWAYS filter by type as specified in the semantic model.
- IMPORTANT: Only use classes as a type declaration of a variable (i.e. ?variable a prefix:class). In all other cases Subject and Object of the triple need to be variables (i.e. ?variable1 prefix:predicate ?variable2).
{optional_example_instances_block}

- The following prefixes are predefined and are considered present. They serve only as assistance. You do not need to specify them in the query:
PREFIX owl:    <http://www.w3.org/2002/07/owl#>
PREFIX plasma: <http://plasma.uni-wuppertal.de/ontology#>
PREFIX plcm:   <http://plasma.uni-wuppertal.de/cm#>
PREFIX plsm:   <http://plasma.uni-wuppertal.de/sm/>
PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:    <http://www.w3.org/2001/XMLSchema#>
PREFIX local:  <https://local.ontology#>
PREFIX schema: <https://schema.org/>
PREFIX hdpe:   <http://example.org/hdpe-pipe-ontology#>

{optional_few_shot_examples}

Now create ONE SINGLE valid SPARQL query based on the following information to answer the user query.
User query:
"{query}"
For the query, the following semantic model types were identified as relevant and the corresponding models were selected. Each block contains the triples for a specific model:
{model_info_blocks}
Notes from the model check (information about what each model can cover or not):
{model_check_hints}

{final_output_instructions}
""")

# Output instruction for Step 4
OUTPUT_INSTRUCTIONS_GENERATE_SPARQL = """
Now provide ONLY the complete SPARQL query starting from SELECT - no explanation and no surrounding quotation marks or Markdown code blocks."""





###AGENTIC REASONER PROMPTS###




# Prompt Agentic Reasoner: SCHRITT 1: Modelltypen identifizieren
# IDENTIFY_REQUIRED_MODEL_TYPES_AGENTIC_REASONER_PROMPT = ChatPromptTemplate.from_template("""
# Du sollst ein Zwischenergebnis im Rahmen eines Prozesses analysieren, bei dem natürlichsprachige Anfragen in SPARQL Queries umgewandelt werden.



# Dieser Schritt diente dazu, aus der Nutzeranfrage die notwendigen semantischen Modelltypen zu identifizieren, die für die spätere Query-Erstellung benötigt werden.

# Die ursprüngliche Nutzeranfrage lautete:
# "{query}"

# Die im vorherigen Schritt identifizierten Modelltypen (das zu prüfende Ergebnis) sind:
# {identified_model_types}

# Der Kontext für diese Identifikation war folgender Prompt:
# Folgender Prompt wurde für die ursprüngliche Identifikation der Modelltypen verwendet:
# [Anfang Original Prompt]
# Das hier ist der erste Teilschritt in einem Prozess, bei dem eine natürlichsprachige Nutzeranfrage in eine SPARQL-Query umgewandelt wird.

# Die Grundlage bilden eine Vielzahl einzelner Datensätze. Zu jedem Datensatz existiert ein eigenes, separates semantisches Modell,das die zugrunde liegende Datenstruktur beschreibt.

# Deine Aufgabe ist es, die semantischen Modelle nennen, die benötigt werden, um die folgende Nutzeranfrage vollständig beantworten zu können:

# "{query}"

# Beachte dabei:
# - Gib nur die Modelle an, die wirklich notwendig sind, um die Anfrage zu beantworten.
# - Wenn sich die Anfrage auf mehrere Themen oder Städte bezieht, müssen entsprechend 
#   mehrere Modelle genannt werden - jeweils eins pro Konzept und Stadt.
# - Verallgemeinerungen sind nicht ausreichend. Die Modelle müssen so benannt sein, dass eindeutig 
#   ist, auf welchen Datensatz sie sich beziehen.
# - Verwende so wenige Modelle wie möglich, aber so viele wie nötig.

# Gib deine Antwort ausschließlich im folgenden JSON-Format aus - ohne Begrüßung, Erklärung oder 
# sonstigen Text:

# {{
#   "required_models": [
#     "Erstes benötigtes semantisches Modell",
#     "Zweites benötigtes semantisches Modell (nur falls nötig)"
#   ]
# }}
# ")
# [Ende Original Prompt]

# Deine Aufgabe ist es, die oben als "{identified_model_types}" dargestellte Liste von Modellen sorgfältig auf Basis der ursprünglichen Nutzeranfrage ("{query}") und des Kontexts des ursprünglichen Prompts zu prüfen. 
# Bestätige, ob mit diesem Ergebnis weitergearbeitet werden kann.

# Bitte gib deine Antwort im folgenden JSON-Format aus:
# {{
#   "assessment": "korrekt" / "fehlerhaft" / "teilweise korrekt",
#   "justification": "Eine detaillierte Begründung deiner Bewertung. Wenn die Auswahl 'korrekt' ist, bestätige dies kurz. Wenn 'teilweise korrekt' oder 'fehlerhaft', erkläre präzise, warum eine Änderung *zwingend notwendig* ist (z.B. ein offensichtlicher Fehler, ein kritisch fehlendes Modell) oder warum eine vorgeschlagene Änderung eine *deutliche und unumgängliche* Verbesserung darstellt.",
#   "corrected_model_types": [
#     "Korrigierter erster Modelltyp (falls nötig)",
#     "Zweiter Modelltyp (falls nötig)"
#   ]
# }}

# Wichtige Hinweise für deine Antwort:
# - Die `assessment` muss einer der drei Werte sein: "korrekt", "fehlerhaft", "teilweise korrekt".
# - Die `justification` muss immer ausgefüllt sein.
# - Die `corrected_model_types` Liste soll nur dann von den `identified_model_types` abweichen, wenn eine Korrektur *zwingend notwendig* ist (offensichtlicher Fehler, kritisch fehlendes Modell) oder eine *deutliche und unumgängliche* Verbesserung darstellt. Ansonsten soll sie die `identified_model_types` unverändert (also den Wert von {identified_model_types}) enthalten.
# - Gib KEINEN Text außerhalb des JSON-Objekts aus.
# """)

#Prompt Agentic Reasoner: SCHRITT 2: Retrieval-Begriff bestimmen
# DETERMINE_RETRIEVAL_CONCEPT_AGENTIC_REASONER_PROMPT = ChatPromptTemplate.from_template("""
# Du sollst ein Zwischenergebnis im Rahmen eines Prozesses analysieren, bei dem natürlichsprachige Anfragen in SPARQL Queries umgewandelt werden.

# Dieser Schritt diente dazu, aus einer Modellbeschreibung einen passenden Retrieval-Suchbegriff zu generieren, der zur späteren Indexsuche verwendet wird.

# Folgender Prompt wurde für die ursprüngliche Erzeugung des Begriffs verwendet:
# ---
# [Original Retrieval-Begriff-Generierungs-Prompt]
# Das hier ist der zweite Teilschritt im Prozess eine Nutzeranfrage in eine SPARQL-Query umzuwandeln.
# Die Grundlage bilden eine Vielzahl einzelner Datensätze. Zu jedem Datensatz existiert ein eigenes, separates semantisches Modell,das die zugrunde liegende Datenstruktur beschreibt.

# Deine Aufgabe ist es, einen prägnanten Schlüsselbegriff/Konzept aus der gegebenen Modellbeschreibung zu extrahieren, der für die
# Suche bzw. das Retrieval benutzt wird. Der Index basiert auf den Tripeln der semantischen Modellen.
# Mache aus Mehrzahl Einzahl, falls zutreffend.
# Wichtig: Der Suchbegriff darf keine Sonderzeichen, keine Umlaute (ä, ö, ü) und KEIN scharfes S ('ß') enthalten. Ersetze Umlaute (ae, oe, ue) und ß (ss).
# Bedenke, dass der Suchbegriff nicht zu allgemein sein sollte und ermöglichen sollte das gesuchte semantische Modell herauszufiltern.
# Bedenke, dass es Datensätze zum gleichen Thema aus verschiedenen Städten gibt.
# Antworte NUR mit diesem einen Schlüsselbegriff/Konzept.
# Modellbeschreibung: {model_type_description}


# [Ende Original Prompt]

# Das vom vorherigen Schritt erzeugte Zwischenergebnis lautet:
# "{retrieval_concept}"

# Deine Aufgabe ist es, den oben als "{retrieval_concept}" dargestellten Suchbegriff sorgfältig zu prüfen.\n
# Der Suchbegriff ist ausschließlich für das semantische Modell gedacht, das durch die Modellbeschreibung "{model_type_description}" repräsentiert wird.\n
# Beurteile, ob "{retrieval_concept}" ein optimaler Suchbegriff ist, um Informationen *spezifisch zu dieser Modellbeschreibung* ("_model_type_description_") zu finden.\n

# WICHTIG: Der Suchbegriff soll sich NUR auf die gegebene "{model_type_description}" beziehen.\n
# Das Hinzufügen von themenfremden Begriffen zum Suchbegriff für dieses spezifische Modell ist **keine** Verbesserung.\n

# Schlage nur dann eine Korrektur vor, wenn der ursprüngliche Begriff unter Berücksichtigung dieses strikten Fokus auf "{model_type_description}":\na) offensichtlich ungeeignet ist.

# Bitte gib deine Antwort im folgenden JSON-Format aus:
# {{
#   "assessment": "korrekt" / "fehlerhaft" / "teilweise korrekt",
#   "justification": "Eine detaillierte Begründung deiner Bewertung, fokussiert auf die Eignung des Suchbegriffs für die spezifische '{model_type_description}'. Wenn der Begriff 'korrekt' ist, bestätige dies kurz. Wenn 'teilweise korrekt' oder 'fehlerhaft', erkläre präzise, warum eine Änderung *zwingend notwendig* ist (z.B. ungeeignet für '{model_type_description}', führt zu falschen Ergebnissen für dieses Modell) oder warum eine vorgeschlagene Änderung eine *deutliche und unumgängliche* Verbesserung für die Indexsuche *spezifisch für '{model_type_description}'* darstellt.",
#   "corrected_concept": "Der korrigierte Suchbegriff (falls eine Korrektur gemäß den oben genannten strikten Kriterien notwendig ist). Der korrigierte Begriff muss sich ebenfalls ausschließlich auf '{model_type_description}' beziehen. Ansonsten ein leerer String, um den ursprünglichen Begriff beizubehalten."
# }}

# Wichtige Hinweise für deine Antwort:
# - Die `assessment` muss einer der drei Werte sein: "korrekt", "fehlerhaft", "teilweise korrekt".
# - Die `justification` muss immer ausgefüllt sein.
# - Der `corrected_concept` muss nur dann einen neuen Wert enthalten, wenn eine Korrektur *zwingend notwendig* ist oder eine *deutliche und unumgängliche* Verbesserung darstellt. Ansonsten soll er leer bleiben, was bedeutet, dass der ursprüngliche Begriff verwendet wird.
# - Gib KEINEN Text außerhalb des JSON-Objekts aus.
# """)

#Prompt Agentic Reasoner: SCHRITT 3: Modellprüfung
LLM_COMBINED_MODEL_VALIDATION_AGENTIC_REASONER_PROMPT = ChatPromptTemplate.from_template("""
Du sollst ein Zwischenergebnis im Rahmen eines Prozesses analysieren, bei dem natürlichsprachige Anfragen in SPARQL Queries umgewandelt werden.

Dieser Schritt diente dazu zu prüfen, ob die Kombination der bereitgestellten semantischen Modelle ausreicht, um die Nutzeranfrage vollständig beantworten zu können.

Folgender Prompt wurde für die ursprüngliche Validierung verwendet:
---
[Anfang Original Prompt]
Das hier ist ein Teilschritt im Prozess eine Nutzeranfrage in eine SPARQL-Query umzuwandeln.
Die Grundlage bilden eine Vielzahl einzelner Datensätze. Zu jedem Datensatz existiert ein eigenes, separates semantisches Modell,das die zugrunde liegende Datenstruktur beschreibt.
Analysiere die folgende Nutzeranfrage und die bereitgestellten semantischen Modelle.
Nutzeranfrage:
"{query}"

Tripel der als relevant identifizierten semantischen Modelle:
{combined_model_triples}

Aufgabe:
Bewerte, ob man mit Hilfe des Semantischen Modells, bzw. der Kombination der Semantischen Modelle
in der Lage ist, eine SPARQL Query zu generieren, die die Nutzeranfrage beantwortet.
Antworte strikt mit "JA" oder "NEIN" in der ersten Zeile. Gib ZUSÄTZLICH eine kurze, prägnante Begründung für deine Entscheidung in einer neuen Zeile an, beginnend mit "Begründung:".
Bedenke, dass dies nur die semantischen Modelle sind, die die Grundlage für eine SPARQL-Query bilden.
Also entsprechend keine direkten Instanzdaten sind, diese sind aber in der Datenbank hinterlegt.

Format deiner Antwort:
JA
Begründung: [Deine Begründung hier]

Beispiel 1:
JA
Begründung: Die Modelle decken alle Aspekte der Anfrage ab, einschließlich X, Y und Z.

Beispiel 2:
NEIN
Begründung: Wichtige Informationen zu Aspekt A fehlen in den bereitgestellten Modellen. Es wird ein Modell zu Thema A benötigt.

Stelle sicher, dass deine Antwort genau diesem Format folgt.
""
[Ende Original Prompt]

Die ursprüngliche Validierungsentscheidung des vorherigen Schritts lautete:
Entscheidung: "{original_validation_decision}"
Begründung: "{original_validation_justification}"

Deine Aufgabe ist es, die oben genannte ursprüngliche Validierungsentscheidung ("{original_validation_decision}") und deren Begründung ("{original_validation_justification}") zu prüfen. Bestätige, ob die Schlussfolgerung der vorherigen Stufe (ob die Modelle zur Anfrage passen) haltbar ist. 
Greife nur dann korrigierend ein, wenn die ursprüngliche Bewertung offensichtlich falsch ist, kritische Aspekte
der Nutzeranfrage durch die Modelle klar nicht abgedeckt sind oder die ursprüngliche Begründung irreführend ist.

Bitte gib deine Antwort im folgenden JSON-Format aus:
{{
  "assessment": "korrekt" / "fehlerhaft" / "teilweise korrekt",
  "justification": "Eine kurze Begründung deiner Bewertung. Wenn die ursprüngliche Bewertung 'korrekt' ist, bestätige dies kurz. Wenn du sie als 'teilweise korrekt' oder 'fehlerhaft' einstufst, erkläre präzise, warum eine Änderung der ursprünglichen Bewertung *zwingend notwendig* ist (z.B. offensichtlicher Fehler in der Logik, kritische Aspekte der Nutzeranfrage klar nicht abgedeckt).",
  "missing_model_info": [
    "Falls erforderlich: Beschreibung fehlender Modellinhalte, die für eine vollständige Beantwortung der Nutzeranfrage *eindeutig und kritisch* benötigt werden",
    "Sonst: leere Liste"
  ]
}}

Wichtige Hinweise für deine Antwort:
- Die `assessment` muss einer der drei Werte sein: "korrekt", "fehlerhaft", "teilweise korrekt".
- Die `justification` muss immer enthalten sein.
- Die `missing_model_info` muss eine Liste sein – leer, wenn alles korrekt abgedeckt ist.
- Gib KEINEN Text außerhalb des JSON-Objekts aus.
""")


# Prompt Agentic Reasoner: SCHRITT 4: SPARQL Agentic Reasoner
SPARQL_AGENTIC_REASONER_PROMPT = ChatPromptTemplate.from_template("""
Du sollst eine erzeugte SPARQL-Query analysieren.
Die Query entstand im Rahmen eines Prozesses aus mehreren Schritten zur Umwandlung von natürlichsprachigen Anfragen in SPARQL Queries.
Folgender Prompt wurde für die ursprüngliche Erstellung der SPARQL-Query verwendet:
---
[Original SPARQL Generation Prompt]
Das hier ist der vierte Teilschritt im Prozess eine Nutzeranfrage in eine SPARQL-Query umzuwandeln.
Die Grundlage bilden eine Vielzahl einzelner Datensätze. Zu jedem Datensatz existiert ein eigenes, separates semantisches Modell,das die zugrunde liegende Datenstruktur beschreibt.
Erstelle EINE EINZIGE gültige SPARQL-Query auf Basis der folgenden Informationen, um die Nutzeranfrage zu beantworten.
Nutzeranfrage:
"{query}"
Für die Anfrage wurden folgende semantische Modelltypen als relevant identifiziert und die entsprechenden Modelle ausgewählt. Jeder Block enthält die Tripel für ein spezifisches Modell:
{model_info_blocks}
Hinweise aus der Modellprüfung (Informationen darüber, was jedes Modell abdecken kann oder nicht):
{model_check_hints}
Regeln:
- Ziel ist es, EINE Query zu erstellen, die die Nutzeranfrage beantwortet, indem du Informationen aus den bereitgestellten Tripel-Blöcken kombinierst.
- Wenn nötig, verwende `UNION`, um Ergebnisse aus verschiedenen Teilen der WHERE-Klausel zu kombinieren.
- Verwende, wenn nötig SELECT DISTINCT, um Duplikate zu vermeiden und achte darauf die korrekten Variablen mit SELECT zu wählen.
- Verwende nur korrekte Bezeichnungen aus den jeweiligen Tripel-Blöcken der zugehörigen Modelle, sowohl bei den Klassen, als auch den Prädikaten und Objekten.
- Verkürze die Query nicht, um sie übersichtlich und fehlerfrei zu halten.
- Nutze die richtigen Prefixes und achte darauf Klassen immer richtig zu benennen und wenn nötig nach den Klassen filtern, also immer z.B. ?item a local:SomeClass , da es sonst zu zuvielen Einträgen kommen kann.
- WICHTIG: Verwende NIEMALS direkt Klassennamen als Subjekt in Tripeln. Definiere IMMER eine Variable (z.B. ?entity) und typisiere sie: ?entity a local:ClassName .
- Beachte die Struktur der Daten, die das semantische Modell vorgibt und gehe bei der Abfrage entsprechend tief genug um den gesuchten Wert abzufragen.
- Wenn die Anfrage Instanzen einer Entität abfragt (also konkrete Objekte und nicht nur aggregierte Werte), MÜSSEN diese Instanzen-URIs immer in der ersten Spalte der Ergebnistabelle stehen. Bei reinen Zählabfragen (z.B. 'Anzahl der X in Y') oder wenn nur Eigenschaften/Werte gefordert sind (z.B. 'Straßennamen'), entfällt diese Regel.
- Achte darauf, was WIRKLICH gesucht wird und verwende die korrekten Klassen und Prädikate aus den Tripel-Blöcken.
- WICHTIG: Wenn ein Prädikat mehrere Zielobjekte haben kann, IMMER über den Typ filtern, wie im semantischen Modell vorgegeben. 
- WICHTIG: Auch wenn das semantische Modell etwas anderes vorgibt: Um den eigentlichen Wert (z.B. eine Zahl, ein Text, ein Datum) von einer Entität zu erhalten, die diesen Wert repräsentiert, musst du IMMER das Prädikat plasma:hasValue verwenden. Sonst erhälst du im Ergebnis nur das Objekt, nicht den gesuchten Wert. Du musst eigentlich für alles wonach gefragt wird, am Ende plasma:hasValue verwenden.
- Alle tatsächlichen Werte sind als Strings hinterlegt und müssen ggf. explizit zu Zahlen konvertiert werden, wenn zum Beispiel SUM verwendet wird. Auch Boolesche Ausdrücke sind als String mit "1" für True und "0" für False repräsentiert und müssen über plasma:hasValue abgefragt werden. 

- Folgende Präfixe sind vorgegeben und werden als vorhanden angesehen. Sie dienen nur zur Hilfestellung. Du musst sie in Query NICHT angeben:
PREFIX owl:    <http://www.w3.org/2002/07/owl#>
PREFIX plasma: <http://plasma.uni-wuppertal.de/ontology#>
PREFIX plcm:   <http://plasma.uni-wuppertal.de/cm#>
PREFIX plsm:   <http://plasma.uni-wuppertal.de/sm/>
PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:    <http://www.w3.org/2001/XMLSchema#>
PREFIX local:  <https://local.ontology#>
PREFIX schema: <https://schema.org/>
PREFIX hdpe:   <http://example.org/hdpe-pipe-ontology#>
Gib nun NUR die vollständige SPARQL-Query ab SELECT aus - keine Erklärung und keine umschließenden Anführungszeichen oder Markdown-Codeblöcke.
---
[Ende Original SPARQL Generation Prompt]

Die vom vorherigen Schritt generierte SPARQL-Query lautet:
```sparql
{generated_sparql_query}
Deine Aufgabe ist es, diese Query auf Basis der Nutzeranfrage, den gegebenen Hinweisen zur Erstellung der Query und den bereitgestellten semantischen Modellen zu analysieren und zu bewerten.
Analysiere ob alle Hinweise zur Erstellung der Query beachtet wurden, ob Fehler gemacht wurden bei der Auswahl der Klassen, Objekte oder Prädikate und ob die Query die Anfrage korrekt beantwortet.
Bitte gib deine Antwort im folgenden JSON-Format aus:
{{
"assessment": "korrekt" / "fehlerhaft" / "teilweise korrekt",
"justification": "Eine detaillierte Begründung deiner Bewertung. Wenn die ursprüngliche Bewertung 'korrekt' ist, bestätige dies kurz. Wenn du sie als 'teilweise korrekt' oder 'fehlerhaft' einstufst, erkläre präzise, warum eine Änderung der ursprünglichen Bewertung zwingend notwendig ist (z.B. offensichtlicher Fehler in der Logik, kritische Aspekte der Nutzeranfrage klar nicht abgedeckt).",
"corrected_query": "Die korrigierte SPARQL-Query, falls 'assessment' nicht 'korrekt' ist. Wenn 'assessment' 'korrekt' ist, wiederhole hier die ursprüngliche Query oder gib einen leeren String an."
}}
Wichtige Hinweise für deine Antwort:
Die assessment muss einer der drei Werte sein: "korrekt", "fehlerhaft", "teilweise korrekt".
Die justification muss immer ausgefüllt sein und deine Entscheidung klar begründen.
Die corrected_query muss eine vollständige, gültige SPARQL-Query sein, wenn eine Korrektur nötig ist. Sie muss alle notwendigen Prefixes enthalten.
Stelle sicher, dass deine gesamte Ausgabe ein valides JSON-Objekt ist. Gib KEINEN Text außerhalb des JSON-Objekts aus.
""")



LLM_SPARQL_QUERY_EDIT_EVALUATION_PROMPT_STEP_1 = ChatPromptTemplate.from_template("""
Du bist ein SPARQL-Reparatursystem innerhalb eines Evaluationsprozesses für ein System das natürlichsprachliche Anfragen in SPARQL-Queries umwandelt.

Deine Aufgabe ist es, eine SPARQL-Query, die von einem LLM generiert wurde, so zu analysieren, korrigieren und Korrekturen zu beschreiben, dass sie dieselbe Funktion erfüllt wie eine korrekt funktionierende Groundtruth-Query, also dasselbe Ergebnis liefert.
Variablennamen dürfen abweichen, solange die zugrundeliegende Funktionsweise dieselbe ist.

Dein Ziel ist es NICHT, die LLM-Query komplett inhaltlich anzugleichen, sondern die Groundtruth Query als Unterstützung nehmen, 
die erzeugte so zu korrigieren, dass sie das gewünschte Ergebnis liefert.
Du sollst also anhand er Groundtruth-Query, den Tripeln aus den Semantischen Modellen und den Hinweisen, verstehen, wie exakt
die Nutzeranfrage beantwortet werden soll. 

Folgende Hinweise bzw. Regeln gab es bei der ursprünglichen SPARQL Generierung:
Regeln:
- Ziel war es, EINE Query zu erstellen, die die Nutzeranfrage beantwortet, indem du Informationen aus den bereitgestellten Tripel-Blöcken kombinierst.
- Wenn nötig, verwende `UNION`, um Ergebnisse aus verschiedenen Teilen der WHERE-Klausel zu kombinieren.
- Verwende SELECT DISTINCT, um Duplikate zu vermeiden und achte darauf die korrekten Variablen mit SELECT zu wählen.
- Verwende nur korrekte Bezeichnungen aus den jeweiligen Tripel-Blöcken der zugehörigen Modelle, sowohl bei den Klassen, als auch den Prädikaten und Objekten.
- Verkürze die Query nicht, um sie übersichtlich und fehlerfrei zu halten.
- Nutze die richtigen Prefixes und achte darauf Klassen immer richtig zu benennen und wenn nötig nach den Klassen filtern, also immer z.B. ?XY a local:Haus , da es sonst zu zuvielen Einträgen kommen kann.
- Beachte die Struktur der Daten, die das semantische Modell vorgibt und gehe bei der Abfrage entsprechend tief genug um den gesuchten Wert abzufragen.
- Achte darauf, was WIRKLICH gesucht wird und verwende die korrekten Klassen und Prädikate aus den Tripel-Blöcken.
- WICHTIG: Wenn ein Prädikat mehrere Zielobjekte haben kann, IMMER über den Typ filtern, wie im semantischen Modell vorgegeben. Bei der Filterung nach Städten nutze das Tripel local:located_in "Stadt"^^xsd:string .
- WICHTIG: Um den eigentlichen Wert (z.B. eine Zahl, ein Text, ein Datum) von einer Entität zu erhalten, die diesen Wert repräsentiert, musst du IMMER das Prädikat plasma:hasValue verwenden. Sonst erhälst du im Ergebnis nur das Objekt, nicht den gesuchten Wert. Du musst eigentlich für alles wonach gefragt wird, am Ende plasma:hasValue verwenden.
- Alle tatsächlichen Werte sind als Strings hinterlegt und müssen ggf. explizit zu Zahlen konvertiert werden, wenn zum Beispiel SUM verwendet wird.

Vorgehen jetzt:
1. Lies dir die Groundtruth-Query sorgfältig durch.
2. Erkläre in eigenen Worten, welche Funktionsweise sie erfüllt Was tut die Query? Welche Daten filtert oder extrahiert sie?.
3. Vergleiche die Funktionsweise der LLM-Query damit: Welche Informationen fehlen oder sind falsch umgesetzt?
4. Finde die Fehler in der erzeugten Query und überlege wie man diese korrigiert.
5. Ermittle dann die minimal notwendigen und klar abgrenzbaren Änderungsschritte, damit die LLM-Query dieselbe Funktionsweise erfüllt wie die Groundtruth-Query. 
   Fokussiere dich auf einzelne, logische Korrekturen. 
6. Notiere die Änderungen in Form einer Liste von klaren, präzisen Schritten. 
7. Liste wirklich ALLE Änderungen auf, die die Funktionsweise ändern bzw. das erzeugte Ergebnis inhaltlich beeinflussen. Nenne aber ALLE Änderungen die dem entsprechen.
8. Erstelle auf Basis der gesammelten Änderungen eine korrigierte SPARQL-Query.

Beispiele für gültige Schritte:
- "Variable ?Name durch ?NameWert ersetzen in SELECT-Struktur"
- "Fehlendes Triple `?Adresse a local:Adresse` hinzufügen"
- "Falsches Prädikat `local:stadtname` durch `local:located_in` ersetzen"
- "Fehlender FILTER `FILTER(xsd:integer(?wert) > 4)` ergänzen"
- "COUNT-Struktur `COUNT(?station)` mit `AS ?anzahl` hinzufügen"
- "BIND-Ausdruck `BIND(xsd:integer(?str) AS ?int)` hinzufügen"
- "UNION-Struktur zwischen zwei Blöcken ergänzen"

Wichtig:
- Gib NUR Schritte zurück, die funktional notwendig sind, ignoriere kosmetische Unterschiede wie zb. Variablennamen.
- Du darfst Tripel, Filter oder Operatoren ergänzen, ändern oder entfernen solange das Ergebnis stimmt.
- Formuliere die Schritte so, dass sie als Grundlage für eine anschließende Bewertung verwendet werden können. Orientiere dich an den Beispielen.
- Die Groundtruth Query dient nur als Hilfestellung und als Orientierung für die Funktionsweise, du musst keine Variablennamen an Groundtruth anpassen, wenn es nicht erfordert ist.
- Bei der Betrachtung des Ergebnisses spielen Datentypen keine Rolle, es muss also nicht zwingend gebindet werden.
- Übernehme auch keine Kommentare aus der Groudntruth Query

WICHTIGES AUSGABEFORMAT:
Deine gesamte Antwort muss ein einziges, valides JSON-Objekt sein. Deine Antwort darf absolut keinen Text, keine Kommentare und keine Markdown-Codeblöcke wie ```json außerhalb des JSON-Objekts enthalten. Beginne direkt mit `{{` und ende mit `}}`.

Struktur des JSON-Objekts:
{{
  "groundtruth_analysis": "[Hier dein Absatz, der die Funktion der Groundtruth-Query erklärt]",
  "llm_query_deviation": "[Hier dein Absatz, der die Abweichungen der LLM-Query beschreibt]",
  "changes": [
    "Beschreibung der funktional notwendigen Änderung 1",
    "Beschreibung Änderung 2"
  ],
  "corrected_query": "SELECT ... WHERE {{{{ ... }}}}"
}}

BEISPIEL FÜR EINGABE UND AUSGABE:
Nutzeranfrage: "Ich suche alle Schwebebahnhaltestellen die 'Straße' oder 'Strasse' enthalten. Einfach die Namen untereinander."
Semantische Modelltripel: local:Schwebebahnstation a local:Haltestelle ; local:hat ?Bezeichnung ; local:located_in "Wuppertal"^^xsd:string .
Groundtruth-Query zum Vergleich: SELECT DISTINCT ?Name WHERE {{{{ ?station a local:Schwebebahnstation ; local:hat ?Bezeichnung . ?Bezeichnung plasma:hasValue ?RoherWert . BIND(LCASE(?RoherWert) AS ?NameLower) FILTER (CONTAINS(?NameLower, \\"straße\\") || CONTAINS(?NameLower, \\"strasse\\")) BIND(?RoherWert AS ?Name) }}}}
LLM-Query: SELECT ?Bezeichnung WHERE {{{{ ?station a local:Schwebebahnstation . ?station local:hat ?Bezeichnung . FILTER (CONTAINS(?Bezeichnung, \\"Straße\\") || CONTAINS(?Bezeichnung, \\"Strasse\\")) }}}}

BEISPIEL-ANTWORT (deine Ausgabe muss exakt diesem JSON-Format folgen):
{{
  "groundtruth_analysis": "Die Query findet alle Schwebebahnhaltestellen, deren Bezeichnungs-String (nach Abruf via plasma:hasValue) \\"straße\\" oder \\"strasse\\" in beliebiger Groß-/Kleinschreibung enthält. Sie gibt die originalen String-Werte der Bezeichnungen aus.",
  "llm_query_deviation": "Die LLM-Query filtert direkt auf die Entität ?Bezeichnung (anstatt auf ihren String-Wert) und führt eine case-sensitive Suche durch. Zudem wird die Entität selbst (nicht der String-Wert) ausgegeben.",
  "changes": [
    "Fehlendes Triple `?Bezeichnung plasma:hasValue ?RoherWert` hinzufügen",
    "FILTER direkt auf Entität durch FILTER auf String-Wert ersetzen",
    "Case-insensitive Suche durch LCASE und Kleinbuchstaben-Vergleich implementieren",
    "Ausgabe des originalen String-Werts (?RoherWert als ?Name) statt der Entität"
  ],
  "corrected_query": "SELECT DISTINCT ?Name\\nWHERE {{{{ \\n  ?station a local:Schwebebahnstation ;\\n        local:hat ?Bezeichnung .\\n  ?Bezeichnung plasma:hasValue ?RoherWert .\\n  BIND(LCASE(?RoherWert) AS ?NameLower)\\n  FILTER (CONTAINS(?NameLower, \\"straße\\") || CONTAINS(?NameLower, \\"strasse\\"))\\n  BIND(?RoherWert AS ?Name)\\n}}}}"
}}

Verfahre nun wie vorgegeben.
Hier sind nochmal die ursprünglichen Hinweise zur SPARQL-Query Generation:
Regeln:
- Ziel war es, EINE Query zu erstellen, die die Nutzeranfrage beantwortet, indem du Informationen aus den bereitgestellten Tripel-Blöcken kombinierst.
- Wenn nötig, verwende `UNION`, um Ergebnisse aus verschiedenen Teilen der WHERE-Klausel zu kombinieren.
- Verwende SELECT DISTINCT, um Duplikate zu vermeiden und achte darauf die korrekten Variablen mit SELECT zu wählen.
- Verwende nur korrekte Bezeichnungen aus den jeweiligen Tripel-Blöcken der zugehörigen Modelle, sowohl bei den Klassen, als auch den Prädikaten und Objekten.
- Verkürze die Query nicht, um sie übersichtlich und fehlerfrei zu halten.
- Nutze die richtigen Prefixes und achte darauf Klassen immer richtig zu benennen und wenn nötig nach den Klassen filtern, also immer z.B. ?XY a local:Haus , da es sonst zu zuvielen Einträgen kommen kann.
- Achte darauf, was WIRKLICH gesucht wird und verwende die korrekten Klassen und Prädikate aus den Tripel-Blöcken.
- WICHTIG: Wenn ein Prädikat mehrere Zielobjekte haben kann, IMMER über den Typ filtern, wie im semantischen Modell vorgegeben. Bei der Filterung nach Städten nutze das Tripel local:located_in "Stadt"^^xsd:string .
- Alle tatsächlichen Werte sind als Strings hinterlegt und müssen ggf. explizit zu Zahlen konvertiert werden, wenn zum Beispiel SUM verwendet wird.
- WICHTIG: Um den eigentlichen Wert (z.B. eine Zahl, ein Text, ein Datum) von einer Entität zu erhalten, die diesen Wert repräsentiert, musst du IMMER das Prädikat plasma:hasValue verwenden. Sonst erhälst du im Ergebnis nur das Objekt, nicht den gesuchten Wert.

Hier die gesammelten und erzeugten Elemente
Wichtig bleibt, alle Änderungen aufzulisten. 
Vorgehen jetzt:
1. Lies dir die gegebenen Elemente sorgfältig durch.
2. Erkläre in eigenen Worten, welche Funktionsweise sie erfüllt Was tut die Query? Welche Daten filtert oder extrahiert sie?.
3. Vergleiche die Funktionsweise der LLM-Query damit: Welche Informationen fehlen oder sind falsch umgesetzt?
4. Ermittle dann die minimal notwendigen und klar abgrenzbaren Änderungsschritte, damit die LLM-Query dasselbe Ergebnis erzeugt wie die Groundtruth Query. Ausgegebene Variablennamen sind nicht relevant. 
5. Notiere die Änderungen in Form einer Liste von klaren, präzisen Schritten. Die Begründungen für Änderungen sollten nur auf Basis der Query und nicht auf der Groundtruth Query basieren.
6. Liste wirklich nur die Änderungen auf, die die Funktionsweise ändern bzw. das erzeugte Ergebnis inhaltlich beeinflussen. Nenne aber ALLE Änderungen die dem entsprechen.
7. Erstelle auf Basis der gesammelten Änderungen eine korrigierte SPARQL-Query. 

Nutzeranfrage:
{query}

Semantische Modelltripel:
{model_info_blocks}

Modellhinweise:
{model_check_hints}

Groundtruth-Query zum Vergleich:
{groundtruth_sparql_query}

LLM-Query:
{generated_sparql_query}

Ergebnis-Ausschnitte (um den Unterschied zu verdeutlichen):

Erwartetes Ergebnis (aus Groundtruth-Query, mit LIMIT 5):
Generated json
{groundtruth_query_result_snippet}

Tatsächliches Ergebnis (aus falscher LLM-Query, mit LIMIT 5):
Generated json
{generated_query_result_snippet}

""")



# Prompt für SPARQL Syntax-Fehler Korrektur
SPARQL_SYNTAX_ERROR_CORRECTION_PROMPT = ChatPromptTemplate.from_template("""
Du bist ein SPARQL-Experte. Eine SPARQL-Query hat einen Syntax-Fehler und muss korrigiert werden.

{optional_internal_reasoning_block}

BENUTZERANFRAGE:
"{user_query}"

SEMANTISCHE MODELLE:
{semantic_models_content}

FEHLGESCHLAGENE SPARQL-QUERY:
{failed_query}

SYNTAX-FEHLER-DETAILS:
{syntax_error_details}

Deine Aufgabe:
Analysiere den Syntax-Fehler und korrigiere die SPARQL-Query. Achte besonders auf:
- Korrekte PREFIX-Deklarationen (werden automatisch hinzugefügt)
- Gültige SPARQL-Syntax (Klammern, Semikolons, etc.)
- Richtige Verwendung der semantischen Modelle
- Korrekte Prädikat- und Klassennamen aus den Modellen

Wichtige Regeln für die Korrektur:
- Verwende nur korrekte Bezeichnungen aus den semantischen Modellen
- Für Mobilitätsdatensätze: Verwende IMMER plasma:hasValue um den tatsächlichen Wert zu erhalten
- Nutze korrekte Klassennamen mit Variablen: ?entity a local:ClassName
- Beachte die Struktur der Daten aus den semantischen Modellen
- WICHTIG: Verwende NIEMALS direkt Klassennamen als Subjekt in Tripeln

Folgende Präfixe sind vorgegeben und werden automatisch hinzugefügt - du musst sie NICHT in der Query angeben:
PREFIX owl:    <http://www.w3.org/2002/07/owl#>
PREFIX plasma: <http://plasma.uni-wuppertal.de/ontology#>
PREFIX plcm:   <http://plasma.uni-wuppertal.de/cm#>
PREFIX plsm:   <http://plasma.uni-wuppertal.de/sm/>
PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:    <http://www.w3.org/2001/XMLSchema#>
PREFIX local:  <https://local.ontology#>
PREFIX schema: <https://schema.org/>
PREFIX hdpe:   <http://example.org/hdpe-pipe-ontology#>

{final_output_instructions}
""")

# Output-Instruktionen für Syntax-Fehler-Korrektur
OUTPUT_INSTRUCTIONS_SYNTAX_CORRECTION = """
Gib nur die korrigierte SPARQL-Query ab SELECT aus - keine Erklärung und keine umschließenden Anführungszeichen oder Markdown-Codeblöcke.
"""

# Prompt für SPARQL Empty Results Korrektur
SPARQL_EMPTY_RESULTS_CORRECTION_PROMPT = ChatPromptTemplate.from_template("""
Du bist ein SPARQL-Experte. Eine SPARQL-Query hat nicht die gewünschten Ergebnisse produziert und soll verbessert werden.

{optional_internal_reasoning_block}

BENUTZERANFRAGE:
"{user_query}"

SEMANTISCHE MODELLE:
{semantic_models_content}

Als Hilfestellung bekommst du einen beispielhaften Einblick in die Instanzdaten, die hinter den Modellen liegen:                                                                          
{optional_example_instances_block}

FEHLGESCHLAGENE SPARQL-QUERY:
{failed_query}


Deine Aufgabe:
Analysiere die SPARQL Query und vergleiche sie mit der ursprünglichen Anfrage. 
Überlege was vielleicht zu einem unerwünschten Ergebnis führen könnte und verbessere die SPARQL Query darauf basierend, damit sie die gewünschten Ergebnisse produziert.

Mögliche Ursachen für leere oder falsche Ergebnisse können sein:
- Falsche oder unvollständige Verwendung von Prädikaten oder Klassen aus den semantischen Modellen
- Die falsche Zielvariable wird ausgewählt
- Fehlende oder falsche FILTER-Bedingungen
- Es fehlt eine Berechnung oder Aggregation
                                                                        
                                                                          
Folgende Präfixe sind vorgegeben und werden automatisch hinzugefügt - du musst sie NICHT in der Query angeben:
PREFIX owl:    <http://www.w3.org/2002/07/owl#>
PREFIX plasma: <http://plasma.uni-wuppertal.de/ontology#>
PREFIX plcm:   <http://plasma.uni-wuppertal.de/cm#>
PREFIX plsm:   <http://plasma.uni-wuppertal.de/sm/>
PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:    <http://www.w3.org/2001/XMLSchema#>
PREFIX local:  <https://local.ontology#>
PREFIX schema: <https://schema.org/>
PREFIX hdpe:   <http://example.org/hdpe-pipe-ontology#>

{final_output_instructions}
""")

# Output-Instruktionen für Empty Results Korrektur
OUTPUT_INSTRUCTIONS_EMPTY_CORRECTION = """
Gib nur die korrigierte SPARQL-Query ab SELECT aus - keine Erklärung und keine umschließenden Anführungszeichen oder Markdown-Codeblöcke.
"""

CONTINUE_SPARQL_GENERATION_PROMPT = ChatPromptTemplate.from_template("""
Du bist ein Assistent in einem Chat2SPARQL-System. Eine vorherige Stufe hat eine Nutzeranfrage analysiert und festgestellt, dass sie nur teilweise mit den vorhandenen Daten beantwortet werden kann. Dem Nutzer wurde eine Rückfrage gestellt.

Hier ist der gesamte Kontext:

1.  Ursprüngliche Nutzeranfrage: "{original_user_query}"
2.  Analyse der vorherigen Stufe: "{initial_llm_reasoning}"
3.  Rückfrage an den Nutzer: "{clarification_question}"
4.  Antwort des Nutzers: "{user_response}"

Deine Aufgabe ist es, basierend auf der Antwort des Nutzers zu entscheiden, ob die SPARQL-Query-Generierung fortgesetzt werden soll.

Regeln:
- Wenn die Antwort des Nutzers positiv oder zustimmend ist (z.B. "Ja", "mach weiter", "ok", "trotzdem ausführen"), antworte mit "JA".
- Wenn die Antwort des Nutzers negativ oder ablehnend ist (z.B. "Nein", "lass es", "abbrechen"), antworte mit "NEIN".
- Versuche, die Absicht des Nutzers zu verstehen, auch wenn die Antwort nicht exakt "Ja" oder "Nein" ist.

Antworte NUR mit dem Wort "JA" oder "NEIN". Gib keinen weiteren Text aus.
""")

# LLM_SPARQL_QUERY_EDIT_EVALUATION_PROMPT_STEP_2 = ChatPromptTemplate.from_template("""
# Du erhältst eine Liste von Änderungsschritten, die an einer SPARQL-Query vorgenommen werden müssen, um sie funktional korrekt zu machen.
# Hier sind die identifizierten Änderungen:
# {identified_changes_list}

# Ziel ist es zu berechnen wie nah die erzeugte Query an einer funktionierenden Form ist.
# Deine Aufgabe ist es, diese Schritte systematisch durchzugehen und gemäß vordefinierter Regeln die Editkosten zu berechnen.

# Zähle alle notwendigen Änderungen nach folgenden erweiterten Regeln:

# TRIPLE-PATTERNS:
# - Jedes fehlende Triple: +3 Edits (1 Edit je Subjekt, Prädikat, Objekt)
# - Jede Änderung an einem Element (Subjekt, Prädikat, Objekt): +1 Edit
# - Fehlendes OPTIONAL-Blöcke: +2 Edits pro Block

# FILTER:
# - FILTER komplett fehlt: +2 Edits
# - FILTER vorhanden, aber Bedingung falsch: +1 Edit
# - Fehlende BIND-Expression innerhalb FILTER: +1 Edit

# SELECT & PROJECTION:
# - SELECT DISTINCT fehlt: +1 Edit
# - Falsche/fehlende Projektionsvariable: +1 Edit je Variable
# - Fehlendes GROUP BY: +2 Edits
# - Falsche Aggregationsfunktion (COUNT/SUM/MIN/MAX): +2 Edits

# BIND:
# - Kompletter BIND-Ausdruck fehlt: +2 Edits
# - Nur Ausdruck falsch: +1 Edit
# - Fehlende Typkonvertierung (xsd:integer, xsd:date): +1 Edit

# AGGREGATION:
# - COUNT/SUM/MIN/MAX komplett fehlt: +3 Edits
# - COUNT-Ausdruck falsch: +1 Edit
# - AS ?variable fehlt oder falsch: +1 Edit
# - Fehlende Subselects bei Aggregation: +3 Edits

# OPERATOR-STRUKTUREN:
# - UNION fehlt oder falsch: +1 Edit je fehlendem Pfad
# - OPTIONAL falsch implementiert: +2 Edits
# - SERVICE oder Federated Query fehlerhaft: +3 Edits
# - VALUES-Block fehlt: +2 Edits

# LÖSCHUNGEN:
# - Entfernen von Elementen kostet KEINE Edits!
# - Vereinfachung von Strukturen kostet KEINE Edits!
# - Veränderungen von Reihenfolge oder so kostet nichts, wenn nicht die Funktionalität beeinflusst wird

# ALLGEMEIN:
# - Syntaxfehler (Klammern, Semikolon): +1 Edit
# - Logische Operatoren (||, &&) falsch: +1 Edit

# WICHTIGES AUSGABEFORMAT:
# Deine gesamte Antwort muss ein einziges, valides JSON-Objekt sein, ohne jeglichen vorangehenden oder nachfolgenden Text, Kommentare oder Markdown-Formatierungen. Gib NUR das JSON-Objekt aus.

# Struktur des JSON-Objekts:
# {{
#   "total_edits": <Gesamtzahl>,
#   "edits": [
#     {{ "change": "<Beschreibung>", "cost": <Kosten> }},
#     ...
#   ]
# }}

# Beispielausgabe:
# {{
#   "total_edits": 7,
#   "edits": [
#     {{ "change": "Fehlendes Triple `?Bezeichnung plasma:hasValue ?Wert`", "cost": 3 }},
#     {{ "change": "BIND(LCASE(?Wert)) ergänzt", "cost": 2 }},
#     {{ "change": "FILTER-Bedingung korrigiert", "cost": 1 }},
#     {{ "change": "SELECT ?Bezeichnung zu SELECT ?Wert", "cost": 1 }}
#   ]
# }}


# Gehe nun schrittweise durch jede Änderung:
# 1. Übernimm die Beschreibung der Änderung aus der Liste 1:1.
# 2. Wende die passende Regel an, um die Kosten (`cost`) für DIESE EINE ÄNDERUNG zu bestimmen.
# 3. Wiederhole dies für alle Änderungen in der Liste.
# 4. Berechne am Ende die GESAMTSUMME (`total_edits`) aller Einzelkosten.
# 5. Gib das JSON-Objekt aus. Die Summe MUSS der Summe der Einzelkosten entsprechen.

# Hier ist die Liste der identifizierten Änderungen, die du bewerten sollst:
# {identified_changes_list}
# """)




# # Prompt: Max Edit Cost Calculation for Corrected SPARQL Query
# LLM_SPARQL_QUERY_MAX_EDIT_COST_PROMPT = ChatPromptTemplate.from_template("""
# Du bist Teil eines Evaluationssystems für SPARQL-Queries.
# Deine Aufgabe ist es, für eine gegebene, als korrekt angenommene SPARQL-Query die theoretischen "Editkosten" von Grund auf zu berechnen. Also wieviele Editkosten es braucht, um die Query von Grund auf zu erzeugen.
# Du erhältst eine vollständige Query. Zerlege sie in ihre fundamentalen Bestandteile und berechne die Gesamtkosten basierend auf den folgenden festen Regeln.

# Zähle die Kosten für den Aufbau der Query nach folgenden Regeln:

# TRIPLE-PATTERNS:
# - Jedes vollständige Triple (Subjekt, Prädikat, Objekt): +3 Edits
# - Jeder OPTIONAL-Block, der Tripel umschließt: +2 Edits pro Block

# FILTER:
# - Jeder vollständige FILTER-Block: +2 Edits
# - Jede BIND-Expression innerhalb eines Filters: +1 Edit

# SELECT & PROJECTION:
# - Das SELECT-Statement selbst: +1 Edit
# - Jede Projektionsvariable (z.B. ?name): +1 Edit pro Variable
# - Jedes DISTINCT-Schlüsselwort: +1 Edit
# - Jeder GROUP BY-Block: +2 Edits
# - Jede Aggregationsfunktion (COUNT, SUM, etc.) im SELECT: +2 Edits pro Funktion

# BIND:
# - Jeder vollständige BIND-Ausdruck außerhalb von Filtern: +2 Edits
# - Jede Typkonvertierung (z.B. xsd:integer): +1 Edit

# OPERATOR-STRUKTUREN:
# - Jeder UNION-Block, der zwei Abfrage-Teile verbindet: +1 Edit
# - Jeder SERVICE-Block: +3 Edits
# - Jeder VALUES-Block: +2 Edits

# LÖSCHUNGEN / SONSTIGES:
# - Entfernen, Vereinfachen oder Umordnen von Elementen kostet 0 Edits.
# - Syntax (Klammern, Punkte) ist in den Kosten der jeweiligen Blöcke enthalten.
# - Logische Operatoren (||, &&) sind Teil des FILTER-Blocks und kosten nichts extra.

# Beachte bei der Ausgabe:
# 1. Gehe die Query Zeile für Zeile oder Block für Block durch.
# 2. Liste jeden Bestandteil mit seinen Kosten auf.
# 3. Gib am Ende eine JSON-Struktur mit der Gesamtsumme und der detaillierten Auflistung zurück.

# WICHTIGES AUSGABEFORMAT:
# Deine gesamte Antwort muss ein einziges, valides JSON-Objekt sein, ohne jeglichen vorangehenden oder nachfolgenden Text, Kommentare oder Markdown-Formatierungen. Gib NUR das JSON-Objekt aus.

# Struktur des JSON-Objekts:
# {{
# "max_edit_cost": <Gesamtzahl der Editkosten>,
# "cost_breakdown": [
# {{ "component": "<Beschreibung des Bestandteils>", "cost": <Kosten> }},
# ...
# ]
# }}

# Beispiel für eine Query:
# SELECT DISTINCT ?Name WHERE {{ ?s a local:Station; local:hat ?b. ?b plasma:hasValue ?Name. FILTER(CONTAINS(?Name, "Haupt")) }}
# Beispielausgabe für die Query oben:
# {{
# "max_edit_cost": 14,
# "cost_breakdown": [
# {{ "component": "SELECT Statement", "cost": 1 }},
# {{ "component": "DISTINCT Keyword", "cost": 1 }},
# {{ "component": "Projection Variable ?Name", "cost": 1 }},
# {{ "component": "Triple: ?s a local:Station", "cost": 3 }},
# {{ "component": "Triple: ?s local:hat ?b", "cost": 3 }},
# {{ "component": "Triple: ?b plasma:hasValue ?Name", "cost": 3 }},
# {{ "component": "FILTER Block", "cost": 2 }}
# ]
# }}

# Führe nun die Analyse für die folgende Query durch:
# ```sparql
# {corrected_sparql_query}
# ```
# """)