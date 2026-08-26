# 02 — Methodik: Zähleinheiten

Die wichtigste Entscheidung dieses Konzepts ist nicht, *welche* Kennzahlen berechnet werden, sondern
**was gezählt wird**. Dieselben Rohdaten liefern je nach Zähleinheit interne Anteile, die um 15 bis 25
Prozentpunkte auseinanderliegen. Wer nur eine Zahl zeigt, zeigt die Zahl, die er sich ausgesucht hat.

## Die vier Einheiten

| Einheit | Was sie ist | Wofür sie taugt |
|---|---|---|
| **Nachricht** | eine E-Mail | Aufwands- und Lastmetriken |
| **Vorgang (Thread)** | ein zusammenhängender Kommunikationsstrang | Themen- und Anteilsmetriken |
| **Kontakt** | eine Person (nicht eine Adresse) | Netzwerk, Beteiligung |
| **Domain** | eine externe Organisation | Markt- und Lieferantensicht |

## Grundregel

> **Anteile werden auf Vorgangsebene berichtet. Lasten werden auf Nachrichtenebene berichtet.**

Begründung: Die Frage "wie viel unserer Themen sind intern" ist eine Themenfrage — ein Vorgang ist ein Thema,
egal ob er drei oder dreißig Mails brauchte. Die Frage "wie viel Aufwand bindet das" ist eine Lastfrage —
da zählt jede Mail einzeln.

Beide Antworten gehören **nebeneinander** ins Dashboard. Divergieren sie stark, ist genau das der Befund:

- interner Vorgangsanteil 55 %, interner Nachrichtenanteil 80 %
  → die Mehrheit der *Themen* hat Außenbezug, aber die interne Abstimmung verbraucht überproportional
  viel Kommunikation. Das ist ein Koordinationsproblem, kein Ausrichtungsproblem.
- interner Vorgangsanteil 80 %, interner Nachrichtenanteil 80 %
  → die Organisation beschäftigt sich tatsächlich überwiegend mit sich selbst. Das ist ein Ausrichtungsthema.

Diese Unterscheidung ist der eigentliche analytische Mehrwert gegenüber einer simplen Mailquote.

## Warum reine Nachrichtenzählung intern überschätzt

Vier systematische Effekte, alle in dieselbe Richtung:

1. **Interne Threads haben mehr Runden.** Rückfragen, Freigaben, Weiterleitungen, "FYI" — externe
   Kommunikation ist formeller und dichter.
2. **Eigene gesendete Mails liegen doppelt im Postfach** (Gesendete Elemente + ggf. Thread-Ordner).
   Ohne Deduplikation trifft das interne Kommunikation härter, weil dort mehr gesendet wird.
3. **CC-Kaskaden.** Eine interne Mail an sechs Personen ist eine Nachricht, erzeugt aber sechs
   Postfacheinträge — im eigenen Postfach nur einen, aber in der Teamaggregation mehrfach.
4. **Automatisierte interne Mails** (Systeme, Workflows, Freigabetools) sind fast immer intern und
   fast nie Arbeit im gemeinten Sinne.

Punkt 4 ist der wichtigste und der einzige, der sich sauber beheben lässt: automatisierte Nachrichten
werden als eigene Klasse ausgewiesen und aus den Kern-KPIs ausgeschlossen. Ohne diesen Schritt misst man
im Zweifel die SAP-Workflow-Engine, nicht die Organisation.

## Klassifikation eines Vorgangs

Über die **Vereinigungsmenge aller Teilnehmer aller Nachrichten** des Vorgangs — Absender, TO und CC:

- alle Adressen intern → **intern**
- mindestens eine externe Adresse und keine nennenswerte interne Zusatzabstimmung → **extern**
- mindestens eine externe Adresse **und** mindestens eine rein interne Nachricht im selben Vorgang
  → **gemischt**

**"Gemischt" ist eine eigene Klasse und darf nicht in "intern" aufgehen.** Ein Lieferantenvorgang mit
interner Abstimmung ist wertschöpfende Arbeit, keine Selbstbeschäftigung. Sie in die interne Quote zu
schieben, würde die Hypothese künstlich bestätigen — genau das, was vermieden werden soll.

Zusatzkennzahl innerhalb der gemischten Klasse: **interner Nachrichtenanteil je gemischtem Vorgang**.
Sie beantwortet "wie viel interne Abstimmung kostet ein Lieferantenthema" und ist damit die präziseste
verfügbare Annäherung an die eigentliche Managementfrage.

## Kontakte statt Adressen

Eine Person kann mehrere Adressen haben (Alias, Namensänderung, Funktionspostfach, X500-Adresse).
Vor jeder Zählung steht deshalb eine **Identitätsauflösung**: Adresse → Person. Ohne sie zählt man
dieselbe Person mehrfach und überschätzt Netzwerkgröße und Beteiligungsbreite. Vorgehen in Kapitel 03.

Funktionspostfächer (`einkauf@`, `bestellung@`) sind bewusst **keine Personen** und werden als eigene
Kategorie geführt — sonst erscheinen sie als hyperaktive "Kollegen" in jeder Netzwerkgrafik.

## Richtung: gesendet vs. empfangen

Immer getrennt auswerten. Empfangene Kommunikation ist fremdbestimmt, gesendete ist die eigene
Kapazitätsentscheidung. Eine Gesamtquote vermischt beides und ist deshalb für Steuerungsfragen
schwächer als die getrennte Betrachtung (vgl. K5).

Praktisch: die Richtung wird nicht am Ordner festgemacht (Ordner sind unzuverlässig, siehe Kapitel 03),
sondern daran, ob die eigene aufgelöste Identität der Absender ist.

## Zeitraum

Default: die letzten **12 vollen Monate**. Gründe: deckt Saison- und Budgetzyklen ab, hält die Laufzeit
beherrschbar, und vermeidet den Fehler, angefangene Randmonate als volle zu zählen. Für Trendaussagen
mindestens 24 Monate, dann aber nur die Kern-KPIs — ältere Archive sind lückenhaft und verzerren
Absolutwerte.

Alle Vorgänge, deren erste Nachricht vor dem Fenster liegt, werden markiert (`randvorgang`) und aus
Dauer- und Tiefenkennzahlen ausgeschlossen, weil sie systematisch abgeschnitten sind.

## Verteilergröße: zwei Zahlen, nicht eine

Für TO, CC und BCC werden je zwei Kennzahlen berichtet:

- **Ø je Nachricht** — rechnet Nachrichten ohne CC mit null mit
- **Median wenn genutzt** — betrachtet nur die Nachrichten, die das Feld verwenden

Erst zusammen trennen sie zwei völlig verschiedene Muster, die derselbe Mittelwert erzeugt:
*selten, dann breit* (ein Rundmail an 30 Personen im Monat) und *ständig, aber knapp*
(jede Mail mit zwei Leuten in CC). Das erste ist ein Informationsformat, das zweite eine Kultur.

Ergänzend: **wodurch** ein großer Verteiler groß wird. Ein Verteiler mit mehr CC- als TO-Empfängern
bedeutet, dass die Mehrheit der Beteiligten nicht adressiert, sondern informiert wird.

BCC steht nur für selbst gesendete Nachrichten. Bei empfangenen ist es prinzipiell unsichtbar —
es wird deshalb getrennt geführt und niemals in die TO-Zahl geschlagen, sonst wäre jede TO-Kennzahl
still verfälscht.

## Was nicht gemacht wird

- **Keine Gewichtung nach "Wichtigkeit"** — jede Gewichtung wäre eine unbelegte Annahme
- **Keine Hochrechnung fehlender Zeiträume**
- **Keine Schätzung nicht aufgelöster Verteilerlisten** — Lücken werden ausgewiesen, nicht gefüllt
- **Keine Bereinigung von "unwichtigen" Mails** außer der klar regelbasierten Klasse "automatisiert"
