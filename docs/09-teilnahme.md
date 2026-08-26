# 09 — Teilnahme-Workflow für Kollegen

Wie Kollegen die Analyse **selbst** ausführen und ihre Kennzahlen beisteuern können, wenn sie möchten.
Der Weg ist bewusst so gehalten, dass er ohne IT-Projekt funktioniert. Grundlage: Kapitel 08.

## Verteilung — kein Setup beim Teilnehmer

Ein ZIP-Ordner mit einer Datei zum Doppelklicken: `start.bat`.
Kein Installer, keine Adminrechte, kein Outlook-Add-in, keine Änderung am Postfach.

Ist Python im Unternehmen nicht verfügbar, wird ein PyInstaller-One-Folder-Build ausgeliefert —
derselbe Ordner, dieselbe Bedienung, nur größer. Die Prüfbarkeit bleibt erhalten, weil der Quellcode
öffentlich einsehbar ist.

## Ablauf beim Teilnehmer — drei Schritte

**1. Doppelklick auf `start.bat`**

Die Oberfläche öffnet sich:
- Zeitraum (vorbelegt: letzte 12 volle Monate)
- interne Domain (vorbelegt)
- ein klar formulierter Hinweis: *"Die Analyse liest nur Absender, Empfänger, Zeitpunkt und Ordner.
  Es werden keine Mailtexte, Betreffzeilen oder Anhänge gelesen oder gespeichert. Am Postfach wird
  nichts verändert."*

**2. Lauf** — je nach Postfachgröße einige Minuten. Zwei Ergebnisse im selben Ordner:

| Datei | Inhalt | Bleibt / geht |
|---|---|---|
| `Mein_Report.html` | vollständiger persönlicher Report | **bleibt beim Teilnehmer** |
| `team_export.json` | aggregierte Kennzahlen, anonym | optional teilbar |

**3. Abschluss**

Unter „Weitergabe und Team“ zeigt „Eigene Kennzahlen ablegen“ den
**vollständigen Inhalt von `team_export.json` im Klartext** an, mit der Überschrift
*"Das — und nur das — würde geteilt."* Darunter zwei gleichwertig gestaltete Schaltflächen:

- *Anonym übermitteln*
- *Nicht teilen — nur meinen eigenen Report behalten*

Die zweite Schaltfläche ist bewusst nicht kleiner, nicht grau und nicht versteckt. Wer eine echte
Freiwilligkeit behauptet, muss sie auch gestalten.

## Rückgabe — der einfache Weg zuerst

Der Übermittlungsweg kostet **keinen Entwicklungsaufwand**: Die Exportdatei ist in jedem Fall dieselbe,
klein und im Klartext lesbar. Was der Weg verändert, ist nicht der Aufwand, sondern der Grad der Anonymität.
Deshalb hier ehrlich sortiert nach dem, was man dafür bekommt.

### Standard — jeder schickt, was er will

Wer teilnehmen möchte, führt das Programm aus und schickt die `team_export.json` per Mail — oder legt sie
in einen Teamordner, oder gibt sie gar nicht ab. Kein Share, keine IT-Anfrage, keine Vorbereitung.

Das funktioniert sofort und ist für einen ersten Durchlauf völlig ausreichend. Zwei Dinge sind dabei
aber sauber zu benennen, statt sie zu übergehen:

- Der **Inhalt** ist aggregiert und enthält keine Namen, Adressen, Betreffe oder Uhrzeiten
  (vollständige Liste unten). Insofern ist die Datei harmlos.
- Der **Absender** ist bei einer Mail sichtbar. Das Ergebnis ist damit korrekt als **pseudonym**
  zu bezeichnen, nicht als anonym: Du weißt, von wem welche Kennzahlen stammen — auch wenn du
  gar nicht hinsehen willst. Und du siehst, wer nicht geschickt hat.

Der zweite Punkt ist der eigentliche: Freiwilligkeit gegenüber der eigenen Führungskraft ist nur dann
echt, wenn Nichtteilnahme unsichtbar bleibt. Das ist keine juristische Feinheit, sondern der Grund,
warum Leute mitmachen oder eben nicht.

### Wenn es ohne Zusatzaufwand besser gehen soll

Zwei Varianten, die beide **null Programmieraufwand** bedeuten und den Absender trotzdem verdecken —
wähle die, die in deiner Umgebung leichter zu bekommen ist:

- **Neutraler Sammler.** Eine dritte Person — Assistenz, Datenschutzbeauftragte(r), Betriebsratsmitglied —
  nimmt die Mails entgegen und gibt dir nur den Dateistapel weiter. Rein organisatorisch, in fünf Minuten
  vereinbart, und die Beteiligung des Betriebsrats zahlt nebenbei auf die Akzeptanz ein.
- **Write-only-Ordner.** Ein Netzlaufwerk-Ordner mit dem Recht „Dateien erstellen", aber ohne
  „Ordnerinhalt auflisten" und ohne „Lesen". Standard-NTFS, eine einmalige Bitte an die IT.
  Jeder legt unter einer Zufalls-ID ab; niemand sieht, wer abgelegt hat, auch du nicht.
  *(Zu beachten: Das Dateisystem speichert einen Besitzer je Datei — du solltest auf diesem Ordner
  bewusst keine Adminrechte haben.)*

Beides ist optional. Wenn es hakt, nimm den Standardweg und nenne das Ergebnis pseudonym.

### Was unabhängig vom Weg gilt

Die Zusammenführung verweigert unter 5 Teilnehmern die Auswertung und unterdrückt zu kleine Kategorien
(siehe unten). Das ist im Programm fest verdrahtet und hängt nicht daran, wie die Dateien zu dir kommen.
Damit bleibt auch der bequemste Weg auswertbar, ohne einzelne Personen sichtbar zu machen.

## Zusammenführung bei der Führungskraft

Ein eigenes Kommando, das ausschließlich `team_export.json`-Dateien einliest — ohne jeden Zugang zu
Postfächern, Rohdaten oder Cache-Dateien. Es ist gleichgültig, ob die Dateien per Mail, aus einem
Ordner oder von einem USB-Stick kommen:

```
Reiter „Weitergabe und Team“  →  Dateien zusammenführen …  →  Gruppenkennzahlen
```

Verhalten:
- **Abbruch bei weniger als 5 Dateien**, mit Klartexthinweis statt Teilergebnis
- Zellensperre bei k < 5 zugrunde liegenden Vorgängen → "n. a."
- keine Auflistung der Einzelbeiträge, keine Min-/Max-Werte, keine Spannweiten
- Ausgabe: Median und Quartile der Gruppe (`Team_Report.json`), keine Einzelwerte

## Inhalt von `team_export.json` — vollständig und abschließend

Damit jeder Teilnehmer es selbst prüfen kann, hier die komplette Liste dessen, was übermittelt wird:

- Zeitraum in **Monatsauflösung** (kein Tagesdatum, kein Laufzeitstempel)
- Anzahl Vorgänge, getrennt nach intern / gemischt / extern
- Anzahl Nachrichten, getrennt nach denselben Klassen
- Ø und Median Nachrichten je Vorgang, je Klasse
- Ø und Median Teilnehmerzahl je Vorgang, je Klasse
- CC-Quote und Ø CC-Empfänger (intern)
- Anteil Vorgänge mit >5 und mit >10 Nachrichten, je Klasse
- Anteil selbst gesendeter Nachrichten mit externem Empfänger (K5)
- Volumensanteile je **Fachbereichslabel** — nie je Person
- Anzahl distinkter externer Domains und Konzentrationsmaß (HHI) — **ohne Domainnamen**
- Wochentagsverteilung
- Datenqualitätswerte: Anteil unauflösbarer Adressen, Anteil Duplikate, Anteil Klasse "automatisiert"

**Nicht enthalten:** Namen, E-Mail-Adressen, Domainnamen, Betreffzeilen, Anhangnamen, Uhrzeiten,
Tagesdaten, Postfach- oder Rechnername, Benutzer-ID, Ordnernamen, Einzelvorgänge.

## Und weiterhin gilt

Auch der bequemste Weg ersetzt die Einbindung von Datenschutzbeauftragtem und Betriebsrat nicht —
freiwillig oder nicht, es bleibt eine Auswertung von Beschäftigtenkommunikation. Was dieses Konzept
leistet, ist, die Zustimmung **erreichbar** zu machen: Der geteilte Datensatz ist aggregiert,
vollständig dokumentiert, vom Teilnehmer vorab einsehbar und enthält nichts, was auf eine einzelne
Person zurückführt. Das ist ein kurzes Gespräch statt einer Betriebsvereinbarung.

Und der Einstieg bleibt ohnehin **dein eigenes Postfach** — dafür brauchst du niemanden zu fragen.
