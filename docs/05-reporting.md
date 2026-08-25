# 05 — Reporting

## Format

Eine einzelne, **selbsttragende HTML-Datei** — keine externen Assets, keine Internetverbindung,
per Mail weitergebbar, in jedem Browser lesbar, druckbar als PDF. Dazu eine Excel-Datei mit den
Rohkennzahlen für Rückfragen ("wo kommt die Zahl her").

Kein Dashboard-Server, kein Power BI, keine IT-Freigabe. Wer das Ergebnis nicht in einer Datei
weitergeben kann, wird es nicht verbreiten.

## Aufbau: fünf Seiten plus Anhang

### Seite 1 — Managementsicht

Die einzige Seite, die ein Vorgesetzter zwingend lesen muss. Sie beantwortet die Ausgangsfrage
und stellt sofort den entscheidenden Kontrast her.

**Oben: der Hypothesenvergleich.**

```
Vermutet:  ~80 % interne Kommunikation
Gemessen:  Vorgänge  intern 54 %  |  gemischt 21 %  |  extern 25 %
           Nachrichten intern 71 %  |  gemischt 18 %  |  extern 11 %
```

Diese Gegenüberstellung ist der Kern des ganzen Berichts. Sie zeigt in zwei Zeilen, dass die
Ausgangshypothese je nach Zählweise stimmt oder nicht — und macht die eigentliche Erkenntnis sichtbar:
nicht *wie viele* Themen intern sind, sondern *wie viel Kommunikation* interne Themen kosten.

**Darunter: sechs Kernzahlen als Kacheln** (K1–K6 aus Kapitel 01), jede mit
Wert, Vergleichswert (Vorjahr/Vorquartal, wenn vorhanden) und einem Klick auf die Definition.

**Darunter: ein einziges Diagramm** — Monatsverlauf intern vs. extern (Vorgänge), gestapelt.
Mehr nicht. Seite 1 hat maximal drei visuelle Elemente.

### Seite 2 — Interne Koordinationslast

- Verteilung Nachrichten je Vorgang, intern vs. extern (Histogramm, nicht nur Mittelwert)
- Anteil Langläufer (>5, >10 Nachrichten) je Klasse
- CC-Quote und Ø CC-Empfänger
- Anteil Nachrichten an Großverteilern und Verteilerlisten
- Beteiligungsbreite: Ø/Median Teilnehmer je Vorgang
- **Kernsatz der Seite** als Fließtext: "Interne Vorgänge haben im Median X Nachrichten und Y Teilnehmer,
  externe Z bzw. W."

### Seite 3 — Fachbereiche

Nur vorhanden, wenn das Mapping gepflegt wurde; sonst mit Hinweis ausgeblendet.

- Volumen je Fachbereich, **immer doppelt**: Vorgänge und Nachrichten
- Ø Vorgangsgröße je Fachbereich — zeigt, mit wem Abstimmung teuer ist
- Anteil "Unbekannt/Sonstige" **prominent oben** — solange der über ~25 % liegt, sind die
  Fachbereichsaussagen nicht belastbar, und das muss dastehen
- Entwicklung über die Zeit, sofern ≥12 Monate vorhanden

### Seite 4 — Lieferanten und Markt

- Anzahl aktiver externer Domains (≥1 und ≥3 Vorgänge)
- Volumen je Domain, Top 15
- Konzentration: Anteil Top-10 am externen Volumen, HHI
- Verhältnis eigene Sendungen zu Eingang je Domain — wer treibt die Beziehung?
- neue Domains im Zeitraum (Marktscreening-Indikator, explorativ markiert)

### Seite 5 — Zeitliche Muster

- Monatsverlauf intern/gemischt/extern, Vorgänge und Nachrichten
- Wochentagsprofil
- Tageszeitprofil *(nur im persönlichen Report, nicht im Teamreport — Kapitel 08)*

### Anhang — Methodik und Datenqualität

Kein Nebenschauplatz, sondern der Teil, der die Zahlen verteidigungsfähig macht:

- Zeitraum, ausgewertete Stores und Ordner, ausgeschlossene Ordner
- Anzahl Elemente gesamt / nach Deduplikation / nach Klassifikation
- **Anteil unauflösbarer Adressen** (>5 % → Warnhinweis)
- **Anteil entfernter Duplikate**
- **Abweichung der Kern-KPIs zwischen den beiden Thread-Verfahren** (Stabilitätsindikator)
- Anteil Klasse "automatisiert" und was darunter fällt
- Hinweis: Empfängerzahlen sind wegen nicht aufgelöster Verteilerlisten Untergrenzen
- Definitionen aller Kennzahlen im Wortlaut

## Gestaltungsregeln

1. **Jede Zahl mit Bezugsgröße.** "1.240 interne Nachrichten" ist wertlos, "71 % von 1.750" ist eine Aussage.
2. **Anteile immer als Vorgangs- *und* Nachrichtensicht.** Nie nur eine.
3. **Median vor Mittelwert** bei allem, was Thread-Längen betrifft.
4. **Explorative Kennzahlen visuell abgesetzt** und mit "explorativ" beschriftet.
5. **Keine Ampelfarben, keine Zielwerte.** Es gibt keinen Benchmark für "richtige" interne Quote.
   Eine rote Kachel würde eine Bewertung behaupten, die die Daten nicht hergeben.
6. **Keine Personennamen im Report.** Auch im persönlichen Report reichen Fachbereichslabels;
   Netzwerkgrafiken laufen mit Rollen- statt Klarnamen.

Punkt 5 und 6 sind nicht Kosmetik. Sie entscheiden darüber, ob das Ergebnis als Analyse oder als
Bewertung gelesen wird — und damit, ob man es überhaupt zeigen kann.
