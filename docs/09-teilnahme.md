# 09 — Teilnahme-Workflow für Kollegen

Wie Kollegen die Analyse **selbst** ausführen und ihre Kennzahlen **wirklich anonym** beisteuern können,
wenn sie möchten. Grundlage: Kapitel 08.

## Verteilung — kein Setup beim Teilnehmer

Ein ZIP-Ordner mit einer Datei zum Doppelklicken: `Analyse_starten.bat`.
Kein Installer, keine Adminrechte, kein Outlook-Add-in, keine Änderung am Postfach.

Ist Python im Unternehmen nicht verfügbar, wird ein PyInstaller-One-Folder-Build ausgeliefert —
derselbe Ordner, dieselbe Bedienung, nur größer. Die Prüfbarkeit bleibt erhalten, weil der Quellcode
öffentlich einsehbar ist.

## Ablauf beim Teilnehmer — drei Schritte

**1. Doppelklick auf `Analyse_starten.bat`**

Ein kurzer Startdialog:
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

**3. Abschlussdialog**

Er zeigt den **vollständigen Inhalt von `team_export.json` im Klartext** an, mit der Überschrift
*"Das — und nur das — würde geteilt."* Darunter zwei gleichwertig gestaltete Schaltflächen:

- *Anonym übermitteln*
- *Nicht teilen — nur meinen eigenen Report behalten*

Die zweite Schaltfläche ist bewusst nicht kleiner, nicht grau und nicht versteckt. Wer eine echte
Freiwilligkeit behauptet, muss sie auch gestalten.

## Anonyme Rückgabe — drei Wege, in dieser Reihenfolge

### Weg 1 — Write-only-Ablageordner *(empfohlen)*

Ein Ordner auf einem Netzlaufwerk, auf dem die Gruppe das Recht **"Dateien erstellen / Daten schreiben"**
hat, aber **nicht** "Ordnerinhalt auflisten" und nicht "Lesen". Das ist mit Standard-NTFS-Rechten
abbildbar und muss von der IT einmalig eingerichtet werden.

Wirkung:
- Jeder legt seine Datei unter einer Zufalls-ID ab.
- Niemand sieht, **wer** abgelegt hat — auch die Führungskraft nicht.
- Teilnehmer sehen die Dateien der anderen nicht.
- **Nichtteilnahme bleibt unsichtbar.** Das ist der Punkt, der Freiwilligkeit überhaupt erst echt macht,
  und der Hauptgrund, warum dieser Weg den anderen vorzuziehen ist.

Zu beachten und offen anzusprechen: Das Dateisystem speichert einen **Besitzer** je Datei. Wer
Administratorrechte auf dem Share hat, könnte ihn auslesen. Deshalb: Die Führungskraft erhält
bewusst **keine** Adminrechte auf diesem Ordner, und die IT wird gebeten, das zu bestätigen.
Wer es strenger braucht, lässt den Ordner von der IT oder dem Betriebsrat verwalten und nur den
fertigen Dateistapel übergeben.

### Weg 2 — neutraler Sammler

Eine dritte Person — Assistenz, Datenschutzbeauftragte(r) oder ein Betriebsratsmitglied — nimmt die
Dateien per Mail entgegen, trennt sie von den Absendern und übergibt nur den Stapel.
Organisatorische statt technischer Lösung; funktioniert zuverlässig, wenn Weg 1 an der IT scheitert,
und hat den Nebeneffekt zusätzlichen Vertrauens durch die Beteiligung des Betriebsrats.

### Weg 3 — direkte Mail an die Führungskraft *(schlechteste Option)*

Der Dateiinhalt ist anonym, der Absender jedoch nicht. Damit ist die Zuordnung wiederhergestellt und
der Schutz weitgehend aufgehoben — ebenso die Unsichtbarkeit der Nichtteilnahme.

Nur akzeptabel, wenn alle Beteiligten das ausdrücklich so wollen. In diesem Fall ist das Ergebnis
korrekt als **pseudonym** zu bezeichnen, nicht als anonym.

## Zusammenführung bei der Führungskraft

Ein eigenes Kommando, das ausschließlich `team_export.json`-Dateien einliest — ohne jeden Zugang zu
Postfächern, Rohdaten oder Cache-Dateien:

```
merge_starten.bat   →  Ordner mit den eingegangenen Dateien wählen  →  Team_Report.html
```

Verhalten:
- **Abbruch bei weniger als 5 Dateien**, mit Klartexthinweis statt Teilergebnis
- Zellensperre bei k < 5 zugrunde liegenden Vorgängen → "n. a."
- keine Auflistung der Einzelbeiträge, keine Min-/Max-Werte, keine Spannweiten
- Ausgabe: Median und Quartile der Gruppe, Verteilungen, Anteile — ein einziger HTML-Report

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

Dieser Weg ersetzt die Einbindung von Datenschutzbeauftragtem und Betriebsrat nicht. Er macht sie
**zustimmungsfähig** — weil nachweisbar ist, dass bei der Führungskraft keine personenbezogenen
Daten ankommen können.
