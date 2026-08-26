# 11 — Vollerhebung

Für die Auswertung des **eigenen** Postfachs. Sie erhebt alles, was die Outlook-Schnittstelle
hergibt, und rechnet die Auswertungen, die Stufe 1 bewusst weggelassen hatte.

```
python -m okoa analyse --domain firma.de --alles
python -m okoa demo --alles                     # zum Ansehen, ohne Outlook
```

## Was zusätzlich erhoben wird

| Feld | Wozu |
|---|---|
| Betreff (Klartext) | Grundlage für die spätere regelbasierte Klassifikation (Roadmap Stufe 5) |
| Anhangnamen | Dateitypen — was tatsächlich hin- und hergeschickt wird |
| Mailgröße | Volumen, ausdrücklich **kein** Aufwandsmaß |
| BCC-Anzahl | eigene Sendungen; bei empfangenen Mails prinzipiell unsichtbar |
| Weiterleitungskennzeichen | Durchreichen statt Entscheiden |

Diese Felder landen in `messages.csv`. Ohne `--alles` bleiben sie leer — durchgesetzt beim
Schreiben der Datei, nicht erst beim Auslesen: Woher die Daten kommen, darf für diese Zusage keine
Rolle spielen.

## Was zusätzlich gerechnet wird

**Antwortzeiten** — Median, Quartile, Anteil unter 4 h und über 48 h; getrennt nach Vorgangsklasse
und nach Richtung („ich antworte" / „mir wird geantwortet"). Gezählt wird nur der **Sprecherwechsel**
innerhalb eines Vorgangs; zwei Nachrichten derselben Person hintereinander sind Nachfassen, keine
Antwort. Spannen über zwei Wochen fallen heraus — das ist kein Reaktions-, sondern ein neuer Anlauf.

**Arbeitszeitmuster** — Anteil außerhalb 7–19 Uhr, am Wochenende, vor Beginn, nach Feierabend.
Nur **selbst gesendete** Nachrichten: Empfangene sagen etwas über die Arbeitszeit der anderen aus.

**Kommunikationsnetzwerk** — wichtigste interne und externe Gegenüber mit Volumen, Vorgängen und
„Grad" (mit wie vielen anderen jemand gemeinsam in Vorgängen auftaucht), dazu Konzentrationsmaße:
Anteil Top 5 und Top 10 sowie Gini (0 = gleich verteilt, 1 = alles hängt an einer Person).

**Anhänge** — Anteil mit Anhang, Anhänge je Nachricht, häufigste Dateitypen, Median-Größe.

**Termine** — Anzahl, Anteil mit externer Beteiligung, Organisatoren, mittlere Teilnehmerzahl.
Terminobjekte werden weiterhin **nicht** als Mail gezählt; eine Serie erzeugte sonst dutzende
„Nachrichten". Der eigentliche Sprung kommt erst mit den Kalenderdaten (Roadmap Stufe 4) — hier
sieht man nur die Einladungen.

**BCC und Weiterleitungen** — beides als eigene Kennzahl statt versteckt in den Empfängerzahlen.

## Warum das alles „explorativ" heißt

Im Report steht dieser Teil in einem eigenen, abgesetzten Abschnitt mit der Marke *explorativ*.
Das ist keine Förmlichkeit:

- **Antwortzeiten** hängen an Urlaub, Teilzeit, Zeitzonen und daran, ob eine Mail überhaupt eine
  Antwort brauchte. Als Prozessindikator brauchbar, als Leistungsmaß unbrauchbar.
- **Netzwerkwerte** beschreiben eine Rolle, keine Qualität. Ein hoher Grad kann Bottleneck heißen —
  oder die zutreffende Stellenbeschreibung sein.
- **Arbeitszeitmuster** beschreiben Verhalten. Beim eigenen Postfach ist das eine ehrliche
  Selbstauskunft; über andere wäre es etwas anderes.
- **Größe** misst Dateianhänge, nicht Arbeit. Sie steht im Report, weil sie erhoben wurde, und ist
  ausdrücklich als untauglich für Aufwandsaussagen gekennzeichnet.

Deshalb bleibt die Trennung: Die Kern-KPIs auf Seite 1 tragen die Managementaussage; dieser Teil
liefert Hinweise, denen man nachgehen kann.

## Was sich dadurch **nicht** ändert

Der **Teamexport bleibt unverändert aggregiert**. Auch mit `--alles` enthält `team_export.json`
nur die in [Kapitel 09](09-teilnahme.md) aufgelisteten Felder — keine Netzwerkdaten, keine
Uhrzeiten, keine Adressen. Das ist durch die Feldprüfung erzwungen und durch einen Test
abgesichert. Was für das eigene Postfach erhoben wird, wandert nicht in eine Gruppenauswertung.

Ebenso unverändert: Es wird ausschließlich **gelesen**, am Postfach ändert sich nichts.

Namen und Adressen erscheinen in den Netzwerktabellen des **persönlichen** Reports. Wenn dieser
Report weitergegeben werden soll, ist er ohne `--alles` zu erzeugen — dann fehlt der ganze Abschnitt.
