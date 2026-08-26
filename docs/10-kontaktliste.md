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
| Unternehmen | Firmenname, soweit ermittelbar |
| **Herkunft Unternehmen** | `Signatur` oder `Domainname` — wie sicher der Name ist |
| Belege | wie oft die Signatur den Namen bestätigt hat |
| Kategorie | aus `mapping_domains`, falls gepflegt |
| Nachrichten, gesendet, empfangen, Vorgänge | Intensität und Richtung der Beziehung |
| Erstkontakt, Letzter Kontakt, Tage seit letztem Kontakt | Verlauf |
| Status | `aktiv` oder `eingeschlafen` (Schwelle 180 Tage) |

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

Erwartungswert aus der Praxis: Bei aktiven Geschäftspartnern greift die Signaturerkennung gut, bei
Einmalkontakten selten. Ein Feld bleibt lieber leer, als einen falschen Namen zu behaupten — deshalb
steht die Herkunft in jeder Zeile.

## Datenschutz — hier gilt etwas anderes

Die Kennzahlenanalyse erzeugt Aggregate. Diese Liste erzeugt **eine personenbezogene Datensammlung
über externe Ansprechpartner**, die bisher nur verstreut im Postfach lag. Das ist ein eigener
Verarbeitungszweck und keine Fortsetzung des alten.

Was daraus folgt:

- **Zweck vorher festlegen.** Lieferantenübersicht, Ansprechpartnerpflege, Übergabe bei
  Stellenwechsel — der Zweck bestimmt, wie lange die Datei existieren darf.
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
