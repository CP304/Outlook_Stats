# 08 — Datenschutz und Team-Nutzung

> Dieses Kapitel ist eine fachliche Einordnung, **keine Rechtsberatung**. Verbindlich entscheiden
> Datenschutzbeauftragte(r) und Betriebsrat.

## Die Ausgangslage

Die Analyse des **eigenen** Postfachs ist unproblematisch: eigene Daten, eigener Rechner, keine
Weitergabe. Sobald aber Postfächer von Mitarbeitern einbezogen werden, ändert sich die Bewertung
grundlegend — und zwar unabhängig von der guten Absicht.

## Was nicht geht

**Zugriff der Führungskraft auf Postfächer von Mitarbeitern** — per Delegate-Recht, Vollzugriff,
Admin-Export oder PST — um deren Kommunikation auszuwerten.

Begründung:

- Es ist eine Verarbeitung personenbezogener Beschäftigtendaten (Art. 6, Art. 88 DSGVO i. V. m. § 26 BDSG).
  Ein berechtigtes Interesse an Organisationsanalyse ist denkbar, trägt aber keinen anlasslosen
  Vollzugriff auf die Korrespondenz Beschäftigter.
- Es ist eine technische Einrichtung, die zur Überwachung von Verhalten und Leistung **geeignet** ist,
  und damit nach **§ 87 Abs. 1 Nr. 6 BetrVG mitbestimmungspflichtig**. Entscheidend ist die Eignung,
  nicht die Absicht. "Ich will das gar nicht auswerten" ist rechtlich unerheblich.
- Betroffen sind nicht nur die Teammitglieder, sondern auch **deren Kommunikationspartner** — interne
  Kollegen anderer Bereiche und externe Ansprechpartner bei Lieferanten, die von alldem nichts wissen.
- Ist private E-Mail-Nutzung erlaubt oder geduldet, kommt eine zusätzliche Risikoebene hinzu.
  Das ist vorab zu klären.

Praktische Konsequenz: Ohne Betriebsratsbeteiligung sind so gewonnene Ergebnisse nicht nur unzulässig,
sondern auch **wertlos** — man kann sie nicht vorzeigen, ohne die Frage nach ihrer Herkunft zu provozieren.

Ebenfalls nicht vertretbar, auch mit Zustimmung:

- Auswertungen, aus denen einzelne Beschäftigte identifizierbar sind (Rankings, Antwortzeiten je Person,
  "wer schreibt wie viel")
- stillschweigendes Mitlaufen ohne Kenntnis der Betroffenen
- Zweckänderung im Nachhinein ("wir schauen doch mal, wer …")

## Was tragfähig ist: Aggregation an der Quelle

Das Architekturprinzip lautet: **Personenbezogene Daten verlassen den Rechner des Teilnehmers nie.**
Was die Führungskraft erreicht, ist bereits aggregiert und anonym.

1. **Jeder führt das Skript selbst aus**, lokal, auf dem eigenen Rechner, im eigenen Postfach.
   Kein Fremdzugriff, keine Delegate-Rechte, kein zentraler Export. Die Führungskraft sieht
   zu keinem Zeitpunkt ein fremdes Postfach.

2. **Zwei getrennte Ausgaben:**
   - `Mein_Report.html` — der vollständige persönliche Report. Bleibt beim Teilnehmer, wird nie geteilt.
   - `team_export.json` — eine kleine, rein aggregierte Kennzahlendatei. Im Klartext lesbar,
     ohne Namen, ohne Adressen, ohne Betreffe, ohne Domainnamen.

3. **Technische Schutzmaßnahmen, im Code fest verdrahtet** (nicht konfigurierbar):
   - **Mindestgruppengröße n ≥ 5.** Bei weniger eingegangenen Dateien verweigert der Merge die Auswertung.
   - **Zellensperre k = 5.** Jede Kategorie, die auf weniger als 5 zugrunde liegenden Vorgängen beruht,
     wird als "n. a." ausgegeben statt als Zahl. Das verhindert Rückschlüsse über Kombinationen
     (der klassische Angriff auf anonymisierte Aggregate).
   - **Keine Min-/Max-Werte, keine Spannweiten, keine Einzelbeiträge** im Teamreport — sie verraten
     Ausreißer und damit Personen. Stattdessen Median und Quartile, und auch die erst ab ausreichender Fallzahl.
   - **Keine Zeitauflösung feiner als Wochentag.** Tageszeit- und After-hours-Auswertungen sind
     Verhaltensauswertungen und im Teamexport ausgeschlossen — sie existieren nur im persönlichen Report.
   - **Keine IDs, kein Postfachname, kein Laufzeitstempel** in der Exportdatei; Reihenfolge der
     Merkmale zufällig, Dateiname eine Zufalls-ID.
   - Externe Domains nur als **Kategorie und Konzentrationsmaß**, nie namentlich.

4. **Der Merge-Code hat konstruktionsbedingt keinen Zugang zu Rohdaten.** Er liest ausschließlich
   `team_export.json`-Dateien und kennt weder COM noch Cache. Das ist nicht nur eine Zusage,
   sondern in der Modulstruktur nachprüfbar — ein wesentliches Argument gegenüber DSB und Betriebsrat.

## Der organisatorische Rahmen

Ohne diesen Teil startet nichts. Die Technik macht die Sache zustimmungsfähig, sie ersetzt die
Zustimmung nicht.

- [ ] **Datenschutzbeauftragte(n) und Betriebsrat vorab einbinden** — nicht nachträglich informieren.
      Ein fertiges, offen einsehbares Konzept (dieses Repository) ist dafür die beste Gesprächsgrundlage.
- [ ] **Schriftliche Zweckbindung:** Prozess- und Organisationsanalyse. Ausdrücklich **keine** Leistungs-
      oder Verhaltenskontrolle. Zweckänderung ausgeschlossen.
- [ ] **Vollständige Transparenz:** Teilnehmende können den Code einsehen (öffentliches Repository),
      sehen ihre eigene Ausgabe vollständig und kennen den exakten Inhalt des Aggregats vor dem Teilen.
- [ ] **Freiwilligkeit — mit Realismus.** Freiwilligkeit gegenüber der eigenen Führungskraft ist
      erfahrungsgemäß eingeschränkt belastbar. Deshalb: Teilnahme freiwillig **und** durch eine
      BR-Regelung getragen. Nichtteilnahme muss folgenlos **und unsichtbar** bleiben — die Führungskraft
      darf nicht erkennen können, wer nicht teilgenommen hat (siehe Kapitel 09, Übermittlungsweg).
- [ ] **Löschkonzept:** lokaler Cache mit definierter Frist beim Teilnehmer; der Teamexport enthält
      keine personenbezogenen Daten mehr und unterliegt daher keiner Löschpflicht — was ihn erst
      teilbar macht.
- [ ] **Einmalige Auswertung statt Dauerbetrieb.** Eine wiederholte Momentaufnahme (z. B. halbjährlich)
      ist analytisch ausreichend. Ein Dauerbetrieb wäre eine Überwachungsinfrastruktur — und würde
      auch so bewertet.

## Empfohlener Weg

**Stufe 0 zuerst: nur das eigene Postfach.** Das erzeugt null Datenschutzaufwand, liefert bereits eine
belastbare Indikation, und ist gleichzeitig das überzeugendste Argument gegenüber DSB und Betriebsrat —
weil man dann nicht über eine Idee spricht, sondern ein fertiges, geprüftes Ergebnis samt Methodik
und Grenzen vorlegen kann.

Der Teammodus ist der zweite Schritt, nicht der erste.
