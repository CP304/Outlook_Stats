# Outlook-Kommunikationsanalyse

Metadatenbasierte Analyse der Frage:

> **Wie viel Kommunikations- und Koordinationskapazität des strategischen Einkaufs wird für
> interne Abstimmung gebunden — und wie viel steht für Lieferanten-, Markt- und strategische
> Arbeit zur Verfügung?**

Das Repository enthält die fachliche Konzeption **und** die lauffähige Umsetzung. Die Konzeption steht
bewusst voran: Die methodischen Festlegungen entscheiden über die Belastbarkeit der Ergebnisse weit
mehr als der Code. Wer die Zahlen später vor einer Geschäftsführung vertreten muss, muss erklären
können, *was* gezählt wurde und *warum*.

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

## Schnellstart

**Doppelklick auf `start.bat`.** Mehr ist nicht nötig: Fehlt Python, richtet die Datei es selbst
ein — zuerst über `winget`, sonst direkt von python.org, jeweils nur für den eigenen Benutzer und
ohne Adminrechte. Anschließend installiert sie die beiden Pakete (`pywin32` für den
Outlook-Zugriff, `openpyxl` für die Excel-Dateien) und startet die Oberfläche.

Dann nur noch: interne Domain eintragen, „Analyse starten“. Wer erst sehen will, was herauskommt,
drückt „Beispiel ansehen“ — das rechnet mit synthetischen Daten und braucht kein Outlook.

Scheitert die Einrichtung am Firmenproxy, sagt die Datei genau das und nennt den Befehl zum
Nachholen von Hand. Das Konsolenfenster bleibt bewusst offen: Dort stehen die Meldungen, falls
doch etwas klemmt.

Die Oberfläche ist mit tkinter gebaut, das zum Lieferumfang von Python gehört: keine Installation,
kein Wartebalken beim Start, nichts zu erklären, wenn man das Werkzeug weitergibt.

Alles geht auch auf der Kommandozeile:

```
python -m okoa                             # Oberfläche
python -m okoa demo --ordner Beispiel      # Beispielreport, ohne Outlook
python -m okoa analyse --domain firma.de   # eigenes Postfach
```

Das erzeugt im Ordner `Auswertung`:

| Datei | Inhalt |
|---|---|
| `Mein_Report.html` | der vollständige Report, eine einzelne Datei ohne externe Abhängigkeiten |
| `mapping_personen.xlsx` | Personen nach Volumen sortiert — Spalte „Fachbereich“ ausfüllen |
| `mapping_domains.xlsx` | externe Domains nach Volumen — Spalte „Kategorie“ ausfüllen |
| `messages.csv` | Metadaten-Zwischendatei (keine Betreffe, keine Texte) |

Für das eigene Postfach: `--alles` erhebt zusätzlich Betreff, Anhangnamen, Größe und BCC und rechnet
Antwortzeiten, Arbeitszeitmuster und Kommunikationsnetzwerk ([Kapitel 11](docs/11-vollerhebung.md)).
Der Teamexport bleibt davon unberührt aggregiert.

Die Fachbereiche werden direkt in der Oberfläche gepflegt („Interne Kontakte und Fachbereiche …“):
eine nach Volumen sortierte Tabelle, mehrere Zeilen auswählen, Fachbereich zuweisen, speichern.
Die Statuszeile zeigt, wie viel Volumen bereits abgedeckt ist — meist genügen die obersten 15 bis 25
Zeilen. Wer lieber in Excel arbeitet, öffnet die Datei von dort aus.

Nach dem Ausfüllen der Zuordnung genügt `python -m okoa neu` — das rechnet auf der Zwischendatei und
braucht weder Outlook noch einen zweiten Postfachzugriff.

Alle externen Kontakte als Excel — mit Firmenname, Volumen, Richtung und letztem Kontakt:

```
python -m okoa kontakte --domain firma.de              # Firma aus dem Domainnamen
python -m okoa kontakte --domain firma.de --signaturen # Firma aus Signaturen belegt
```

Mit `--signaturen` kommen Funktion, Telefon und Mobil aus der Signatur dazu — regelbasiert, ohne
Sprachmodell, und nur wenn mindestens zwei Signaturen dasselbe sagen. Fax wird nie übernommen.

Für die Massenpflege ins Adressbuch erzeugt `--fuer-import` zusätzlich eine vCard-Datei und eine
Outlook-CSV, mit in Vor- und Nachname zerlegten Namen.

`--signaturen` ist die einzige Stelle im Projekt, die Mailtexte liest — bewusst nicht die Vorgabe.
Warum das trotzdem deterministisch bleibt und was datenschutzrechtlich dazugehört, steht in
[Kapitel 10](docs/10-kontaktliste.md).

Einmal gepflegte Zuordnungen an Kollegen weitergeben (oder beim Rechnerwechsel mitnehmen):

```
python -m okoa export                      # Einstellungen.json schreiben
python -m okoa import Einstellungen.json   # übernehmen; eigene Zuordnung gewinnt
```

Mit wandern Domains, Fachbereiche, Rollen und Kategorien — **nicht** die Volumenzahlen aus der
Zuordnungsdatei, denn die gehören zum Postfach des Erstellers.

Für den Teammodus führt jeder die Analyse selbst aus; die Zusammenführung der freiwillig geteilten
Kennzahlen läuft über den Reiter „Weitergabe und Team“ oder `python -m okoa merge --ordner Eingang`. Sie
verweigert unter fünf Teilnehmern bewusst jedes Ergebnis — Einzelheiten in Kapitel 08 und 09.

## Aufbau

```
okoa/gui.py               Oberfläche (tkinter) — sammelt Eingaben, zeigt an
okoa/auftrag.py           Hintergrundarbeiten, damit das Fenster nicht einfriert
okoa/extract_outlook.py   Outlook-COM, ausschließlich lesend   (nur Windows)
okoa/normalize.py         Adressauflösung, Deduplikation, Klassifikation
okoa/threads.py           Vorgangsbildung mit zwei Verfahren
okoa/metrics.py           KPI-Berechnung
okoa/report.py            HTML-Report mit eigenen SVG-Diagrammen
okoa/team_export.py       anonymer Export und Zusammenführung
okoa/einstellungen.py     Weitergabe von Konfiguration und Zuordnungen
okoa/kontakte.py          externe Kontaktliste als Excel
okoa/kontaktexport.py     vCard und Outlook-CSV für die Massenpflege
okoa/signaturen.py        Firmennamen aus Signaturen, regelbasiert
```

Nur die erste Stufe braucht Windows und Outlook. Alles Weitere rechnet auf der Zwischendatei und ist
damit ohne Postfach testbar, reproduzierbar und für Dritte nachvollziehbar — was zugleich das
Kernargument gegenüber Datenschutzbeauftragtem und Betriebsrat ist.

Pflichtabhängigkeiten gibt es keine: Auswertung, Report und Zusammenführung laufen mit der
Standardbibliothek. `pywin32` wird nur zum Auslesen gebraucht, `openpyxl` nur, damit die
Zuordnungsdateien als `.xlsx` statt `.csv` entstehen.

## Tests

```
python -m pytest tests/ -q
```

`tests/test_datenschutz.py` ist dabei mehr als ein Test: Er prüft die Zusagen aus Kapitel 08 —
dass die Zwischendatei keine Betreffzeilen enthält, dass der Teamexport nur die dokumentierten Felder
kennt, dass unter fünf Teilnehmern kein Ergebnis entsteht und dass der Zusammenführungs-Code
konstruktionsbedingt keinen Zugang zu Rohdaten hat.

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
| [10 – Kontaktliste](docs/10-kontaktliste.md) | Externe Kontakte als Excel — mit eigener Rechtslage |
| [11 – Vollerhebung](docs/11-vollerhebung.md) | Alles erheben, für das eigene Postfach |

## Wichtiger Hinweis

Kapitel 08 und 09 enthalten eine fachliche Einordnung, **keine Rechtsberatung**. Verbindlich
entscheiden Datenschutzbeauftragte(r) und Betriebsrat des Unternehmens.
