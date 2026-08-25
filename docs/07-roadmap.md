# 07 — Roadmap

Die ursprünglich angedachte Stufung (Metadaten → Mapping → Netzwerk → Regelbasiert → NLP) ist im Kern
richtig, hat aber eine Lücke: Sie führt geradewegs auf Textanalyse zu, obwohl der größte ungehobene
Erkenntnisgewinn woanders liegt — **in den Kalenderdaten**.

## Stufe 0 — nur das eigene Postfach *(Start hier)*

Vollständige Basisanalyse, ein Teilnehmer, kein Setup außer der Domain, keine Datenschutzfrage.
Beantwortet die Managementfrage bereits als belastbares Indiz und ist die Grundlage, mit der man
alles Weitere überhaupt erst begründen kann.

**Abbruchkriterium:** Wenn die Zahlen hier nichts Überraschendes zeigen, lohnt der Rest nicht.
Das ist ein Feature, keine Schwäche.

## Stufe 1 — Metadaten-Baseline, sauber

Deduplikation, Adressauflösung, Klasse `automatisiert`, doppelte Thread-Bildung, Kern-KPIs,
Datenqualitätsanhang. Das ist der eigentliche Aufwand des Projekts — und der Teil, der über
Glaubwürdigkeit entscheidet.

## Stufe 2 — Mapping

Fachbereichszuordnung und Domainkategorien über die generierten Excel-Dateien. Geringer Aufwand
(20 Zeilen pflegen), hoher Ertrag: erst hier wird aus "intern" eine Aussage über *Schnittstellen*.

## Stufe 3 — Zeitreihe und Netzwerk

Trends über 24 Monate, Schnittstellenintensität zwischen Einkauf und Fachbereichen, Konzentrations-
und Bottleneck-Indikatoren. **Explorativ, mit Rollen- statt Klarnamen.**

## Stufe 4 — Kalenderdaten *(die eigentliche Erweiterung)*

Über dieselbe COM-Schnittstelle sind Termine mit reinen Metadaten auslesbar: Dauer, Teilnehmerzahl,
Wiederkehr, interner/externer Teilnehmerkreis, Organisator vs. Eingeladener.

Warum das wichtiger ist als jede Textanalyse: **Koordinationslast steckt primär in Meetings, nicht in Mails.**
Ein wöchentlicher Jour fixe mit acht Teilnehmern bindet mehr Kapazität als hunderte Mails — und
Meetingzeit ist im Gegensatz zu Mailvolumen tatsächlich *messbare Zeit*, keine Schätzung.

Erst mit Stufe 4 lässt sich die Managementfrage quantitativ statt indikativ beantworten:
`gebundene Stunden interne Meetings` vs. `gebundene Stunden externe Termine` ist eine echte
Kapazitätsaussage. Alles davor ist ein Proxy.

Datenschutzlage: identisch zu Mails, also nach denselben Regeln (Kapitel 08). Beim eigenen Kalender
unproblematisch.

## Stufe 5 — regelbasierte Metadatenklassifikation

Erst jetzt, und nur wenn nötig: Betreffmuster für Vorgangstypen (Anfrage, Bestellung, Reklamation,
Rechnung) über eine gepflegte Schlüsselwortliste. Deterministisch, prüfbar, erklärbar.

**Bewusst nachgelagert**, weil hier zum ersten Mal Textinhalte verarbeitet werden — das ändert die
Datenschutzbewertung und die Erklärbarkeit spürbar, für einen im Vergleich zu Stufe 4 kleinen Zugewinn.

## Stufe 6 — NLP / LLM

Nur bei nachgewiesenem Restnutzen, den die Stufen 0–5 nicht liefern konnten, und nur auf lokal
verarbeiteten Daten. In der Praxis ist die realistische Erwartung: **diese Stufe wird nie gebraucht.**
Die Managementfrage ist eine Struktur-, keine Inhaltsfrage.

## Was bewusst nicht auf der Roadmap steht

- **Teams-/Chatdaten** — technisch nur über Graph mit Admin-Consent, datenschutzrechtlich deutlich heikler,
  und methodisch schwer mit Mails vergleichbar. Falls verfügbar, würde es die Ergebnisse allerdings
  relativieren: ein niedriger Mailverkehr bei hoher Chatnutzung bedeutet nichts. **Als Limitation
  im Report nennen.**
- **Telefonie-/Systemdaten** — Aufwand und Sensibilität stehen in keinem Verhältnis
- **Automatisierte Dauerüberwachung** — eine wiederholte Momentaufnahme (halbjährlich) ist
  aussagekräftiger und ungleich unproblematischer als ein Dauerbetrieb, der zur Überwachungsinfrastruktur würde
