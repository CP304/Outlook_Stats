# 10 — Externe Kontaktliste

Ein Nebenprodukt mit eigener Rechtslage. Dieses Kapitel steht getrennt, weil die Kontaktliste
**nicht** dasselbe ist wie die übrige Auswertung — und weil dieser Unterschied leicht übersehen wird.

## Was es tut

```
python -m okoa kontakte --domain firma.de
python -m okoa kontakte --domain firma.de --signaturen
```

Ergebnis: `Externe_Kontakte.xlsx` mit Autofilter, absteigend nach Volumen sortiert.

| Spalte | Inhalt |
|---|---|
| E-Mail, Anzeigename, Domain | der Kontakt |
| **Funktion** | Rolle aus der Signatur, z. B. „Leiterin Vertrieb" |
| **Telefon, Mobil** | Rufnummern aus der Signatur — Fax nie |
| Unternehmen | Firmenname, soweit ermittelbar |
| **Herkunft Unternehmen** | `Signatur` oder `Domainname` — wie sicher der Name ist |
| Belege Unternehmen | wie oft die Signatur den Firmennamen bestätigt hat |
| Signaturbelege | wie viele auswertbare Signaturen dieser Person vorlagen |
| Kategorie | aus `mapping_domains`, falls gepflegt |
| Nachrichten, gesendet, empfangen, Vorgänge | Intensität und Richtung der Beziehung |
| Erstkontakt, Letzter Kontakt | echte Zeitstempel mit Uhrzeit, in Excel sortierbar |
| Letzte eigene Nachricht / Letzte Nachricht von dort | wer zuletzt geschrieben hat |
| Tage seit letztem Kontakt | Abstand zum Stichtag |
| Status | `aktiv` oder `eingeschlafen` (Schwelle 180 Tage) |

Die Zeitspalten stehen als **Datumswerte**, nicht als Text. Das klingt nach einer Kleinigkeit, ist
aber der Unterschied zwischen einer sortierbaren Liste und einer, in der Excel den 01.02. vor den
30.01. stellt. Filter wie „letzter Kontakt vor mehr als einem Jahr" funktionieren damit direkt.

Die Richtung ist getrennt ausgewiesen, weil sie die Frage „ist der Kontakt noch aktuell" anders
beantwortet: Eine eigene Nachricht, auf die seit Monaten nichts kam, ist etwas anderes als ein
laufender Dialog — im Zweifel ein Hinweis auf eine eingeschlafene Beziehung, nicht auf eine aktive.

Ausgelassen werden hier **nur Junk und Papierkorb** — anders als bei der Kennzahlenanalyse, die
zusätzlich Entwürfe, RSS und Synchronisierungsordner ausschließt. Für eine Adressernte zählt
Vollständigkeit, für Kennzahlen zählt Sauberkeit.

Absender ohne Menschen dahinter (`noreply@`, `mailer-daemon@`, `postmaster@` …) bleiben draußen.

## Der Bruch mit dem Grundsatz — offen benannt

Das übrige Projekt liest **keine Mailtexte**. `--signaturen` tut es. Das ist der einzige Ort im
gesamten Werkzeug, an dem ein Mailtext angefasst wird, und deshalb:

- **Nicht die Vorgabe.** Ohne den Schalter wird kein Text gelesen; der Firmenname kommt dann aus dem
  Domainnamen und ist entsprechend als `Domainname` gekennzeichnet.
- **Nur das Ende.** Gelesen werden die letzten Zeilen, in denen Signaturen stehen.
- **Nichts wird gespeichert.** Weiterverwendet wird allein der gefundene Firmenname, kein Text,
  keine Betreffzeile.
- **Eine einzige Fundstelle im Code**, die ein Test festnagelt — damit der Zugriff nicht unbemerkt
  in andere Funktionen einwandert.

## Warum „deterministisch“ hier hält

Kein Sprachmodell, keine Heuristik über Wahrscheinlichkeiten. Zwei Regeln:

1. **Rechtsform als Beleg.** Eine Zeile gilt nur dann als Firmenname, wenn sie eine bekannte
   Rechtsform enthält (GmbH, GmbH & Co. KG, AG, SE, B.V., Ltd., Inc. …). Zeilen mit Telefon,
   Registergericht, Geschäftsführer, IBAN oder Anschrift werden übersprungen, ebenso
   Vertraulichkeitshinweise — die enthalten fast immer eine Rechtsform und nie den Absender.
2. **Konsens über die Domain.** Ein Name wird erst übernommen, wenn er bei derselben Domain
   **mindestens zweimal** gefunden wurde. Bei Gleichstand zwischen zwei Namen wird nichts
   übernommen — ein Münzwurf wäre nicht reproduzierbar.

Die Konsensregel ist der eigentliche Trick: Sie filtert den Einzelfall heraus, in dem jemand eine
fremde Firma im Fließtext erwähnt hat, und sie lässt den Kollegen, der nie eine Signatur
mitschickt, die Firmierung seines Hauses erben.

### Funktion und Rufnummern — dieselben Regeln, andere Ebene

Der Firmenname gilt für das ganze Haus, **Funktion und Rufnummern gelten nur für eine Person**.
Der Konsens läuft deshalb je Adresse, nicht je Domain: Niemand erbt die Rolle seines Kollegen.

- **Funktion**: Eine Zeile zählt nur, wenn sie ein Rollenwort enthält (Leiter, Leitung, Einkauf,
  Vertrieb, Prokurist, Key Account Manager, Head of …) und weder Rechtsform noch Rufnummer noch
  Anschrift. Damit fällt die Firmenzeile heraus, die sonst regelmäßig als Funktion durchgeht.
- **Rufnummern**: Übernommen wird nur, was **beschriftet** ist — `Tel`, `Telefon`, `Phone`, `Fon`,
  `Durchwahl`, `T:` für Festnetz, `Mobil`, `Handy`, `Cell`, `M:` für mobil. Eine unbeschriftete
  Ziffernfolge bleibt liegen: Sie könnte eine Kunden-, Auftrags- oder Registernummer sein.
- **Fax wird nie übernommen.** Eine Faxnummer im Telefonfeld ist schlimmer als ein leeres Feld,
  weil sie jahrelang unbemerkt weiterverwendet wird.
- Die Durchwahl bleibt erhalten (`089 123456-12`), und beide Spalten stehen in Excel als **Text** —
  sonst frisst die Tabelle die führende Null der Vorwahl.

Erwartung an die Trefferquote: Signaturen stehen meist nur in der **ersten** Mail eines Vorgangs,
nicht in jeder Antwort. Leere Felder sind daher der Normalfall und kein Fehler. Die Spalte
„Signaturbelege" zeigt, auf wie vielen Signaturen eine Zeile beruht — bei 0 wurde schlicht keine
gefunden.

Erwartungswert aus der Praxis: Bei aktiven Geschäftspartnern greift die Signaturerkennung gut, bei
Einmalkontakten selten. Ein Feld bleibt lieber leer, als einen falschen Namen zu behaupten — deshalb
steht die Herkunft in jeder Zeile.

## Für die Massenpflege aufbereiten

Die Excel-Liste ist eine Auswertung zum Ansehen. Wer die Kontakte ins Adressbuch übernehmen will,
braucht getrennte Namensfelder und ein Importformat:

```
python -m okoa kontakte --domain firma.de --signaturen --fuer-import
```

Es entstehen zwei Dateien:

| Datei | Wofür |
|---|---|
| `Kontakte_Import.vcf` | vCard 3.0, alle Kontakte in einer Datei — **sprachunabhängig und der zuverlässigere Weg** |
| `Kontakte_Import.csv` | Outlook-Importformat mit den Spaltennamen, die der Importassistent erwartet |

Die CSV-Spaltennamen hängen an der Sprache der Outlook-Installation: Ein deutsches Outlook erkennt
`First Name` nicht und legt den Wert dann in gar keinem Feld ab. Deshalb `--sprache de|en`,
Vorgabe deutsch. Wer unsicher ist, nimmt die vCard.

**Die Namenszerlegung ist regelbasiert.** „Anna Schmidt", „Schmidt, Anna", „Dr. Anna von der Heide"
und „Lea Wolter (Einkauf)" werden korrekt zerlegt; Titel und Namenszusätze bleiben am richtigen Feld.
Wo es nicht eindeutig geht, bleibt der Vorname leer und der ganze Text steht im Nachnamen — ein
falsch zerlegter Name fällt beim Import nicht auf und steht danach jahrelang falsch im Adressbuch.

**Zwei bewusste Filter**, damit kein Datenmüll ins Adressbuch wandert:

- Einträge ohne erkennbaren Personennamen werden übersprungen. Sonst entstehen Kontakte, die
  „kontakt@lieferant1.com" heißen. Mit `--alle-kontakte` kommen sie trotzdem mit.
- Ein aus dem Domainnamen abgeleiteter Firmenname wandert **nicht** ins Feld „Firma". „Lieferant4"
  ist eine Lesehilfe für die Analyse, keine Firmierung. Nur was aus Signaturen belegt ist, wird
  übernommen.

Jeder Kontakt bekommt eine Notiz mit Herkunft und Stand: *„Outlook-Kommunikationsanalyse; aus 3
Signaturen gelesen; letzter Kontakt: 14.05.2026; Nachrichten: 12"*. Damit ist im Adressbuch später
nachvollziehbar, woher der Eintrag stammt und wie belastbar er ist.

Ohne `--signaturen` bleibt für ein Adressbuch wenig übrig — Namen und Rufnummern stehen nun einmal
in der Signatur.

## Datenschutz — hier gilt etwas anderes

Die Kennzahlenanalyse erzeugt Aggregate. Diese Liste erzeugt **eine personenbezogene Datensammlung
über externe Ansprechpartner**, die bisher nur verstreut im Postfach lag. Das ist ein eigener
Verarbeitungszweck und keine Fortsetzung des alten.

Was daraus folgt:

- **Zweck vorher festlegen.** Lieferantenübersicht, Ansprechpartnerpflege, Übergabe bei
  Stellenwechsel — der Zweck bestimmt, wie lange die Datei existieren darf.
- **Ein Import ins Adressbuch ist eine dauerhafte Speicherung.** Die Excel-Liste wirft man nach der
  Analyse weg; Kontakte im Adressbuch überleben Rechnerwechsel und wandern in Backups und
  Mobilgeräte. Vor dem Import lohnt die Frage, ob wirklich alle Einträge dort hingehören — die
  Notiz macht später wenigstens nachvollziehbar, woher sie kamen.
- **Mit Funktion und Rufnummer wird aus einer Adressliste ein Profil.** Name, Rolle, Durchwahl,
  Mobilnummer und Kontakthistorie in einer Zeile sind mehr als die Summe der Teile. Genau diese
  Datei ist es, die man nicht unbedacht weitergibt — und die ein Argument dafür ist, sie nicht
  „für alle Fälle" mitlaufen zu lassen, sondern nur, wenn ein konkreter Zweck vorliegt.
- **Die Betroffenen sind Dritte.** Die Ansprechpartner bei Lieferanten wissen nichts von dieser
  Liste. Ihre Daten stammen aus einer Geschäftsbeziehung und dürfen dort auch bleiben; ein
  Weiterverwenden für anderes (Marketing, Bewertung, Weitergabe) wäre eine erneute Zweckänderung.
- **Nicht in den Teamexport.** Der anonyme Teamexport enthält weder Adressen noch Domainnamen; die
  Kontaktliste bleibt lokal und wandert nirgends mit. Diese Trennung ist im Code erzwungen und
  durch Tests abgesichert.
- **Löschen nicht vergessen.** Eine Excel-Datei mit Hunderten Kontakten überlebt sonst jeden
  Rechnerwechsel. Frist festlegen, Ablageort bewusst wählen — nicht der Downloads-Ordner.
- **Vor betrieblicher Nutzung Rücksprache.** Wenn die Liste über den eigenen Arbeitsplatz hinaus
  genutzt oder geteilt werden soll, gehört sie vorher der oder dem Datenschutzbeauftragten vorgelegt.
  Das ist ein kurzes Gespräch — aber es gehört geführt.

Wie in Kapitel 08: fachliche Einordnung, keine Rechtsberatung.
