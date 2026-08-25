# 01 — KPI-Konzept

## Vorbemerkung: was diese Analyse messen kann und was nicht

E-Mail-Metadaten messen **Kommunikationsvolumen**, nicht **Zeitaufwand**. Eine Mail mit drei Zeilen
und eine Mail, die zwei Stunden Vorbereitung gekostet hat, sind in den Daten identisch. Jede Aussage
über "gebundene Kapazität" ist deshalb eine **Schätzung unter offengelegten Annahmen**, nie eine Messung.

Das ist keine Schwäche, solange man es sagt. Es ist eine Schwäche, sobald man es verschweigt.

Wer trotzdem eine Kapazitätsaussage braucht, rechnet sie als **Szenario**: "bei angenommenen 4 Minuten
je Nachricht entspricht das X Stunden pro Woche" — mit sichtbarem Faktor, den der Leser ändern kann.
Nie als Kennzahl ausweisen, immer als Rechnung mit Stellschraube.

## Ebene 1 — Kern-KPIs (belastbar, dashboardfähig)

Diese sechs tragen die Managementaussage. Sie sind robust gegen die typischen Outlook-Artefakte
(Duplikate, Threadbrüche, Verteilerlisten) oder werden bewusst paarweise gelesen, sodass eine Verzerrung
sichtbar wird statt zu wirken.

### K1 — Anteil interner / externer / gemischter Vorgänge
**Definition:** Anteil der Kommunikationsvorgänge (Threads) je Klasse an allen Vorgängen im Zeitraum.
**Zähleinheit:** Vorgang.
**Klassifikation:** über die Vereinigungsmenge aller Teilnehmer aller Nachrichten des Vorgangs.
Nur interne Adressen → `intern`. Mindestens eine externe → `extern` (wenn kein nennenswerter interner
Anteil) bzw. `gemischt`. Details siehe [Methodik](02-methodik.md).
**Warum belastbar:** Die Vorgangsebene neutralisiert die stärkste Verzerrung der Rohzählung —
dass interne Themen mehr Hin und Her erzeugen als externe.
**Bekannte Verzerrung:** hängt an der Qualität der Thread-Bildung (siehe Kapitel 03).

### K2 — Anteil interner / externer Nachrichten
**Definition:** dasselbe auf Nachrichtenebene.
**Zähleinheit:** Nachricht.
**Warum belastbar:** nicht als Einzelzahl, sondern **im Kontrast zu K1**. Die Differenz zwischen K1 und K2
ist selbst der interessanteste Befund: Liegt der interne Anteil auf Nachrichtenebene deutlich höher als
auf Vorgangsebene, bedeutet das *nicht* "mehr interne Themen", sondern **mehr Aufwand je internem Thema**.
Genau das ist die Koordinationslast.
**Bekannte Verzerrung:** überschätzt intern systematisch. Deshalb nie allein zeigen.

### K3 — Koordinationstiefe
**Definition:** Ø und Median Nachrichten je Vorgang, getrennt nach intern / extern / gemischt.
**Zähleinheit:** Nachrichten je Vorgang.
**Aussage:** Wie viele Runden braucht ein Thema, bis es erledigt ist? Interne Werte deutlich über
externen deuten auf Abstimmungsschleifen, unklare Zuständigkeiten oder fehlende Entscheidungsbefugnis.
**Warum belastbar:** unabhängig vom absoluten Volumen und damit vergleichbar über Zeiträume und Personen.
**Immer mit Median berichten** — der Mittelwert wird von einzelnen Endlosthreads dominiert.

### K4 — Beteiligungsbreite
**Definition:** Ø und Median Anzahl distinkter Teilnehmer je Vorgang, getrennt nach Klasse.
**Zähleinheit:** Personen je Vorgang.
**Aussage:** Wie viele Menschen sind an einem Vorgang beteiligt? Zusammen mit K3 ergibt das die eigentliche
Koordinationslast: `Nachrichten × Teilnehmer` ist der Aufwandstreiber, nicht die Mailanzahl allein.
**Bekannte Verzerrung:** Verteilerlisten werden unterzählt (siehe Kapitel 03) — die Zahl ist also eher
eine Untergrenze.

### K5 — Außenorientierung (Outbound-Fokus)
**Definition:** Anteil der **selbst gesendeten** Nachrichten, die an mindestens einen externen Empfänger gehen.
**Zähleinheit:** Nachricht, nur eigene Sendungen.
**Warum das die schärfste Kennzahl ist:** Empfangene Mails sind fremdbestimmt — man wird in CC gesetzt,
ob man will oder nicht. Was man selbst schreibt, ist die eigene Kapazitätsallokation. K5 misst daher
Außenorientierung deutlich näher an der Managementfrage als jede Gesamtquote.
**Bekannte Verzerrung:** Weiterleitungen nach intern nach einem externen Vorgang zählen als intern —
korrekt, aber es lohnt der getrennte Ausweis von Erstnachrichten vs. Antworten.

### K6 — Externe Reichweite
**Definition:** Anzahl distinkter externer Domains mit mindestens einem Vorgang im Zeitraum,
plus Anzahl mit mindestens 3 Vorgängen (aktive Beziehungen statt Zufallskontakte).
**Zähleinheit:** Domain.
**Aussage:** Marktbreite. Ein strategischer Einkauf mit acht aktiven Lieferantenbeziehungen im Jahr
hat ein anderes Profil als einer mit achtzig.
**Bekannte Verzerrung:** Newsletter, Portale, Dienstleister blähen die Zahl auf → Filterung
automatisierter Absender ist Voraussetzung (Kapitel 03).

## Ebene 2 — Sekundäre KPIs (sinnvoll, aber erklärungsbedürftig)

| KPI | Definition | Wofür |
|---|---|---|
| CC-Quote intern | Anteil interner Nachrichten mit ≥1 CC; Ø CC-Empfänger | Indikator für Absicherungs- und Informationskultur |
| Großverteiler | Anteil interner Nachrichten mit >8 Empfängern | Streuverluste, "alle informieren statt einen fragen" |
| Langläufer | Anteil Vorgänge mit >5 bzw. >10 Nachrichten, nach Klasse | wo Abstimmung entgleist |
| Vorgangsdauer | Median Zeit erste bis letzte Nachricht, nach Klasse | Durchlaufzeit von Abstimmung |
| Fachbereichsvolumen | Vorgänge **und** Nachrichten je Fachbereichslabel | wohin die interne Last fließt |
| Externe Konzentration | Anteil Top-10-Domains am externen Volumen, HHI | Klumpenrisiko vs. Zersplitterung |
| Zeitverlauf | Monatstrend intern vs. extern | Entwicklung, Projekt- und Saisoneffekte |
| Wochentagsprofil | Verteilung nach Wochentag | Meeting-/Rhythmuseffekte |

Diese Kennzahlen sind gut messbar, aber ihre Interpretation ist mehrdeutig. Eine hohe CC-Quote kann
Absicherungskultur sein — oder eine sinnvolle Reaktion auf eine Matrixorganisation. Sie gehören ins
Dashboard, aber nicht auf die erste Seite.

## Ebene 3 — Explorativ (mit Vorbehalt kennzeichnen)

Diese Kennzahlen sind interessant, aber methodisch angreifbar. Im Report klar als explorativ markieren
und **nie** als Bewertungsgrundlage verwenden.

- **Antwortzeiten intern vs. extern** — nur als Prozessindikator, nie personenbezogen. Verzerrt durch
  Urlaub, Teilzeit, Zeitzonen, Mails, die nie eine Antwort brauchten.
- **Netzwerkkennzahlen** (Degree, Betweenness) — schöne Bilder, aber ein hoher Betweenness-Wert kann
  Bottleneck *oder* schlicht die korrekte Rollenbeschreibung sein.
- **After-hours-Anteil** — Vorsicht: das ist eine Verhaltensauswertung. Im persönlichen Report vertretbar,
  im Teamreport bewusst ausgeschlossen (Kapitel 08).
- **Neue vs. wiederkehrende externe Domains** — brauchbarer Indikator für Marktscreening, aber stark
  abhängig vom Beobachtungsfenster.

## Ebene 4 — Ausdrücklich nicht empfohlen

| Metrik | Warum nicht |
|---|---|
| Mailgröße / Anhangsgröße als Aufwandsproxy | misst Dateianhänge, nicht Arbeit. Ein 12-MB-PDF ist kein Aufwand, ein Dreizeiler kann Tage gekostet haben |
| BCC-Auswertung | im eigenen Postfach nur bei selbst gesendeten Mails sichtbar, bei empfangenen prinzipiell nicht — systematisch und unbehebbar verzerrt |
| Antwortzeit als Leistungs- oder Belastungsmaß | misst Erreichbarkeit, nicht Leistung; personenbezogen zudem mitbestimmungspflichtig |
| Absolute Mailanzahl je Person als Ranking | erzeugt genau die Fehlsteuerung, die man untersuchen wollte; wer viel mailt, arbeitet nicht viel |
| Anhangnamen | häufig vertraulich (Preise, Vertragsentwürfe, Namen), geringer analytischer Mehrwert |
| "Interne Quote" als einzelne Erfolgskennzahl | eine Quote ohne Benchmark und ohne Rollenbezug ist keine Bewertung, sondern eine Zahl (siehe Kapitel 06) |
| Sentiment / Dringlichkeit aus Betreff ("URGENT", "!!!") | Betreffanalyse ist bereits Textanalyse und in Stufe 1 ausgeschlossen; zudem sehr schwacher Indikator |

## Welche KPIs die Managementfrage wirklich beantworten

Die Frage lautet nicht "wie viel wird gemailt", sondern "wie verteilt sich Kapazität zwischen innen und außen".
Darauf antworten in absteigender Trennschärfe:

1. **K5 Außenorientierung** — was tue ich aktiv, statt was passiert mir
2. **K3 × K4 Koordinationstiefe × Beteiligungsbreite** — der eigentliche Aufwandstreiber
3. **K1 vs. K2** — der Kontrast zwischen Themenanteil und Aufwandsanteil
4. **K6 externe Reichweite** — ob Außenorientierung überhaupt Substanz hat

Die klassische "interne Mailquote", also die Zahl, mit der die Hypothese formuliert wurde, ist von diesen
die **schwächste**. Sie steht im Dashboard, weil sie die Ausgangsfrage ist — nicht, weil sie die beste Antwort ist.
