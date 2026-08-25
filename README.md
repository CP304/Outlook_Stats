# Outlook-Kommunikationsanalyse

Metadatenbasierte Analyse der Frage:

> **Wie viel Kommunikations- und Koordinationskapazität des strategischen Einkaufs wird für
> interne Abstimmung gebunden — und wie viel steht für Lieferanten-, Markt- und strategische
> Arbeit zur Verfügung?**

Dieses Repository enthält zunächst **die fachliche Konzeption**, noch keinen Code. Das ist Absicht:
Die methodischen Festlegungen entscheiden über die Belastbarkeit der Ergebnisse weit mehr als die
Implementierung. Wer die Zahlen später vor einer Geschäftsführung vertreten muss, muss vorher
erklären können, *was* gezählt wurde und *warum*.

## Grundhaltung

Die Ausgangshypothese lautet: *"ca. 80 % unserer Mailkommunikation ist rein intern."*
Diese Hypothese soll **geprüft, nicht bestätigt** werden. Das Konzept ist deshalb so angelegt,
dass es die Hypothese auch widerlegen kann — unter anderem, indem es bewusst zwei Zählweisen
gegeneinander stellt, die typischerweise unterschiedliche Ergebnisse liefern.

Leitplanken der ersten Stufe:

- **read-only** — das Postfach wird nicht verändert
- **nur Metadaten** — keine Mailtexte, keine Betreffzeilen in der Auswertung, kein NLP, kein LLM
- **deterministisch und reproduzierbar** — gleiche Eingabe, gleiches Ergebnis
- **erklärbar** — jede Kennzahl hat eine Definition, eine Datenquelle und eine bekannte Verzerrung
- **datensparsam** — bei Teamnutzung verlässt nichts Personenbezogenes den Rechner des Teilnehmers

## Lesereihenfolge

| Kapitel | Inhalt |
|---|---|
| [01 – KPI-Konzept](docs/01-kpi-konzept.md) | Welche Kennzahlen belastbar sind, welche nicht — und warum |
| [02 – Methodik](docs/02-methodik.md) | Zähleinheiten: wann Nachrichten, wann Vorgänge |
| [03 – Outlook-COM-Realität](docs/03-outlook-com-realitaet.md) | Was die Schnittstelle wirklich liefert, und die Fallstricke |
| [04 – Setup und Architektur](docs/04-setup-und-architektur.md) | Minimal-Setup, Zwei-Pass-Modell, Pipeline |
| [05 – Reporting](docs/05-reporting.md) | Aufbau des Management-Dashboards |
| [06 – Managementinterpretation](docs/06-managementinterpretation.md) | Von der Beobachtung zum Handlungsfeld — ohne Kurzschlüsse |
| [07 – Roadmap](docs/07-roadmap.md) | Ausbaustufen, kritisch sortiert |
| [08 – Datenschutz](docs/08-datenschutz.md) | Was als Führungskraft geht und was nicht |
| [09 – Teilnahme](docs/09-teilnahme.md) | Wie Kollegen freiwillig und anonym teilnehmen können |

## Wichtiger Hinweis

Kapitel 08 und 09 enthalten eine fachliche Einordnung, **keine Rechtsberatung**. Verbindlich
entscheiden Datenschutzbeauftragte(r) und Betriebsrat des Unternehmens.
