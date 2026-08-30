# 03 — Outlook-COM-Realität

Dieses Kapitel ist der Grund, warum das Konzept vor dem Code steht. Die meisten Fehlanalysen dieser Art
scheitern nicht an der Statistik, sondern an falsch verstandenen Outlook-Feldern.

## Was zuverlässig ist

| Feld | Anmerkung |
|---|---|
| `ReceivedTime` / `SentOn` | zuverlässig; `SentOn` bei selbst gesendeten, `ReceivedTime` bei empfangenen |
| `Recipients` mit `Type` (1=TO, 2=CC, 3=BCC) | zuverlässig, **sofern** die Adressen aufgelöst sind |
| `MessageClass` | zuverlässig; Grundlage für die Filterung von Terminen, Aufgaben, Systemmeldungen |
| `Attachments.Count` | zuverlässig, aber zählt auch eingebettete Signaturbilder mit — nur grob verwendbar |
| `Size` | zuverlässig gemessen, aber inhaltlich wertlos (siehe Kapitel 01) |
| Ordnerstruktur (`Folders`, rekursiv) | zuverlässig auslesbar |

## Was gefährlich ist

### 1. `SenderEmailAddress` liefert bei internen Mails keine E-Mail-Adresse

Bei Exchange-internen Nachrichten steht dort eine X500/EX-DN-Adresse der Form
`/O=FIRMA/OU=EXCHANGE ADMINISTRATIVE GROUP.../CN=RECIPIENTS/CN=ABC123`.
Wer darauf `@firma.de` prüft, klassifiziert **jede interne Mail als extern** — oder, je nach Fallback,
gar nicht. Das ist der häufigste und folgenschwerste Fehler dieser Analyseart.

Lösung, in dieser Reihenfolge:
1. `SenderEmailType` prüfen — bei `"EX"` ist Auflösung zwingend
2. `PropertyAccessor.GetProperty("http://schemas.microsoft.com/mapi/proptag/0x39FE001E")` (PR_SMTP_ADDRESS)
3. `Recipient.AddressEntry.GetExchangeUser().PrimarySmtpAddress`
4. schlägt alles fehl: Nachricht als `adresse_unaufgeloest` markieren und **aus den Kern-KPIs ausschließen**,
   Anteil im Report ausweisen. Nicht raten.

Der Anteil unauflösbarer Adressen ist selbst eine Qualitätskennzahl und gehört in den Methodikanhang.
Über ~5 % ist das Ergebnis nicht mehr belastbar.

### 2. Conversation-Zuordnung

`ConversationID` existiert ab Outlook 2007 und ist innerhalb einer Mailbox meist brauchbar, aber:

- sie bricht, wenn jemand den Betreff ändert
- sie bricht über Mailbox- und teilweise über Store-Grenzen (Archiv-PST)
- sie kann bei extern zurücklaufenden Threads neu vergeben werden
- sie fasst gelegentlich **zu viel** zusammen (Dauerthreads über Monate, "Re: Re: Re: Kurze Frage")

Vorgehen: Vorgänge werden **mit zwei Verfahren** gebildet —
(a) `ConversationID`,
(b) Fallback über normalisierten Betreff (Präfixe `RE:`, `AW:`, `FW:`, `WG:`, `FWD:`, `[EXTERN]` und
Ähnliches entfernt, Groß/Klein und Whitespace normalisiert) **plus** Teilnehmerüberlappung **plus**
zeitliches Fenster (z. B. keine Verbindung über >30 Tage Lücke).

Beide Ergebnisse werden gegeneinander berichtet. Weichen die Kern-KPIs zwischen den Verfahren um mehr als
wenige Prozentpunkte ab, ist die Thread-Bildung instabil und die Vorgangsebene entsprechend zu relativieren.
Das ist unbequem, aber ehrlich — und es ist der Unterschied zwischen einer Analyse und einer Behauptung.

Wichtig: Der normalisierte Betreff wird nur als **Hash zur Gruppierung** verwendet und **nicht gespeichert**.
Damit bleibt die Zusage "keine Betreffzeilen in der Auswertung" eingehalten.

### 3. Duplikate

Quellen: Gesendete Elemente + Thread-Ordner, Archiv-PST neben Online-Archiv, mehrfach eingebundene
Mailboxen, wiederhergestellte Ordner.

Deduplikation über `PR_INTERNET_MESSAGE_ID` (`0x1035001E`) als primären Schlüssel.
Fallback, wenn leer (kommt bei manchen internen Mails vor): Hash aus
`(aufgelöste Absenderadresse, Zeitstempel auf Minute, Empfängermenge, Größe)`.
`EntryID` ist **kein** geeigneter Duplikatschlüssel — sie ist pro Store verschieden.

Der Anteil entfernter Duplikate gehört ebenfalls in den Methodikanhang.

### 4. Verteilerlisten

Ein Empfänger vom Typ Verteilerliste erscheint als **ein** Recipient. Die dahinterliegenden 40 Personen
sind unsichtbar, sofern die Liste nicht expandiert wurde. Auflösung über das Adressbuch ist technisch
möglich (`AddressEntry.Members`), aber:

- oft durch Berechtigungen blockiert
- langsam
- und der Mitgliederstand von *heute* passt nicht zur Mail von vor acht Monaten

**Entscheidung: nicht auflösen.** Verteilerlisten werden als solche markiert und gezählt
("Anzahl Nachrichten an Verteiler"), Empfängerzahlen sind damit ausdrücklich eine **Untergrenze**.
Das ist im Report so zu benennen. Eine Schätzung wäre eine Scheingenauigkeit.

Nebeneffekt, der nützlich ist: Der Anteil "Nachrichten an Verteilerlisten" ist selbst ein guter Indikator
für Broadcast-Kommunikation.

### 5. BCC

Bei selbst gesendeten Mails sichtbar, bei empfangenen prinzipiell nicht. Jede BCC-Kennzahl wäre damit
auf die eigene Sendeseite beschränkt und in Vergleichen irreführend. **BCC wird nicht ausgewertet**
(vgl. Kapitel 01, Ebene 4). Empfänger vom Typ 3 werden bei eigenen Sendungen der Empfängerzahl zugerechnet,
aber nicht separat berichtet.

### 6. Aliase und Mehrfachidentitäten

Dieselbe Person erscheint als `max.mustermann@firma.de`, `m.mustermann@firma.de`, `mmustermann@firma.de`
und als X500-DN. Auflösung:

1. über `GetExchangeUser()` → `PrimarySmtpAddress` als kanonische Identität (der zuverlässige Weg)
2. hilfsweise über den Exchange-Alias
3. hilfsweise über normalisierten Anzeigenamen (nur als Kandidatenvorschlag, nie automatisch zusammenführen)
4. optionale manuelle Alias-Mapping-Datei für den Rest

Automatisches Zusammenführen nach Namensähnlichkeit ist zu unterlassen — bei häufigen Nachnamen entstehen
falsche Verschmelzungen, die im Netzwerkbild dramatisch aussehen und schlicht falsch sind.

### 7. Nicht-Mail-Objekte und Automaten

Über `MessageClass` sauber trennbar und **vor** der Analyse zu klassifizieren:

- `IPM.Schedule.Meeting.*` — Terminanfragen, Zu-/Absagen, Aktualisierungen.
  **Nicht als normale Mail zählen.** Eine Terminserie erzeugt sonst dutzende "Nachrichten".
  Getrennt ausweisen — sie sind ein eigener, sehr aussagekräftiger Koordinationsindikator (siehe Roadmap).
- `IPM.Note.Rules.*`, `REPORT.*` (NDR, Lesebestätigungen), `IPM.Task.*`, `IPM.Contact*` — ausschließen
- Abwesenheitsnotizen, `no-reply@`, `noreply@`, `donotreply@`, `mailer-daemon@`, `postmaster@` → Klasse `automatisiert`
- Newsletter: erkennbar über den Header `List-Unsubscribe` bzw. `Precedence: bulk`
  (`PropertyAccessor` auf `PR_TRANSPORT_MESSAGE_HEADERS`, `0x007D001E`) → Klasse `automatisiert`

Die Klasse `automatisiert` wird **nicht gelöscht**, sondern separat ausgewiesen. Ihre Größe ist selbst
ein Befund ("18 % des Posteingangs ist Maschinenverkehr").

### 8. Antworten und Weiterleitungen

Über den normalisierten Betreff bzw. `PR_LAST_VERB_EXECUTED` unterscheidbar. Der Anteil
Weiterleitungen an internen Nachrichten ist ein brauchbarer sekundärer Indikator ("Durchreichen"),
aber `PR_LAST_VERB_EXECUTED` ist nicht durchgängig gesetzt — daher nur explorativ verwenden.

### 9. Shared Mailboxes und Archive

- Rekursion über alle `Stores` bzw. `Session.Folders`, nicht nur den Standard-Posteingang
- Shared Mailboxes: technisch zugänglich, **datenschutzrechtlich aber nur mit ausdrücklicher Freigabe**
  auswerten. Default: nur eigene Postfächer, fremde Stores werden aufgelistet und **standardmäßig übersprungen**
  (explizites Opt-in nötig, siehe Kapitel 08)
- Online-Archiv erscheint als eigener Store und muss aktiv eingebunden sein; nicht eingebundene Archive
  erzeugen stillschweigend Lücken → das Tool listet gefundene Stores im Report auf, damit die Lücke sichtbar ist
- Ältere Zeiträume sind durch Aufbewahrungsrichtlinien systematisch dünner. Trendaussagen über Zeiträume
  mit unterschiedlicher Aufbewahrung sind unzulässig

### 10. Zwei Fallen, die still zu null Nachrichten führen

Beide liefern keinen Fehler, sondern ein leeres Ergebnis — und genau das macht sie gefährlich.

**`Folder.DefaultItemType` gehört zu `OlItemType`, dort ist `olMailItem = 0`.** Die vielzitierte
**43** stammt aus einer anderen Aufzählung (`OlObjectClass.olMail`) und gehört zu `Item.Class`.
Wer beide verwechselt, erkennt keinen einzigen Mailordner und wertet null Nachrichten aus, ohne
dass irgendwo eine Ausnahme auftritt. Ordner ohne Angabe werden deshalb mitgenommen — Nicht-Mails
filtert die `MessageClass`-Prüfung ohnehin heraus.

**`Restrict` mit `[ReceivedTime] >= '01.09.2025 00:00'` hängt an den Windows-Ländereinstellungen.**
Ein Format, das die Installation nicht erwartet, wirft nicht — es liefert eine leere Menge. Deshalb
wird der Zeitfilter über DASL gestellt:

```
@SQL="urn:schemas:httpmail:datereceived" >= '2025-09-01 00:00'
```

Das ist sprachunabhängig. Zusätzlich wird geprüft, ob der gefilterte Ordner leer ist, obwohl er
Elemente enthält; dann wird ungefiltert gelesen und der Zeitraum in Python geprüft — langsamer,
aber nicht leer. Der Report benennt betroffene Ordner.

Für den Ernstfall gibt es `python -m okoa pruefen` beziehungsweise „Postfach prüfen“ in der
Oberfläche: Sie listet Speicher, Ordner, Elementzahlen und ob der Zeitfilter greift.

Beides landet zusätzlich in `Auswertung/protokoll.txt`, zusammen mit einem Umgebungskopf
(Programmstand, Python, pywin32, Outlook-Version, Profil, Speicherliste). Das ist bewusst so
gebaut, dass die Datei **allein** aussagefähig ist: Auf dem auswertenden Rechner sitzt niemand,
der nachfragen kann.

### 11. Performance

- `Items.Restrict("[ReceivedTime] >= '...'")` statt Vollscan; `Items.Sort` vorher setzen
- niemals `Items.Item(i)` in einer Schleife über große Ordner — stattdessen `GetFirst`/`GetNext`
- jeder `PropertyAccessor`-Zugriff kostet; die benötigten Properties in einem Durchlauf einsammeln
- Cached-Exchange-Modus mit begrenztem Offline-Zeitraum liefert nur die lokal vorhandenen Elemente —
  bei mehrjährigen Analysen prüfen und im Report vermerken
- Realistische Erwartung: 30.000–80.000 Elemente sind ohne Weiteres machbar, dauern aber Minuten, nicht Sekunden

### 12. Read-only-Garantie

Keine Schreib-Property, kein `Save()`, kein `Move()`, kein `Delete()`, kein Markieren als gelesen.
Zu beachten: bereits der Zugriff auf `.Body` kann bei manchen Konfigurationen Nebeneffekte auslösen und
den Sicherheitsdialog triggern — der Body wird ohnehin nicht gelesen, was diesen Punkt entschärft.
Die Vermeidung von `.Body` ist also nicht nur Datenschutz, sondern auch technische Robustheit.
